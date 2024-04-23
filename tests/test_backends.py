import os

import pytest
from qibo import gates
from qibo.backends import (
    GlobalBackend,
    NumpyBackend,
    list_available_backends,
    set_backend,
)
from qibo.quantum_info import random_clifford

from qibo_cloud_backends import MetaBackend, QiboClientBackend, QiskitClientBackend

NP_BACKEND = NumpyBackend()
QISKIT_TK = os.environ.get("IBMQ_TOKEN")
QIBO_TK = os.environ.get("QIBO_CLIENT_TII_TOKEN")


def test_qiskit_client_backend():
    c = random_clifford(3, backend=NP_BACKEND)
    c.add(gates.M(0, 2))
    client = QiskitClientBackend(
        token=QISKIT_TK, provider="ibm-q", platform="ibmq_qasm_simulator"
    )
    local_res = NP_BACKEND.execute_circuit(c)
    remote_res = client.execute_circuit(c)
    NP_BACKEND.assert_allclose(
        local_res.probabilities(qubits=[0, 2]), remote_res.probabilities(), atol=1e-1
    )


def test_qibo_client_backend():
    c = random_clifford(3, backend=NP_BACKEND)
    c.add(gates.M(0, 2))
    client = QiboClientBackend(token=QIBO_TK, provider="TII")
    local_res = NP_BACKEND.execute_circuit(c)
    remote_res = client.execute_circuit(c)
    NP_BACKEND.assert_allclose(
        local_res.probabilities(qubits=[0, 2]),
        remote_res.probabilities(qubits=[0, 2]),
        atol=1e-1,
    )


@pytest.mark.parametrize(
    "backend,token", [("qibo-client", QIBO_TK), ("qiskit-client", QISKIT_TK)]
)
def test_set_backend(backend, token):
    set_backend("qibo-cloud-backends", worker=backend, token=token)
    assert isinstance(GlobalBackend(), MetaBackend.load(backend, token=token).__class__)


def test_list_available_backends():
    available_backends = {
        "numpy": True,
        "tensorflow": False,
        "pytorch": False,
        "qibojit": False,
        "qibolab": False,
        "qibo-cloud-backends": {"qibo-client": True, "qiskit-client": True},
        "qibotn": False,
    }
    assert list_available_backends() == available_backends
