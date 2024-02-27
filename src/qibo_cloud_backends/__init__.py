import importlib.metadata as im
import os

from qibo_cloud_backends.qibo_client import QiboClientBackend
from qibo_cloud_backends.qiskit_client import QiskitClientBackend

__version__ = im.version(__package__)

QibocloudBackend = QiboClientBackend | QiskitClientBackend

WORKERS = ("qibo-client", "qiskit")


class MetaBackend:
    """Meta-backend class which takes care of loading the qibojit backends."""

    @staticmethod
    def load(
        worker: str, token: str, provider: str = None, platform: str = None
    ) -> QibocloudBackend:
        """Loads the backend.

        Args:
            platform (str): Name of the backend to load: either `numba`, `cupy` or `cuquantum`.
        Returns:
            qibo.backends.abstract.Backend: The loaded backend.
        """

        if worker == "qibo-client":
            return QiboClientBackend(token, provider, platform)
        elif worker == "qiskit":
            return QiskitClientBackend(token, provider, platform)
        else:
            raise_error(
                ValueError,
                f"Unsupported worker, please use one among {WORKERS}.",
            )

    def list_available(self) -> dict:
        """Lists all the available qibocloud backends."""
        available_backends = {}
        for worker in WORKERS:
            try:
                MetaBackend.load(worker=worker, token=os.environ["QIBOCLOUD_TOKEN"])
                available = True
            except:
                available = False
            available_backends[worker] = available
        return available_backends
