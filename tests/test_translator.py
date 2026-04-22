from __future__ import annotations

import types

import pytest
import sympy
from qibo import gates
from qibo.models import Circuit

from qibo_cloud_backends.nexus_errors import NexusBackendError
from qibo_cloud_backends.nexus_translation import (
    prepare_qibo_circuit,
    translate_qibo_to_pytket,
    translate_qibo_to_pytket_for_helios,
)


def test_prepare_qibo_circuit_decomposes_multicontrol() -> None:
    circuit = Circuit(3)
    circuit.add(gates.TOFFOLI(0, 1, 2))
    circuit.add(gates.M(2, register_name="m0"))

    prepared, qasm = prepare_qibo_circuit(circuit)

    assert all(len(g.control_qubits) <= 1 for g in prepared.queue)
    assert qasm.startswith("OPENQASM")


def test_prepare_qibo_circuit_raises_for_unbound_params() -> None:
    theta = sympy.Symbol("theta")
    circuit = Circuit(1)
    circuit.add(gates.RZ(0, theta=theta))
    circuit.add(gates.M(0))

    with pytest.raises(NexusBackendError):
        prepare_qibo_circuit(circuit)


def test_translate_qibo_to_pytket(monkeypatch: pytest.MonkeyPatch) -> None:
    def circuit_from_qasm_str(source: str):
        return {"parsed": source}

    pytket_mod = types.ModuleType("pytket")
    qasm_mod = types.ModuleType("pytket.qasm")
    qasm_mod.circuit_from_qasm_str = circuit_from_qasm_str

    monkeypatch.setitem(__import__("sys").modules, "pytket", pytket_mod)
    monkeypatch.setitem(__import__("sys").modules, "pytket.qasm", qasm_mod)

    circuit = Circuit(3)
    circuit.add(gates.M(2, 0, register_name="m0"))
    parsed, metadata = translate_qibo_to_pytket(circuit)

    assert parsed["parsed"].startswith("OPENQASM")
    assert metadata.measured_qubits == [2, 0]


def test_translate_qibo_to_pytket_for_helios_strips_measurements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def circuit_from_qasm_str(source: str):
        return {"parsed": source}

    pytket_mod = types.ModuleType("pytket")
    qasm_mod = types.ModuleType("pytket.qasm")
    qasm_mod.circuit_from_qasm_str = circuit_from_qasm_str

    monkeypatch.setitem(__import__("sys").modules, "pytket", pytket_mod)
    monkeypatch.setitem(__import__("sys").modules, "pytket.qasm", qasm_mod)

    circuit = Circuit(2)
    circuit.add(gates.H(0))
    circuit.add(gates.CNOT(0, 1))
    circuit.add(gates.M(1, 0, register_name="m0"))

    parsed, metadata = translate_qibo_to_pytket_for_helios(circuit)

    assert parsed["parsed"].startswith("OPENQASM")
    assert "measure" not in parsed["parsed"].lower()
    assert metadata.measured_qubits == [1, 0]


def test_translate_qibo_to_pytket_for_helios_rejects_non_terminal_measurements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytket_mod = types.ModuleType("pytket")
    qasm_mod = types.ModuleType("pytket.qasm")
    qasm_mod.circuit_from_qasm_str = lambda source: {"parsed": source}

    monkeypatch.setitem(__import__("sys").modules, "pytket", pytket_mod)
    monkeypatch.setitem(__import__("sys").modules, "pytket.qasm", qasm_mod)

    circuit = Circuit(2)
    circuit.add(gates.M(0, register_name="m0"))
    circuit.add(gates.H(1))

    with pytest.raises(NexusBackendError, match="terminal"):
        translate_qibo_to_pytket_for_helios(circuit)


def test_prepare_qibo_circuit_binds_parameters() -> None:
    circuit = Circuit(1)
    circuit.add(gates.RZ(0, theta=0.0))
    circuit.add(gates.M(0, register_name="m0"))

    prepared, qasm = prepare_qibo_circuit(circuit, parameters=[1.23])

    assert "1.23" in qasm
    assert "0.0" in circuit.to_qasm()


def test_prepare_qibo_circuit_normalizes_invalid_register_name() -> None:
    circuit = Circuit(1)
    circuit.add(gates.M(0, register_name="1-invalid"))

    prepared, _ = prepare_qibo_circuit(circuit)

    assert prepared.queue[0].register_name == "m0"
    assert circuit.queue[0].register_name == "1-invalid"


def test_prepare_qibo_circuit_requires_qibo_circuit_api() -> None:
    with pytest.raises(AttributeError):
        prepare_qibo_circuit(types.SimpleNamespace())
