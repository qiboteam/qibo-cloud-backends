import os
from itertools import repeat

from qibo.backends import NumpyBackend
from qibo.config import raise_error
from qibo.result import MeasurementOutcomes, QuantumState
from qiskit import QuantumCircuit
from qiskit_ibm_provider import IBMProvider


class QiskitClientBackend(NumpyBackend):
    """Backend for the remote execution of Qiskit circuits on the IBM servers.

    Args:
        token (str): User authentication token. By default this is read from the 'IBMQ_TOKEN' environment variable.
        provider (str): Name of the IBM service provider. Defaults to `"ibm-q"`.
        platform (str): The IBM platform. Defaults to `"ibm_osaka"`.
    """

    def __init__(self, token=None, provider=None, platform=None):
        super().__init__()
        if token is None:
            try:
                token = os.environ["IBMQ_TOKEN"]
            except KeyError:  # pragma: no cover
                raise_error(
                    RuntimeError,
                    "No token provided. Please explicitely pass the token `token='your_token'` or set the environment vairable `IBMQ_TOKEN='your_token'`.",
                )
        if provider is None:
            provider = "ibm-q"
        if platform is None:
            platform = "ibm_osaka"
        self.platform = platform
        self.name = "qiskit-client"
        self.device = provider
        provider = IBMProvider(token)
        self.backend = provider.get_backend(platform)

    def execute_circuit(self, circuit, initial_state=None, nshots=1000, **kwargs):
        """Executes the passed circuit.

        Args:
            circuit (qibo.models.Circuit): The circuit to execute.
            initial_state (ndarray): The initial state of the circuit. Defaults to `|00...0>`.
            nshots (int): Total number of shots.
            kwargs (dict): Additional keyword arguments passed to the qiskit backends' `run()` method.
        Returns:
            (qibo.result.MeasurementOutcomes) The outcome of the circuit execution.
        """
        if initial_state is not None:
            raise_error(
                NotImplementedError,
                "The use of an `initial_state` is not supported yet.",
            )
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
        return MeasurementOutcomes(
            measurements, backend=self, samples=self.np.asarray(samples), nshots=nshots
        )
