import qibo_client
from qibo.backends import NumpyBackend
from qibo.config import raise_error

PROVIDERS_LIST = [
    "TII",
]


class QiboClientBackend(NumpyBackend):
    """Backend for the remote execution of Qibo circuits.

    Args:
        provider (str): Name of the service provider.
        token (str): User authentication token.
        platform (str): Name of the platform.
    """

    def __init__(self, token, provider=None, platform=None):
        super().__init__()
        if provider is None:
            provider = "TII"
        if platform is None:
            platform = "sim"
        self.platform = platform
        if provider not in PROVIDERS_LIST:
            raise_error(
                RuntimeError,
                f"Unsupported provider {provider}, please pick one in {PROVIDERS_LIST}.",
            )
        self.client = getattr(qibo_client, provider)(token)

    def execute_circuit(self, circuit, initial_state=None, nshots=1000):
        return self.client.run_circuit(
            circuit, initial_state=initial_state, nshots=nshots, device=self.platform
        )
