import random
from itertools import repeat

from qibo.backends import NumpyBackend
from qibo.config import raise_error
from qibo.result import MeasurementOutcomes, QuantumState
from qiskit import QuantumCircuit
from qiskit_ibm_provider import IBMProvider


class QiskitClientBackend(NumpyBackend):
    """Backend for the remote execution of Qiskit circuits on the IBM servers.

    Args:
        token (str): User authentication token.
        provider (str): Name of the IBM service provider.
        platform (str): The IBM platform.
    """

    def __init__(self, token, provider=None, platform=None):
        super().__init__()
        if not provider:
            provider = "ibm-q"
        if not platform:
            platform = "ibmq_qasm_simulator"
        provider = IBMProvider(token)
        self.backend = provider.get_backend(platform)

    def execute_circuit(self, circuit, initial_state=None, nshots=1000, **kwargs):
        measurements = circuit.measurements
        if not measurements:
            raise_error(RuntimeError, "No measurement found in the provided circuit.")
        nqubits = circuit.nqubits
        circuit = QuantumCircuit.from_qasm_str(circuit.to_qasm())
        result = self.backend.run(circuit, shots=nshots, **kwargs).result()
        samples = []
        for state, count in result.get_counts().items():
            sample = [int(bit) for bit in reversed(state)]
            samples += list(repeat(sample, count))
        random.shuffle(samples)
        return MeasurementOutcomes(
            measurements, backend=self, samples=self.np.asarray(samples), nshots=nshots
        )
