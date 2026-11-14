# VIGI Provisioner

Python components for TP-Link VIGI discovery, inventory, certificate pinning,
initialization, and ONVIF static-IP planning. The package includes the earlier
UDP workflow and the newer guarded initialization components.

## Setup and offline checks

Use Python 3.10 or later. On Ubuntu, from the project directory:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python scripts/check_offline.py
```

On Windows, activate the environment with `.venv\Scripts\Activate.ps1`.
If the dependencies are already installed, run `python scripts/check_offline.py`
directly from the checkout. The check imports every package module and runs
the selected protocol and transport-ownership tests without a camera.

See [project layout and Ubuntu handoff](docs/project-layout.md).

## Protocol and source documentation

- [Provisioning workflow](docs/provisioning-workflow.md)
- [TP-Link UDP discovery](docs/tplink-discovery.md)
- [Factory camera HTTPS initialization](docs/https-initialization.md)
- [ONVIF network settings and readback](docs/onvif-network.md)
- [Every Python file](docs/python-reference.md)
