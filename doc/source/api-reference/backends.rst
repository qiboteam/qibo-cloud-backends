.. _backends:

Cloud Backends
--------------

Here are reported the Qibo backends that support the execution of Quantum Circuits through different cloud service providers.

Qibo Cloud Backend
^^^^^^^^^^^^^^^^^^

This backend supports qibo-based providers.

.. autoclass:: qibo_cloud_backends.qibo_client.QiboClientBackend
    :members:
    :member-order: bysource

Qiskit Cloud Backend
^^^^^^^^^^^^^^^^^^

This backend support IBM as provider, namely the qibo circuits are loaded as qiskit circuits and the job is sent to the IBM servers.

.. autoclass:: qibo_cloud_backends.qiskit_client.QiskitClientBackend
    :members:
    :member-order: bysource
