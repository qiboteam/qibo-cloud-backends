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
   Circuits with no measurements are not supported yet. Remember to add measurements to your circuit!

.. autoclass:: qibo_cloud_backends.qiskit_client.QiskitClientBackend
    :members:
    :member-order: bysource


Braket Backend
^^^^^^^^^^^^^^

This backend provides support for AWS Braket devices, ranging from the LocalSimulator to the devices available on Amazon Braket. Here, Qibo circuits are translated into Braket circuits and sent to the Braket device. There is an additional option to submit a Qibo circuit written in the device's native gates and targeting specific qubits, fully avoiding any transpilation. This can be done by changing the default setting from `verbatim_circuit=False` to `verbatim_circuit=True`.

.. note::
   If `verbatim_circuit=True`, the Qibo circuit only undergoes translation to a Braket circuit before execution on :meth:`qibo_cloud_backends.braket_client.BraketClientBackend.execute_circuit`. No transpilation will take place on the Braket device. A warning will be raised by the device if the qubits are out of range or if it detects non-native gates.

.. note::
   Circuits with no measurements are not supported yet. Remember to add measurements to your circuit!

.. autoclass:: qibo_cloud_backends.braket_client.BraketClientBackend
    :members:
    :member-order: bysource


IonQ Cloud Backend
^^^^^^^^^^^^^^^^^^

This backend supports IonQ as provider, namely the ``qibo`` circuits are loaded as QASM circuits and the job is sent to the IonQ Cloud servers.

.. note::
   The :meth:`qibo_cloud_backends.ionq_client.IonQClientBackend.execute_circuit` does not take care of any transpilation and expects the passed circuit to be transpiled already.

.. note::
   Circuits with no measurements are not supported yet. Remember to add measurements to your circuit!

.. autoclass:: qibo_cloud_backends.ionq_client.IonQClientBackend
    :members:
    :member-order: bysource
