import importlib.metadata as im
import os
from typing import Union

from qibo.config import raise_error

from qibo_cloud_backends.qibo_client import QiboClientBackend
from qibo_cloud_backends.qiskit_client import QiskitClientBackend

__version__ = im.version(__package__)

QibocloudBackend = Union[QiboClientBackend, QiskitClientBackend]

SERVICES = ("qibo-client", "qiskit-client")
TOKENS = ("QIBO_CLIENT_TOKEN", "IBMQ_TOKEN")


class MetaBackend:
    """Meta-backend class which takes care of loading the qibo-cloud backends."""

    @staticmethod
    def load(service: str, token: str = None, platform: str = None) -> QibocloudBackend:
        """Loads the backend.

        Args:
            service (str): Name of the cloud service to load, one in ("qibo-client", "qiskit-client").
            token (str): User token for the remote connection.
            platform (str): Name of the platform to connect to on the provider's servers, e.g. `ibm_osaka`.
        Returns:
            qibo.backends.abstract.Backend: The loaded backend.
        """

        if service == "qibo-client":
            return QiboClientBackend(token, platform)
        elif service == "qiskit-client":
            return QiskitClientBackend(token, platform)
        else:
            raise_error(
                ValueError,
                f"Unsupported service, please use one among {SERVICES}.",
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
        for service, token in zip(SERVICES, TOKENS):
            try:
                token = tokens.get(service, os.environ[token])
                MetaBackend.load(service=service, token=token)
                available = True
            except:  # pragma: no cover
                available = False
            available_backends[service] = available
        return available_backends
