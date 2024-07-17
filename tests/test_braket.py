import pytest
from braket.circuits import Circuit as BraketCircuit
from qibo import Circuit
from qibo import gates
import numpy as np
from qibo.quantum_info import random_clifford
from qibo_cloud_backends.braket_client import BraketClientBackend
from qibo_cloud_backends.braket_translation import to_braket
from qibo.backends import NumpyBackend

NP_BACKEND = NumpyBackend()


def test_aws_client_backend():
    circuit_qibo = random_clifford(3, backend=NP_BACKEND)
    circuit_qibo.add(gates.M(0))
    circuit_qibo.add(gates.M(1))
    circuit_qibo.add(gates.M(2))
    

    # Local simulator test, does not cost money
    client = BraketClientBackend()
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


@pytest.mark.parametrize(
    "gate, expected",
    [
        (gates.I(0), BraketCircuit().i(0)),
        (gates.H(0), BraketCircuit().h(0)),
        (gates.X(0), BraketCircuit().x(0)),
        (gates.Y(0), BraketCircuit().y(0)),
        (gates.Z(0), BraketCircuit().z(0)),
        (gates.S(0), BraketCircuit().s(0)),
        (gates.SDG(0), BraketCircuit().si(0)),
        (gates.T(0), BraketCircuit().t(0)),
        (gates.TDG(0), BraketCircuit().ti(0)),
        (gates.SX(0), BraketCircuit().v(0)),
        (gates.SXDG(0), BraketCircuit().vi(0)),
        (gates.CNOT(0, 1), BraketCircuit().cnot(0, 1)),
        (gates.CY(0, 1), BraketCircuit().cy(0, 1)),
        (gates.CZ(0, 1), BraketCircuit().cz(0, 1)),
        (gates.CSX(0, 1), BraketCircuit().cv(0, 1)),
        (gates.SWAP(0, 1), BraketCircuit().swap(0, 1)),
        (gates.iSWAP(0, 1), BraketCircuit().iswap(0, 1)),
        (gates.ECR(0, 1), BraketCircuit().ecr(0, 1)),
        (gates.TOFFOLI(0, 1, 2), BraketCircuit().ccnot(0, 1, 2)),
        (gates.RX(0, np.pi), BraketCircuit().rx(0, np.pi)),
        (gates.RY(0, np.pi), BraketCircuit().ry(0, np.pi)),
        (gates.RZ(0, np.pi), BraketCircuit().rz(0, np.pi)),
        (gates.RXX(0, 1, np.pi), BraketCircuit().xx(0, 1, np.pi)),
        (gates.RYY(0, 1, np.pi), BraketCircuit().yy(0, 1, np.pi)),
        (gates.RZZ(0, 1, np.pi), BraketCircuit().zz(0, 1, np.pi)),
        (gates.RXXYY(0, 1, np.pi), BraketCircuit().xy(0, 1, -np.pi)),
        (gates.GPI(0, np.pi), BraketCircuit().gpi(0, np.pi)),
        (gates.GPI2(0, np.pi), BraketCircuit().gpi2(0, np.pi)),
        (gates.PRX(0, np.pi, np.pi / 2), BraketCircuit().prx(0, np.pi, np.pi / 2)),
        (gates.MS(0, 1, np.pi, np.pi / 2, np.pi / 4), BraketCircuit().ms(0, 1, np.pi, np.pi / 2, np.pi / 4)),
        (gates.U3(0, np.pi, np.pi / 2, np.pi / 4), BraketCircuit().u(0, np.pi, np.pi / 2, np.pi / 4)),
    ]
)
def test_to_braket(gate, expected):
    circuit = Circuit(len(gate.qubits))
    circuit.add(gate)
    assert to_braket(circuit, False) == expected


def test_to_braket_verbatim():
    circuit = Circuit(1)
    circuit.add(gates.PRX(0, np.pi, np.pi / 2))
    assert to_braket(circuit, True) == BraketCircuit().add_verbatim_box(BraketCircuit().prx(0, np.pi, np.pi / 2))
