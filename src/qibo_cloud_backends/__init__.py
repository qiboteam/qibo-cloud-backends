import importlib.metadata as im
import os
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
            platform (str): Name of the backend to load, one in ("qibo-client", "qiskit-client").
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

    def list_available(self) -> dict:
        """Lists all the available qibocloud backends."""
        available_backends = {}
        for worker, token in zip(WORKERS, TOKENS):
            try:
                MetaBackend.load(worker=worker, token=os.environ[token])
                available = True
            except:
                available = False
            available_backends[worker] = available
        return available_backends
