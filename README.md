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

The following two examples show how to submit a job on the TII cluster and the IBM servers. Remember to replace `"your token"` string with your actual valid token received after registration. Alternatively, you can register your token under the environment variables `QIBO_CLIENT_TOKEN` for `qibo-client` and `IBMQ_TOKEN` for `qiskit-client`.

Prepare a QFT circuit to be submitted to the servers:

```python
   import qibo

   circuit = qibo.models.QFT(5)
   circuit.add(qibo.gates.M(0, 2, 4))
```

Then, to simulate the circuit on the `TII` cluster through the `sim` platform:

```python
   qibo.set_backend("qibo-cloud-backends", client="qibo-client", token="your_token", platform="sim")
   result = circuit()
   print(result.frequencies())
```

or, in order to run on one of the chips hosted in `ibm-q`, e.g. `ibm_kyiv`:

```python
   qibo.set_backend("qibo-cloud-backends", client="qiskit-client", token="your_token", platform="ibm_kyiv")
   result = circuit()
   print(result.frequencies())
```
