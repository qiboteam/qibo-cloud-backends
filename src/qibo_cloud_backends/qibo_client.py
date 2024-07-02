import os

import qibo_client
from qibo.backends import NumpyBackend
from qibo.config import raise_error


class QiboClientBackend(NumpyBackend):
    """Backend for the remote execution of Qibo circuits.

    Args:
        token (str): User authentication token. By default this is read from the 'QIBO_CLIENT_TOKEN' environment variable.
        provider (str): Name of the service provider. Defaults to `"TII"`.
        platform (str): Name of the platform. Defaults to `"sim"`.
    """

    def __init__(self, token=None, platform=None):
        super().__init__()
        if token is None:
            try:
                token = os.environ["QIBO_CLIENT_TOKEN"]
            except KeyError:  # pragma: no cover
                raise_error(
                    RuntimeError,
                    "No token provided. Please explicitely pass the token `token='your_token'` or set the environment vairable `QIBO_CLIENT_TOKEN='your_token'`.",
                )
        if platform is None:
            platform = "sim"
        self.platform = platform
        self.name = "qibo-client"
        self.client = qibo_client.Client(token)

    def execute_circuit(self, circuit, initial_state=None, nshots=1000):
        """Executes the passed circuit.

        Args:
            circuit (qibo.models.Circuit): The circuit to execute.
            initial_state (ndarray): The initial state of the circuit. Defaults to `|00...0>`.
            nshots (int): Total number of shots.

        Returns:
            (qibo.result) The qibo result object containing the outcome of the circuit execution.
        """
        if initial_state is not None:
            raise_error(
                NotImplementedError,
                "The use of an `initial_state` is not supported yet.",
            )
        return self.client.run_circuit(circuit, nshots=nshots, device=self.platform)
