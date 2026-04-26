"""Helios-specific translation and result helpers."""

from __future__ import annotations

import linecache
from collections import Counter
from itertools import repeat
from typing import Any, Iterable

import numpy as np
from qibo.models import Circuit

from .nexus_errors import NexusBackendError, NexusResultMappingError
from .nexus_results import map_counts_to_qibo_frequencies
from .nexus_translation import TranslationMetadata, translate_qibo_to_pytket_for_helios

_MEASUREMENT_REGISTER = "m"


def _import_guppy() -> Any:
    try:
        from guppylang import guppy
    except Exception as exc:  # pragma: no cover - import environment specific
        raise NexusBackendError(
            "guppylang is required for Helios execution. Install qibo-cloud-backends with the 'nexus' extra."
        ) from exc
    return guppy


def _prepare_pytket_for_guppy(pytket_circuit: Any) -> Any:
    try:
        from pytket.circuit import OpType

        # pylint: disable=no-name-in-module
        from pytket.passes import AutoRebase, DecomposeBoxes
    except Exception as exc:  # pragma: no cover - import environment specific
        raise NexusBackendError(
            "pytket decomposition passes are required for Helios translation."
        ) from exc

    try:
        DecomposeBoxes().apply(pytket_circuit)
        AutoRebase({OpType.CX, OpType.H, OpType.Rz}).apply(pytket_circuit)
    except Exception as exc:
        raise NexusBackendError(
            f"Failed to normalize pytket circuit for Guppy loading: {exc}"
        ) from exc

    return pytket_circuit


def _build_entrypoint_source(
    *, loaded_name: str, entrypoint_name: str, metadata: TranslationMetadata
) -> str:
    qubit_names = [f"q{i}" for i in range(metadata.nqubits)]
    lines = [
        "from guppylang.std.builtins import result",
        "from guppylang.std.quantum import discard, measure, qubit",
        "",
        "@guppy",
        f"def {entrypoint_name}() -> None:",
    ]

    if not qubit_names:
        lines.append(f"    {loaded_name}()")
        return "\n".join(lines)

    for name in qubit_names:
        lines.append(f"    {name} = qubit()")
    lines.append(f"    {loaded_name}({', '.join(qubit_names)})")

    measured_qubits = set(metadata.measured_qubits)
    for idx, qubit in enumerate(metadata.measured_qubits):
        lines.append(
            f'    result("{_MEASUREMENT_REGISTER}[{idx}]", measure({qubit_names[qubit]}))'
        )
    for idx, name in enumerate(qubit_names):
        if idx not in measured_qubits:
            lines.append(f"    discard({name})")

    return "\n".join(lines)


def build_helios_hugr_package(
    circuit: Circuit,
    *,
    parameters: Any = None,
    entrypoint_name: str = "helios_entrypoint",
) -> tuple[Any, TranslationMetadata]:
    """Compile a Qibo circuit into a Guppy/HUGR package for Helios."""

    guppy = _import_guppy()
    pytket_circuit, metadata = translate_qibo_to_pytket_for_helios(
        circuit, parameters=parameters
    )
    pytket_circuit = _prepare_pytket_for_guppy(pytket_circuit)

    try:
        # pylint: disable=assignment-from-none
        loaded_pytket = guppy.load_pytket(
            "loaded_pytket", pytket_circuit, use_arrays=False
        )
    except Exception as exc:
        raise NexusBackendError(
            f"Failed to load pytket circuit into Guppy: {exc}"
        ) from exc

    namespace = {"guppy": guppy, "loaded_pytket": loaded_pytket}
    source = _build_entrypoint_source(
        loaded_name="loaded_pytket",
        entrypoint_name=entrypoint_name,
        metadata=metadata,
    )
    source_filename = f"<qibo-cloud-backends:{entrypoint_name}>"
    linecache.cache[source_filename] = (
        len(source),
        None,
        [f"{line}\n" for line in source.splitlines()],
        source_filename,
    )
    try:
        exec(compile(source, source_filename, "exec"), namespace)
    except Exception as exc:
        raise NexusBackendError(
            f"Failed to build Helios Guppy entrypoint: {exc}"
        ) from exc

    entrypoint = namespace[entrypoint_name]
    try:
        return entrypoint.compile(), metadata
    except Exception as exc:
        raise NexusBackendError(
            f"Failed to compile Helios HUGR package: {exc}"
        ) from exc


def _to_bit(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        if value in {0, 1}:
            return str(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"0", "1"}:
            return normalized
        if normalized in {"true", "false"}:
            return "1" if normalized == "true" else "0"
    raise NexusResultMappingError(f"Unsupported Helios result value: {value!r}")


def _extract_named_results(shot: Any) -> dict[str, Any]:
    if isinstance(shot, dict):
        return {str(k): v for k, v in shot.items()}

    if hasattr(shot, "as_dict"):
        data = shot.as_dict()
        if isinstance(data, dict):
            return {str(k): v for k, v in data.items()}

    if hasattr(shot, "results"):
        shot = shot.results

    values: dict[str, Any] = {}
    if isinstance(shot, Iterable) and not isinstance(shot, (str, bytes)):
        for item in shot:
            if isinstance(item, tuple) and len(item) == 2:
                tag, value = item
            else:
                tag = getattr(item, "tag", None)
                if tag is None:
                    tag = getattr(item, "name", None)
                if tag is None:
                    tag = getattr(item, "key", None)
                value = getattr(item, "value", None)
            if tag is None:
                raise NexusResultMappingError(
                    f"Unsupported Helios shot entry: {item!r}"
                )
            values[str(tag)] = value
        return values

    raise NexusResultMappingError(f"Unsupported Helios shot type: {type(shot)}")


def _extract_helios_counts(backend_result: Any, measured_count: int) -> Counter[str]:
    if hasattr(backend_result, "register_bitstrings"):
        try:
            register_bitstrings = backend_result.register_bitstrings()
        except Exception:
            register_bitstrings = None
        if isinstance(register_bitstrings, dict):
            values = register_bitstrings.get(_MEASUREMENT_REGISTER)
            if values is not None:
                return Counter(str(bitstring) for bitstring in values)

    shots = getattr(backend_result, "shots", None)
    if shots is None:
        shots = getattr(backend_result, "results", None)
    if (
        shots is None
        and isinstance(backend_result, Iterable)
        and not isinstance(backend_result, (str, bytes, dict))
    ):
        shots = backend_result
    if shots is None:
        raise NexusResultMappingError(
            f"Unsupported Helios backend result type '{type(backend_result)}'."
        )

    counts: Counter[str] = Counter()
    expected_tags = [f"{_MEASUREMENT_REGISTER}[{idx}]" for idx in range(measured_count)]
    for shot in shots:
        named = _extract_named_results(shot)
        try:
            bitstring = "".join(_to_bit(named[tag]) for tag in expected_tags)
        except KeyError as exc:
            raise NexusResultMappingError(
                f"Missing Helios measurement tag '{exc.args[0]}' in shot result."
            ) from exc
        counts[bitstring] += 1
    return counts


def map_helios_result_to_qibo(
    *,
    execution_result_ref: Any,
    circuit: Circuit,
    backend: Any,
    nshots: int,
    measured_qubits: list[int],
    reverse_endianness: bool = False,
) -> Any:
    """Download and convert a Helios execution result to a Qibo result object."""

    backend_result = (
        execution_result_ref.download_result()
        if hasattr(execution_result_ref, "download_result")
        else execution_result_ref
    )
    counts = _extract_helios_counts(backend_result, len(measured_qubits))
    frequencies = map_counts_to_qibo_frequencies(
        counts,
        measured_qubits=measured_qubits,
        reverse_endianness=reverse_endianness,
    )

    try:
        from qibo.result import MeasurementOutcomes
    except Exception as exc:  # pragma: no cover - import environment specific
        raise NexusResultMappingError(
            "qibo is required to build result objects."
        ) from exc

    measurements = list(circuit.measurements)
    total_shots = int(sum(frequencies.values()))
    effective_nshots = total_shots if total_shots > 0 else int(nshots)

    samples = []
    for bitstring, count in frequencies.items():
        sample = [int(b) for b in bitstring]
        samples.extend(repeat(sample, count))

    return MeasurementOutcomes(
        measurements,
        backend=backend,
        nshots=effective_nshots,
        samples=np.array(samples, dtype=int),
    )


__all__ = [
    "build_helios_hugr_package",
    "map_helios_result_to_qibo",
]
