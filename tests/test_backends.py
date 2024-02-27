from qibo import gates
from qibo.backends import NumpyBackend
from qibo.quantum_info import random_clifford

from qibo_cloud_backends import QiboClientBackend, QiskitClientBackend

NP_BACKEND = NumpyBackend()
QISKIT_TK = "qiskit token"
QIBO_TK = "qibo token"


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
    client = QiboClientBackend(token=QIBO_TK, platform="TII")
    local_res = NP_BACKEND.execute_circuit(c)
    remote_res = client.execute_circuit(c)
    NP_BACKEND.assert_allclose(
        local_res.probabilities(qubits=[0, 2]), remote_res.probabilities(), atol=1e-1
    )
