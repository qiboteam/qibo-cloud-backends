import os
import sys

import numpy as np
import pytest
from qibo import Circuit, gates
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


@pytest.mark.parametrize("token", [None, QIBO_TK])
def test_qibo_client_backend(token):
    c = random_clifford(3, backend=NP_BACKEND)
    c.add(gates.M(0, 2))
    client = QiboClientBackend(token=token, provider="TII")
    local_res = NP_BACKEND.execute_circuit(c)
    remote_res = client.execute_circuit(c)
    NP_BACKEND.assert_allclose(
        local_res.probabilities(qubits=[0, 2]),
        remote_res.probabilities(qubits=[0, 2]),
        atol=1e-1,
    )


def test_qibo_client_backend_provider_error():
    with pytest.raises(RuntimeError):
        QiboClientBackend(provider="non-existing-provider")


@pytest.mark.parametrize(
    "backend,token",
    [
        ("qibo-client", QIBO_TK),
        ("qiskit-client", QISKIT_TK),
        ("non-existing-client", None),
    ],
)
def test_set_backend(backend, token):
    if backend == "non-existing-client":
        with pytest.raises(ValueError):
            set_backend("qibo-cloud-backends", worker=backend, token=token)
    else:
        set_backend("qibo-cloud-backends", worker=backend, token=token)
        assert isinstance(
            GlobalBackend(), MetaBackend.load(backend, token=token).__class__
        )
        assert GlobalBackend().name == backend


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


@pytest.mark.skipif(
    not (sys.platform == "linux" and sys.version_info[:2] == (3, 11)),
    reason="Multiple parallel jobs on IBMQ are not supported.",
)
@pytest.mark.parametrize("token", [None, QISKIT_TK])
def test_qiskit_client_backend(token):
    # ibm_osaka's native gates are: ECR, I, RZ, SX, X
    c = Circuit(3)
    c.add(gates.X(0))
    # c.add(gates.ECR(0,1)) # ECR not supported by (our) QASM apparently
    # c.add(gates.ECR(1,2))
    c.add(gates.SX(1))
    c.add(gates.RZ(2, theta=np.pi / 2))
    c.add(gates.M(0, 2))
    client = QiskitClientBackend(token=token, provider="ibm-q", platform="ibm_osaka")
    local_res = NP_BACKEND.execute_circuit(c)
    remote_res = client.execute_circuit(c)
    NP_BACKEND.assert_allclose(
        local_res.probabilities(qubits=[0, 2]), remote_res.probabilities(), atol=0.2
    )
