from qibo.backends import NumpyBackend
from qibo.config import raise_error
from qibo.result import MeasurementOutcomes, QuantumState

import re
import importlib.util
import sys

# names of aws module requirements, dict for whether module is importable
names = {'braket': False}
AWS_REQUIREMENTS = False

error_messages = []

# iter through names, check if module is importable
for name, value in names.items():
    if name in sys.modules:
        names[name] = True
    elif (spec := importlib.util.find_spec(name)) is not None:
        names[name] = True
    else:
        names[name] = False

# if any module is not importable, print missing modules, else imports requriements
if any(value == False for name, value in names.items()):
    error_messages.append('The following modules are missing:')
    for name, value in names.items():
        if value == False:
            error_messages.append(f'    {name}')
    error_messages.append('Please install the modules from the aws-requirements.txt file.')
    error_message = '\n'.join(error_messages)
    print(f'The required module is not installed\n\n{error_message}')
else:
    from braket.aws import AwsDevice, AwsQuantumTask
    from braket.circuits import Circuit, Gate, observables
    from braket.circuits import Circuit
    # from braket.device_schema import DeviceActionType
    from braket.devices import Devices, LocalSimulator
    # from braket.parametric import FreeParameter
    from braket.ir.openqasm import Program
    AWS_REQUIREMENTS = True
    print('Modules are imported.')

if AWS_REQUIREMENTS:
    class AWSClientBackend(NumpyBackend):
        """Backend for the remote execution of AWS circuits on the AWS backends.

        Args:
            device (str): The AWS platform. Defaults to `"LocalSimulator()"`.
        """

        def __init__(self, device=None):
            super().__init__()

            if device is None:
                self.device = LocalSimulator()
            # self.device = device
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

        def insert_verbatim_box(self, qasm_code):
            lines = qasm_code.split('\n')
            modified_code = ""
        
            register_index = -1
            measure_index = -1
            
            # This loop is to find the line indices to start and close the verbatim box.
            for i, line in enumerate(lines):
                if "creg register" in line:
                    register_index = i
                if "measure" in line and measure_index == -1:
                    measure_index = i
        
            # Use previously found indices to start and close the verbatim box.
            for i, line in enumerate(lines):
                if i == register_index:
                    modified_code += line + "\n#pragma braket verbatim\nbox{\n"
                elif i == measure_index:
                    modified_code += "}\n" + line + "\n"
                else:
                    modified_code += line + '\n'
        
            return modified_code
            
        def execute_aws_circuit(self, circuit, initial_state=None, nshots=1000, verbatim_circuit=False, **kwargs):
            """Executes the passed circuit.

            Args:
                circuit (qibo.models.Circuit): The circuit to execute.
                initial_state (ndarray): The initial state of the circuit. Defaults to `|00...0>`.
                nshots (int): Total number of shots.
                kwargs (dict): Additional keyword arguments passed to the AWS backends' `run()` method. At the moment, I dont know of any.
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
            qasm_program = self.remove_qelib1_inc(circuit_qasm)
            qasm_program = self.qasm_convert_gates(qasm_program)
            if verbatim_circuit is True:
                qasm_program = self.insert_verbatim_box(qasm_program)
            qasm_program = Program(source = qasm_program)
            result = self.device.run(qasm_program, shots=nshots).result()
            samples = result.measurements
            return MeasurementOutcomes(
                measurements=measurements, backend=self, samples=samples, nshots=nshots
            )

else:
    class AWSClientBackend():
        """
        Dummy class to disable AWS backend if requirements are not installed.
        """
        def __init__(self):
            raise ImportError(f'The required module is not installed\n\n{error_message}')

if __name__ == '__main__':
    test = AWSClientBackend()
