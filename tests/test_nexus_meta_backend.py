"""MetaBackend / set_backend integration tests for the Nexus client.

Kept separate from ``tests/test_backends.py`` so that the nexus tests can be
collected and run in environments that do not have the optional braket / ionq /
qiskit extras installed.
"""

from qibo.backends import get_backend, set_backend

import qibo_cloud_backends.nexus_client as nexus_mod
from qibo_cloud_backends import MetaBackend, NexusClientBackend


def test_meta_backend_load_nexus_client(monkeypatch):
    monkeypatch.setattr(nexus_mod, "_ensure_nexus_dependencies", lambda: None)
    backend = MetaBackend.load(client="nexus-client", platform="hseries:H2-1LE")
    assert isinstance(backend, NexusClientBackend)
    assert backend.name == "nexus-client"


def test_meta_backend_load_nexus_client_uses_default_platform(monkeypatch):
    """Omitting `platform=` must fall through to NexusClientBackend's default
    (`hseries:H2-1LE`) rather than passing platform=None and breaking parse_platform."""
    monkeypatch.setattr(nexus_mod, "_ensure_nexus_dependencies", lambda: None)
    backend = MetaBackend.load(client="nexus-client")
    assert isinstance(backend, NexusClientBackend)
    assert backend.config.platform == "hseries:H2-1LE"


def test_set_backend_nexus_client(monkeypatch):
    monkeypatch.setattr(nexus_mod, "_ensure_nexus_dependencies", lambda: None)
    set_backend("qibo-cloud-backends", client="nexus-client", platform="hseries:H2-1LE")
    assert isinstance(get_backend(), NexusClientBackend)
    assert get_backend().name == "nexus-client"
