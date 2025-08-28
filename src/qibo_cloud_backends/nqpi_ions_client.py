from qibo.backends import NumpyBackend
from qibo.config import raise_error


class NQPIIonsClientBackend(NumpyBackend):
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

        self.name = "nqpi-ions-client"
        self.verbosity = verbosity

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
        # TODO
        json = circuit.raw
        print(json)
        return 0
