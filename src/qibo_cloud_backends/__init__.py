import importlib.metadata as im
import os
from typing import Union

from typing import Union

from qibo.config import raise_error

from qibo_cloud_backends.qibo_client import QiboClientBackend
from qibo_cloud_backends.qiskit_client import QiskitClientBackend

__version__ = im.version(__package__)

QibocloudBackend = Union[QiboClientBackend, QiskitClientBackend]

WORKERS = ("qibo-client", "qiskit-client")
TOKENS = ("QIBO_CLIENT_TII_TOKEN", "IBMQ_TOKEN")


class MetaBackend:
    """Meta-backend class which takes care of loading the qibojit backends."""

    @staticmethod
    def load(
        worker: str, token: str, provider: str = None, platform: str = None
    ) -> QibocloudBackend:
        """Loads the backend.

        Args:
            worker (str): Name of the backend to load, one in ("qibo-client", "qiskit-client").
            token (str): User token for the remote connection.
            provider (str): Name of the provider of the service, e.g. `ibm-q` for IBM.  
            platform (str): Name of the platform to connect to on the provider's servers, e.g. `ibmq_qasm_simulator` for IBM.
        Returns:
            qibo.backends.abstract.Backend: The loaded backend.
        """

        if worker == "qibo-client":
            return QiboClientBackend(token, provider, platform)
        elif worker == "qiskit-client":
            return QiskitClientBackend(token, provider, platform)
        else:
            raise_error(
                ValueError,
                f"Unsupported worker, please use one among {WORKERS}.",
            )

    def list_available(self, tokens: dict=None) -> dict:
        """Lists all the available qibocloud backends."""
        if tokens is None:
            tokens = {}
        available_backends = {}
        for worker, token in zip(WORKERS, TOKENS):
            try:
                token = tokens.get(worker, os.environ[f"{worker.replace('-', '_').upper()}_TOKEN"])
                MetaBackend.load(worker=worker, token=token)
                available = True
            except:
                available = False
            available_backends[worker] = available
        return available_backends
