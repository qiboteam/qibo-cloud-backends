import os
from itertools import repeat

from qibo.backends import NumpyBackend
from qibo.config import raise_error
from qibo.result import MeasurementOutcomes
from qiskit import QuantumCircuit
from qiskit_ionq import IonQProvider  # type: ignore


class IonQClientBackend(NumpyBackend):
    """Backend for the remote execution of Qibo circuits on the IonQ Cloud servers.

    Args:
        token (str, optional): User authentication token. By default this is read from the 'IONQ_TOKEN' environment variable.
        platform (str, optional ): The IBM platform. Defaults to `"ionq_simulator"`.
    """

    def __init__(self, token=None, platform=None, **kwargs):
        super().__init__()
        if token is None:
            try:
                token = os.environ["IONQ_TOKEN"]
            except KeyError:  # pragma: no cover
                raise_error(
                    RuntimeError,
                    "No token provided. Please explicitely pass the token `token='your_token'` or set the environment variable `IONQ_TOKEN='your_token'`.",
                )
        if platform is None:
            platform = "ionq_simulator"
        self.name = "ionq-client"
        provider = IonQProvider(token)
        self.backend = provider.get_backend(platform)

        # For the classical simulator, options like noise model can be set
        self.backend.set_options(**kwargs)

    def execute_circuit(self, circuit, initial_state=None, nshots=1000, **kwargs):
        """Executes the passed circuit.

        Args:
            circuit (:class:`qibo.models.Circuit`): Circuit to be executed.
            initial_state (ndarray, optional): Initial state of the circuit. Defaults to `|00...0>`.
            nshots (int, optional): Total number of shots. Defaults to :math:`1000`.
            kwargs (dict, optional): Additional keyword arguments passed to the IonQ backends' `run()` method.

        Returns:
            :class:`qibo.result.MeasurementOutcomes`: Outcome of the circuit execution.
        """
        if initial_state is not None:
            raise_error(
                NotImplementedError,
                "The use of an `initial_state` is not supported yet.",
            )
        measurements = circuit.measurements
        if not measurements:
            raise_error(RuntimeError, "No measurement found in the provided circuit.")
        circuit = QuantumCircuit.from_qasm_str(circuit.to_qasm())
        result = self.backend.run(circuit, shots=nshots, **kwargs).result()
        samples = []
        for state, count in result.get_counts().items():
            sample = [int(bit) for bit in state[::-1].split()]
            samples += list(repeat(sample, count))
        return MeasurementOutcomes(
            measurements, backend=self, samples=self.np.asarray(samples), nshots=nshots
        )
