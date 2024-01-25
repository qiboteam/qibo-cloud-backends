import random
from itertools import repeat

from qibo.backends import NumpyBackend
from qibo.result import MeasurementOutcomes
from qiskit import QuantumCircuit
from qiskit_ibm_provider import IBMProvider


class QiskitClientBackend(NumpyBackend):
    """Backend for the remote execution of Qiskit circuits on the IBM servers.

    Args:
        platform (str): The IBM platform.
        token (str): User authentication token.
        runcard (dict): A dictionary containing the settings for the execution:
        - backend (str): One of the backends supported by the platform.
    """

    def __init__(self, token, provider="ibm-q", platform="ibmq_qasm_simulator"):
        super().__init__()
        provider = IBMProvider(token)
        self.backend = provider.get_backend(platform)

    def execute_circuit(self, circuit, nshots=1000, **kwargs):
        measurements = circuit.measurements
        nqubits = circuit.nqubits
        circuit = QuantumCircuit.from_qasm_str(circuit.to_qasm())
        job = self.backend.run(circuit, shots=nshots, **kwargs)
        samples = []
        for state, count in job.result().get_counts().items():
            sample = [int(bit) for bit in reversed(state)]
            samples += list(repeat(sample, count))
        random.shuffle(samples)
        return MeasurementOutcomes(
            measurements, backend=self, samples=self.np.asarray(samples), nshots=nshots
        )
