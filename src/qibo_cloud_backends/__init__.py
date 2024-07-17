import importlib.metadata as im
import os
from typing import Union

from qibo.config import raise_error

from qibo_cloud_backends.qibo_client import QiboClientBackend
from qibo_cloud_backends.qiskit_client import QiskitClientBackend
from qibo_cloud_backends.braket_client import BraketClientBackend

__version__ = im.version(__package__)

QibocloudBackend = Union[QiboClientBackend, QiskitClientBackend, BraketClientBackend]

CLIENTS = ("qibo-client", "qiskit-client")
TOKENS = ("QIBO_CLIENT_TOKEN", "IBMQ_TOKEN")


class MetaBackend:
    """Meta-backend class which takes care of loading the qibo-cloud backends."""

    @staticmethod
    def load(client: str, token: str = None, platform: str = None) -> QibocloudBackend:
        """Loads the backend.

        Args:
            client (str): Name of the cloud client to load, one in ("qibo-client", "qiskit-client").
            token (str): User token for the remote connection.
            platform (str): Name of the platform to connect to on the provider's servers, e.g. `ibm_osaka`.
        Returns:
            qibo.backends.abstract.Backend: The loaded backend.
        """

        if client == "qibo-client":
            return QiboClientBackend(token, platform)
        elif client == "qiskit-client":
            return QiskitClientBackend(token, platform)
        elif client == "aws-client":
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
            try:
                token = tokens.get(client, os.environ[token])
                MetaBackend.load(client=client, token=token)
                available = True
            except:  # pragma: no cover
                available = False
            available_backends[client] = available
        return available_backends



# import importlib.metadata as im

# from qibo_cloud_backends.qibo_client import QiboClientBackend
# from qibo_cloud_backends.qiskit_client import QiskitClientBackend
# from qibo_cloud_backends.aws_client import BraketClientBackend

# __version__ = im.version(__package__)
