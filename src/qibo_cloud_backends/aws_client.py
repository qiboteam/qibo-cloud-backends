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

from qibo import Circuit as QiboCircuit

from braket.aws import AwsDevice, AwsQuantumTask
from braket.circuits import Gate, observables
from braket.circuits import Circuit as BraketCircuit
from braket.devices import Devices, LocalSimulator
# from braket.device_schema import DeviceActionType
# from braket.parametric import FreeParameter
# from braket.ir.openqasm import Program

_QASM_BRAKET_GATES = {
    "id": "i",
    "cx": "cnot",
    "sx": "v",
    "sxdg": "vi",
    "sdg": "si",
    "tdg": "ti",
}

class BraketBackend(NumpyBackend):
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

    def get_circuit_type(self, circuit):
        """Returns circuit type: Qibo, Qiskit, or Braket.

        Args:
            circuit (quantum circuit)
        Returns:
            circuit_type (str)
        
        """
        if isinstance(circuit, QiboCircuit):
            return "Qibo"
        elif isinstance(circuit, QuantumCircuit):
            return "Qiskit"
        elif isinstance(circuit, BraketCircuit):
            return "Braket"
        else:
            return "Unknown"
    
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
    
    def transpile_qasm_circuit(self, circuit_qasm, native_gates, custom_coupling_map, optimization_level=1):
        """Transpiles a circuit given in OpenQASM format using Qiskit's transpiler.
            Returns a circuit given in OpenQASM format.

        Args:
            circuit_qasm (OpenQASM circuit, str): circuit given in the OpenQASM format.
            native_gates (list, str): A list of strings representing the native gates of the QPU.
                e.g. native_gates = ['ecr', 'i', 'rz', 'sx', 'x']
            custom_coupling_map (list, list): A list containing lists representing the connectivity of the qubits.
                e.g. custom_coupling_map. E.g. [[0, 1], [1, 2], [2, 3]]
            optimization_level (int): Optimization level for Qiskit's transpiler. Range is from 0 to 3. Defaults to 1.

        Returns:
            transpiled_circuit_qasm (OpenQASM circuit, str): Transpiled circuit in the OpenQASM format.
        """

        self.native_gates = native_gates
        self.custom_coupling_map = custom_coupling_map

        if optimization_level < 0 or optimization_level > 3:
            raise_error(ValueError, "Optimization_level is between 0 to 3.")
        if custom_coupling_map is None:
            raise_error(ValueError, "Expected custom_coupling_map. E.g. custom_coupling_map = [[0, 1], [1, 2], [2, 3]]")
        if native_gates is None:
            raise_error(ValueError, "Expected native gates for transpilation. E.g. native_gates = ['ecr', 'i', 'rz', 'sx', 'x']")

        # Convert to Qiskit circuit for transpilation
        circuit_qiskit = QuantumCircuit.from_qasm_str(circuit_qasm)
        transpiled_circuit = transpile(circuit_qiskit,
                                       basis_gates = self.native_gates,
                                       optimization_level = self.optimization_level,
                                       coupling_map = self.custom_coupling_map)
        transpiled_circuit_qasm = qasm2.dumps(transpiled_circuit) # Convert back to qasm.
        return transpiled_circuit_qasm
    
    def transpile_qibo_to_braket(self, circuit_qibo, native_gates, custom_coupling_map, optimization_level=1):
        """Transpiles a Qibo circuit using Qiskit's transpiler. Returns a Braket circuit.
    
        Args:
            circuit_qibo (qibo.models.Circuit): Qibo circuit to transpile.
            native_gates (list, str): A list of strings representing the native gates of the QPU.
                e.g. native_gates = ['ecr', 'i', 'rz', 'sx', 'x']
            custom_coupling_map (list, list): A list containing lists representing the connectivity of the qubits.
                e.g. custom_coupling_map. E.g. [[0, 1], [1, 2], [2, 3]]
            optimization_level (int): Optimization level for Qiskit's transpiler. Range is from 0 to 3. Defaults to 1.
    
        Returns:
            transpiled_circuit_braket (braket.circuits.Circuit): Braket circuit to that has been transpiled.
        """
            
        self.native_gates = native_gates
        self.custom_coupling_map = custom_coupling_map
        if optimization_level < 0 or optimization_level > 3:
            raise_error(ValueError, "Optimization_level is between 0 to 3.")
        else:
            self.optimization_level = optimization_level
        if custom_coupling_map is None:
            raise_error(ValueError, "Expected custom_coupling_map. E.g. custom_coupling_map = [[0, 1], [1, 2], [2, 3]]")
        if native_gates is None:
            raise_error(ValueError, "Expected native gates for transpilation. E.g. native_gates = ['ecr', 'i', 'rz', 'sx', 'x']")

        circuit_qasm = circuit_qibo.to_qasm()
        circuit_qiskit = QuantumCircuit.from_qasm_str(circuit_qasm)
        transpiled_circuit = transpile(circuit_qiskit,
                                       basis_gates = self.native_gates,
                                       optimization_level = self.optimization_level,
                                       coupling_map = self.custom_coupling_map)
        transpiled_circuit_qasm = qasm2.dumps(transpiled_circuit) # Convert back to qasm.
        transpiled_circuit_qasm = self.remove_qelib1_inc(transpiled_circuit_qasm)
        transpiled_circuit_qasm = self.qasm_convert_gates(transpiled_circuit_qasm)
        braket_circuit = BraketCircuit.from_ir(transpiled_circuit_qasm)
        return braket_circuit

    def execute_circuit(self,
                        circuit,
                        nshots=1000,
                        verbatim_circuit=False,
                        **kwargs):
        """Executes a circuit (Qibo or Qibo-transpiled-to-Braket) on an AWS Braket device. The device defaults to the LocalSimulator().
           This function allows the user to opt for verbatim_circuit on the device by indicating `verbatim_circuit=True`.
            

        Args:
            circuit (quantum circuit): Either qibo.models.Circuit or braket.circuits.Circuit to execute on the Braket device.
            nshots (int): Total number of shots.
            verbatim_circuit (bool): If `True`, wrap the Braket circuit in a verbatim box to run it on the QPU without any transpilation.
                Defaults to `False`.
            # kwargs (dict): Additional keyword arguments passed to the AWS backends' `run()` method. At the moment, I dont know of any.

        Returns:
            Measurement outcomes (qibo.measurement.MeasurementOutcomes): The outcome of the circuit execution.
        """
        
        if kwargs:
            raise_error(
                NotImplementedError,
                "The use of additional arguments to `run()` is not supported yet.",
            )

        circuit_type = self.get_circuit_type(circuit)

        if circuit_type == "Qibo":
            # If Qibo circuit, run these to convert to Braket circuit.
            measurements = circuit.measurements
            if not measurements:
                raise_error(RuntimeError, "No measurement found in the provided circuit.")
            nqubits = circuit.nqubits
            circuit_qasm = circuit.to_qasm()
            circuit_qasm = self.remove_qelib1_inc(circuit_qasm)
            circuit_qasm = self.qasm_convert_gates(circuit_qasm)
            braket_circuit = BraketCircuit.from_ir(circuit_qasm)

        elif circuit_type == "Braket":
            # Create measurements = qibo.circuit.measurements
            qibo_circuit = QiboCircuit(len(circuit.qubits))
            for i in range(0,len(circuit.qubits)):
                qibo_circuit.add(gates.M(i))
            measurements = qibo_circuit.measurements
            braket_circuit = circuit

        # Wrap verbatim box, execute:
        if verbatim_circuit:
            braket_circuit = BraketCircuit().add_verbatim_box(braket_circuit)
        result = self.device.run(braket_circuit, shots=nshots).result()
        samples = result.measurements
        return MeasurementOutcomes(
            measurements=measurements, backend=self, samples=samples, nshots=nshots
        )
