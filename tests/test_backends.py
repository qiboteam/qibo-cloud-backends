import os

from qibo import gates
from qibo.backends import NumpyBackend
from qibo.quantum_info import random_clifford

from qibo_cloud_backends import QiboClientBackend, QiskitClientBackend

NP_BACKEND = NumpyBackend()
QISKIT_TK = os.environ.get("IBMQ_TOKEN")
QIBO_TK = os.environ.get("QIBO_CLIENT_TII_TOKEN")


# def test_qiskit_client_backend():
#     c = random_clifford(3, backend=NP_BACKEND)
#     c.add(gates.M(0, 2))
#     client = QiskitClientBackend(
#         token=QISKIT_TK, provider="ibm-q", platform="ibmq_qasm_simulator"
#     )
#     local_res = NP_BACKEND.execute_circuit(c)
#     remote_res = client.execute_circuit(c)
#     NP_BACKEND.assert_allclose(
#         local_res.probabilities(qubits=[0, 2]), remote_res.probabilities(), atol=1e-1
#     )


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

# def test_aws_client_backend():
#     circuit_qibo = random_clifford(3, backend=NP_BACKEND)
#     circuit_qibo.add(gates.M(0, 2))
# 
#     # Local simulator test, does not cost money
#     client = aws_client.BraketClientBackend()
#     # AWS device tests, cost money
#     # AWS = aws_client.BraketClientBackend(device = AwsDevice("arn:aws:braket:eu-west-2::device/qpu/oqc/Lucy"))
#     # AWS = aws_client.BraketClientBackend(device = AwsDevice("arn:aws:braket:::device/quantum-simulator/amazon/sv1"))
# 
#     local_res = NP_BACKEND.execute_circuit(circuit_qibo)
#     remote_res = client.execute_circuit(circuit_qibo)
# 
#     NP_BACKEND.assert_allclose(
#         local_res.probabilities(qubits=[0, 2]),
#         remote_res.probabilities(qubits=[0, 2]),
#         atol=1e-1,
#     )
