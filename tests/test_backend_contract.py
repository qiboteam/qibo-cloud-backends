from __future__ import annotations

import types

import pytest
from qibo import gates
from qibo.models import Circuit

import qibo_cloud_backends.nexus_client as backend_mod
from qibo_cloud_backends.nexus_errors import UnsupportedExecutionError
from qibo_cloud_backends.nexus_translation import TranslationMetadata


def make_measured_circuit(
    nqubits: int = 1, measured_qubits: tuple[int, ...] | None = None
) -> Circuit:
    circuit = Circuit(nqubits)
    targets = measured_qubits if measured_qubits is not None else tuple(range(nqubits))
    circuit.add(gates.M(*targets))
    return circuit


@pytest.fixture
def backend(monkeypatch: pytest.MonkeyPatch) -> backend_mod.NexusClientBackend:
    monkeypatch.setattr(backend_mod, "_ensure_nexus_dependencies", lambda: None)
    monkeypatch.setattr(backend_mod, "authenticate", lambda **kwargs: None)
    monkeypatch.setattr(
        backend_mod, "ensure_project", lambda project_name: "project-ref"
    )
    monkeypatch.setattr(
        backend_mod, "build_nexus_backend_config", lambda cfg: "backend-config"
    )
    monkeypatch.setattr(backend_mod, "_import_qnexus", lambda: types.SimpleNamespace())
    return backend_mod.NexusClientBackend(
        platform="hseries:H2-1LE",
        project="proj",
        job_name_prefix="team-alpha",
    )


def test_execute_circuit_contract_shape(
    backend: backend_mod.NexusClientBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: dict[str, object] = {}

    def fake_upload(self, circuit, *, parameters=None, sequence_idx=0):
        calls["upload"] = {"parameters": parameters, "sequence_idx": sequence_idx}
        return "program-ref", TranslationMetadata(
            measured_qubits=[0, 1], nqubits=2, qasm="q"
        )

    def fake_run_compile_execute(**kwargs):
        calls["run"] = kwargs
        return ["execution-item"]

    def fake_map(**kwargs):
        calls["map"] = kwargs
        return {"kind": "MeasurementOutcomes", "nshots": kwargs["nshots"]}

    monkeypatch.setattr(
        backend_mod.NexusClientBackend, "_upload_translated_program", fake_upload
    )
    monkeypatch.setattr(backend_mod, "run_compile_execute", fake_run_compile_execute)
    monkeypatch.setattr(backend_mod, "map_nexus_result_to_qibo", fake_map)

    circuit = make_measured_circuit(1)
    result = backend.execute_circuit(circuit, nshots=123, parameters=[0.5])

    assert result["kind"] == "MeasurementOutcomes"
    assert result["nshots"] == 123
    assert calls["upload"] == {"parameters": [0.5], "sequence_idx": 0}
    assert calls["run"]["n_shots"] == 123
    assert calls["run"]["job_name_prefix"] == "team-alpha"
    assert calls["map"]["execution_result_ref"] == "execution-item"
    assert calls["map"]["measured_qubits"] == [0, 1]


def test_upload_translated_program_uses_job_name_prefix(
    backend: backend_mod.NexusClientBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        backend_mod,
        "translate_qibo_to_pytket",
        lambda circuit, parameters=None: (
            "pytket-circuit",
            TranslationMetadata(measured_qubits=[0], nqubits=1, qasm="OPENQASM 2.0;"),
        ),
    )

    qnx = types.SimpleNamespace(
        circuits=types.SimpleNamespace(
            upload=lambda *, circuit, name, project: captured.update(
                {"circuit": circuit, "name": name, "project": project}
            )
            or "program-ref"
        )
    )
    monkeypatch.setattr(backend_mod, "_import_qnexus", lambda: qnx)

    program_ref, metadata = backend._upload_translated_program(
        make_measured_circuit(1),
        sequence_idx=7,
    )

    assert program_ref == "program-ref"
    assert metadata.measured_qubits == [0]
    assert captured["circuit"] == "pytket-circuit"
    assert captured["project"] == "project-ref"
    assert str(captured["name"]).startswith("team-alpha-program-7-")


def test_execute_circuits_cardinality_and_order(
    backend: backend_mod.NexusClientBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload_calls: list[dict[str, object]] = []
    map_calls: list[dict[str, object]] = []

    def fake_upload(self, circuit, *, parameters=None, sequence_idx=0):
        upload_calls.append({"parameters": parameters, "sequence_idx": sequence_idx})
        return f"program-ref-{sequence_idx}", TranslationMetadata(
            measured_qubits=[0], nqubits=1, qasm="q"
        )

    def fake_run_compile_execute(**kwargs):
        assert kwargs["programs"] == ["program-ref-0", "program-ref-1"]
        assert kwargs["n_shots"] == [10, 20]
        return ["execution-item-0", "execution-item-1"]

    def fake_map(**kwargs):
        map_calls.append(kwargs)
        return f"mapped-{kwargs['execution_result_ref']}"

    monkeypatch.setattr(
        backend_mod.NexusClientBackend, "_upload_translated_program", fake_upload
    )
    monkeypatch.setattr(backend_mod, "run_compile_execute", fake_run_compile_execute)
    monkeypatch.setattr(backend_mod, "map_nexus_result_to_qibo", fake_map)

    circuits = [make_measured_circuit(1), make_measured_circuit(1)]
    result = backend.execute_circuits(
        circuits, nshots=[10, 20], parameters_list=[["a"], ["b"]]
    )

    assert result == ["mapped-execution-item-0", "mapped-execution-item-1"]
    assert upload_calls == [
        {"parameters": ["a"], "sequence_idx": 0},
        {"parameters": ["b"], "sequence_idx": 1},
    ]
    assert [call["nshots"] for call in map_calls] == [10, 20]


def test_execute_circuits_nshots_cardinality_mismatch(
    backend: backend_mod.NexusClientBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_upload(self, circuit, *, parameters=None, sequence_idx=0):
        return f"program-ref-{sequence_idx}", TranslationMetadata(
            measured_qubits=[0], nqubits=1, qasm="q"
        )

    monkeypatch.setattr(
        backend_mod.NexusClientBackend, "_upload_translated_program", fake_upload
    )

    circuits = [make_measured_circuit(1), make_measured_circuit(1)]
    with pytest.raises(ValueError, match="nshots cardinality mismatch"):
        backend.execute_circuits(circuits, nshots=[10], parameters_list=[None, None])

    with pytest.raises(ValueError, match="nshots cardinality mismatch"):
        backend.estimate_circuits(circuits, nshots=[10], parameters_list=[None, None])


def test_estimate_circuit_contract_shape(
    backend: backend_mod.NexusClientBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: dict[str, object] = {}

    def fake_upload(self, circuit, *, parameters=None, sequence_idx=0):
        calls["upload"] = {"parameters": parameters, "sequence_idx": sequence_idx}
        return "program-ref", TranslationMetadata(
            measured_qubits=[0, 1], nqubits=2, qasm="q"
        )

    def fake_prepare(**kwargs):
        calls["prepare"] = kwargs
        return backend_mod._PreparedCompilation(
            compiled_programs=["compiled-program"],
            submission_n_shots=123,
            shot_values=[123],
            compile_job_id="compile-123",
            batch_mode=False,
        )

    def fake_estimate(**kwargs):
        calls["estimate"] = kwargs
        return backend_mod.ExecutionEstimate(
            platform="hseries:H2-1LE",
            optimisation_level=2,
            batch_mode=False,
            total_hqcs=1.75,
            items=[
                backend_mod.EstimateItem(
                    sequence_idx=0,
                    nshots=123,
                    hqcs=1.75,
                    compile_job_id="compile-123",
                )
            ],
        )

    monkeypatch.setattr(
        backend_mod.NexusClientBackend, "_upload_translated_program", fake_upload
    )
    monkeypatch.setattr(backend_mod, "_prepare_compiled_programs", fake_prepare)
    monkeypatch.setattr(backend_mod, "_estimate_prepared_compilation", fake_estimate)
    monkeypatch.setattr(
        backend_mod,
        "_import_qnexus",
        lambda: types.SimpleNamespace(
            circuits=types.SimpleNamespace(cost=lambda *a, **k: None)
        ),
    )

    circuit = make_measured_circuit(1)
    estimate = backend.estimate_circuit(circuit, nshots=123, parameters=[0.5])

    assert estimate.total_hqcs == 1.75
    assert estimate.items[0].nshots == 123
    assert calls["upload"] == {"parameters": [0.5], "sequence_idx": 0}
    assert calls["prepare"]["programs"] == ["program-ref"]
    assert calls["prepare"]["n_shots"] == 123
    assert calls["prepare"]["batch_mode"] is False
    assert calls["estimate"]["prepared"].compile_job_id == "compile-123"


def test_estimate_circuits_batch_contract_shape(
    backend: backend_mod.NexusClientBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload_calls: list[dict[str, object]] = []

    def fake_upload(self, circuit, *, parameters=None, sequence_idx=0):
        upload_calls.append({"parameters": parameters, "sequence_idx": sequence_idx})
        return f"program-ref-{sequence_idx}", TranslationMetadata(
            measured_qubits=[0], nqubits=1, qasm="q"
        )

    def fake_prepare(**kwargs):
        assert kwargs["programs"] == ["program-ref-0", "program-ref-1"]
        assert kwargs["n_shots"] == [10, 20]
        assert kwargs["batch_mode"] is True
        return backend_mod._PreparedCompilation(
            compiled_programs=["compiled-0", "compiled-1"],
            submission_n_shots=[10, 20],
            shot_values=[10, 20],
            compile_job_id="compile-456",
            batch_mode=True,
        )

    def fake_estimate(**kwargs):
        prepared = kwargs["prepared"]
        assert prepared.compiled_programs == ["compiled-0", "compiled-1"]
        return backend_mod.ExecutionEstimate(
            platform="hseries:H2-1LE",
            optimisation_level=2,
            batch_mode=True,
            total_hqcs=5.0,
            items=[
                backend_mod.EstimateItem(0, 10, 2.0, "compile-456"),
                backend_mod.EstimateItem(1, 20, 3.0, "compile-456"),
            ],
        )

    monkeypatch.setattr(
        backend_mod.NexusClientBackend, "_upload_translated_program", fake_upload
    )
    monkeypatch.setattr(backend_mod, "_prepare_compiled_programs", fake_prepare)
    monkeypatch.setattr(backend_mod, "_estimate_prepared_compilation", fake_estimate)
    monkeypatch.setattr(
        backend_mod,
        "_import_qnexus",
        lambda: types.SimpleNamespace(
            circuits=types.SimpleNamespace(cost=lambda *a, **k: None)
        ),
    )

    circuits = [make_measured_circuit(1), make_measured_circuit(1)]
    estimate = backend.estimate_circuits(
        circuits, nshots=[10, 20], parameters_list=[["a"], ["b"]]
    )

    assert estimate.total_hqcs == 5.0
    assert [item.hqcs for item in estimate.items] == [2.0, 3.0]
    assert upload_calls == [
        {"parameters": ["a"], "sequence_idx": 0},
        {"parameters": ["b"], "sequence_idx": 1},
    ]


def test_estimate_circuits_non_batch_aggregates_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(backend_mod, "_ensure_nexus_dependencies", lambda: None)
    monkeypatch.setattr(backend_mod, "authenticate", lambda **kwargs: None)
    monkeypatch.setattr(
        backend_mod, "ensure_project", lambda project_name: "project-ref"
    )
    monkeypatch.setattr(
        backend_mod, "build_nexus_backend_config", lambda cfg: "backend-config"
    )

    backend = backend_mod.NexusClientBackend(
        platform="hseries:H2-1LE",
        project="proj",
        job_name_prefix="team-alpha",
        batch_mode=False,
    )

    def fake_upload(self, circuit, *, parameters=None, sequence_idx=0):
        return f"program-ref-{sequence_idx}", TranslationMetadata(
            measured_qubits=[0], nqubits=1, qasm="q"
        )

    def fake_prepare(**kwargs):
        sequence_idx = int(str(kwargs["programs"][0]).rsplit("-", 1)[-1])
        shots = kwargs["n_shots"]
        return backend_mod._PreparedCompilation(
            compiled_programs=[f"compiled-{sequence_idx}"],
            submission_n_shots=shots,
            shot_values=[shots],
            compile_job_id=f"compile-{sequence_idx}",
            batch_mode=False,
        )

    def fake_estimate(**kwargs):
        prepared = kwargs["prepared"]
        sequence_idx = int(str(prepared.compiled_programs[0]).rsplit("-", 1)[-1])
        shots = prepared.shot_values[0]
        return backend_mod.ExecutionEstimate(
            platform="hseries:H2-1LE",
            optimisation_level=2,
            batch_mode=False,
            total_hqcs=float(sequence_idx + 1),
            items=[
                backend_mod.EstimateItem(
                    sequence_idx=0,
                    nshots=shots,
                    hqcs=float(sequence_idx + 1),
                    compile_job_id=prepared.compile_job_id,
                )
            ],
        )

    monkeypatch.setattr(
        backend_mod.NexusClientBackend, "_upload_translated_program", fake_upload
    )
    monkeypatch.setattr(backend_mod, "_prepare_compiled_programs", fake_prepare)
    monkeypatch.setattr(backend_mod, "_estimate_prepared_compilation", fake_estimate)
    monkeypatch.setattr(
        backend_mod,
        "_import_qnexus",
        lambda: types.SimpleNamespace(
            circuits=types.SimpleNamespace(cost=lambda *a, **k: None)
        ),
    )

    circuits = [make_measured_circuit(1), make_measured_circuit(1)]
    estimate = backend.estimate_circuits(
        circuits, nshots=[10, 20], parameters_list=[["a"], ["b"]]
    )

    assert estimate.batch_mode is False
    assert estimate.total_hqcs == 3.0
    assert [(item.sequence_idx, item.nshots, item.hqcs) for item in estimate.items] == [
        (0, 10, 1.0),
        (1, 20, 2.0),
    ]


def test_unsupported_execution_modes(backend: backend_mod.NexusClientBackend) -> None:
    with pytest.raises(UnsupportedExecutionError, match="execute_circuit_repeated"):
        backend.execute_circuit_repeated(Circuit(1), nshots=10, repetitions=2)

    with pytest.raises(UnsupportedExecutionError, match="Distributed execution"):
        backend.execute_distributed_circuit(Circuit(1))

    with pytest.raises(UnsupportedExecutionError, match="initial_state"):
        backend.execute_circuit(make_measured_circuit(1), initial_state=[1, 0])

    with pytest.raises(UnsupportedExecutionError, match=r"(?i)shot-based"):
        backend.execute_circuit(Circuit(1), nshots=10)

    with pytest.raises(UnsupportedExecutionError, match=r"(?i)shot-based"):
        backend.estimate_circuit(Circuit(1), nshots=10)


def test_platform_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backend_mod, "_ensure_nexus_dependencies", lambda: None)
    monkeypatch.setattr(backend_mod, "authenticate", lambda **kwargs: None)
    monkeypatch.setattr(
        backend_mod, "ensure_project", lambda project_name: "project-ref"
    )
    monkeypatch.setattr(
        backend_mod, "build_nexus_backend_config", lambda cfg: "backend-config"
    )
    backend = backend_mod.NexusClientBackend(platform="hseries:H2-1LE", project="proj")
    assert backend.config.platform == "hseries:H2-1LE"


def test_execute_circuit_contract_shape_aer_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(backend_mod, "_ensure_nexus_dependencies", lambda: None)
    monkeypatch.setattr(backend_mod, "authenticate", lambda **kwargs: None)
    monkeypatch.setattr(
        backend_mod, "ensure_project", lambda project_name: "project-ref"
    )
    monkeypatch.setattr(
        backend_mod, "build_nexus_backend_config", lambda cfg: "aer-backend-config"
    )

    calls: dict[str, object] = {}

    def fake_upload(self, circuit, *, parameters=None, sequence_idx=0):
        calls["upload"] = {"parameters": parameters, "sequence_idx": sequence_idx}
        return "program-ref", TranslationMetadata(
            measured_qubits=[0, 1], nqubits=2, qasm="q"
        )

    def fake_run_compile_execute(**kwargs):
        calls["run"] = kwargs
        return ["execution-item"]

    def fake_map(**kwargs):
        calls["map"] = kwargs
        return {"kind": "MeasurementOutcomes", "nshots": kwargs["nshots"]}

    monkeypatch.setattr(
        backend_mod.NexusClientBackend, "_upload_translated_program", fake_upload
    )
    monkeypatch.setattr(backend_mod, "run_compile_execute", fake_run_compile_execute)
    monkeypatch.setattr(backend_mod, "map_nexus_result_to_qibo", fake_map)

    backend = backend_mod.NexusClientBackend(
        platform="aer:aer_simulator",
        project="proj",
        job_name_prefix="team-alpha",
    )
    circuit = make_measured_circuit(2)
    result = backend.execute_circuit(circuit, nshots=128, parameters=[0.1])

    assert result["kind"] == "MeasurementOutcomes"
    assert result["nshots"] == 128
    assert calls["upload"] == {"parameters": [0.1], "sequence_idx": 0}
    assert calls["run"]["backend_config"] == "aer-backend-config"
    assert calls["run"]["job_name_prefix"] == "team-alpha"
    assert calls["run"]["platform"] == "aer:aer_simulator"
    assert calls["map"]["execution_result_ref"] == "execution-item"


def test_constructor_is_lazy_and_project_defaults_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"auth": 0, "project": 0, "config": 0}

    monkeypatch.setattr(backend_mod, "_ensure_nexus_dependencies", lambda: None)
    monkeypatch.setattr(
        backend_mod,
        "authenticate",
        lambda **kwargs: calls.__setitem__("auth", calls["auth"] + 1),
    )
    monkeypatch.setattr(
        backend_mod,
        "ensure_project",
        lambda project_name: calls.__setitem__("project", calls["project"] + 1)
        or project_name,
    )
    monkeypatch.setattr(
        backend_mod,
        "build_nexus_backend_config",
        lambda cfg: calls.__setitem__("config", calls["config"] + 1)
        or "backend-config",
    )

    backend = backend_mod.NexusClientBackend(platform="hseries:H2-1LE")

    assert backend.config.project is None
    assert calls == {"auth": 0, "project": 0, "config": 0}


def test_ensure_connected_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"auth": 0, "project": 0, "config": 0}

    monkeypatch.setattr(backend_mod, "_ensure_nexus_dependencies", lambda: None)
    monkeypatch.setattr(
        backend_mod,
        "authenticate",
        lambda **kwargs: calls.__setitem__("auth", calls["auth"] + 1),
    )
    monkeypatch.setattr(
        backend_mod,
        "ensure_project",
        lambda project_name: calls.__setitem__("project", calls["project"] + 1)
        or "project-ref",
    )
    monkeypatch.setattr(
        backend_mod,
        "build_nexus_backend_config",
        lambda cfg: calls.__setitem__("config", calls["config"] + 1)
        or "backend-config",
    )

    backend = backend_mod.NexusClientBackend(platform="hseries:H2-1LE", project="proj")
    backend._ensure_connected()
    backend._ensure_connected()

    assert calls == {"auth": 1, "project": 1, "config": 1}


def test_execute_circuit_helios_uses_hugr_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backend_mod, "_ensure_nexus_dependencies", lambda: None)
    monkeypatch.setattr(backend_mod, "authenticate", lambda **kwargs: None)
    monkeypatch.setattr(
        backend_mod, "ensure_project", lambda project_name: "project-ref"
    )

    build_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        backend_mod,
        "build_nexus_backend_config",
        lambda cfg, **kwargs: build_calls.append(kwargs) or "helios-backend-config",
    )
    monkeypatch.setattr(
        backend_mod,
        "build_helios_hugr_package",
        lambda circuit, parameters=None, entrypoint_name="helios_entrypoint": (
            "hugr-package",
            TranslationMetadata(measured_qubits=[0, 1], nqubits=2, qasm="OPENQASM"),
        ),
    )

    calls: dict[str, object] = {}

    class JobRef:
        id = "execute-job-1"

    qnx = types.SimpleNamespace(
        hugr=types.SimpleNamespace(
            upload=lambda *, hugr_package, name, project: calls.update(
                {"uploaded": (hugr_package, name, project)}
            )
            or "hugr-ref",
            cost_confidence=lambda *, programs, n_shots, **kw: calls.update(
                {"cost": (programs, n_shots)}
            )
            or [(1.25, 84.0)],
        ),
        circuits=types.SimpleNamespace(
            upload=lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("circuits.upload called")
            )
        ),
        start_compile_job=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("start_compile_job called")
        ),
        start_execute_job=lambda **kwargs: calls.update({"execute": kwargs})
        or JobRef(),
        jobs=types.SimpleNamespace(
            wait_for=lambda job, timeout: job,
            results=lambda job, allow_incomplete=False: ["helios-result"],
            status=lambda job: "COMPLETED",
        ),
    )
    monkeypatch.setattr(backend_mod, "_import_qnexus", lambda: qnx)
    monkeypatch.setattr(
        backend_mod,
        "map_helios_result_to_qibo",
        lambda **kwargs: calls.update({"map": kwargs})
        or {"kind": "MeasurementOutcomes"},
    )

    backend = backend_mod.NexusClientBackend(
        platform="helios:Helios-1",
        project="proj",
        emulator=True,
    )
    circuit = make_measured_circuit(2)
    result = backend.execute_circuit(circuit, nshots=64)

    assert result["kind"] == "MeasurementOutcomes"
    assert calls["cost"] == (["hugr-ref"], [64])
    assert calls["execute"]["programs"] == ["hugr-ref"]
    assert "language" not in calls["execute"]
    assert build_calls[-1]["n_qubits"] == 2
    assert calls["execute"]["max_cost"] == 1.25
    assert calls["map"]["execution_result_ref"] == "helios-result"


def test_estimate_circuit_helios_uses_hugr_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(backend_mod, "_ensure_nexus_dependencies", lambda: None)
    monkeypatch.setattr(backend_mod, "authenticate", lambda **kwargs: None)
    monkeypatch.setattr(
        backend_mod, "ensure_project", lambda project_name: "project-ref"
    )
    monkeypatch.setattr(
        backend_mod, "build_nexus_backend_config", lambda cfg, **kwargs: None
    )
    monkeypatch.setattr(
        backend_mod,
        "build_helios_hugr_package",
        lambda circuit, parameters=None, entrypoint_name="helios_entrypoint": (
            "hugr-package",
            TranslationMetadata(measured_qubits=[0], nqubits=1, qasm="OPENQASM"),
        ),
    )

    calls: dict[str, object] = {}
    qnx = types.SimpleNamespace(
        hugr=types.SimpleNamespace(
            upload=lambda *, hugr_package, name, project: "hugr-ref",
            cost_confidence=lambda *, programs, n_shots, **kw: calls.update(
                {"cost": (programs, n_shots)}
            )
            or [(2.5, 84.0)],
        ),
        circuits=types.SimpleNamespace(
            upload=lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("circuits.upload called")
            )
        ),
        start_compile_job=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("start_compile_job called")
        ),
    )
    monkeypatch.setattr(backend_mod, "_import_qnexus", lambda: qnx)

    backend = backend_mod.NexusClientBackend(
        platform="helios:Helios-1",
        project="proj",
        emulator=True,
    )
    estimate = backend.estimate_circuit(make_measured_circuit(1), nshots=11)

    assert calls["cost"] == (["hugr-ref"], [11])
    assert estimate.total_hqcs == 2.5
    assert estimate.items[0].nshots == 11


def test_estimate_circuits_helios_submits_single_batch_cost_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(backend_mod, "_ensure_nexus_dependencies", lambda: None)
    monkeypatch.setattr(backend_mod, "authenticate", lambda **kwargs: None)
    monkeypatch.setattr(
        backend_mod, "ensure_project", lambda project_name: "project-ref"
    )
    monkeypatch.setattr(
        backend_mod, "build_nexus_backend_config", lambda cfg, **kwargs: None
    )
    monkeypatch.setattr(
        backend_mod,
        "build_helios_hugr_package",
        lambda circuit, parameters=None, entrypoint_name="helios_entrypoint": (
            "hugr-package",
            TranslationMetadata(measured_qubits=[0], nqubits=1, qasm="OPENQASM"),
        ),
    )

    cost_calls: list[dict[str, object]] = []
    qnx = types.SimpleNamespace(
        hugr=types.SimpleNamespace(
            upload=lambda *, hugr_package, name, project: f"hugr-ref-{name}",
            cost_confidence=lambda *, programs, n_shots, **kw: cost_calls.append(
                {"programs": list(programs), "n_shots": list(n_shots)}
            )
            or [(1.5, 84.0), (2.5, 84.0)],
        ),
        circuits=types.SimpleNamespace(
            upload=lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("circuits.upload called")
            )
        ),
        start_compile_job=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("start_compile_job called")
        ),
    )
    monkeypatch.setattr(backend_mod, "_import_qnexus", lambda: qnx)

    backend = backend_mod.NexusClientBackend(
        platform="helios:Helios-1",
        project="proj",
        emulator=True,
    )
    circuits = [make_measured_circuit(1), make_measured_circuit(1)]
    estimate = backend.estimate_circuits(circuits, nshots=[10, 20])

    assert len(cost_calls) == 1
    assert len(cost_calls[0]["programs"]) == 2
    assert cost_calls[0]["n_shots"] == [10, 20]
    assert estimate.total_hqcs == 4.0
    assert estimate.items[0].nshots == 10
    assert estimate.items[0].hqcs == 1.5
    assert estimate.items[1].nshots == 20
    assert estimate.items[1].hqcs == 2.5
    assert estimate.batch_mode is False


def test_execute_circuits_helios_emulator_propagates_per_program_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test for batched Helios execute_circuits.

    Verifies that the execute path:
      - sizes the emulator state with the maximum metadata.nqubits across circuits
      - passes per-program max_cost (as a list) to qnx.start_execute_job
      - does NOT inject attempt_batching=True into backend_options
        (vendor: batching is unsupported on Helios emulators).
    """
    monkeypatch.setattr(backend_mod, "_ensure_nexus_dependencies", lambda: None)
    monkeypatch.setattr(backend_mod, "authenticate", lambda **kwargs: None)
    monkeypatch.setattr(
        backend_mod, "ensure_project", lambda project_name: "project-ref"
    )

    build_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        backend_mod,
        "build_nexus_backend_config",
        lambda cfg, **kwargs: build_calls.append({"cfg": cfg, **kwargs})
        or "helios-backend-config",
    )

    metadata_by_idx = [
        TranslationMetadata(measured_qubits=[0], nqubits=1, qasm="q1"),
        TranslationMetadata(measured_qubits=[0, 1, 2], nqubits=3, qasm="q3"),
    ]

    def fake_build(circuit, parameters=None, entrypoint_name="helios_entrypoint"):
        # Return a metadata object whose nqubits matches the circuit width.
        idx = circuit.nqubits - 1 if circuit.nqubits == 1 else 1
        return f"hugr-package-{idx}", metadata_by_idx[idx]

    monkeypatch.setattr(backend_mod, "build_helios_hugr_package", fake_build)

    calls: dict[str, object] = {}

    class JobRef:
        id = "execute-job-batch"

    qnx = types.SimpleNamespace(
        hugr=types.SimpleNamespace(
            upload=lambda *, hugr_package, name, project: f"hugr-ref-{hugr_package}",
            cost_confidence=lambda *, programs, n_shots, **kw: calls.update(
                {
                    "cost_programs": list(programs),
                    "cost_n_shots": list(n_shots),
                    "cost_system_name": kw.get("system_name"),
                }
            )
            or [(1.5, 10.0), (4.25, 12.0)],
        ),
        circuits=types.SimpleNamespace(
            upload=lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("circuits.upload called")
            )
        ),
        start_compile_job=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("start_compile_job called")
        ),
        start_execute_job=lambda **kwargs: calls.update({"execute": kwargs})
        or JobRef(),
        jobs=types.SimpleNamespace(
            wait_for=lambda job, timeout: job,
            results=lambda job, allow_incomplete=False: ["res-0", "res-1"],
            status=lambda job: "COMPLETED",
        ),
    )
    monkeypatch.setattr(backend_mod, "_import_qnexus", lambda: qnx)
    monkeypatch.setattr(
        backend_mod,
        "map_helios_result_to_qibo",
        lambda **kwargs: f"mapped-{kwargs['execution_result_ref']}",
    )

    backend = backend_mod.NexusClientBackend(
        platform="helios:Helios-1E",
        project="proj",
        emulator=True,
    )
    circuits = [make_measured_circuit(1), make_measured_circuit(3)]
    results = backend.execute_circuits(circuits, nshots=[10, 30])

    assert results == ["mapped-res-0", "mapped-res-1"]

    # Per-program max_cost list and shots flow into start_execute_job (vendor pattern).
    assert calls["execute"]["max_cost"] == [1.5, 4.25]
    assert calls["execute"]["n_shots"] == [10, 30]

    # Emulator state is sized for the widest circuit (max nqubits across programs).
    last_build = build_calls[-1]
    assert last_build["n_qubits"] == 3

    # No batching auto-injection on emulator (vendor: unsupported on Helios emulators).
    cfg = last_build["cfg"]
    assert "attempt_batching" not in cfg.backend_options
    assert "max_batch_cost" not in cfg.backend_options

    # Cost estimation always targets Helios-1 syntax checker — qnexus internally builds
    # `QuantinuumConfig(device_name=f"{system_name}SC")`, and only "Helios-1SC" exists.
    # Even when the user-target platform is Helios-1E, system_name must stay "Helios-1".
    assert calls["cost_system_name"] == "Helios-1"
