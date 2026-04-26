"""Configuration models and Nexus backend-config construction."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
import inspect
from typing import Any

LOGGER = logging.getLogger(__name__)

_SUPPORTED_PLATFORM_FAMILIES = {"hseries", "helios", "aer"}


@dataclass
class NexusBackendConfig:
    """Runtime configuration for the Qibo <-> Nexus integration backend."""

    platform: str = "hseries:H2-1LE"
    project: str | None = None
    optimisation_level: int = 2
    timeout: float = 1800.0
    allow_incomplete: bool = False
    language: Any = None
    credential_login: bool | None = None
    batch_mode: bool = True
    reverse_endianness: bool = False
    backend_options: dict[str, Any] = field(default_factory=dict)
    job_name_prefix: str = "qibo-nexus"

    @property
    def platform_family(self) -> str:
        return parse_platform(self.platform)[0]

    @property
    def platform_name(self) -> str:
        return parse_platform(self.platform)[1]

    @property
    def shot_only(self) -> bool:
        return self.platform_family in {"hseries", "helios", "aer"}


def parse_platform(platform: str) -> tuple[str, str]:
    """Parse platform string in the form '<family>:<name>'."""

    if ":" not in platform:
        LOGGER.warning('Platform string missing family prefix. Assuming "hseries".')
        return "hseries", platform

    family, raw_name = platform.split(":", 1)
    family = family.strip().lower()
    name = raw_name.strip()
    if not family or not name:
        raise ValueError(f"Invalid platform '{platform}'. Expected '<family>:<name>'.")
    if family not in _SUPPORTED_PLATFORM_FAMILIES:
        expected = ", ".join(sorted(_SUPPORTED_PLATFORM_FAMILIES))
        raise ValueError(
            f"Unsupported platform family '{family}'. Expected one of: {expected}."
        )
    return family, name


def _should_use_helios_emulator(name: str, forced: Any) -> bool:
    if forced is not None:
        return bool(forced)
    lowered = name.lower()
    return "emulator" in lowered or lowered.endswith("-1e")


def _resolve_qnexus_model(qnx: Any, name: str) -> Any:
    model = getattr(qnx, name, None)
    if model is not None:
        return model
    models = getattr(qnx, "models", None)
    if models is None:
        return None
    return getattr(models, name, None)


def _call_named_constructor(model: Any, *, name: str, **kwargs: Any) -> Any:
    for field_name in ("system_name", "hardware_name", "device_name"):
        try:
            return model(**{field_name: name, **kwargs})
        except TypeError:
            continue
    return model(name=name, **kwargs)


def _supports_parameter(model: Any, parameter: str) -> bool:
    try:
        return parameter in inspect.signature(model).parameters
    except (TypeError, ValueError):
        return False


def _build_helios_backend_config(
    qnx: Any,
    *,
    name: str,
    options: dict[str, Any],
    n_qubits: int | None,
) -> Any:
    helios_config_cls = _resolve_qnexus_model(qnx, "HeliosConfig")
    helios_emulator_cls = _resolve_qnexus_model(qnx, "HeliosEmulatorConfig")
    if helios_config_cls is None:
        return qnx.QuantinuumConfig(device_name=name, **options)

    forced_emulator = options.pop("emulator", None)
    emulator_requested = _should_use_helios_emulator(name, forced_emulator)

    if emulator_requested and helios_emulator_cls is not None:
        emulator_options = dict(options)
        if n_qubits is not None:
            emulator_options.setdefault("n_qubits", int(n_qubits))

        if _supports_parameter(helios_config_cls, "emulator_config"):
            # Split options: keys accepted by HeliosEmulatorConfig go on the
            # emulator; any remaining user-supplied options (e.g. attempt_batching
            # for real Helios-1) belong on HeliosConfig.
            emulator_only = {
                k: v for k, v in emulator_options.items()
                if _supports_parameter(helios_emulator_cls, k)
            }
            helios_level = {
                k: v for k, v in emulator_options.items()
                if not _supports_parameter(helios_emulator_cls, k)
            }
            emulator_config = helios_emulator_cls(**emulator_only)
            return _call_named_constructor(
                helios_config_cls,
                name=name,
                emulator_config=emulator_config,
                **helios_level,
            )

        return _call_named_constructor(helios_emulator_cls, name=name, **emulator_options)

    return _call_named_constructor(helios_config_cls, name=name, **options)


def build_nexus_backend_config(
    cfg: NexusBackendConfig,
    *,
    n_qubits: int | None = None,
) -> Any:
    """Build a concrete qnexus backend config object for compile/execute jobs."""

    try:
        import qnexus as qnx
    except Exception as exc:  # pragma: no cover - import environment specific
        raise ImportError("qnexus is required to build Nexus backend configs.") from exc

    family, name = parse_platform(cfg.platform)
    options = dict(cfg.backend_options)

    if family == "aer":
        return qnx.AerConfig(**options)

    if family == "hseries":
        options.pop("emulator", None)
        return qnx.QuantinuumConfig(device_name=name, **options)

    return _build_helios_backend_config(
        qnx,
        name=name,
        options=options,
        n_qubits=n_qubits,
    )
