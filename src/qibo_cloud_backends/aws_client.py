from qibo.backends import NumpyBackend
from qibo.config import raise_error
from qibo.result import MeasurementOutcomes, QuantumState

import re
import importlib.util
import sys

# Import Qiskit packages for transpiler
from qiskit import transpile
from qiskit import QuantumCircuit
from qiskit.transpiler import CouplingMap
from qiskit.circuit.random import random_circuit
from qiskit import qasm2

from braket.aws import AwsDevice, AwsQuantumTask
from braket.circuits import Gate, observables
from braket.circuits import Circuit as braket_Circuit
# from braket.device_schema import DeviceActionType
from braket.devices import Devices, LocalSimulator
# from braket.parametric import FreeParameter
# from braket.ir.openqasm import Program

class AWSClientBackend(NumpyBackend):
    """Backend for the remote execution of AWS circuits on the AWS backends.

    Args:
        device_arn (str | None): The ARN of the Braket device.
            If `None`, instantiates the `LocalSimulator("default")`.
    """

    def __init__(self, device=None):
        super().__init__()

        if device is None:
            self.device = LocalSimulator("default")
            # self.device = LocalSimulator("braket_dm")
        else:
            self.device = device
        self.name = "aws"

    def remove_qelib1_inc(self, qasm_string):
        # Remove the "include "qelib1.inc";\n" line
        modified_code = re.sub(r'include\s+"qelib1.inc";\n', '', qasm_string)
        return modified_code

    def qasm_convert_gates(self, qasm_code):
        # To replace the notation for certain gates in OpenQASM
        # To add more gates if necessary
        dict = {
            "id": "i",
            "cx": "cnot",
            "sx": "v",
            "sdg": "si",
            "tdg": "ti",
        }
        lines = qasm_code.split('\n')
        modified_code = ""
        for line in lines:
            for key in dict:
                if key in line:
                    line = line.replace(key, dict[key])
                    break
            modified_code += line + '\n'
        return modified_code

    def execute_circuit(self,
                        circuit,
                        initial_state=None,
                        nshots=1000,
                        transpilation=False,
                        custom_coupling_map=None,
                        native_gates=None,
                        optimization_level=1,
                        verbatim_circuit=False,
                        **kwargs):
        """Executes a Qibo circuit on an AWS Braket device. The device defaults to the LocalSimulator().
            This function allows manual transpilation to a set of specified gates using Qiskit's transpiler.
            The user can opt to execute a verbatim_circuit on the device by indicating `verbatim_circuit=True`.

        Args:
            circuit (qibo.models.Circuit): The circuit to execute.
            initial_state (ndarray): The initial state of the circuit. Defaults to `|00...0>`.
            nshots (int): Total number of shots.
            transpilation (bool): If `True`, use Qiskit's transpiler to map the input circuit to gates specified in `native_gates`,
                adhering to the qubit topology defined in `custom_coupling_map`. Defaults to `False`.
            custom_coupling_map (list, list): A list containing lists representing the connectivity of the qubits.
                e.g. custom_coupling_map. E.g. [[0, 1], [1, 2], [2, 3]]
            native_gates (list, str): A list of strings representing the native gates of the QPU.
                e.g. native_gates = ['ecr', 'i', 'rz', 'sx', 'x']
            optimization_level (int): Optimization level for Qiskit's transpiler. Range is from 0 to 3. Defaults to 1.
            verbatim_circuit (bool): If `True`, wrap the Braket circuit in a verbatim box to run it on the QPU without any transpilation.
                Defaults to `False`.
            # kwargs (dict): Additional keyword arguments passed to the AWS backends' `run()` method. At the moment, I dont know of any.

        returns:
            (qibo.measurement.MeasurementOutcomes) The outcome of the circuit execution.
        """


        if initial_state is not None:
            raise_error(
                NotImplementedError,
                "The use of an `initial_state` is not supported yet.",
            )
        if kwargs:
            raise_error(
                NotImplementedError,
                "The use of additional arguments to `run()` is not supported yet.",
            )

        measurements = circuit.measurements
        if not measurements:
            raise_error(RuntimeError, "No measurement found in the provided circuit.")
        nqubits = circuit.nqubits
        circuit_qasm = circuit.to_qasm()

        if transpilation:
            if custom_coupling_map is None:
                raise_error(ValueError, "Expected custom_coupling_map. E.g. custom_coupling_map = [[0, 1], [1, 2], [2, 3]]")
            if native_gates is None:
                raise_error(ValueError, "Expected native gates for transpilation. E.g. native_gates = ['ecr', 'i', 'rz', 'sx', 'x']")

            # Convert to Qiskit circuit for transpilation
            circuit_qiskit = QuantumCircuit.from_qasm_str(circuit_qasm)
            transpiled_circuit = transpile(circuit_qiskit,
                                           basis_gates = native_gates,
                                           optimization_level = 1,
                                           coupling_map = custom_coupling_map)
            circuit_qasm = qasm2.dumps(transpiled_circuit) # Convert back to qasm.

        circuit_qasm = self.remove_qelib1_inc(circuit_qasm)
        circuit_qasm = self.qasm_convert_gates(circuit_qasm)
        braket_circuit = braket_Circuit.from_ir(circuit_qasm)
        if verbatim_circuit:
            braket_circuit = braket_Circuit().add_verbatim_box(braket_circuit)
        result = self.device.run(braket_circuit, shots=nshots).result()
        samples = result.measurements
        return MeasurementOutcomes(
            measurements=measurements, backend=self, samples=samples, nshots=nshots
        )
