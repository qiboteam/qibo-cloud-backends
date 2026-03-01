"""Configuration models and Nexus backend-config construction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
        print('Warning: Platform string missing family prefix. Assuming "hseries".')
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
    return "emulator" in lowered or lowered.endswith("-1e") or lowered.endswith("-1sc")



def build_nexus_backend_config(cfg: NexusBackendConfig) -> Any:
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

    forced_emulator = options.pop("emulator", None)
    has_helios_api = hasattr(qnx, "HeliosConfig") and hasattr(qnx, "HeliosEmulatorConfig")

    if has_helios_api:
        if _should_use_helios_emulator(name, forced_emulator):
            return qnx.HeliosEmulatorConfig(hardware_name=name, **options)
        return qnx.HeliosConfig(hardware_name=name, **options)

    # No HeliosConfig: go through QuantinuumConfig.
    return qnx.QuantinuumConfig(device_name=name, **options)
