import os

import qibo_client
from qibo.backends import NumpyBackend
from qibo.config import raise_error


class QiboClientBackend(NumpyBackend):
    """Backend for the remote execution of Qibo circuits.

    Args:
        token (str): User authentication token. By default this is read from the 'QIBO_CLIENT_TOKEN' environment variable.
        project (str): The project to be billed for the service. Defaults to the `personal` project.
        platform (str): Name of the platform. Defaults to `"sim"`.
        verbosity (str): Enable verbose mode for the client. Default is False.
    """

    def __init__(
        self,
        token: str = None,
        project: str = None,
        platform: str = None,
        verbosity: bool = False,
    ):
        super().__init__()
        if token is None:
            try:
                token = os.environ["QIBO_CLIENT_TOKEN"]
            except KeyError:  # pragma: no cover
                raise_error(
                    RuntimeError,
                    "No token provided. Please explicitely pass the token `token='your_token'` or set the environment variable `QIBO_CLIENT_TOKEN='your_token'`.",
                )
        self.project = project if project is not None else "personal"
        self.platform = platform if platform is not None else "k2"
        self.name = "qibo-client"
        self.verbosity = verbosity
        self.client = qibo_client.Client(token)

    def execute_circuit(self, circuit, initial_state=None, nshots=1000, verbatim=False):
        """Executes the passed circuit.

        Args:
            circuit (qibo.models.Circuit): The circuit to execute.
            initial_state (ndarray): The initial state of the circuit. Defaults to `|00...0>`.
            nshots (int): Total number of shots. Defaults to ``1000``.
            verbatim (bool): Whether to trigger the automatic transpilation (``verbatim=False``) or execute the circuit as is. Defaults to ``False``.

        Returns:
            (qibo.result) The qibo result object containing the outcome of the circuit execution.
        """
        if initial_state is not None:
            raise_error(
                NotImplementedError,
                "The use of an `initial_state` is not supported yet.",
            )
        job = self.client.run_circuit(
            circuit,
            nshots=nshots,
            device=self.platform,
            project=self.project,
            verbatim=verbatim,
        )
        return job.result(verbose=self.verbosity)
