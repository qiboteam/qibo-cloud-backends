.. _tutorials:

Using Braket Client
-------------------

Registering for an AWS Account
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The usage of the AWS Braket LocalSimulator does not require an account. However, to use AWS Braket devices such as the statevector simulator and hardware, the user needs to register for an account here: https://signin.aws.amazon.com/signup?request_type=register.

Extracting AWS Braket device parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In this tutorial, we will learn how to set the `backend` parameter to the BraketClientBackend and use two devices, the LocalSimulator as well as the IQM device Garnet. More information on Garnet here: https://aws.amazon.com/braket/quantum-computers/iqm/.

To use BraketClientBackend, one needs to import these packages first.

.. code-block:: python

   from braket.aws import AwsDevice
   from braket.devices import Devices, LocalSimulator
   from qibo_cloud_backend.braket_client import BraketClientBackend

The qubit connectivity on the IQM Garnet device can be drawn using networkx as follows. We will also extract the device's native gates.

.. code-block:: python

   import networkx as nx

   device = 'arn:aws:braket:eu-north-1::device/qpu/iqm/Garnet'
   connectivity_graph = AwsDevice(device).properties.paradigm.connectivity.connectivityGraph
   native_gates = AwsDevice(device).properties.paradigm.nativeGateSet
   print(native_gates)

   G = nx.Graph()
   for node, neighbors in connectivity_graph.items():
      for neighbor in neighbors:
         G.add_edge(node, neighbor)

   nx.draw(G, pos=nx.spring_layout(G), with_labels=True, node_color='lightblue', node_size=500, font_size=10, font_weight='bold', edge_color='gray')

Executing a circuit without verbatim mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Let us run a circuit with `verbatim_circuit=False` on an AWS device. We will use IQM Garnet as an example. Note that when `verbatim_circuit=False`, the transpilation of the input circuit and assignment of the best qubits to use will be left to the device.

.. code-block:: python

   from qibo import gates, Circuit as QiboCircuit
   import numpy as np

   c = QiboCircuit(2)
   c.add(gates.H(0))
   c.add(gates.CNOT(0, 1))
   c.add(gates.M(0))
   c.add(gates.M(1))

   print(c.draw())

We should get this circuit:

.. code-block:: python

   q0: -H-o-M-
   q1: ---x-M-

Now, we initialize the AWS device and execute circuit `c` on the backend `AWS`.

.. code-block:: python

   device = AwsDevice('arn:aws:braket:eu-north-1::device/qpu/iqm/Garnet')
   AWS = BraketClientBackend(device = device, verbatim_circuit=False)

   counts = AWS.execute_circuit(c, nshots=1000).frequencies()
   print(counts)

For completeness, one can also use the LocalSimulator to execute circuit `c` as follows.

.. code-block:: python

   device = device = LocalSimulator("default")
   AWS = BraketClientBackend(device = device, verbatim_circuit=False)

   counts = AWS.execute_circuit(c, nshots=1000).frequencies()
   print(counts)



Executing a circuit in verbatim mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Let us run a circuit with `verbatim_circuit=True` on an AWS device, using IQM Garnet as an example. Here, when `verbatim_circuit=True`, the circuit is submitted as is onto the AWS device. The device expects to receive a circuit that is written in native gates with qubits in the range of the device. For IQM Garnet, the native gates are `CZ` and `PRX` gates. IQM Garnet has qubits indexed from 1 to 20.

.. code-block:: python

   from qibo import gates, Circuit as QiboCircuit
   import numpy as np

   c = QiboCircuit(5)
   c.add(gates.PRX(1, 0.5*np.pi, 1.5*np.pi))
   c.add(gates.PRX(4, 0.142857142857143*np.pi, 0))
   c.add(gates.CZ(4, 1))
   c.add(gates.PRX(1, 0.5*np.pi, 0.5*np.pi))
   c.add(gates.M(1))
   c.add(gates.M(4))

   print(c.draw())

We should get this circuit:

.. code-block:: python

   q0: -------------
   q1: -prx-Z-prx-M-
   q2: -----|-------
   q3: -----|-------
   q4: -prx-o-M-----

Since IQM Garnet has qubits indexed from 1 to 20, we will intentionally leave qubit `q0` empty. An error will be raised if there are gates on any qubits not in the range from 1 to 20.

Now, we initialize the AWS device and execute circuit `c` on the backend `AWS`.

.. code-block:: python

   device = AwsDevice('arn:aws:braket:eu-north-1::device/qpu/iqm/Garnet')
   AWS = BraketClientBackend(device = device, verbatim_circuit=True)

   counts = AWS.execute_circuit(c, nshots=1000).frequencies()
   print(counts)

For completeness, one can also use the LocalSimulator to execute circuit `c` as follows.

.. code-block:: python

   device = device = LocalSimulator("default")
   AWS = BraketClientBackend(device = device, verbatim_circuit=True)

   counts = AWS.execute_circuit(c, nshots=1000).frequencies()
   print(counts)

Using Zero Noise Extrapolation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In this example, we illustrate the use of Zero Noise Extrapolation (ZNE) to improve the results of a Quantum Approximate Optimization Algorithm (QAOA) circuit. The circuit solves a trivial MaxCut problem with a single QAOA layer.

Here, we make several assumptions:
1. The user is able to transpile any Qibo circuit with IQM Garnet's qubit topology.
2. The optimal angles for the single QAOA layer are found and will be used.

With these assumptions met, we provide an example circuit `c` below is written in IQM Garnet's native gates with specific qubits. The parameters for the `PRX` gates are optimal. We select `verbatim_circuit=True` as we do not want the device to transpile the circuit.

.. code-block:: python

   c = QiboCircuit(10):
   c.add(gates.PRX(3, -np.pi, np.pi/2))
   c.add(gates.PRX(3, np.pi, -np.pi/2))
   c.add(gates.PRX(4, np.pi/2, np.pi/2))
   c.add(gates.PRX(4, np.pi, 0))
   c.add(gates.CZ(3, 4))
   c.add(gates.PRX(3, -1.081592653589793, 0))
   c.add(gates.PRX(3, np.pi, -np.pi))
   c.add(gates.CZ(3, 4))
   c.add(gates.PRX(3, np.pi/2, np.pi/2))
   c.add(gates.PRX(3, np.pi, 0))
   c.add(gates.PRX(5, -np.pi, np.pi/2))
   c.add(gates.PRX(5, np.pi, -np.pi/2))
   c.add(gates.PRX(9, -np.pi, np.pi/2))
   c.add(gates.PRX(9, np.pi, -np.pi/2))
   c.add(gates.CZ(4, 9))
   c.add(gates.PRX(9, -1.081592653589793, 0))
   c.add(gates.PRX(9, np.pi, -np.pi))
   c.add(gates.CZ(4, 9))
   c.add(gates.CZ(4, 5))
   c.add(gates.PRX(5, -1.081592653589793, 0))
   c.add(gates.PRX(5, np.pi, -np.pi))
   c.add(gates.CZ(4, 5))
   c.add(gates.PRX(4, 2.850796326794897, 0))
   c.add(gates.PRX(5, -np.pi, np.pi/2))
   c.add(gates.PRX(5, np.pi, -np.pi/2))
   c.add(gates.PRX(9, -np.pi/2, -np.pi))
   c.add(gates.PRX(9, np.pi, -np.pi/4))
   c.add(gates.CZ(4, 9))
   c.add(gates.PRX(4, np.pi/2, 0))
   c.add(gates.PRX(9, np.pi/2, 0))
   c.add(gates.CZ(4, 9))
   c.add(gates.PRX(4, np.pi/2, 0))
   c.add(gates.PRX(9, np.pi/2, 0))
   c.add(gates.CZ(4, 9))
   c.add(gates.PRX(4, np.pi/2, np.pi/2))
   c.add(gates.PRX(4, np.pi, 0))
   c.add(gates.CZ(3, 4))
   c.add(gates.PRX(4, -1.081592653589793, 0))
   c.add(gates.PRX(4, np.pi, -np.pi))
   c.add(gates.CZ(3, 4))
   c.add(gates.PRX(3, 1.28, 0))
   c.add(gates.PRX(4, np.pi/2, np.pi/2))
   c.add(gates.PRX(4, np.pi, 0))
   c.add(gates.CZ(4, 5))
   c.add(gates.PRX(4, -1.081592653589793, 0))
   c.add(gates.PRX(4, np.pi, -np.pi))
   c.add(gates.CZ(4, 5))
   c.add(gates.PRX(4, 1.28, 0))
   c.add(gates.PRX(5, -np.pi/2, -2.850796326794897))
   c.add(gates.PRX(5, np.pi, -0.64)
   c.add(gates.M(9))
   c.add(gates.M(3))
   c.add(gates.M(4))
   c.add(gates.M(5))

We define the Hamiltonian, `obs`. The `obs` has to be written according to the qubit mapping applied for circuit `c`.

.. code-block:: python

   obs = 2.5 - 0.5*Z(3)*Z(9) - 0.5*Z(4)*Z(3) - 0.5*Z(4)*Z(5) - 0.5*Z(4)*Z(9) - 0.5*Z(9)*Z(5)
   obs = SymbolicHamiltonian(obs, nqubits=c.nqubits, backend=NumpyBackend())

Finally, we can run ZNE by setting the backend to the AWS to obtain the estimated (extrapolated) result.

.. code-block:: python

   device = AwsDevice('arn:aws:braket:eu-north-1::device/qpu/iqm/Garnet')
   AWS = BraketClientBackend(device = device, verbatim_circuit=True)

   shots=1000
   estimate = ZNE(
       circuit=c,
       observable=obs,
       noise_levels=np.array(range(5)),
       nshots=shots,
       backend=AWS,
   )
   print(estimate)

.. note::
   Running circuits on an AWS Braket device (other than LocalSimulator) incurs cost. The prices can be found on https://aws.amazon.com/braket/pricing/.
