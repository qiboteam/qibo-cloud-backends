from qibo.backends import NumpyBackend
from qibo.config import raise_error
from qibo.result import MeasurementOutcomes, QuantumState
from qibo import gates
from qibo import Circuit as QiboCircuit
from qibo.transpiler.pipeline import Passes, assert_transpiling
from qibo.transpiler.optimizer import Preprocessing
from qibo.transpiler.router import ShortestPaths
from qibo.transpiler.unroller import Unroller, NativeGates
from qibo.transpiler.placer import Random

import re
import importlib.util
import sys
import networkx as nx

# # Import Qiskit packages for transpiler
# from qiskit import transpile
# from qiskit import QuantumCircuit
# from qiskit.transpiler import CouplingMap
# from qiskit.circuit.random import random_circuit
# from qiskit import qasm2

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
    "u3": "U",
    
}

class BraketBackend(NumpyBackend):
    """Backend for the remote execution of AWS circuits on the AWS backends.

    Args:
        device_arn (str | None): The ARN of the Braket device.
            If `None`, instantiates the `LocalSimulator("default")`.
    """

    def __init__(self, device=None, verbatim_circuit=False, transpilation=False, native_gates=None, coupling_map=None):
        """Initializes BraketBackend.

        Args:
            device (str): Default device is Braket's statevector LocalSimulator, LocalSimulator("default").
                Other devices are Braket's density matrix simulator, LocalSimulator("braket_dm"), or any other
                QPUs.
            verbatim_circuit (bool): If `True`, wrap the Braket circuit in a verbatim box to run it on the QPU
                without any transpilation. Defaults to `False`.
            transpilation (bool): If `True`, use Qibo's transpilation. Requires two additional arguments:
                native_gates and coupling_map.
            native_gates (list, qibo.gates): e.g. [gates.I, gates.RZ, gates.SX, gates.X, gates.ECR]
            coupling_map (list, list): E.g. [[0, 1], [0, 7], [1, 2], [2, 3], [4, 3], [4, 5], [6, 5], [7, 6]]
        """
        
        super().__init__()
        
        self.verbatim_circuit = verbatim_circuit

        self.transpilation = transpilation
        if transpilation:
            if coupling_map is None:
                raise_error(ValueError, "Expected qubit_map. E.g. qubit_map = [[0, 1], [0, 7], [1, 2], [2, 3], [4, 3], [4, 5], [6, 5], [7, 6]]")
            else:
                self.coupling_map = coupling_map
            if native_gates is None:
                raise_error(ValueError, "Expected native gates for transpilation. E.g. native_gates = [gates.I, gates.RZ, gates.SX, gates.X, gates.ECR]")
            else:
                self.native_gates = native_gates

        
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

    def custom_connectivity(self, coupling_map):
        """Converts a coupling map given in list form to a networkx graph.
    
        Args:
            coupling_map (list): E.g. [[0, 1], [0, 7], [1, 2], [2, 3], [4, 3], [4, 5], [6, 5], [7, 6]]
        Returns:
            graph (networkx graph): graph
        """
        
        graph = nx.Graph()
        for connection in coupling_map:
            q1, q2 = connection
            graph.add_edge(q1, q2)
        return graph
    
    def transpile_qibo_to_qibo(self, circuit):
        """Transpiles a Qibo circuit with a specific topology specified by connectivity and custom_native_gates.
            There is no option for optimization_level like Qiskit. Therefore, no gates will be collapsed.
    
        Args:
            circuit (qibo.models.Circuit): Circuit to transpile
        Returns:
            transpiled_circuit (qibo.models.Circuit): Transpiled circuit.
            final_layout (dict): dict of connectivity?
        """
        
        # Define custom passes as a list
        custom_passes = []
        
        # Preprocessing adds qubits in the original circuit to match the number of qubits in the chip
        custom_passes.append(Preprocessing(connectivity=self.custom_connectivity(self.coupling_map)))
    
        # Placement step
        custom_passes.append(Random(connectivity=self.custom_connectivity(self.coupling_map))) 
    
        # Routing step
        custom_passes.append(ShortestPaths(connectivity=self.custom_connectivity(self.coupling_map)))
    
        # custom_native_gates = [gates.I, gates.RZ, gates.SX, gates.X, gates.ECR]
        custom_native_gates = [gates.I, gates.Z, gates.U3, gates.CZ]
        custom_passes.append(Unroller(native_gates=NativeGates.from_gatelist(self.native_gates))) # Gate decomposition ste
    
        custom_pipeline = Passes(custom_passes, 
                                 connectivity=self.custom_connectivity(self.coupling_map),
                                 native_gates=NativeGates.from_gatelist(self.native_gates)) 
                                # native_gates=NativeGates.default()
    
        transpiled_circuit, final_layout = custom_pipeline(circuit)
    
        return transpiled_circuit, final_layout

    #def transpile_qasm_circuit(self, circuit_qasm, native_gates, custom_coupling_map, optimization_level=1):
        # """Transpiles a circuit given in OpenQASM format using Qiskit's transpiler.
        #     Returns a circuit given in OpenQASM format.

        # Args:
        #     circuit_qasm (OpenQASM circuit, str): circuit given in the OpenQASM format.
        #     native_gates (list, str): A list of strings representing the native gates of the QPU.
        #         e.g. native_gates = ['ecr', 'i', 'rz', 'sx', 'x']
        #     custom_coupling_map (list, list): A list containing lists representing the connectivity of the qubits.
        #         e.g. custom_coupling_map. E.g. [[0, 1], [1, 2], [2, 3]]
        #     optimization_level (int): Optimization level for Qiskit's transpiler. Range is from 0 to 3. Defaults to 1.

        # Returns:
        #     transpiled_circuit_qasm (OpenQASM circuit, str): Transpiled circuit in the OpenQASM format.
        # """

        # self.native_gates = native_gates
        # self.custom_coupling_map = custom_coupling_map

        # if optimization_level < 0 or optimization_level > 3:
        #     raise_error(ValueError, "Optimization_level is between 0 to 3.")
        # if custom_coupling_map is None:
        #     raise_error(ValueError, "Expected custom_coupling_map. E.g. custom_coupling_map = [[0, 1], [1, 2], [2, 3]]")
        # if native_gates is None:
        #     raise_error(ValueError, "Expected native gates for transpilation. E.g. native_gates = ['ecr', 'i', 'rz', 'sx', 'x']")

        # # Convert to Qiskit circuit for transpilation
        # circuit_qiskit = QuantumCircuit.from_qasm_str(circuit_qasm)
        # transpiled_circuit = transpile(circuit_qiskit,
        #                                basis_gates = self.native_gates,
        #                                optimization_level = self.optimization_level,
        #                                coupling_map = self.custom_coupling_map)
        # transpiled_circuit_qasm = qasm2.dumps(transpiled_circuit) # Convert back to qasm.
        # return transpiled_circuit_qasm
    
    #def transpile_qibo_to_braket(self, circuit_qibo, native_gates, custom_coupling_map, optimization_level=1):
        # """Transpiles a Qibo circuit using Qiskit's transpiler. Returns a Braket circuit.
    
        # Args:
        #     circuit_qibo (qibo.models.Circuit): Qibo circuit to transpile.
        #     native_gates (list, str): A list of strings representing the native gates of the QPU.
        #         e.g. native_gates = ['ecr', 'i', 'rz', 'sx', 'x']
        #     custom_coupling_map (list, list): A list containing lists representing the connectivity of the qubits.
        #         e.g. custom_coupling_map. E.g. [[0, 1], [1, 2], [2, 3]]
        #     optimization_level (int): Optimization level for Qiskit's transpiler. Range is from 0 to 3. Defaults to 1.
    
        # Returns:
        #     transpiled_circuit_braket (braket.circuits.Circuit): Braket circuit to that has been transpiled.
        # """
            
        # self.native_gates = native_gates
        # self.custom_coupling_map = custom_coupling_map
        # if optimization_level < 0 or optimization_level > 3:
        #     raise_error(ValueError, "Optimization_level is between 0 to 3.")
        # else:
        #     self.optimization_level = optimization_level
        # if custom_coupling_map is None:
        #     raise_error(ValueError, "Expected custom_coupling_map. E.g. custom_coupling_map = [[0, 1], [1, 2], [2, 3]]")
        # if native_gates is None:
        #     raise_error(ValueError, "Expected native gates for transpilation. E.g. native_gates = ['ecr', 'i', 'rz', 'sx', 'x']")

        # circuit_qasm = circuit_qibo.to_qasm()
        # circuit_qiskit = QuantumCircuit.from_qasm_str(circuit_qasm)
        # transpiled_circuit = transpile(circuit_qiskit,
        #                                basis_gates = self.native_gates,
        #                                optimization_level = self.optimization_level,
        #                                coupling_map = self.custom_coupling_map)
        # transpiled_circuit_qasm = qasm2.dumps(transpiled_circuit) # Convert back to qasm.
        # transpiled_circuit_qasm = self.remove_qelib1_inc(transpiled_circuit_qasm)
        # transpiled_circuit_qasm = self.qasm_convert_gates(transpiled_circuit_qasm)
        # braket_circuit = BraketCircuit.from_ir(transpiled_circuit_qasm)
        # return braket_circuit

    def execute_circuit(self,
                        circuit,
                        nshots=1000,
                        **kwargs):
        """Executes a Qibo circuit on an AWS Braket device. The device defaults to the LocalSimulator().
            
        Args:
            circuit (qibo.models.Circuit): circuit to execute on the Braket device.
            nshots (int): Total number of shots.
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

        if self.verbatim_circuit:
            braket_circuit = BraketCircuit().add_verbatim_box(braket_circuit)
        result = self.device.run(braket_circuit, shots=nshots).result()
        samples = result.measurements
        return MeasurementOutcomes(
            measurements=measurements, backend=self, samples=samples, nshots=nshots
        )
