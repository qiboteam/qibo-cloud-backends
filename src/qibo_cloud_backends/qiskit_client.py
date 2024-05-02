from itertools import repeat

from qibo.backends import NumpyBackend
from qibo.config import raise_error
from qibo.result import MeasurementOutcomes, QuantumState

import qiskit.qasm2
from qiskit import QuantumCircuit
from qiskit.providers.basic_provider import BasicProvider
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import SamplerV2 as Sampler, QiskitRuntimeService
import qiskit_ibm_runtime.fake_provider as fake_provider
from qiskit.transpiler import CouplingMap

import re

class QiskitClientBackend(NumpyBackend):
    """Backend for the remote execution of Qiskit circuits on the IBM servers.

    Args:
        token (str): User authentication token.
        provider (str): Name of the IBM service provider. Defaults to `"BasicProvider()"`.
        platform (str): The IBM platform. Defaults to `"basic_simulator"`.
        basis_gates (list, str): List of basis gates for the IBM platform. e.g. ['ECR', 'id', 'rz', 'sx', 'x']
        coupling_map (list, list): List of coupling map (not tested yet, dependent on platform)
        optimization_level (int): 0 for no optimization, 3 for maximum optimization. Defaults to 1.
    """
    
    def __init__(self, token=None, provider=None, platform=None, basis_gates=None, coupling_map=None, optimization_level=1):
        super().__init__()
        # if token=None default to backend = BasicProvider().get_backend("basic_simulator")
        # elif: backend = fake_provider.FakeProvider
        # elif: backend = QiskitRuntimeService().get_backend("backend")

        if provider is None:
            provider = BasicProvider()
            platform = "basic_simulator"
            self.backend = provider.get_backend(platform)
        elif provider == "fake_provider":
            provider = fake_provider
            backend = getattr(fake_provider, platform)()
            self.backend = backend
        else:
            self.backend = provider.get_backend(platform)
        self.platform = platform

        self.name = "qiskit"

        if optimization_level < 0 or optimization_level > 3:
            raise_error(ValueError, "optimization level needs to be between 0 to 3, inclusive of 0 and 3.")
        else:
            self.optimization_level = optimization_level
        if coupling_map is not None:
            self.coupling_map = CouplingMap(coupling_map)
        if basis_gates is not None:
            self.basis_gates = basis_gates

    def convert_counts_to_bin_keys(self, qc, counts):
        """To convert the keys in the count_dictionary into binary.
            E.g. {'0x0': 511, '0x1': 489} is converted to {'0000': 511, '0001': 489}.
            One needs to input the quantum circuit that was executed to count the
            number of qubits being measured.
    
        Arguments:
            qc (qiskit circuit): quantum circuit that was executed.
            counts (dict): the dictionary containing the counts extracted from
                           the executed job using job.result().results[0].data.counts
        Returns:
            counts (dict): dictionary of counts with the keys converted to binary.
        """
        
        num_measurements = 0
        for data in qc.data:
            if data[0].name == 'measure':
                num_measurements += 1 
    
        converted_counts_data = {}
        largest_key = int(max(counts.keys()), 16)
        for hex_key, val in counts.items():
            binary_key = bin(int(hex_key, 16))[2:].zfill(num_measurements)
            converted_counts_data[binary_key] = val
        
        return converted_counts_data    
    
    def register0_to_meas(self, qasm_string):
        """ To replace "register0" with "meas", else qiskit will not convert register0 into measurements.
        Args:
            qasm_string
        Returns:
            qasm_string
        """
        updated_string = re.sub(r'\bregister0\b', 'meas', qasm_string)
        return updated_string
                
    def execute_circuit(self, circuit, initial_state=None, nshots=1000, **kwargs):
        """Executes the passed circuit.

        Args:
            circuit (qibo.models.Circuit): The circuit to execute.
            initial_state (ndarray): The initial state of the circuit. Defaults to `|00...0>`.
            nshots (int): Total number of shots.
            kwargs (dict): Additional keyword arguments passed to the qiskit backends' `run()` method.
        Returns:
            (qibo.result.MeasurementOutcomes) The outcome of the circuit execution.
        """
        if initial_state is not None:
            raise_error(
                NotImplementedError,
                "The use of an `initial_state` is not supported yet.",
            )
        measurements = circuit.measurements
        if not measurements:
            raise_error(RuntimeError, "No measurement found in the provided circuit.")
        nqubits = circuit.nqubits

        # Convert Qibo circuit --> OpenQASM --> Qiskit circuit
        circuit = qiskit.qasm2.loads(self.register0_to_meas(circuit_qibo.to_qasm()))

        if self.platform == "basic_simulator":
            print('BASIC SIMULATOR')
            # Don't need to perform transpilation.
            
            # Use backend.run() to generate counts.
            job = self.backend.run(circuit, shots=1000)
            counts = job.result().results[0].data.counts
            counts = self.convert_counts_to_bin_keys(circuit, counts)

        else:
            print('FAKE PROVIDER or CLOUD BACKEND')
            # Perform transpilation using generate_preset_pass_manager
            pm = generate_preset_pass_manager(backend=self.backend, optimization_level=1)
            isa_qc = pm.run(circuit)

            # Use Sampler to generate counts.
            sampler = Sampler(backend=self.backend)
            job = sampler.run([isa_qc], shots=nshots)
            counts = job.result()[0].data.meas.get_counts()
    
        samples = []
        for state, count in counts.items():
            sample = [int(bit) for bit in reversed(state)]
            samples += list(repeat(sample, count))
        return MeasurementOutcomes(
            measurements, backend=self, samples=self.np.asarray(samples), nshots=nshots
        )
