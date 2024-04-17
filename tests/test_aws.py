from qibo import Circuit
from qibo import gates
import numpy as np
from qibo.quantum_info import random_clifford
from qibo_cloud_backends import aws_client
from qibo.backends import NumpyBackend

NP_BACKEND = NumpyBackend()


def test_aws_client_backend():
    circuit_qibo = random_clifford(3, backend=NP_BACKEND)
    circuit_qibo.add(gates.M(0, 2))

    # Local simulator test, does not cost money
    client = aws_client.AWSClientBackend()
    # AWS device tests, cost money
    # AWS = aws_client.AWSClientBackend(device = AwsDevice("arn:aws:braket:eu-west-2::device/qpu/oqc/Lucy"))
    # AWS = aws_client.AWSClientBackend(device = AwsDevice("arn:aws:braket:::device/quantum-simulator/amazon/sv1"))

    local_res = NP_BACKEND.execute_circuit(circuit_qibo)
    remote_res = client.execute_circuit(circuit_qibo)

    NP_BACKEND.assert_allclose(
        local_res.probabilities(qubits=[0, 2]),
        remote_res.probabilities(qubits=[0, 2]),
        atol=1e-1,
    )
