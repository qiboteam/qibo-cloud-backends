.. _backends:

API Reference
-------------

Here are reported the Qibo backends that support the execution of Quantum Circuits through different cloud service providers.

Qibo Cloud Backend
^^^^^^^^^^^^^^^^^^

This backend supports qibo-based providers.

.. autoclass:: qibo_cloud_backends.qibo_client.QiboClientBackend
    :members:
    :member-order: bysource

Qiskit Cloud Backend
^^^^^^^^^^^^^^^^^^^^

This backend supports IBM as provider, namely the qibo circuits are loaded as qiskit circuits and the job is sent to the IBM servers.

.. note::
   The :meth:`qibo_cloud_backends.qiskit_client.QiskitClientBackend.execute_circuit` does not take care of any transpilation and expects the passed circuit to be transpiled already.

.. note::
   Circuits with no measurements are not supported yet. Remeber to add measurements to your circuit!

.. autoclass:: qibo_cloud_backends.qiskit_client.QiskitClientBackend
    :members:
    :member-order: bysource


AWS Cloud Backend
^^^^^^^^^^^^^^^^^

This backend supports AWS Braket devices, from LocalSimulator to the devices hosted on Amazon Braket. Here, qibo circuits are translated to Braket circuits and sent to the Braket device. 


.. note::
   If `verbatim_circuit=True`, the qibo circuit is only translated to a Braket circuit before execution on :meth:`qibo_cloud_backends.aws_client.BraketClientBackend.execute_circuit`. No transpilation will take place on the Braket device.  

.. note::
   Circuits with no measurements are not supported yet. Remeber to add measurements to your circuit!

.. autoclass:: qibo_cloud_backends.aws_client.BraketClientBackend
    :members:
    :member-order: bysource

