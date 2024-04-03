from qibo import Circuit
from qibo import gates
import numpy as np
from qibo_cloud_backends import aws_client
from qibo.backends import NumpyBackend

NP_BACKEND = NumpyBackend()


def test_aws_client_backend():
    circuit_qibo = Circuit(1)
    circuit_qibo.add(gates.RX(0, np.pi / 7))
    circuit_qibo.add(gates.M(0))

    # Local simulator test, does not cost money
    client = aws_client.AWSClientBackend()
    # AWS device tests, cost money
    # AWS = aws_client.AWSClientBackend(device = AwsDevice("arn:aws:braket:eu-west-2::device/qpu/oqc/Lucy"))
    # AWS = aws_client.AWSClientBackend(device = AwsDevice("arn:aws:braket:::device/quantum-simulator/amazon/sv1"))

    local_res = NP_BACKEND.execute_circuit(circuit_qibo)
    remote_res = client.execute_aws_circuit(circuit_qibo, nshots=1000)

    NP_BACKEND.assert_allclose(
        local_res.probabilities(qubits=[0]),
        remote_res.probabilities(qubits=[0]),
        atol=1e-1,
    )