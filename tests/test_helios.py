from __future__ import annotations

import types

from qibo import gates
from qibo.models import Circuit

from qibo_cloud_backends.nexus_helios import (
    _build_entrypoint_source,
    build_helios_hugr_package,
    map_helios_result_to_qibo,
)
from qibo_cloud_backends.nexus_translation import TranslationMetadata


def test_build_entrypoint_source_preserves_measurement_order() -> None:
    source = _build_entrypoint_source(
        loaded_name="loaded_pytket",
        entrypoint_name="helios_entrypoint",
        metadata=TranslationMetadata(measured_qubits=[2, 0], nqubits=3, qasm="OPENQASM"),
    )

    assert 'result("m[0]", measure(q2))' in source
    assert 'result("m[1]", measure(q0))' in source
    assert "discard(q1)" in source


def test_build_helios_hugr_package_loads_pytket_with_rebasing(
    monkeypatch,
) -> None:
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        "qibo_cloud_backends.nexus_helios.translate_qibo_to_pytket_for_helios",
        lambda circuit, parameters=None: (
            "pytket-circuit",
            TranslationMetadata(measured_qubits=[0], nqubits=1, qasm="OPENQASM"),
        ),
    )

    class DecomposeBoxes:
        def apply(self, circuit):
            calls["decompose"] = circuit

    class AutoRebase:
        def __init__(self, gate_set):
            calls["gate_set"] = gate_set

        def apply(self, circuit):
            calls["rebase"] = circuit

    pytket_circuit_mod = types.ModuleType("pytket.circuit")
    pytket_circuit_mod.OpType = types.SimpleNamespace(CX="CX", H="H", Rz="Rz")
    pytket_passes_mod = types.ModuleType("pytket.passes")
    pytket_passes_mod.DecomposeBoxes = DecomposeBoxes
    pytket_passes_mod.AutoRebase = AutoRebase

    class FakeLoaded:
        def __call__(self, *args):
            return None

    class FakeEntrypoint:
        def compile(self):
            return {"kind": "hugr-package"}

    class FakeGuppy:
        def load_pytket(self, name, circuit, use_arrays=False):
            calls["load_pytket"] = {
                "name": name,
                "circuit": circuit,
                "use_arrays": use_arrays,
            }
            return FakeLoaded()

        def __call__(self, fn):
            calls["decorated_name"] = fn.__name__
            return FakeEntrypoint()

    guppy_mod = types.ModuleType("guppylang")
    guppy_mod.guppy = FakeGuppy()
    builtins_mod = types.ModuleType("guppylang.std.builtins")
    builtins_mod.result = lambda tag, value: (tag, value)
    quantum_mod = types.ModuleType("guppylang.std.quantum")
    quantum_mod.qubit = lambda: object()
    quantum_mod.measure = lambda q: True
    quantum_mod.discard = lambda q: None

    monkeypatch.setitem(__import__("sys").modules, "pytket.circuit", pytket_circuit_mod)
    monkeypatch.setitem(__import__("sys").modules, "pytket.passes", pytket_passes_mod)
    monkeypatch.setitem(__import__("sys").modules, "guppylang", guppy_mod)
    monkeypatch.setitem(__import__("sys").modules, "guppylang.std.builtins", builtins_mod)
    monkeypatch.setitem(__import__("sys").modules, "guppylang.std.quantum", quantum_mod)

    circuit = Circuit(1)
    circuit.add(gates.M(0))
    package, metadata = build_helios_hugr_package(circuit)

    assert package == {"kind": "hugr-package"}
    assert metadata.measured_qubits == [0]
    assert calls["decompose"] == "pytket-circuit"
    assert calls["rebase"] == "pytket-circuit"
    assert calls["load_pytket"]["use_arrays"] is False


def test_map_helios_result_to_qibo_with_tagged_shots(monkeypatch) -> None:
    class MeasurementOutcomes:
        def __init__(self, measurements, backend=None, nshots=0, samples=None):
            self.measurements = measurements
            self.backend = backend
            self.nshots = nshots
            self.samples = samples

    qibo_result = types.ModuleType("qibo.result")
    qibo_result.MeasurementOutcomes = MeasurementOutcomes
    monkeypatch.setitem(__import__("sys").modules, "qibo.result", qibo_result)

    class ExecutionResultRef:
        def download_result(self):
            return [
                [("m[0]", True), ("m[1]", False)],
                [("m[0]", False), ("m[1]", True)],
                [("m[0]", True), ("m[1]", False)],
            ]

    circuit = Circuit(2)
    circuit.add(gates.M(1, 0))
    result = map_helios_result_to_qibo(
        execution_result_ref=ExecutionResultRef(),
        circuit=circuit,
        backend=object(),
        nshots=3,
        measured_qubits=[1, 0],
    )

    assert result.nshots == 3
    assert result.samples.shape == (3, 2)
    rows = [tuple(row) for row in result.samples.tolist()]
    assert rows.count((1, 0)) == 2
    assert rows.count((0, 1)) == 1
