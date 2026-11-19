# Local test GUI

Start on Ubuntu with the existing virtual environment active:

```bash
cd /opt/vigi-provisioner
PYTHONPATH=src python -m vigi_provisioner.vigi_test_gui \
  --inventory "$HOME/vigi-test-inventory.sqlite3" \
  --config provisioning.toml
```

Open http://127.0.0.1:8765 in the Ubuntu browser. From Windows, forward the local port with `ssh -L 8765:127.0.0.1:8765 USER@UBUNTU_ADDRESS`, then open the same local URL. The default bind address is Ubuntu loopback. To serve the GUI on the VM management interface, add `--bind 192.168.10.143` and open http://192.168.10.143:8765 from Windows. Requests must use that configured address. The service has no user login, so this listener gives management-LAN clients access to the provisioning controls and credential prompts. Camera traffic continues to use the existing camera-facing interface at 192.168.0.10.

Enter scanned Device ID, MAC and label serial, model and the approved IP/netmask/gateway. The form adds inventory records and enforces unique IDs, MACs and target IPs. Existing records are displayed. This first version has no edit or delete control. Additional models can be recorded. The current provisioning engine still requires the tested VIGI C320I and lab subnet.

Select a factory-state camera and start provisioning. The step log streams output from the existing CLI. Answer fingerprint approval and target-IP confirmation prompts with the values requested. Password and recovery-email inputs are hidden and sent to the worker in memory. Credentials are not put in the database or log.

The GUI adds label serial, firmware, status, observation metadata and last-run time columns to the inventory. UDP discovery observations are retained with the selected record. Missing observations remain unknown. The label serial is operator-supplied and is not compared against the QR field. The engine authorizes the camera using its MAC and Device ID.

One run can be active at a time. Keep the GUI server running through completion. Closing the browser allows reconnection to the current prompts. The interface uses the existing provisioning engine and its site TOML, certificate approval and ONVIF/HTTPS verification.

The GUI has been checked offline. Its first Ubuntu browser and live-camera run remains pending.
