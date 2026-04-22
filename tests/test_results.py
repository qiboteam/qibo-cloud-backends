from __future__ import annotations

import types

from qibo import gates
from qibo.models import Circuit

from qibo_cloud_backends.nexus_results import (
    map_counts_to_qibo_frequencies,
    map_nexus_result_to_qibo,
)


def test_map_counts_to_qibo_frequencies_reverses_when_requested() -> None:
    counts = {(0, 1, 1): 5}
    freq = map_counts_to_qibo_frequencies(
        counts,
        measured_qubits=[0, 1, 2],
        reverse_endianness=True,
    )
    assert freq["110"] == 5


def test_map_nexus_result_to_qibo_with_fake_qibo(monkeypatch):
    from collections import Counter

    class MeasurementOutcomes:
        def __init__(self, measurements, backend=None, nshots=0, samples=None):
            self.measurements = measurements
            self.backend = backend
            self.nshots = nshots
            self.samples = samples

    qibo_result = types.ModuleType("qibo.result")
    qibo_result.MeasurementOutcomes = MeasurementOutcomes

    monkeypatch.setitem(__import__("sys").modules, "qibo.result", qibo_result)

    class BackendResult:
        def get_counts(self):
            return {(0, 1): 4, (1, 0): 6}

    class ExecutionResultRef:
        def download_result(self):
            return BackendResult()

    circuit = Circuit(2)
    circuit.add(gates.M(0, 1))
    result = map_nexus_result_to_qibo(
        execution_result_ref=ExecutionResultRef(),
        circuit=circuit,
        backend=object(),
        nshots=10,
        measured_qubits=[0, 1],
        reverse_endianness=True,
    )

    assert result.nshots == 10
    assert result.samples.shape == (10, 2)
    # counts {(0,1):4, (1,0):6} with reverse_endianness → frequencies {"10":4, "01":6}
    row_counts = Counter(tuple(row) for row in result.samples.tolist())
    assert row_counts[(1, 0)] == 4  # bitstring "10"
    assert row_counts[(0, 1)] == 6  # bitstring "01"


def test_map_counts_preserves_measurement_order() -> None:
    counts = {(1, 0): 7}
    freq = map_counts_to_qibo_frequencies(
        counts,
        measured_qubits=[2, 0],
        reverse_endianness=False,
    )
    assert freq["10"] == 7


def test_map_counts_preserves_non_sorted_measurement_order() -> None:
    counts = {(0, 1, 1): 3}
    freq = map_counts_to_qibo_frequencies(
        counts,
        measured_qubits=[2, 0, 1],
        reverse_endianness=False,
    )
    assert freq["011"] == 3


def test_map_counts_accepts_string_and_int_keys() -> None:
    counts = {"11": 3, 0b01: 2}
    freq = map_counts_to_qibo_frequencies(
        counts,
        measured_qubits=[0, 1],
        reverse_endianness=False,
    )
    assert freq["11"] == 3
    assert freq["01"] == 2


def test_map_nexus_result_to_qibo_with_aer_like_string_counts(monkeypatch) -> None:
    from collections import Counter

    class MeasurementOutcomes:
        def __init__(self, measurements, backend=None, nshots=0, samples=None):
            self.measurements = measurements
            self.backend = backend
            self.nshots = nshots
            self.samples = samples

    qibo_result = types.ModuleType("qibo.result")
    qibo_result.MeasurementOutcomes = MeasurementOutcomes
    monkeypatch.setitem(__import__("sys").modules, "qibo.result", qibo_result)

    class BackendResult:
        def get_counts(self):
            return {"00": 3, "11": 1}

    class ExecutionResultRef:
        def download_result(self):
            return BackendResult()

    circuit = Circuit(2)
    circuit.add(gates.M(0, 1))
    result = map_nexus_result_to_qibo(
        execution_result_ref=ExecutionResultRef(),
        circuit=circuit,
        backend=object(),
        nshots=4,
        measured_qubits=[0, 1],
        reverse_endianness=False,
    )

    assert result.nshots == 4
    assert result.samples.shape == (4, 2)
    row_counts = Counter(tuple(row) for row in result.samples.tolist())
    assert row_counts[(0, 0)] == 3
    assert row_counts[(1, 1)] == 1


def test_map_nexus_result_to_qibo_preserves_measurement_samples(monkeypatch) -> None:
    from collections import Counter

    class MeasurementOutcomes:
        def __init__(self, measurements, backend=None, nshots=0, samples=None):
            self.measurements = measurements
            self.backend = backend
            self.nshots = nshots
            self.samples = samples

    qibo_result = types.ModuleType("qibo.result")
    qibo_result.MeasurementOutcomes = MeasurementOutcomes
    monkeypatch.setitem(__import__("sys").modules, "qibo.result", qibo_result)

    class BackendResult:
        def get_counts(self):
            return {"011": 5}

    class ExecutionResultRef:
        def download_result(self):
            return BackendResult()

    circuit = Circuit(3)
    circuit.add(gates.M(2, 0, 1))
    result = map_nexus_result_to_qibo(
        execution_result_ref=ExecutionResultRef(),
        circuit=circuit,
        backend=object(),
        nshots=5,
        measured_qubits=[2, 0, 1],
        reverse_endianness=False,
    )

    row_counts = Counter(tuple(row) for row in result.samples.tolist())
    assert row_counts[(0, 1, 1)] == 5
