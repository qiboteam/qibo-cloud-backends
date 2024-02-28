# Qibo cloud backends

For the complete documentation please refer to [qibo-cloud-backends](https://qibo.science/qibo-cloud-backends/stable/)

## Installation instructions

Install first the package dependencies with the following commands.

We recommend to start with a fresh virtual environment to avoid dependencies
conflicts with previously installed packages.

```bash
   $ python -m venv ./env
   source activate ./env/bin/activate
```

The qibo-client-backends package can be installed through pip:

```bash
   pip install qibo-cloud-backends
```

## Quickstart

Once installed, the plugin allows for setting and using the new backends in Qibo.

The following two examples show how to submit a job on the TII cluster and the IBM servers. Remember to replace `"your token"` string with your actual valid token
received after registration.

Prepare a QFT circuit to be submitted to the servers:

```python
   from qibo.models import QFT
   from qibo import gates

   circuit = qibo.models.QFT(5)
   circuit.add(gates.M(0, 2, 5))
```

Then, to simulate the circuit on the `TII` cluster through the `sim` platform:

```python

   from qibo.backends import set_backend

   set_backend("qibo-cloud", token="your_token", provider="TII", platform="sim")
   result = circuit()
   print(result.frequencies())
```

or, in order to use the `ibmq_qasm_simulator` platform on the IBM `ibm-q` server:

```python

   set_backend("qiskit", token="your_token", provider="ibm-q", platform="ibmq_qasm_simulator")
   result = circuit()
   print(result.frequencies())
```
