"""Nexus backend implementation aligned with qibo-cloud-backends style."""

from __future__ import annotations

import logging
from importlib import import_module
import re
import warnings
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Iterable

from qibo.backends import NumpyBackend
from qibo.models import Circuit

from .nexus_auth import authenticate, ensure_project
from .nexus_config import NexusBackendConfig, build_nexus_backend_config, parse_platform
from .nexus_errors import (
    NexusBackendError,
    UnsupportedExecutionError,
)
from .nexus_helios import build_helios_hugr_package, map_helios_result_to_qibo
from .nexus_results import map_nexus_result_to_qibo
from .nexus_translation import TranslationMetadata, translate_qibo_to_pytket

LOGGER = logging.getLogger(__name__)
_H2_SYNTAX_CHECKER_BASE_RE = re.compile(r"^(H2-\d+)(?:LE|E)?$")


@dataclass(frozen=True)
class EstimateItem:
    sequence_idx: int
    nshots: int
    hqcs: float
    compile_job_id: str


@dataclass(frozen=True)
class ExecutionEstimate:
    platform: str
    optimisation_level: int
    batch_mode: bool
    total_hqcs: float
    items: list[EstimateItem]


@dataclass(frozen=True)
class _PreparedCompilation:
    compiled_programs: list[Any]
    submission_n_shots: int | list[int]
    shot_values: list[int]
    compile_job_id: str
    batch_mode: bool


def _normalize_nshots(nshots: Any) -> int:
    if nshots is None:
        LOGGER.warning("nshots is None, defaulting to 1000.")
        return 1000
    return int(nshots)


def _normalize_batch_nshots(nshots: Any, batch_size: int) -> int | list[int]:
    if isinstance(nshots, Iterable) and not isinstance(nshots, (str, bytes)):
        values = [int(v) for v in nshots]
        if len(values) != batch_size:
            raise ValueError(
                f"nshots cardinality mismatch: got {len(values)} entries for {batch_size} circuits."
            )
        return values
    return int(nshots)


def _resolve_language(language: Any) -> Any:
    if language is not None:
        return language
    try:
        return _import_qnexus().Language.AUTO
    except Exception:  # pragma: no cover - import environment specific
        # qnexus execute APIs accept string literals; keep a safe fallback.
        return "AUTO"


def _import_qnexus() -> Any:
    try:
        return import_module("qnexus")
    except Exception as exc:  # pragma: no cover - import environment specific
        raise NexusBackendError(
            "qnexus is not installed. Install qibo-cloud-backends with the 'nexus' extra."
        ) from exc


def _import_quantinuum_config() -> Any:
    try:
        return import_module("qnexus.models").QuantinuumConfig
    except Exception as exc:  # pragma: no cover - import environment specific
        raise NexusBackendError(
            "qnexus is not installed. Install qibo-cloud-backends with the 'nexus' extra."
        ) from exc


def _ensure_nexus_dependencies() -> None:
    _import_qnexus()
    try:
        import_module("pytket.qasm")
    except Exception as exc:  # pragma: no cover - import environment specific
        raise NexusBackendError(
            "pytket is not installed. Install qibo-cloud-backends with the 'nexus' extra."
        ) from exc


def _job_id(job: Any) -> str:
    for attr in ("id", "job_id", "uid"):
        value = getattr(job, attr, None)
        if value is not None:
            return str(value)
    return "unknown"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _normalize_job_name_prefix(prefix: str | None) -> str:
    value = (prefix or "qibo-nexus").strip()
    return value or "qibo-nexus"


def _job_name(prefix: str | None, stage: str, suffix: str) -> str:
    normalized_prefix = _normalize_job_name_prefix(prefix)
    normalized_suffix = suffix.replace(":", "-")
    return f"{normalized_prefix}-{stage}-{normalized_suffix}-{_utc_stamp()}"


def _wait_for_job(qnx: Any, job: Any, *, timeout: float, stage: str) -> Any:
    try:
        return qnx.jobs.wait_for(job, timeout=timeout)
    except Exception as exc:
        status = None
        try:
            status = qnx.jobs.status(job)
        except Exception:  # noqa: BLE001 - status retrieval best effort
            status = "unknown"

        raise NexusBackendError(
            f"Nexus {stage} job timed out/failed while waiting. "
            f"job_id={_job_id(job)} status={status} reason={exc}"
        ) from exc


def _extract_compiled_program_refs(compile_results: Any) -> list[Any]:
    if not compile_results:
        raise NexusBackendError("Compile job returned no results.")
    outputs: list[Any] = []
    for item in compile_results:
        if hasattr(item, "get_output"):
            outputs.append(item.get_output())
        elif hasattr(item, "output"):
            outputs.append(item.output)
        else:
            outputs.append(item)
    return outputs


def _expand_n_shots(n_shots: int | list[int], program_count: int) -> list[int]:
    if isinstance(n_shots, Iterable) and not isinstance(n_shots, (str, bytes)):
        values = [int(v) for v in n_shots]
        if len(values) != program_count:
            raise ValueError(
                f"nshots cardinality mismatch: got {len(values)} entries for {program_count} circuits."
            )
        return values
    return [int(n_shots)] * program_count


def _prepare_compiled_programs(
    *,
    qnx: Any,
    programs: list[Any],
    backend_config: Any,
    optimisation_level: int,
    n_shots: int | list[int],
    timeout: float,
    platform: str,
    batch_mode: bool,
    job_name_prefix: str | None = None,
    project: Any = None,
) -> _PreparedCompilation:
    compile_name = _job_name(job_name_prefix, "compile", platform)

    try:
        compile_job = qnx.start_compile_job(
            programs=programs,
            backend_config=backend_config,
            optimisation_level=optimisation_level,
            name=compile_name,
            project=project,
        )
    except Exception as exc:  # noqa: BLE001
        raise NexusBackendError(f"Failed to submit compile job: {exc}") from exc

    compile_job_id = _job_id(compile_job)
    LOGGER.info(
        "Nexus compile job submitted",
        extra={"platform": platform, "compile_job_id": compile_job_id},
    )

    _wait_for_job(
        qnx,
        compile_job,
        timeout=timeout,
        stage="compile",
    )

    try:
        compile_results = qnx.jobs.results(compile_job)
        compiled_programs = _extract_compiled_program_refs(compile_results)
    except Exception as exc:  # noqa: BLE001
        raise NexusBackendError(
            f"Failed to retrieve compile output. job_id={compile_job_id} reason={exc}"
        ) from exc

    return _PreparedCompilation(
        compiled_programs=compiled_programs,
        submission_n_shots=n_shots,
        shot_values=_expand_n_shots(n_shots, len(compiled_programs)),
        compile_job_id=compile_job_id,
        batch_mode=batch_mode,
    )


def _supports_hqc_estimation(backend_config: Any) -> bool:
    return _resolve_estimate_syntax_checker(backend_config, warn_for_emulator=False) is not None


def _resolve_estimate_syntax_checker(
    backend_config: Any, *, warn_for_emulator: bool = True
) -> str | None:
    device_name = getattr(backend_config, "device_name", None)
    if not isinstance(device_name, str):
        return None
    match = _H2_SYNTAX_CHECKER_BASE_RE.match(device_name)
    if match is None:
        return None

    syntax_checker = f"{match.group(1)}SC"
    if warn_for_emulator and device_name != match.group(1):
        message = (
            f"Cost estimation for emulator target '{device_name}' is routed through "
            f"the hardware syntax-checker '{syntax_checker}'."
        )
        LOGGER.warning(message)
        warnings.warn(message, RuntimeWarning, stacklevel=3)
    return syntax_checker


def _estimate_prepared_compilation(
    *,
    qnx: Any,
    prepared: _PreparedCompilation,
    backend_config: Any,
    project: Any,
    platform: str,
    optimisation_level: int,
    timeout: float,
    job_name_prefix: str | None = None,
) -> ExecutionEstimate:
    if not _supports_hqc_estimation(backend_config):
        raise NexusBackendError(
            "Compile-time HQC estimation is only supported for Quantinuum H2 systems."
        )
    syntax_checker = _resolve_estimate_syntax_checker(backend_config)
    if syntax_checker is None:
        raise NexusBackendError(
            "Could not derive an H2 syntax-checker target for compile-time HQC estimation."
        )

    cost_name = _job_name(job_name_prefix, "cost", platform)
    try:
        cost_job = qnx.start_execute_job(
            programs=prepared.compiled_programs,
            n_shots=prepared.submission_n_shots,
            backend_config=_import_quantinuum_config()(device_name=syntax_checker),
            project=project,
            name=cost_name,
        )
    except Exception as exc:  # noqa: BLE001
        raise NexusBackendError(f"Failed to submit cost estimation job: {exc}") from exc

    cost_job_id = _job_id(cost_job)
    LOGGER.info(
        "Nexus cost estimation job submitted",
        extra={
            "platform": platform,
            "compile_job_id": prepared.compile_job_id,
            "cost_job_id": cost_job_id,
        },
    )

    _wait_for_job(
        qnx,
        cost_job,
        timeout=timeout,
        stage="cost-estimate",
    )

    try:
        cost_confidence_items = qnx.jobs.cost_confidence(cost_job)
    except Exception as exc:  # noqa: BLE001
        raise NexusBackendError(
            f"Failed to fetch batched cost estimation results. job_id={cost_job_id} reason={exc}"
        ) from exc

    if len(cost_confidence_items) != len(prepared.shot_values):
        raise NexusBackendError(
            "Cost estimation returned an unexpected number of items. "
            f"job_id={cost_job_id} expected={len(prepared.shot_values)} got={len(cost_confidence_items)}"
        )

    normalized_costs: list[float] = []
    for item in cost_confidence_items:
        if not isinstance(item, tuple) or len(item) < 1 or item[0] is None:
            raise NexusBackendError(
                f"Cost estimation returned invalid per-item cost data. job_id={cost_job_id}"
            )
        try:
            normalized_costs.append(float(item[0]))
        except (TypeError, ValueError) as exc:
            raise NexusBackendError(
                f"Cost estimation returned invalid per-item cost data. job_id={cost_job_id} reason={exc}"
            ) from exc

    items = [
        EstimateItem(
            sequence_idx=idx,
            nshots=nshots,
            hqcs=hqcs,
            compile_job_id=prepared.compile_job_id,
        )
        for idx, (nshots, hqcs) in enumerate(zip(prepared.shot_values, normalized_costs))
    ]
    return ExecutionEstimate(
        platform=platform,
        optimisation_level=optimisation_level,
        batch_mode=prepared.batch_mode,
        total_hqcs=sum(normalized_costs),
        items=items,
    )


_HELIOS_COST_SYSTEM_NAME = "Helios-1"
# qnx.hugr.cost_confidence builds its costing job from QuantinuumConfig(device_name=f"{system_name}SC")
# and only "Helios-1SC" exists as a syntax checker — emulator targets must still use this.


def _estimate_helios_cost(
    *,
    qnx: Any,
    program: Any,
    nshots: int,
    project: Any = None,
) -> float:
    try:
        results = qnx.hugr.cost_confidence(
            programs=[program],
            n_shots=[int(nshots)],
            project=project,
            system_name=_HELIOS_COST_SYSTEM_NAME,
        )
    except Exception as exc:  # noqa: BLE001
        raise NexusBackendError(f"Failed to estimate Helios execution cost: {exc}") from exc
    try:
        items = list(results)
        if not items or not isinstance(items[0], tuple) or len(items[0]) < 1 or items[0][0] is None:
            raise ValueError(f"unexpected result shape: {items!r}")
        return float(items[0][0])
    except (TypeError, ValueError) as exc:
        raise NexusBackendError(f"Invalid Helios cost estimate returned: {results!r}") from exc


def _estimate_helios_costs_batch(
    *,
    qnx: Any,
    programs: list[Any],
    n_shots: list[int],
    project: Any = None,
) -> list[float]:
    try:
        results = qnx.hugr.cost_confidence(
            programs=programs,
            n_shots=n_shots,
            project=project,
            system_name=_HELIOS_COST_SYSTEM_NAME,
        )
    except Exception as exc:  # noqa: BLE001
        raise NexusBackendError(f"Failed to estimate Helios execution costs: {exc}") from exc
    try:
        items = list(results)
    except (TypeError, ValueError) as exc:
        raise NexusBackendError(
            f"Invalid Helios cost estimate returned: {results!r}"
        ) from exc
    if len(items) != len(programs):
        raise NexusBackendError(
            f"Helios batch cost estimate returned {len(items)} values "
            f"for {len(programs)} programs."
        )
    costs: list[float] = []
    for idx, item in enumerate(items):
        if not isinstance(item, tuple) or len(item) < 1 or item[0] is None:
            raise NexusBackendError(
                f"Invalid Helios cost estimate at index {idx}: {item!r}"
            )
        try:
            costs.append(float(item[0]))
        except (TypeError, ValueError) as exc:
            raise NexusBackendError(
                f"Invalid Helios cost estimate at index {idx}: {item!r}"
            ) from exc
    return costs


def _execute_programs(
    *,
    qnx: Any,
    programs: list[Any],
    n_shots: int | list[int],
    backend_config: Any,
    timeout: float,
    allow_incomplete: bool,
    language: Any,
    platform: str,
    job_name_prefix: str | None = None,
    project: Any = None,
    max_cost: float | list[float] | None = None,
) -> list[Any]:
    execute_name = _job_name(job_name_prefix, "execute", platform)

    try:
        execute_kwargs = {
            "programs": programs,
            "n_shots": n_shots,
            "backend_config": backend_config,
            "name": execute_name,
            "project": project,
        }
        if language is not None:
            execute_kwargs["language"] = language
        if max_cost is not None:
            execute_kwargs["max_cost"] = max_cost
        execute_job = qnx.start_execute_job(**execute_kwargs)
    except Exception as exc:  # noqa: BLE001
        raise NexusBackendError(f"Failed to submit execute job: {exc}") from exc

    LOGGER.info(
        "Nexus execute job submitted",
        extra={
            "platform": platform,
            "execute_job_id": _job_id(execute_job),
        },
    )

    _wait_for_job(
        qnx,
        execute_job,
        timeout=timeout,
        stage="execute",
    )

    try:
        items = qnx.jobs.results(execute_job, allow_incomplete=allow_incomplete)
    except Exception as exc:  # noqa: BLE001
        status = None
        try:
            status = qnx.jobs.status(execute_job)
        except Exception:  # noqa: BLE001
            status = "unknown"
        raise NexusBackendError(
            f"Failed to fetch execute results. job_id={_job_id(execute_job)} status={status} reason={exc}"
        ) from exc

    if not items:
        raise NexusBackendError(
            f"Execute job returned no result items. job_id={_job_id(execute_job)}"
        )

    return list(items)


def _execute_prepared_compilation(
    *,
    qnx: Any,
    prepared: _PreparedCompilation,
    backend_config: Any,
    timeout: float,
    allow_incomplete: bool,
    language: Any,
    platform: str,
    job_name_prefix: str | None = None,
    project: Any = None,
) -> list[Any]:
    return _execute_programs(
        qnx=qnx,
        programs=prepared.compiled_programs,
        n_shots=prepared.submission_n_shots,
        backend_config=backend_config,
        timeout=timeout,
        allow_incomplete=allow_incomplete,
        language=language,
        platform=platform,
        job_name_prefix=job_name_prefix,
        project=project,
    )


def run_compile_execute(
    *,
    programs: list[Any],
    backend_config: Any,
    optimisation_level: int,
    n_shots: int | list[int],
    timeout: float,
    allow_incomplete: bool,
    language: Any,
    platform: str,
    job_name_prefix: str | None = None,
    project: Any = None,
) -> list[Any]:
    """Run compile then execute and return execution result refs."""

    qnx = _import_qnexus()
    prepared = _prepare_compiled_programs(
        qnx=qnx,
        programs=programs,
        backend_config=backend_config,
        optimisation_level=optimisation_level,
        n_shots=n_shots,
        timeout=timeout,
        platform=platform,
        batch_mode=len(programs) > 1,
        job_name_prefix=job_name_prefix,
        project=project,
    )
    return _execute_prepared_compilation(
        qnx=qnx,
        prepared=prepared,
        backend_config=backend_config,
        timeout=timeout,
        allow_incomplete=allow_incomplete,
        language=language,
        platform=platform,
        job_name_prefix=job_name_prefix,
        project=project,
    )


class NexusClientBackend(NumpyBackend):
    """Qibo backend that compiles and executes circuits through Quantinuum Nexus."""

    name = "nexus-client"

    def __init__(
        self,
        platform: str = "hseries:H2-1LE",
        project: str | None = None,
        *,
        optimisation_level: int = 2,
        timeout: float = 1800.0,
        allow_incomplete: bool = False,
        language: Any = None,
        credential_login: bool | None = None,
        batch_mode: bool = True,
        reverse_endianness: bool = False,
        job_name_prefix: str = "qibo-nexus",
        **backend_options: Any,
    ) -> None:
        super().__init__()
        _ensure_nexus_dependencies()
        self.platform = platform
        self.project = project

        self.config: NexusBackendConfig = NexusBackendConfig(
            platform=platform,
            project=project,
            job_name_prefix=job_name_prefix,
            optimisation_level=optimisation_level,
            timeout=timeout,
            allow_incomplete=allow_incomplete,
            language=language,
            credential_login=credential_login,
            batch_mode=batch_mode,
            reverse_endianness=reverse_endianness,
            backend_options=backend_options,
        )

        self._project_ref: Any = None
        self._backend_config: Any = None
        self._resolved_language: Any = None
        self._connected = False

    def __repr__(self) -> str:
        return (
            "NexusClientBackend("
            f"platform={self.config.platform!r}, project={self.config.project!r}, "
            f"job_name_prefix={self.config.job_name_prefix!r}, "
            f"optimisation_level={self.config.optimisation_level}, "
            f"timeout={self.config.timeout}, allow_incomplete={self.config.allow_incomplete}, "
            f"batch_mode={self.config.batch_mode}"
            ")"
        )

    def _ensure_connected(self) -> None:
        """Authenticate and resolve project/backend config once on demand."""
        if self._connected:
            return
        authenticate(
            credential_login=self.config.credential_login,
        )
        self._project_ref = ensure_project(self.config.project)
        if self.config.platform_family == "helios":
            self._backend_config = None
            self._resolved_language = None
        else:
            self._backend_config = build_nexus_backend_config(self.config)
            self._resolved_language = _resolve_language(self.config.language)
        self._connected = True

    def _build_execution_backend_config(
        self,
        *,
        nqubits: int | None = None,
    ) -> Any:
        if self.config.platform_family != "helios":
            return self._backend_config
        return build_nexus_backend_config(
            self.config,
            n_qubits=nqubits,
        )

    def _map_execution_result(
        self,
        *,
        execution_result_ref: Any,
        circuit: Circuit,
        nshots: int,
        metadata: TranslationMetadata,
    ) -> Any:
        mapper = (
            map_helios_result_to_qibo
            if self.config.platform_family == "helios"
            else map_nexus_result_to_qibo
        )
        return mapper(
            execution_result_ref=execution_result_ref,
            circuit=circuit,
            backend=self,
            nshots=nshots,
            measured_qubits=metadata.measured_qubits,
            reverse_endianness=self.config.reverse_endianness,
        )

    def _assert_supported_execution(self, circuit: Circuit, initial_state: Any) -> None:
        if initial_state is not None:
            raise UnsupportedExecutionError(
                "Nexus backend does not support custom initial_state injection."
            )

        if self.config.shot_only and len(circuit.measurements) == 0:
            raise UnsupportedExecutionError(
                "Shot-based Nexus targets require measurement gates in the circuit."
            )

    def _upload_translated_program(
        self,
        circuit: Circuit,
        *,
        parameters: Any = None,
        sequence_idx: int = 0,
    ) -> tuple[Any, TranslationMetadata]:
        self._ensure_connected()
        qnx = _import_qnexus()
        upload_name = _job_name(self.config.job_name_prefix, "program", str(sequence_idx))
        if self.config.platform_family == "helios":
            hugr_package, metadata = build_helios_hugr_package(
                circuit,
                parameters=parameters,
                entrypoint_name=f"helios_entrypoint_{sequence_idx}",
            )
            try:
                program_ref = qnx.hugr.upload(
                    hugr_package=hugr_package,
                    name=upload_name,
                    project=self._project_ref,
                )
            except Exception as exc:  # noqa: BLE001
                raise NexusBackendError(f"Failed to upload Helios HUGR to Nexus: {exc}") from exc
            return program_ref, metadata

        pytket_circuit, metadata = translate_qibo_to_pytket(circuit, parameters=parameters)
        try:
            circuit_ref = qnx.circuits.upload(
                circuit=pytket_circuit,
                name=upload_name,
                project=self._project_ref,
            )
        except Exception as exc:  # noqa: BLE001
            raise NexusBackendError(f"Failed to upload circuit to Nexus: {exc}") from exc

        return circuit_ref, metadata

    def execute_circuit(
        self,
        circuit: Circuit,
        initial_state: Any = None,
        nshots: int = 1000,
        parameters: Any = None,
        **kwargs: Any,
    ) -> Any:
        del kwargs
        self._assert_supported_execution(circuit, initial_state)
        self._ensure_connected()
        shots = _normalize_nshots(nshots)

        program_ref, metadata = self._upload_translated_program(
            circuit,
            parameters=parameters,
            sequence_idx=0,
        )

        if self.config.platform_family == "helios":
            qnx = _import_qnexus()
            max_cost = _estimate_helios_cost(
                qnx=qnx,
                program=program_ref,
                nshots=shots,
                project=self._project_ref,
            )
            backend_config = self._build_execution_backend_config(
                nqubits=metadata.nqubits,
            )
            execution_items = _execute_programs(
                qnx=qnx,
                programs=[program_ref],
                n_shots=shots,
                backend_config=backend_config,
                timeout=self.config.timeout,
                allow_incomplete=self.config.allow_incomplete,
                language=None,
                platform=self.config.platform,
                job_name_prefix=self.config.job_name_prefix,
                project=self._project_ref,
                max_cost=max_cost,
            )
        else:
            execution_items = run_compile_execute(
                programs=[program_ref],
                backend_config=self._backend_config,
                optimisation_level=self.config.optimisation_level,
                n_shots=shots,
                timeout=self.config.timeout,
                allow_incomplete=self.config.allow_incomplete,
                language=self._resolved_language,
                platform=self.config.platform,
                job_name_prefix=self.config.job_name_prefix,
                project=self._project_ref,
            )

        LOGGER.info(
            "Nexus execution completed",
            extra={
                "project": self.config.project,
                "platform": self.config.platform,
                "nshots": shots,
                "items": len(execution_items),
            },
        )

        return self._map_execution_result(
            execution_result_ref=execution_items[0],
            circuit=circuit,
            nshots=shots,
            metadata=metadata,
        )

    def estimate_circuit(
        self,
        circuit: Circuit,
        initial_state: Any = None,
        nshots: int = 1000,
        parameters: Any = None,
        **kwargs: Any,
    ) -> ExecutionEstimate:
        del kwargs
        self._assert_supported_execution(circuit, initial_state)
        shots = _normalize_nshots(nshots)
        self._ensure_connected()
        qnx = _import_qnexus()

        program_ref, metadata = self._upload_translated_program(
            circuit,
            parameters=parameters,
            sequence_idx=0,
        )
        if self.config.platform_family == "helios":
            hqcs = _estimate_helios_cost(
                qnx=qnx,
                program=program_ref,
                nshots=shots,
                project=self._project_ref,
            )
            return ExecutionEstimate(
                platform=self.config.platform,
                optimisation_level=self.config.optimisation_level,
                batch_mode=False,
                total_hqcs=hqcs,
                items=[
                    EstimateItem(
                        sequence_idx=0,
                        nshots=shots,
                        hqcs=hqcs,
                        compile_job_id=_job_id(program_ref),
                    )
                ],
            )

        prepared = _prepare_compiled_programs(
            qnx=qnx,
            programs=[program_ref],
            backend_config=self._backend_config,
            optimisation_level=self.config.optimisation_level,
            n_shots=shots,
            timeout=self.config.timeout,
            platform=self.config.platform,
            batch_mode=False,
            job_name_prefix=self.config.job_name_prefix,
            project=self._project_ref,
        )
        return _estimate_prepared_compilation(
            qnx=qnx,
            prepared=prepared,
            backend_config=self._backend_config,
            project=self._project_ref,
            platform=self.config.platform,
            optimisation_level=self.config.optimisation_level,
            timeout=self.config.timeout,
            job_name_prefix=self.config.job_name_prefix,
        )

    def execute_circuits(
        self,
        circuits: list[Circuit],
        nshots: int | list[int] = 1000,
        initial_states: Any = None,
        parameters_list: list[Any] | None = None,
    ) -> list[Any]:
        if initial_states is not None:
            raise UnsupportedExecutionError(
                "Nexus backend does not support initial_states for execute_circuits."
            )

        if not circuits:
            return []
        self._ensure_connected()

        if self.config.platform_family == "helios":
            if parameters_list is None:
                parameters_list = [None] * len(circuits)
            if len(parameters_list) != len(circuits):
                raise ValueError(
                    "parameters_list cardinality mismatch with circuits in execute_circuits."
                )
            shot_values = _normalize_batch_nshots(nshots, len(circuits))
            if isinstance(shot_values, int):
                shot_values = [shot_values] * len(circuits)

            qnx = _import_qnexus()
            program_refs: list[Any] = []
            metadata_list: list[TranslationMetadata] = []
            for idx, (circuit, params) in enumerate(zip(circuits, parameters_list)):
                self._assert_supported_execution(circuit, None)
                program_ref, metadata = self._upload_translated_program(
                    circuit, parameters=params, sequence_idx=idx
                )
                program_refs.append(program_ref)
                metadata_list.append(metadata)

            costs = _estimate_helios_costs_batch(
                qnx=qnx,
                programs=program_refs,
                n_shots=shot_values,
                project=self._project_ref,
            )

            backend_config = self._build_execution_backend_config(
                nqubits=max(m.nqubits for m in metadata_list),
            )

            execution_items = _execute_programs(
                qnx=qnx,
                programs=program_refs,
                n_shots=shot_values,
                backend_config=backend_config,
                timeout=self.config.timeout,
                allow_incomplete=self.config.allow_incomplete,
                language=None,
                platform=self.config.platform,
                job_name_prefix=self.config.job_name_prefix,
                project=self._project_ref,
                max_cost=[float(c) for c in costs],
            )

            if len(execution_items) != len(circuits):
                raise NexusBackendError(
                    f"Helios batch execute returned {len(execution_items)} items "
                    f"for {len(circuits)} circuits."
                )

            return [
                self._map_execution_result(
                    execution_result_ref=item,
                    circuit=circuit,
                    nshots=shots,
                    metadata=metadata,
                )
                for item, circuit, metadata, shots in zip(
                    execution_items, circuits, metadata_list, shot_values
                )
            ]

        if not self.config.batch_mode:
            if parameters_list is None:
                parameters_list = [None] * len(circuits)
            if len(parameters_list) != len(circuits):
                raise ValueError(
                    "parameters_list cardinality mismatch with circuits in execute_circuits."
                )
            if isinstance(nshots, Iterable) and not isinstance(nshots, (str, bytes)):
                shot_values = [int(v) for v in nshots]
                if len(shot_values) != len(circuits):
                    raise ValueError(
                        f"nshots cardinality mismatch: got {len(shot_values)} entries "
                        f"for {len(circuits)} circuits."
                    )
            else:
                shot_values = [int(nshots)] * len(circuits)
            return [
                self.execute_circuit(c, nshots=shots, parameters=params)
                for c, shots, params in zip(circuits, shot_values, parameters_list)
            ]

        if parameters_list is None:
            parameters_list = [None] * len(circuits)
        if len(parameters_list) != len(circuits):
            raise ValueError(
                "parameters_list cardinality mismatch with circuits in execute_circuits."
            )

        uploaded: list[Any] = []
        metadata_list: list[TranslationMetadata] = []
        for idx, (circuit, params) in enumerate(zip(circuits, parameters_list)):
            self._assert_supported_execution(circuit, None)
            circuit_ref, metadata = self._upload_translated_program(
                circuit,
                parameters=params,
                sequence_idx=idx,
            )
            uploaded.append(circuit_ref)
            metadata_list.append(metadata)

        batch_shots = _normalize_batch_nshots(nshots, len(circuits))
        execution_items = run_compile_execute(
            programs=uploaded,
            backend_config=self._backend_config,
            optimisation_level=self.config.optimisation_level,
            n_shots=batch_shots,
            timeout=self.config.timeout,
            allow_incomplete=self.config.allow_incomplete,
            language=self._resolved_language,
            platform=self.config.platform,
            job_name_prefix=self.config.job_name_prefix,
            project=self._project_ref,
        )

        if len(execution_items) != len(circuits):
            raise NexusBackendError(
                "Result cardinality mismatch after batch execution: "
                f"expected {len(circuits)}, got {len(execution_items)}"
            )

        if isinstance(batch_shots, int):
            shot_values = [batch_shots] * len(circuits)
        else:
            shot_values = batch_shots

        results: list[Any] = []
        for item, circuit, metadata, shots in zip(
            execution_items, circuits, metadata_list, shot_values
        ):
            results.append(
                self._map_execution_result(
                    execution_result_ref=item,
                    circuit=circuit,
                    nshots=shots,
                    metadata=metadata,
                )
            )
        return results

    def estimate_circuits(
        self,
        circuits: list[Circuit],
        nshots: int | list[int] = 1000,
        initial_states: Any = None,
        parameters_list: list[Any] | None = None,
    ) -> ExecutionEstimate:
        if initial_states is not None:
            raise UnsupportedExecutionError(
                "Nexus backend does not support initial_states for estimate_circuits."
            )

        if not circuits:
            return ExecutionEstimate(
                platform=self.config.platform,
                optimisation_level=self.config.optimisation_level,
                batch_mode=self.config.batch_mode,
                total_hqcs=0.0,
                items=[],
            )
        self._ensure_connected()
        qnx = _import_qnexus()

        if parameters_list is None:
            parameters_list = [None] * len(circuits)
        if len(parameters_list) != len(circuits):
            raise ValueError(
                "parameters_list cardinality mismatch with circuits in estimate_circuits."
            )

        if self.config.platform_family == "helios":
            shot_values = _normalize_batch_nshots(nshots, len(circuits))
            if isinstance(shot_values, int):
                shot_values = [shot_values] * len(circuits)

            program_refs: list[Any] = []
            for idx, (circuit, params) in enumerate(zip(circuits, parameters_list)):
                self._assert_supported_execution(circuit, None)
                program_ref, _ = self._upload_translated_program(
                    circuit,
                    parameters=params,
                    sequence_idx=idx,
                )
                program_refs.append(program_ref)

            hqcs_list = _estimate_helios_costs_batch(
                qnx=qnx,
                programs=program_refs,
                n_shots=shot_values,
                project=self._project_ref,
            )

            items: list[EstimateItem] = [
                EstimateItem(
                    sequence_idx=idx,
                    nshots=shots,
                    hqcs=hqcs,
                    compile_job_id=_job_id(program_ref),
                )
                for idx, (program_ref, shots, hqcs) in enumerate(
                    zip(program_refs, shot_values, hqcs_list)
                )
            ]
            return ExecutionEstimate(
                platform=self.config.platform,
                optimisation_level=self.config.optimisation_level,
                batch_mode=False,
                total_hqcs=sum(item.hqcs for item in items),
                items=items,
            )

        if not self.config.batch_mode:
            if isinstance(nshots, Iterable) and not isinstance(nshots, (str, bytes)):
                shot_values = [int(v) for v in nshots]
                if len(shot_values) != len(circuits):
                    raise ValueError(
                        f"nshots cardinality mismatch: got {len(shot_values)} entries "
                        f"for {len(circuits)} circuits."
                    )
            else:
                shot_values = [int(nshots)] * len(circuits)

            items: list[EstimateItem] = []
            for idx, (circuit, shots, params) in enumerate(zip(circuits, shot_values, parameters_list)):
                self._assert_supported_execution(circuit, None)
                circuit_ref, _ = self._upload_translated_program(
                    circuit,
                    parameters=params,
                    sequence_idx=idx,
                )
                prepared = _prepare_compiled_programs(
                    qnx=qnx,
                    programs=[circuit_ref],
                    backend_config=self._backend_config,
                    optimisation_level=self.config.optimisation_level,
                    n_shots=shots,
                    timeout=self.config.timeout,
                    platform=self.config.platform,
                    batch_mode=False,
                    job_name_prefix=self.config.job_name_prefix,
                    project=self._project_ref,
                )
                estimate = _estimate_prepared_compilation(
                    qnx=qnx,
                    prepared=prepared,
                    backend_config=self._backend_config,
                    project=self._project_ref,
                    platform=self.config.platform,
                    optimisation_level=self.config.optimisation_level,
                    timeout=self.config.timeout,
                    job_name_prefix=self.config.job_name_prefix,
                )
                items.append(replace(estimate.items[0], sequence_idx=idx))

            return ExecutionEstimate(
                platform=self.config.platform,
                optimisation_level=self.config.optimisation_level,
                batch_mode=False,
                total_hqcs=sum(item.hqcs for item in items),
                items=items,
            )

        uploaded: list[Any] = []
        for idx, (circuit, params) in enumerate(zip(circuits, parameters_list)):
            self._assert_supported_execution(circuit, None)
            circuit_ref, _ = self._upload_translated_program(
                circuit,
                parameters=params,
                sequence_idx=idx,
            )
            uploaded.append(circuit_ref)

        batch_shots = _normalize_batch_nshots(nshots, len(circuits))
        prepared = _prepare_compiled_programs(
            qnx=qnx,
            programs=uploaded,
            backend_config=self._backend_config,
            optimisation_level=self.config.optimisation_level,
            n_shots=batch_shots,
            timeout=self.config.timeout,
            platform=self.config.platform,
            batch_mode=True,
            job_name_prefix=self.config.job_name_prefix,
            project=self._project_ref,
        )
        return _estimate_prepared_compilation(
            qnx=qnx,
            prepared=prepared,
            backend_config=self._backend_config,
            project=self._project_ref,
            platform=self.config.platform,
            optimisation_level=self.config.optimisation_level,
            timeout=self.config.timeout,
            job_name_prefix=self.config.job_name_prefix,
        )

    def execute_circuit_repeated(self, circuit: Circuit, nshots: int, repetitions: int) -> Any:
        raise UnsupportedExecutionError(
            "execute_circuit_repeated is not supported for the remote Nexus backend."
        )

    def execute_distributed_circuit(self, circuit: Circuit, initial_state: Any = None) -> Any:
        raise UnsupportedExecutionError(
            "Distributed execution is not supported for the remote Nexus backend."
        )


__all__ = [
    "EstimateItem",
    "ExecutionEstimate",
    "NexusClientBackend",
    "run_compile_execute",
]
