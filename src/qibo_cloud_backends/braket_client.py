import time

from braket.aws import AwsDevice
from braket.devices import LocalSimulator
from qibo import Circuit as QiboCircuit
from qibo.backends import NumpyBackend
from qibo.config import raise_error
from qibo.result import MeasurementOutcomes

from qibo_cloud_backends.braket_translation import to_braket


class BraketClientBackend(NumpyBackend):
    def __init__(
        self, device=None, verbatim_circuit=False, verbosity=False, token: str = None
    ):
        """Backend for the remote execution of AWS circuits on the AWS backends.

        Args:
            device (str): To specify a Braket device, input the ARN of the Braket device
                          (e.g., "arn:aws:braket:::device/quantum-simulator/amazon/sv1").
                          To specify a LocalSimulator, input "local_simulator:device_string", replacing "device_string" with
                          one of these: ['braket_ahs', 'braket_dm', 'braket_sv', 'default'].
                          (e.g., "local_simulator:braket_dm").
                          Note that LocalSimulator("braket_ahs") is not support at the moment.
                          If `None`, defaults to the statevector LocalSimulator("default").
                          For other Braket devices and their respective ARNs, refer to:
                          https://docs.aws.amazon.com/braket/latest/developerguide/braket-devices.html.
            verbatim_circuit (bool): If `True`, to_braket will wrap the Braket circuit in a verbatim box to run it on the QPU
                                     without any transpilation. Defaults to `False`.
            verbosity (bool): If `True`, the status of the executed task will be displayed. Defaults to `False`.
            token (str): This parameter is not required for executing circuits on Amazon Braket devices.
                         It is included for potential future compatibility but should be left as None.
        """

        super().__init__()

        self.verbatim_circuit = verbatim_circuit
        self.verbosity = verbosity

        if device is None:
            self.device = LocalSimulator("default")
        else:
            self.device = (
                AwsDevice(device)
                if device.split(":")[0] != "local_simulator"
                else LocalSimulator(device.split(":")[1])
            )
        self.name = "aws"

    def execute_circuit(self, circuit_qibo, nshots=1000, **kwargs):
        """Executes a Qibo circuit on an AWS Braket device. The device defaults to the LocalSimulator().

        Args:
            circuit (qibo.models.Circuit): circuit to execute on the Braket device.
            nshots (int): Total number of shots.
        Returns:
            Measurement outcomes (qibo.measurement.MeasurementOutcomes): The outcome of the circuit execution.
        """

        measurements = circuit_qibo.measurements
        if not measurements:
            raise_error(RuntimeError, "No measurement found in the provided circuit.")
        braket_circuit = to_braket(circuit_qibo, self.verbatim_circuit)

        task = self.device.run(braket_circuit, shots=nshots, **kwargs)

        while self.verbosity:
            status = task.state()
            print(f"> Status {status}", end=" ", flush=True)
            if status == "COMPLETED":
                print("\n")
                break
            for _ in range(3):
                time.sleep(1)
                print(".", end=" ", flush=True)
            print("\r" + " " * 30, end="\r")

        samples = task.result().measurements

        return MeasurementOutcomes(
            measurements=measurements, backend=self, samples=samples, nshots=nshots
        )
