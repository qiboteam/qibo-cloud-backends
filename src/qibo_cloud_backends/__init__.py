import importlib.metadata as im
from importlib import import_module
from typing import TYPE_CHECKING, Any

from qibo.config import raise_error

if TYPE_CHECKING:
    from qibo_cloud_backends.braket_client import BraketClientBackend
    from qibo_cloud_backends.ionq_client import IonQClientBackend
    from qibo_cloud_backends.nexus_client import NexusClientBackend
    from qibo_cloud_backends.qibo_client import QiboClientBackend
    from qibo_cloud_backends.qiskit_client import QiskitClientBackend

__version__ = im.version(__package__)

QibocloudBackend = Any

CLIENTS = (
    "ionq-client",
    "qibo-client",
    "qiskit-client",
    "braket-client",
    "nexus-client",
)
TOKENS = ("IONQ_TOKEN", "QIBO_CLIENT_TOKEN", "IBMQ_TOKEN", None, None)
_CLIENT_MODULES = {
    "braket-client": ("qibo_cloud_backends.braket_client", "BraketClientBackend"),
    "ionq-client": ("qibo_cloud_backends.ionq_client", "IonQClientBackend"),
    "nexus-client": ("qibo_cloud_backends.nexus_client", "NexusClientBackend"),
    "qibo-client": ("qibo_cloud_backends.qibo_client", "QiboClientBackend"),
    "qiskit-client": ("qibo_cloud_backends.qiskit_client", "QiskitClientBackend"),
}
_EXPORTED_CLASSES = {
    "BraketClientBackend": ("qibo_cloud_backends.braket_client", "BraketClientBackend"),
    "IonQClientBackend": ("qibo_cloud_backends.ionq_client", "IonQClientBackend"),
    "NexusClientBackend": ("qibo_cloud_backends.nexus_client", "NexusClientBackend"),
    "QiboClientBackend": ("qibo_cloud_backends.qibo_client", "QiboClientBackend"),
    "QiskitClientBackend": ("qibo_cloud_backends.qiskit_client", "QiskitClientBackend"),
}


def _load_client_class(client: str):
    module_name, class_name = _CLIENT_MODULES[client]
    module = import_module(module_name)
    return getattr(module, class_name)


def _client_available(client: str) -> bool:
    try:
        backend_class = _load_client_class(client)
        if client == "nexus-client":
            module = import_module("qibo_cloud_backends.nexus_client")
            getattr(module, "_ensure_nexus_dependencies")()
        else:
            _ = backend_class
        return True
    except Exception:
        return False


def __getattr__(name: str):
    if name in _EXPORTED_CLASSES:
        module_name, class_name = _EXPORTED_CLASSES[name]
        module = import_module(module_name)
        return getattr(module, class_name)
    raise AttributeError(f"module {__package__!r} has no attribute {name!r}")


__all__ = [
    "BraketClientBackend",
    "CLIENTS",
    "IonQClientBackend",
    "MetaBackend",
    "NexusClientBackend",
    "QiboClientBackend",
    "QibocloudBackend",
    "QiskitClientBackend",
    "TOKENS",
    "__version__",
]


class MetaBackend:
    """Meta-backend class which takes care of loading the qibo-cloud backends."""

    @staticmethod
    def load(
        client: str,
        token: str = None,
        platform: str = None,
        verbosity: bool = False,
        **kwargs,
    ) -> QibocloudBackend:
        """Loads the backend.

        Args:
            client (str): Name of the cloud client to load.
                Options are ``("ionq-client", "qibo-client", "qiskit-client", "braket-client", "nexus-client")``.
            token (str): User token for the remote connection.
            platform (str): Name of the platform to connect to on the provider's servers.
            verbosity (bool): Enable verbose mode for the qibo-client. Default is False.
        Returns:
            qibo.backends.abstract.Backend: The loaded backend.
        """

        if client == "qibo-client":
            backend_class = _load_client_class(client)
            return backend_class(
                token=token,
                platform=platform,
                verbosity=verbosity,
                **kwargs,
            )
        elif client == "ionq-client":
            backend_class = _load_client_class(client)
            return backend_class(token=token, platform=platform, **kwargs)
        elif client == "qiskit-client":
            backend_class = _load_client_class(client)
            return backend_class(token=token, platform=platform, **kwargs)
        elif client == "braket-client":
            backend_class = _load_client_class(client)
            return backend_class(verbosity=verbosity, token=token, **kwargs)
        elif client == "nexus-client":
            backend_class = _load_client_class(client)
            return backend_class(platform=platform, **kwargs)
        else:
            raise_error(
                ValueError,
                f"Unsupported service, please use one among {CLIENTS}.",
            )

    def list_available(self, tokens: dict = None) -> dict:
        """Lists all the available qibo cloud backends.

        Args:
            tokens (dict): Mapping between the services and their tokens, e.g.
                           {"qibo-client": "xxxxx", "qiskit-client": "xxxxx", "braket-client": "xxxxx"}.
                           By default reads the variables ("QIBO_CLIENT_TOKEN", "IBMQ_TOKEN", None).
        Returns:
            dict: the qibo-cloud available backends.
        """
        if tokens is None:
            tokens = {}
        available_backends = {}
        for client in CLIENTS:
            available_backends[client] = _client_available(client)
        return available_backends
