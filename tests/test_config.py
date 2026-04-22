from __future__ import annotations

import types

import pytest

from qibo_cloud_backends.nexus_config import (
    NexusBackendConfig,
    _should_use_helios_emulator,
    build_nexus_backend_config,
    parse_platform,
)


def test_helios_emulator_detection_rejects_syntax_checker() -> None:
    assert _should_use_helios_emulator("Helios-1SC", None) is False


def test_helios_emulator_detection_accepts_emulator_suffix() -> None:
    assert _should_use_helios_emulator("Helios-1E", None) is True


def test_helios_emulator_detection_accepts_emulator_keyword() -> None:
    assert _should_use_helios_emulator("helios-emulator", None) is True


def test_helios_emulator_detection_hardware_returns_false() -> None:
    assert _should_use_helios_emulator("Helios-1", None) is False


def test_parse_platform_defaults_to_hseries_when_missing_family() -> None:
    assert parse_platform("H2-1LE") == ("hseries", "H2-1LE")


def test_parse_platform_accepts_aer_family() -> None:
    assert parse_platform("aer:aer_simulator") == ("aer", "aer_simulator")


def test_shot_only_includes_aer_family() -> None:
    cfg = NexusBackendConfig(platform="aer:aer_simulator")
    assert cfg.shot_only is True


def test_parse_platform_rejects_unknown_family() -> None:
    with pytest.raises(ValueError):
        parse_platform("foo:bar")


def test_build_hseries_config(monkeypatch: pytest.MonkeyPatch) -> None:
    class QuantinuumConfig:
        def __init__(self, *, device_name: str, **kwargs):
            self.device_name = device_name
            self.kwargs = kwargs

    fake_qnx = types.SimpleNamespace(QuantinuumConfig=QuantinuumConfig)
    monkeypatch.setitem(__import__("sys").modules, "qnexus", fake_qnx)

    cfg = NexusBackendConfig(platform="hseries:H2-1LE")
    concrete = build_nexus_backend_config(cfg)
    assert concrete.device_name == "H2-1LE"


def test_build_helios_emulator_config(monkeypatch: pytest.MonkeyPatch) -> None:
    class HeliosConfig:
        def __init__(self, *, hardware_name: str, **kwargs):
            self.kind = "hardware"
            self.hardware_name = hardware_name
            self.kwargs = kwargs

    class HeliosEmulatorConfig:
        def __init__(self, *, hardware_name: str, **kwargs):
            self.kind = "emulator"
            self.hardware_name = hardware_name
            self.kwargs = kwargs

    fake_qnx = types.SimpleNamespace(
        QuantinuumConfig=object,
        HeliosConfig=HeliosConfig,
        HeliosEmulatorConfig=HeliosEmulatorConfig,
    )
    monkeypatch.setitem(__import__("sys").modules, "qnexus", fake_qnx)

    cfg = NexusBackendConfig(platform="helios:Helios-1", backend_options={"emulator": True})
    concrete = build_nexus_backend_config(cfg)
    assert concrete.kind == "emulator"
    assert concrete.hardware_name == "Helios-1"


def test_build_helios_modern_config_uses_emulator_config_and_max_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HeliosEmulatorConfig:
        def __init__(self, *, n_qubits: int, simulator: str):
            self.n_qubits = n_qubits
            self.simulator = simulator

    class HeliosConfig:
        def __init__(self, *, system_name: str, emulator_config=None, max_cost=None):
            self.system_name = system_name
            self.emulator_config = emulator_config
            self.max_cost = max_cost

    fake_qnx = types.SimpleNamespace(
        QuantinuumConfig=object,
        HeliosConfig=HeliosConfig,
        HeliosEmulatorConfig=HeliosEmulatorConfig,
    )
    monkeypatch.setitem(__import__("sys").modules, "qnexus", fake_qnx)

    cfg = NexusBackendConfig(
        platform="helios:Helios-1E",
        backend_options={"simulator": "statevector", "emulator": True},
    )
    concrete = build_nexus_backend_config(cfg, n_qubits=12, max_cost=3.5)
    assert concrete.system_name == "Helios-1E"
    assert concrete.max_cost == 3.5
    assert concrete.emulator_config.n_qubits == 12
    assert concrete.emulator_config.simulator == "statevector"


def test_build_helios_emulator_config_ignores_helios_config_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """attempt_batching/max_batch_cost must go to HeliosConfig, not HeliosEmulatorConfig."""

    class HeliosEmulatorConfig:
        def __init__(self, *, n_qubits: int):
            self.n_qubits = n_qubits
            # does NOT accept attempt_batching or max_batch_cost

    class HeliosConfig:
        def __init__(self, *, system_name: str, emulator_config=None, attempt_batching=False, max_batch_cost=2000.0, **kwargs):
            self.system_name = system_name
            self.emulator_config = emulator_config
            self.attempt_batching = attempt_batching
            self.max_batch_cost = max_batch_cost

    fake_qnx = types.SimpleNamespace(
        QuantinuumConfig=object,
        HeliosConfig=HeliosConfig,
        HeliosEmulatorConfig=HeliosEmulatorConfig,
    )
    monkeypatch.setitem(__import__("sys").modules, "qnexus", fake_qnx)

    cfg = NexusBackendConfig(
        platform="helios:Helios-1E",
        backend_options={"emulator": True, "n_qubits": 8, "attempt_batching": True, "max_batch_cost": 99.0},
    )
    concrete = build_nexus_backend_config(cfg)
    assert concrete.attempt_batching is True
    assert concrete.max_batch_cost == 99.0
    assert concrete.emulator_config.n_qubits == 8


def test_build_aer_config(monkeypatch: pytest.MonkeyPatch) -> None:
    class AerConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_qnx = types.SimpleNamespace(
        AerConfig=AerConfig,
        QuantinuumConfig=object,
        HeliosConfig=object,
        HeliosEmulatorConfig=object,
    )
    monkeypatch.setitem(__import__("sys").modules, "qnexus", fake_qnx)

    cfg = NexusBackendConfig(
        platform="aer:aer_simulator",
        backend_options={"seed_simulator": 11, "method": "statevector"},
    )
    concrete = build_nexus_backend_config(cfg)
    assert concrete.kwargs["seed_simulator"] == 11
    assert concrete.kwargs["method"] == "statevector"
