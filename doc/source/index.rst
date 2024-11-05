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

or, in order to use the `ibm_kyiv` platform on the IBM `ibm-q` server:

.. code-block:: python

   set_backend("qibo-cloud-backends", client="qiskit-client", token="your_token", platform="ibm_kyiv")
   result = circuit()
   print(result.frequencies())

To use Amazon Braket devices, refer to :ref:`tutorials` for a tutorial on using the Braket client.

API Reference
=============

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   backends

.. toctree::
   :maxdepth: 2
   :caption: Tutorials:

   tutorials

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
