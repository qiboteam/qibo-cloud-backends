from qibo.backends import NumpyBackend
from qibo.config import raise_error
from qibo.result import MeasurementOutcomes, QuantumState

import re
import importlib.util
import sys

# # Import Qiskit packages for transpiler
# from qiskit import transpile
# from qiskit import QuantumCircuit
# from qiskit.transpiler import CouplingMap
# from qiskit.circuit.random import random_circuit
# from qiskit import qasm2

from qibo import Circuit as QiboCircuit

from braket.aws import AwsDevice, AwsQuantumTask
from braket.circuits import Gate, observables
from braket.circuits import Circuit as BraketCircuit
from braket.devices import Devices, LocalSimulator

_QASM_BRAKET_GATES = {
    "id": "i",
    "cx": "cnot",
    "sx": "v",
    "sxdg": "vi",
    "sdg": "si",
    "tdg": "ti",
}

class BraketClientBackend(NumpyBackend):
    """Backend for the remote execution of AWS circuits on the AWS backends.

    Args:
        device_arn (str | None): The ARN of the Braket device.
            If `None`, instantiates the `LocalSimulator("default")`.
    """

    def __init__(self, device=None, verbatim_circuit=False):
        """Initializes BraketBackend.

        Args:
            device (str): Default device is Braket's statevector LocalSimulator, LocalSimulator("default").
                Other devices are Braket's density matrix simulator, LocalSimulator("braket_dm"), or any other
                QPUs.
            verbatim_circuit (bool): If `True`, wrap the Braket circuit in a verbatim box to run it on the QPU
                without any transpilation. Defaults to `False`.
        """
        
        super().__init__()

        self.verbatim_circuit = verbatim_circuit
        
        if device is None:
            self.device = LocalSimulator("default")
            # self.device = LocalSimulator("braket_dm")
        else:
            self.device = device
        self.name = "aws"
    
    def remove_qelib1_inc(self, qasm_string):
        """To remove the 'includes qe1lib.inc' from the OpenQASM string.

        Args: 
            qasm_code (OpenQASM circuit, str): circuit given in the OpenQASM format.

        Returns:
            qasm_code (OpenQASM circuit, str): circuit given in the OpenQASM format.
        """
        
        # Remove the "include "qelib1.inc";\n" line
        modified_code = re.sub(r'include\s+"qelib1.inc";\n', '', qasm_string)
        return modified_code
    
    def qasm_convert_gates(self, qasm_code):
        """To replace the notation for certain gates in OpenQASM

        Args: 
            qasm_code (OpenQASM circuit, str): circuit given in the OpenQASM format.

        Returns:
            qasm_code (OpenQASM circuit, str): circuit given in the OpenQASM format.
        """
        
        lines = qasm_code.split('\n')
        modified_code = ""
        for line in lines:
            for key in _QASM_BRAKET_GATES:
                if key in line:
                    line = line.replace(key, _QASM_BRAKET_GATES[key])
                    break
            modified_code += line + '\n'
        return modified_code

    def execute_circuit(self,
                        circuit,
                        nshots=1000):
        """Executes a circuit (Qibo or Qibo-transpiled-to-Braket) on an AWS Braket device. The device defaults to the LocalSimulator().
           This function allows the user to opt for verbatim_circuit on the device by indicating `verbatim_circuit=True`.
            

        Args:
            circuit (quantum circuit): Either qibo.models.Circuit or braket.circuits.Circuit to execute on the Braket device.
            nshots (int): Total number of shots.
            verbatim_circuit (bool): If `True`, wrap the Braket circuit in a verbatim box to run it on the QPU without any transpilation.
                Defaults to `False`.

        Returns:
            Measurement outcomes (qibo.measurement.MeasurementOutcomes): The outcome of the circuit execution.
        """

        measurements = circuit.measurements
        if not measurements:
            raise_error(RuntimeError, "No measurement found in the provided circuit.")
        nqubits = circuit.nqubits
        circuit_qasm = circuit.to_qasm()
        circuit_qasm = self.remove_qelib1_inc(circuit_qasm)
        circuit_qasm = self.qasm_convert_gates(circuit_qasm)
        braket_circuit = BraketCircuit.from_ir(circuit_qasm)

        # Wrap verbatim box, execute:
        if self.verbatim_circuit:
            braket_circuit = BraketCircuit().add_verbatim_box(braket_circuit)
        result = self.device.run(braket_circuit, shots=nshots).result()
        samples = result.measurements
        return MeasurementOutcomes(
            measurements=measurements, backend=self, samples=samples, nshots=nshots
        )
