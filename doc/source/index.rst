.. title::
      Qibo-cloud-backends

What is qibo-cloud-backends?
============================

Qibo-cloud-backends is a Qibo plugin that provides some additional backends which allow for the remote execution of Quantum Circuits.

Installation instructions
=========================

Install first the package dependencies with the following commands.

We recommend to start with a fresh virtual environment to avoid dependencies
conflicts with previously installed packages.

.. code-block:: bash

   $ python -m venv ./env
   source activate ./env/bin/activate

The qibo-client-backends package can be installed through pip:

.. code-block:: bash

   pip install qibo-cloud-backends


Quickstart
==========

Once installed, the plugin allows for setting and using the new backends in Qibo.

The following two examples show how to submit a job on the Qibo cloud infrastructure and the IBM servers. Remember to replace `"your token"` string with your actual valid token received after registration. Alternatively, you can register your token under the environment variables `QIBO_CLIENT_TOKEN` for `qibo-client` and `IBMQ_TOKEN` for `qiskit-client`.

Prepare a QFT circuit to be submitted to the servers:

.. code-block:: python

   from qibo.models import QFT
   from qibo import gates

   circuit = qibo.models.QFT(5)
   circuit.add(gates.M(0, 2, 5))

Then, to simulate the circuit using the Qibo cloud service through the `sim` platform:

.. code-block:: python

   from qibo.backends import set_backend

   set_backend("qibo-cloud-backends", client="qibo-client", token="your_token", platform="sim")
   result = circuit()
   print(result.frequencies())

or, in order to use the `ibm_osaka` platform on the IBM `ibm-q` server:

.. code-block:: python

   set_backend("qibo-cloud-backends", client="qiskit-client", token="your_token", platform="ibm_osaka")
   result = circuit()
   print(result.frequencies())


Tutorial for Braket Client
==========================

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

Let us now run a circuit with `verbatim_circuit=True` on an AWS device. We will use IQM Garnet as an example.

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

   q0: ─────────────
   q1: ─prx─Z─prx─M─
   q2: ─────|───────
   q3: ─────|───────
   q4: ─prx─o─M─────

Note that qubit `q0` is intentionally left empty as the IQM Garnet does not have a qubit indexed by 0. An error will occur if there are gates on qubit `q0`. Now, we initialize the AWS device and execute circuit `c` on the backend `AWS`.

.. code-block:: python

   device = AwsDevice('arn:aws:braket:eu-north-1::device/qpu/iqm/Garnet')
   AWS = BraketClientBackend(device = device, verbatim_circuit=True)

   counts = AWS.execute_circuit(c, nshots=1000).frequencies()
   print(counts)

We present an example of running a Quantum Approximate Optimization Algorithm (QAOA) to solve a trivial MaxCut problem with a single QAOA layer. The circuit `c` below is written in IQM Garnet's native gates.

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

We define the Hamiltonian, assuming that we know the qubit mapping for the IQM device.

.. code-block:: python
   obs = 2.5 - 0.5*Z(3)*Z(9) - 0.5*Z(4)*Z(3) - 0.5*Z(4)*Z(5) - 0.5*Z(4)*Z(9) - 0.5*Z(9)*Z(5)
   obs = SymbolicHamiltonian(obs, nqubits=c.nqubits, backend=NumpyBackend())

Finally, we can run Zero Noise Extrapolation and obtain the expected result.

.. code-block:: python

   shots=1000
   estimate = ZNE(
       circuit=c,
       observable=obs,
       noise_levels=np.array(range(5)),
       nshots=shots,
       backend=AWS,
   )
   print(estimate)


API Reference
=============

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   backends

.. toctree::
    :maxdepth: 1
    :caption: Documentation links

    Qibo docs <https://qibo.science/qibo/stable/>
    Qibolab docs <https://qibo.science/qibolab/stable/>
    Qibocal docs <https://qibo.science/qibocal/stable/>
    Qibosoq docs <https://qibo.science/qibosoq/stable/>
    Qibochem docs <https://qibo.science/qibochem/stable/>
    Qibotn docs <https://qibo.science/qibotn/stable/>
    Qibo-cloud-backends docs <https://qibo.science/qibo-cloud-backends/stable/>
