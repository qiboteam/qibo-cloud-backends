"""Result mapping helpers for the Nexus backend."""

from __future__ import annotations

from collections import Counter
from itertools import repeat
from typing import Any, Iterable

import numpy as np
from qibo.models import Circuit

from .nexus_errors import NexusResultMappingError


def _bits_from_key(key: Any) -> list[int]:
    if isinstance(key, str):
        return [int(ch) for ch in key.strip() if ch in {"0", "1"}]
    if isinstance(key, int):
        return [int(ch) for ch in bin(key)[2:]]
    if isinstance(key, Iterable):
        return [int(x) for x in key]
    raise NexusResultMappingError(f"Unsupported count key type: {type(key)}")


def normalize_bitstring(
    *,
    key: Any,
    nbits: int,
    measured_qubits: list[int] | None,
    reverse_endianness: bool,
) -> str:
    """Normalize backend count keys into Qibo-style binary strings."""

    bits = _bits_from_key(key)
    if len(bits) < nbits:
        bits = [0] * (nbits - len(bits)) + bits
    if len(bits) != nbits:
        raise NexusResultMappingError(
            f"Count key width mismatch. Expected {nbits}, received {len(bits)} for key={key!r}."
        )

    if reverse_endianness:
        bits = list(reversed(bits))

    # Measurement targets are already serialized in measurement-register order.
    # Preserve that order when constructing Qibo-facing bitstrings.
    _ = measured_qubits

    return "".join(str(bit) for bit in bits)


def _download_backend_result(execution_result_ref: Any) -> Any:
    if hasattr(execution_result_ref, "download_result"):
        return execution_result_ref.download_result()
    return execution_result_ref


def _extract_counts(backend_result: Any) -> dict[Any, int]:
    if hasattr(backend_result, "get_counts"):
        counts = backend_result.get_counts()
    elif isinstance(backend_result, dict):
        counts = backend_result
    else:
        raise NexusResultMappingError(
            f"Unsupported backend result type '{type(backend_result)}'."
        )

    if not isinstance(counts, dict):
        raise NexusResultMappingError("Nexus get_counts() did not return a dictionary.")
    return counts


def map_counts_to_qibo_frequencies(
    counts: dict[Any, int],
    *,
    measured_qubits: list[int],
    reverse_endianness: bool = False,
) -> Counter[str]:
    """Map backend counts dictionary to Qibo-compatible binary frequencies."""

    nbits = len(measured_qubits) if measured_qubits else 0
    if nbits == 0 and counts:
        first_key = next(iter(counts))
        nbits = len(_bits_from_key(first_key))

    frequencies: Counter[str] = Counter()
    for key, value in counts.items():
        bitstring = normalize_bitstring(
            key=key,
            nbits=nbits,
            measured_qubits=measured_qubits,
            reverse_endianness=reverse_endianness,
        )
        frequencies[bitstring] += int(value)

    return frequencies


def map_nexus_result_to_qibo(
    *,
    execution_result_ref: Any,
    circuit: Circuit,
    backend: Any,
    nshots: int,
    measured_qubits: list[int],
    reverse_endianness: bool = False,
) -> Any:
    """Download and convert a Nexus execution result to a Qibo result object."""

    backend_result = _download_backend_result(execution_result_ref)
    counts = _extract_counts(backend_result)
    frequencies = map_counts_to_qibo_frequencies(
        counts,
        measured_qubits=measured_qubits,
        reverse_endianness=reverse_endianness,
    )

    try:
        from qibo.result import MeasurementOutcomes
    except Exception as exc:  # pragma: no cover - import environment specific
        raise NexusResultMappingError("qibo is required to build result objects.") from exc

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
    "normalize_bitstring",
    "map_counts_to_qibo_frequencies",
    "map_nexus_result_to_qibo",
]
