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

from qibo_cloud_backends import (
    BraketClientBackend,
    MetaBackend,
    QiboClientBackend,
    QiskitClientBackend,
)

NP_BACKEND = NumpyBackend()
QISKIT_TK = os.environ.get("IBMQ_TOKEN")
QIBO_TK = os.environ.get("QIBO_CLIENT_TOKEN")


def qibo_circuit(nqubits=3):
    c = random_clifford(nqubits, backend=NP_BACKEND)
    c.add(gates.M(0, 2))
    return c


def qiskit_circuit(nqubits=3, measurement=True):
    # ibm_kyiv's native gates are: ECR, I, RZ, SX, X
    c = Circuit(nqubits)
    c.add(gates.X(0))
    # c.add(gates.ECR(0,1)) # ECR not supported by (our) QASM apparently
    # c.add(gates.ECR(1,2))
    c.add(gates.SX(1))
    c.add(gates.RZ(2, theta=np.pi / 2))
    if measurement:
        c.add(gates.M(0, 2))
    return c


@pytest.mark.parametrize("token", [None, QIBO_TK])
def test_qibo_client_backend(token):
    c = qibo_circuit(nqubits=3)
    client = QiboClientBackend(token=token)
    local_res = NP_BACKEND.execute_circuit(c)
    remote_res = client.execute_circuit(c)
    NP_BACKEND.assert_allclose(
        local_res.probabilities(qubits=[0, 2]),
        remote_res.probabilities(qubits=[0, 2]),
        atol=1e-1,
    )


def test_qibo_client_backend_initial_state():
    nqubits = 3
    c = qibo_circuit(nqubits)
    client = QiboClientBackend(token=QIBO_TK)
    with pytest.raises(NotImplementedError):
        state = np.zeros(2**nqubits, dtype=complex)
        client.execute_circuit(c, state)


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
            set_backend("qibo-cloud-backends", client=backend, token=token)
    else:
        set_backend("qibo-cloud-backends", client=backend, token=token)
        assert isinstance(
            GlobalBackend(), MetaBackend.load(backend, token=token).__class__
        )
        assert GlobalBackend().name == backend


def test_list_available_backends():
    available_backends = {
        "numpy": True,
        "tensorflow": False,
        "pytorch": False,
        "qulacs": False,
        "qibo-cloud-backends": {
            "qibo-client": True,
            "qiskit-client": True,
            "braket-client": True,
        },
    }
    assert list_available_backends("qibo-cloud-backends") == available_backends


@pytest.mark.skipif(
    not (sys.platform == "linux" and sys.version_info[:2] == (3, 11)),
    reason="Multiple parallel jobs on IBMQ are not supported.",
)
@pytest.mark.parametrize("token", [None, QISKIT_TK])
def test_qiskit_client_backend(token):
    c = qiskit_circuit()
    client = QiskitClientBackend(token=token, platform="ibm_kyiv")
    local_res = NP_BACKEND.execute_circuit(c)
    remote_res = client.execute_circuit(c)
    NP_BACKEND.assert_allclose(
        local_res.probabilities(qubits=[0, 2]), remote_res.probabilities(), atol=0.2
    )


@pytest.mark.parametrize("measurement", [True, False])
def test_qiskit_client_backend_initial_state(measurement):
    nqubits = 3
    c = qiskit_circuit(nqubits, measurement=measurement)
    client = QiskitClientBackend(token=QISKIT_TK, platform="ibm_kyiv")
    if measurement:
        state = np.zeros(2**nqubits, dtype=complex)
        with pytest.raises(NotImplementedError):
            client.execute_circuit(c, state)
    else:
        with pytest.raises(RuntimeError):
            client.execute_circuit(c)


@pytest.mark.parametrize("verbatim", [True, False])
def test_braket_client_backend(verbatim):
    c = random_clifford(3, backend=NP_BACKEND)
    c.add(gates.M(0, 2))
    client = BraketClientBackend(verbatim_circuit=verbatim)
    local_res = NP_BACKEND.execute_circuit(c)
    remote_res = client.execute_circuit(c)
    NP_BACKEND.assert_allclose(
        local_res.probabilities(qubits=[0, 2]),
        remote_res.probabilities(qubits=[0, 2]),
        atol=1e-1,
    )
