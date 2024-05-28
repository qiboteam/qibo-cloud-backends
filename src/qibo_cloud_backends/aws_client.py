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

# Import Qiskit packages for transpiler
from qiskit import transpile
from qiskit import QuantumCircuit
from qiskit.transpiler import CouplingMap
from qiskit.circuit.random import random_circuit
from qiskit import qasm2

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
    "u3": "U",
}

class BraketClientBackend(NumpyBackend):
    """Backend for the remote execution of AWS circuits on the AWS backends.

    Args:
        device (str): The ARN of the Braket device. Defaults to Braket's statevector LocalSimulator, LocalSimulator("default").
                      Other devices are Braket's density matrix simulator, LocalSimulator("braket_dm"), or any other
                      QPUs.
        verbatim_circuit (bool): If `True`, wrap the Braket circuit in a verbatim box to run it on the QPU
                                 without any transpilation. Defaults to `False`.
        transpilation (bool): If `True`, check for two additional arguments: native_gates and coupling_map.
        native_gates: - For qibo transpiler:   (list, qibo.gates): e.g. [gates.I, gates.RZ, gates.SX, gates.X, gates.ECR]
                      - For qiskit transpiler: (list, str):        e.g. ['ecr', 'i', 'rz', 'sx', 'x']
        coupling_map (list, list): E.g. [[0, 1], [0, 7], [1, 2], [2, 3], [4, 3], [4, 5], [6, 5], [7, 6]]
    """

    def __init__(self, device=None, verbatim_circuit=False, transpilation=False, native_gates=None, coupling_map=None):
        super().__init__()
        
        self.verbatim_circuit = verbatim_circuit

        self.transpilation = transpilation
        if transpilation:
            print('Transpile!')
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
        """To replace the notation for certain gates in OpenQAS.

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
        """Converts a coupling map given in list form to a networkx graph. Returns networkx graph.
    
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

    def transpile_qibo_to_qibo_with_qiskit(self, circuit_qibo, optimization_level=1):
        """Transpiles a Qibo circuit using Qiskit's transpiler. Returns a Qibo circuit.
    
        Args:
            circuit_qibo (qibo.models.Circuit): Qibo circuit to transpile.
            native_gates (list, str): A list of strings representing the native gates of the QPU.
                e.g. native_gates = ['ecr', 'i', 'rz', 'sx', 'x']
            custom_coupling_map (list, list): A list containing lists representing the connectivity of the qubits.
                e.g. custom_coupling_map. E.g. [[0, 1], [1, 2], [2, 3]]
            optimization_level (int): Optimization level for Qiskit's transpiler. Range is from 0 to 3. Defaults to 1.
    
        Returns:
            transpiled_circuit_qibo (qibo.models.Circuit): Qibo circuit that has been transpiled.
        """

        print('Transpile qibo to qibo using qiskit transpiler')
        
        if optimization_level < 0 or optimization_level > 3:
            raise_error(ValueError, "Optimization_level is between 0 to 3.")
        else:
            self.optimization_level = optimization_level
        if self.coupling_map is None:
            raise_error(ValueError, "Expected custom_coupling_map. E.g. custom_coupling_map = [[0, 1], [1, 2], [2, 3]]")
        if self.native_gates is None:
            raise_error(ValueError, "Expected native gates for transpilation. E.g. native_gates = ['ecr', 'i', 'rz', 'sx', 'x']")

        circuit_qasm = circuit_qibo.to_qasm()
        circuit_qiskit = QuantumCircuit.from_qasm_str(circuit_qasm)
        transpiled_circuit = transpile(circuit_qiskit,
                                       basis_gates = self.native_gates,
                                       optimization_level = self.optimization_level,
                                       coupling_map = self.coupling_map)
        transpiled_circuit_qasm = qasm2.dumps(transpiled_circuit) # Convert back to qasm.
        transpiled_circuit_qibo = Circuit.from_qasm(transpiled_circuit_qasm)
        # transpiled_circuit_qasm = self.remove_qelib1_inc(transpiled_circuit_qasm)
        # transpiled_circuit_qasm = self.qasm_convert_gates(transpiled_circuit_qasm)
        # braket_circuit = BraketCircuit.from_ir(transpiled_circuit_qasm)
        # return braket_circuit
        return transpiled_circuit_qibo

    def execute_circuit(self,
                        circuit_qibo,
                        nshots=1000,
                        **kwargs):
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
        nqubits = circuit_qibo.nqubits

        # Extract qibo circuit without the measurements
        circuit_qibo_no_meas = circuit_qibo.__class__(**circuit_qibo.init_kwargs)
        meas_on_qubits = []
        for gate in circuit_qibo.queue:
            if gate.name != "measure":
                circuit_qibo_no_meas.add(gate)
            else:
                meas_on_qubits.append(gate.qubits[0])

        # Translate qibo circuit without measurements to qasm then to braket
        circuit_qasm = circuit_qibo_no_meas.to_qasm()
        circuit_qasm = AWS.remove_qelib1_inc(circuit_qasm)
        circuit_qasm = AWS.qasm_convert_gates(circuit_qasm)
        braket_circuit = BraketCircuit.from_ir(circuit_qasm)
        
        if self.verbatim_circuit:
            print('Added verbatim box')
            braket_circuit = BraketCircuit().add_verbatim_box(braket_circuit)
        
        # Add the measurements after the if-verbatim-circuit check, else the
        # measurements are within the verbatim box and an error will be raised.
        braket_circuit.measure(meas_on_qubits)

        # Execute circuit on self.device
        task = self.device.run(braket_circuit, shots=nshots)
        samples = task.result().measurements
        
        return MeasurementOutcomes(
            measurements=measurements, backend=self, samples=samples, nshots=nshots
        )
