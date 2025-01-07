from functools import singledispatch

from braket.circuits import Circuit as BraketCircuit
from braket.circuits import Instruction
from braket.circuits import gates as braket_gates
from qibo import Circuit as QiboCircuit
from qibo import gates as qibo_gates


def to_braket(qibo_circuit: QiboCircuit, verbatim_circuit: bool) -> BraketCircuit:
    circuit = BraketCircuit()

    # Add gates
    for gate in qibo_circuit.queue:
        if isinstance(gate, qibo_gates.M):
            continue

        circuit.add_instruction(Instruction(_translate_op(gate), gate.qubits))

    # Add verbatim box
    if verbatim_circuit:
        circuit = BraketCircuit().add_verbatim_box(circuit)

    # Add measurements
    for register, qubits in qibo_circuit.measurement_tuples.items():
        circuit.measure(qubits)

    return circuit


@singledispatch
def _translate_op(g):
    raise NotImplementedError(f"Amazon Braket does not support gate {g}")


@_translate_op.register
def _(_: qibo_gates.I):
    return braket_gates.I()


@_translate_op.register
def _(_: qibo_gates.H):
    return braket_gates.H()


@_translate_op.register
def _(_: qibo_gates.X):
    return braket_gates.X()


@_translate_op.register
def _(_: qibo_gates.Y):
    return braket_gates.Y()


@_translate_op.register
def _(_: qibo_gates.Z):
    return braket_gates.Z()


@_translate_op.register
def _(_: qibo_gates.S):
    return braket_gates.S()


@_translate_op.register
def _(_: qibo_gates.SDG):
    return braket_gates.Si()


@_translate_op.register
def _(_: qibo_gates.T):
    return braket_gates.T()


@_translate_op.register
def _(_: qibo_gates.TDG):
    return braket_gates.Ti()


@_translate_op.register
def _(_: qibo_gates.SX):
    return braket_gates.V()


@_translate_op.register
def _(_: qibo_gates.SXDG):
    return braket_gates.Vi()


@_translate_op.register
def _(_: qibo_gates.CNOT):
    return braket_gates.CNot()


@_translate_op.register
def _(_: qibo_gates.CY):
    return braket_gates.CY()


@_translate_op.register
def _(_: qibo_gates.CZ):
    return braket_gates.CZ()


@_translate_op.register
def _(_: qibo_gates.CSX):
    return braket_gates.CV()


@_translate_op.register
def _(_: qibo_gates.SWAP):
    return braket_gates.Swap()


@_translate_op.register
def _(_: qibo_gates.iSWAP):
    return braket_gates.ISwap()


@_translate_op.register
def _(_: qibo_gates.ECR):
    return braket_gates.ECR()


@_translate_op.register
def _(_: qibo_gates.TOFFOLI):
    return braket_gates.CCNot()


@_translate_op.register
def _(g: qibo_gates.RX):
    return braket_gates.Rx(g.parameters[0])


@_translate_op.register
def _(g: qibo_gates.RY):
    return braket_gates.Ry(g.parameters[0])


@_translate_op.register
def _(g: qibo_gates.RZ):
    return braket_gates.Rz(g.parameters[0])


@_translate_op.register
def _(g: qibo_gates.RXX):
    return braket_gates.XX(g.parameters[0])


@_translate_op.register
def _(g: qibo_gates.RYY):
    return braket_gates.YY(g.parameters[0])


@_translate_op.register
def _(g: qibo_gates.RZZ):
    return braket_gates.ZZ(g.parameters[0])


@_translate_op.register
def _(g: qibo_gates.RXXYY):
    return braket_gates.XY(-g.parameters[0])


@_translate_op.register
def _(g: qibo_gates.GPI):
    return braket_gates.GPi(g.parameters[0])


@_translate_op.register
def _(g: qibo_gates.GPI2):
    return braket_gates.GPi2(g.parameters[0])


@_translate_op.register
def _(g: qibo_gates.PRX):
    parameters = g.parameters
    return braket_gates.PRx(parameters[0], parameters[1])


@_translate_op.register
def _(g: qibo_gates.MS):
    parameters = g.parameters
    return braket_gates.MS(parameters[0], parameters[1], parameters[2])


@_translate_op.register
def _(g: qibo_gates.U3):
    parameters = g.parameters
    return braket_gates.U(parameters[0], parameters[1], parameters[2])


@_translate_op.register
def _(g: qibo_gates.Unitary):
    return braket_gates.Unitary(g.matrix())
