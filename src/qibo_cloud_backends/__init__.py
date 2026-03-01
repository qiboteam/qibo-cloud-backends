import importlib.metadata as im
import os
from typing import Union

from qibo.config import raise_error

from qibo_cloud_backends.braket_client import BraketClientBackend
from qibo_cloud_backends.ionq_client import IonQClientBackend
from qibo_cloud_backends.nexus_client import NexusClientBackend
from qibo_cloud_backends.qibo_client import QiboClientBackend
from qibo_cloud_backends.qiskit_client import QiskitClientBackend

__version__ = im.version(__package__)

QibocloudBackend = Union[
    BraketClientBackend,
    IonQClientBackend,
    NexusClientBackend,
    QiboClientBackend,
    QiskitClientBackend,
]

CLIENTS = (
    "ionq-client",
    "qibo-client",
    "qiskit-client",
    "braket-client",
    "nexus-client",
)
TOKENS = ("IONQ_TOKEN", "QIBO_CLIENT_TOKEN", "IBMQ_TOKEN", None, None)


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
            return QiboClientBackend(
                token=token,
                platform=platform,
                verbosity=verbosity,
                **kwargs,
            )
        elif client == "ionq-client":
            return IonQClientBackend(token=token, platform=platform, **kwargs)
        elif client == "qiskit-client":
            return QiskitClientBackend(token=token, platform=platform, **kwargs)
        elif client == "braket-client":
            return BraketClientBackend(verbosity=verbosity, token=token, **kwargs)
        elif client == "nexus-client":
            return NexusClientBackend(platform=platform, **kwargs)
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
        for client, token in zip(CLIENTS, TOKENS):
            kwargs = {}
            if token is not None:
                token = tokens.get(client, os.environ.get(token))
                kwargs.update({"token": token})
            try:
                MetaBackend.load(client=client, **kwargs)
                available = True
            except:
                available = False
            available_backends[client] = available
        return available_backends
