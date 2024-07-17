from qibo.backends import NumpyBackend
from qibo.config import raise_error
from qibo.result import MeasurementOutcomes
from qibo import Circuit as QiboCircuit
# from qibo.transpiler.pipeline import Passes, assert_transpiling
# from qibo.transpiler.optimizer import Preprocessing
# from qibo.transpiler.router import ShortestPaths
# from qibo.transpiler.unroller import Unroller, NativeGates
# from qibo.transpiler.placer import Random

import networkx as nx

# Import Qiskit packages for transpiler
from qiskit import transpile
from qiskit import QuantumCircuit
from qiskit import qasm2

from braket.devices import LocalSimulator

from qibo_cloud_backends.braket_translation import to_braket

class BraketClientBackend(NumpyBackend):
    def __init__(self, device=None, verbatim_circuit=False):
        """Backend for the remote execution of AWS circuits on the AWS backends.

        Args:
            device (str): The ARN of the Braket device. Defaults to Braket's statevector LocalSimulator, LocalSimulator("default").
                          Other devices are Braket's density matrix simulator, LocalSimulator("braket_dm"), or any other
                          QPUs.
            verbatim_circuit (bool): If `True`, to_braket will wrap the Braket circuit in a verbatim box to run it on the QPU
                                     without any transpilation. Defaults to `False`.
        """
        super().__init__()
        
        self.verbatim_circuit = verbatim_circuit

        # self.transpilation = transpilation
        # if transpilation:
        #     print('Transpile!')
        #     if coupling_map is None:
        #         raise_error(ValueError, "Expected qubit_map. E.g. qubit_map = [[0, 1], [0, 7], [1, 2], [2, 3], [4, 3], [4, 5], [6, 5], [7, 6]]")
        #     else:
        #         self.coupling_map = coupling_map
        #     if native_gates is None:
        #         raise_error(ValueError, "Expected native gates for transpilation. E.g. native_gates = [gates.I, gates.RZ, gates.SX, gates.X, gates.ECR]")
        #     else:
        #         self.native_gates = native_gates

        self.device = device if device else LocalSimulator()
        self.name = "aws"

    @staticmethod
    def custom_connectivity(coupling_map):
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

    def transpile_qibo_to_qibo_with_qiskit(
        self,
        circuit_qibo,
        native_gates=None,
        coupling_map=None,
        optimization_level=1
    ):
        """Transpiles a Qibo circuit using Qiskit's transpiler. Returns a Qibo circuit.
    
        Args:
            circuit_qibo (qibo.models.Circuit): Qibo circuit to transpile.
            native_gates (list, str): e.g. ['ecr', 'i', 'rz', 'sx', 'x']. IQM uses ['cz', 'prx'].
            coupling_map (list, list): E.g. [[0, 1], [0, 7], [1, 2], [2, 3], [4, 3], [4, 5], [6, 5], [7, 6]]
            optimization_level (int): Optimization level for Qiskit's transpiler. Range is from 0 to 3. Defaults to 1.
    
        Returns:
            transpiled_circuit_qasm (OpenQASM circuit, str): Transpiled circuit in OpenQASM format.
            transpiled_circuit_qibo (qibo.models.Circuit): Qibo circuit that has been transpiled.
        """

        print('Transpile qibo to qibo using qiskit transpiler')
        
        if coupling_map is None:
            raise_error(ValueError, "Expected qubit_map. E.g. qubit_map = [[0, 1], [0, 7], [1, 2], [2, 3], [4, 3], [4, 5], [6, 5], [7, 6]]")
        else:
            self.coupling_map = coupling_map
            
        if native_gates is None:
            raise_error(ValueError, "Expected native gates for transpilation. E.g. native_gates = ['ecr', 'i', 'rz', 'sx', 'x']")
        else:
            self.native_gates = native_gates

        if optimization_level < 0 or optimization_level > 3:
            raise_error(ValueError, "Optimization_level is between 0 to 3.")
        else:
            self.optimization_level = optimization_level

        circuit_qasm = circuit_qibo.to_qasm()
        circuit_qiskit = QuantumCircuit.from_qasm_str(circuit_qasm)
        transpiled_circuit = transpile(
            circuit_qiskit,
            basis_gates=self.native_gates,
            optimization_level=self.optimization_level,
            coupling_map=self.coupling_map
        )
        transpiled_circuit_qasm = qasm2.dumps(transpiled_circuit) # Convert back to qasm.
        transpiled_circuit_qibo = QiboCircuit.from_qasm(transpiled_circuit_qasm)
        return transpiled_circuit, transpiled_circuit_qasm, transpiled_circuit_qibo

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

        task = self.device.run(braket_circuit, shots=nshots)

        # Monitoring: get ID and status of submitted task
        task_id = task.id
        status = task.state()
        print('ID of task:', task_id)
        print('Status of task:', status)
        # wait for job to complete
        while status != 'COMPLETED':
            status = task.state()
            print('Status:', status)
            
        samples = task.result().measurements

        return MeasurementOutcomes(
            measurements=measurements, backend=self, samples=samples, nshots=nshots
        )
