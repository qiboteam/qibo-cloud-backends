"""Translation helpers for the Nexus backend."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from qibo.models import Circuit

from .nexus_errors import NexusBackendError

_QASM_REGISTER_RE = re.compile(r"^[a-z][a-zA-Z0-9_]*$")


@dataclass
class TranslationMetadata:
    measured_qubits: list[int]
    nqubits: int
    qasm: str


def _to_int_qubit_sequence(values: Iterable[Any]) -> list[int]:
    return [int(v) for v in values]


def extract_measurement_qubits(circuit: Circuit) -> list[int]:
    """Return measured qubit indices in gate-application order."""

    measured: list[int] = []
    for gate in circuit.queue:
        if str(gate.name).lower() not in {"m", "measure", "measurement"}:
            continue
        measured.extend(_to_int_qubit_sequence(gate.target_qubits))

    if measured:
        return measured

    return list(range(circuit.nqubits))


def _has_multicontrolled_gates(circuit: Circuit) -> bool:
    for gate in circuit.queue:
        if gate.control_qubits and len(tuple(gate.control_qubits)) > 1:
            return True
    return False


def _normalize_measurement_register_names(circuit: Circuit) -> None:
    index = 0
    for gate in circuit.queue:
        if str(gate.name).lower() not in {"m", "measure", "measurement"}:
            continue

        current = gate.register_name
        if current and _QASM_REGISTER_RE.match(str(current)):
            continue

        fallback = f"m{index}"
        index += 1
        gate.register_name = fallback


def _bind_parameters(circuit: Circuit, parameters: Any) -> Circuit:
    if parameters is None:
        return circuit
    circuit.set_parameters(parameters)
    return circuit


def _replace_unitary_basis_rotations(circuit: Circuit) -> Circuit:
    """Rebuild circuit replacing Y-to-Z basis rotation Unitary gates with SDG+H.

    When a ``gates.M(q, basis=gates.Y)`` gate is added to a qibo circuit, qibo
    inserts ``Y(q).basis_rotation()`` — which is ``Unitary((Y+Z)/sqrt(2), q)`` —
    into the queue before the M gate.  That Unitary is not expressible in
    OpenQASM 2.0.  This helper rebuilds the circuit, substituting every such
    Unitary with the equivalent named-gate sequence ``SDG(q), H(q)``, and
    replacing any non-Z-basis M gate with a plain Z-basis M gate (the explicit
    basis rotations already appear in the queue immediately before it).
    """
    import math

    import numpy as np
    from qibo import gates, matrices

    y_rot_matrix = (matrices.Y + matrices.Z) / math.sqrt(2)

    def _is_y_basis_rotation(g: Any) -> bool:
        return (
            isinstance(g, gates.Unitary)
            and len(g.target_qubits) == 1
            and getattr(g, "matrix", None) is not None
            and g.matrix.shape == (2, 2)
            and bool(np.allclose(g.matrix, y_rot_matrix))
        )

    if not any(_is_y_basis_rotation(g) for g in circuit.queue):
        return circuit

    new_circuit = Circuit(circuit.nqubits)
    for gate in circuit.queue:
        if _is_y_basis_rotation(gate):
            q = gate.target_qubits[0]
            new_circuit.add(gates.SDG(q))
            new_circuit.add(gates.H(q))
        elif isinstance(gate, gates.M):
            # Create a fresh Z-basis M gate so it does not re-inject basis
            # rotation Unitaries from its internal .basis list.
            new_circuit.add(
                gates.M(*gate.target_qubits, register_name=gate.register_name)
            )
        else:
            new_circuit.add(gate)
    return new_circuit


def prepare_qibo_circuit(circuit: Circuit, parameters: Any = None) -> tuple[Circuit, str]:
    """Run QASM preflight and return a QASM-ready circuit and QASM string."""

    working = circuit.copy(deep=True)
    working = _bind_parameters(working, parameters)
    _normalize_measurement_register_names(working)
    working = _replace_unitary_basis_rotations(working)

    if _has_multicontrolled_gates(working):
        working = working.decompose()

    try:
        try:
            qasm = working.to_qasm(extended_compatibility=True)
        except TypeError:
            qasm = working.to_qasm()
    except Exception as exc:
        raise NexusBackendError(f"Failed to export Qibo circuit to OpenQASM: {exc}") from exc

    return working, qasm


def translate_qibo_to_pytket(
    circuit: Circuit, parameters: Any = None
) -> tuple[Any, TranslationMetadata]:
    """Translate a Qibo circuit to a pytket circuit via OpenQASM 2.0."""

    working, qasm = prepare_qibo_circuit(circuit, parameters=parameters)

    try:
        from pytket.qasm import circuit_from_qasm_str
    except Exception as exc:  # pragma: no cover - import environment specific
        raise NexusBackendError("pytket.qasm is required for QASM translation.") from exc

    try:
        pytket_circuit = circuit_from_qasm_str(qasm)
    except Exception as exc:
        raise NexusBackendError(f"Failed to parse OpenQASM with pytket: {exc}") from exc

    metadata = TranslationMetadata(
        measured_qubits=extract_measurement_qubits(working),
        nqubits=working.nqubits,
        qasm=qasm,
    )
    return pytket_circuit, metadata


__all__ = [
    "TranslationMetadata",
    "extract_measurement_qubits",
    "prepare_qibo_circuit",
    "translate_qibo_to_pytket",
]
