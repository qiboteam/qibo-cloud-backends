import importlib.metadata as im

from qibo_cloud_backends.qibo_client import QiboClientBackend
from qibo_cloud_backends.qiskit_client import QiskitClientBackend
from qibo_cloud_backends.aws_client import BraketClientBackend

__version__ = im.version(__package__)
