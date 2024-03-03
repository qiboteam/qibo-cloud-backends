import qibo_client
from qibo.backends import NumpyBackend
from qibo.config import raise_error

PROVIDERS_LIST = [
    "TII",
]


class QiboClientBackend(NumpyBackend):
    """Backend for the remote execution of Qibo circuits.

    Args:
        token (str): User authentication token.
        provider (str): Name of the service provider. Defaults to `"TII"`.
        platform (str): Name of the platform. Defaults to `"sim"`.
    """

    def __init__(self, token, provider=None, platform=None):
        super().__init__()
        if provider is None:
            provider = "TII"
        if platform is None:
            platform = "sim"
        self.platform = platform
        self.name = "qibo-cloud"
        self.device = provider
        if provider not in PROVIDERS_LIST:
            raise_error(
                RuntimeError,
                f"Unsupported provider {provider}, please pick one in {PROVIDERS_LIST}.",
            )
        self.client = getattr(qibo_client, provider)(token)

    def execute_circuit(self, circuit, nshots=1000):
        """Executes the passed circuit.

        Args:
            circuit (qibo.models.Circuit): The circuit to execute.
            nshots (int): Total number of shots.

        Returns:
            (qibo.result) The qibo result object containing the outcome of the circuit execution.
        """
        return self.client.run_circuit(circuit, nshots=nshots, device=self.platform)
