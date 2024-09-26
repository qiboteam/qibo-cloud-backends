import importlib.metadata as im
import os
from typing import Union

from qibo.config import raise_error

from qibo_cloud_backends.braket_client import BraketClientBackend
from qibo_cloud_backends.qibo_client import QiboClientBackend
from qibo_cloud_backends.qiskit_client import QiskitClientBackend

__version__ = im.version(__package__)

QibocloudBackend = Union[QiboClientBackend, QiskitClientBackend, BraketClientBackend]

CLIENTS = ("qibo-client", "qiskit-client", "braket-client")
TOKENS = ("QIBO_CLIENT_TOKEN", "IBMQ_TOKEN", None)


class MetaBackend:
    """Meta-backend class which takes care of loading the qibo-cloud backends."""

    @staticmethod
    def load(
        client: str, token: str = None, platform: str = None, verbosity: bool = False
    ) -> QibocloudBackend:
        """Loads the backend.

        Args:
            client (str): Name of the cloud client to load, one in ("qibo-client", "qiskit-client", "braket-client").
            token (str): User token for the remote connection.
            platform (str): Name of the platform to connect to on the provider's servers, e.g. `ibm_osaka`.
            verbosity (bool): Enable verbose mode for the qibo-client. Default is False.
        Returns:
            qibo.backends.abstract.Backend: The loaded backend.
        """

        if client == "qibo-client":
            return QiboClientBackend(token, platform, verbosity)
        elif client == "qiskit-client":
            return QiskitClientBackend(token, platform)
        elif client == "braket-client":
            return BraketClientBackend()
        else:
            raise_error(
                ValueError,
                f"Unsupported service, please use one among {CLIENTS}.",
            )

    def list_available(self, tokens: dict = None) -> dict:
        """Lists all the available qibo cloud backends.

        Args:
            tokens (dict): Mapping between the services and their tokens, e.g.
                           {"qibo-client": "xxxxx", "qiskit-client": "xxxxx"}.
                           By default reads the variables ("QIBO_CLIENT_TOKEN", "IBMQ_TOKEN").
        Returns:
            dict: the qibo-cloud available backends.
        """
        if tokens is None:
            tokens = {}
        available_backends = {}
        for client, token in zip(CLIENTS, TOKENS):
            if client == "braket-client":
                try:
                    MetaBackend.load(client=client)
                    available = True
                except:
                    available = False
            else:
                try:
                    token = tokens.get(client, os.environ[token])
                    MetaBackend.load(client=client, token=token)
                    available = True
                except:  # pragma: no cover
                    available = False
            available_backends[client] = available
        return available_backends
