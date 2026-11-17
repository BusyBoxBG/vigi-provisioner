# VIGI Provisioner

Factory-to-static-IP provisioning for TP-Link VIGI C320I cameras on an isolated corporate LAN. The Ubuntu workflow matches a scanned Device ID and MAC against SQLite, activates the camera over certificate-pinned HTTPS, applies a shared TOML profile, then configures and verifies static IPv4 over ONVIF.

## Verified test setup

| Parameter | Value |
| --- | --- |
| Camera | TP-Link VIGI C320I, firmware `2.2.1 Build 260605 Rel.12620n` |
| Scanned Device ID | `1326062CFD849E902` |
| Scanned MAC | `18:69:45:9F:31:F7` |
| Ubuntu camera-facing IPv4 | `192.168.0.10/24` |
| Windows camera-facing IPv4, if connected | `192.168.0.100/24` |
| Factory camera IPv4 | `192.168.0.60` |
| Approved IPv4 and netmask | `192.168.0.150/24`, `255.255.255.0` |
| Gateway | `192.168.0.1` |
| Protocols | TP-Link UDP discovery on 5001, HTTPS on 443, ONVIF on HTTP 80 |

Keep host and VM addresses distinct. Reserve the target IPv4 and exclude it from DHCP allocation to other devices.

## 1. Prepare Ubuntu

Use Python 3.10 or later. From the checkout:

```bash
cd /opt/vigi-provisioner
python3 -m venv "$HOME/.venvs/vigi-provisioner"
source "$HOME/.venvs/vigi-provisioner/bin/activate"
python -m pip install .
python scripts/check_offline.py
```

An existing virtual environment can be reused. The offline check imports the package and runs 11 checks without contacting a camera.

## 2. Enter the approved camera in SQLite

Store the printed Device ID and MAC together with the approved assignment. Keep the inventory outside the checkout. This example creates the test inventory from a new file:

```bash
sqlite3 "$HOME/vigi-test-inventory.sqlite3" <<'SQL'
CREATE TABLE camera_inventory (
    device_id TEXT NOT NULL PRIMARY KEY,
    mac_address TEXT NOT NULL UNIQUE,
    model TEXT NOT NULL,
    approved_ipv4 TEXT NOT NULL UNIQUE,
    prefix_length INTEGER NOT NULL CHECK (prefix_length BETWEEN 1 AND 30),
    gateway_ipv4 TEXT NOT NULL
);
INSERT INTO camera_inventory VALUES
    ('1326062CFD849E902', '1869459F31F7', 'VIGI C320I',
     '192.168.0.150', 24, '192.168.0.1');
SQL
```

The CLI opens the database read-only. The factory camera must report both identifiers before HTTPS activation. The C320I Device ID comes from TP-Link discovery TLV `0x0018`, whose observed value wraps the printed ID as `TP1<device-id>020`.

## 3. Set the shared camera profile

Copy [provisioning.example.toml](provisioning.example.toml) to `provisioning.toml` and set your recovery email. The successful run used these settings:

```toml
[camera_defaults]
username = "admin"
recovery_email = "support@comnet.bg"
language = "English"
country = "BG"
time_zone = "UTC+02:00"
zone_id = "Europe/Vilnius"
power_line_frequency = "50hz"
```

Git ignores the local profile. Enter the shared admin password at the hidden prompt for each run. The recovery email comes from TOML. The country code records the intended profile, and the camera's Country/Region value is reported from readback.

## 4. Provision the factory-state camera

Connect the intended camera to the isolated provisioning LAN. If reusing a test camera, factory-reset it and leave the web wizard unsubmitted. Run:

```bash
cd /opt/vigi-provisioner &&
source "$HOME/.venvs/vigi-provisioner/bin/activate" &&
PYTHONPATH=src python -m vigi_provisioner.vigi_factory_workflow \
  --config provisioning.toml \
  --inventory "$HOME/vigi-test-inventory.sqlite3" \
  --device-id 1326062CFD849E902
```

1. Review the discovered Device ID, MAC, and approved assignment. The CLI shows the fresh certificate fingerprint. Type `APPROVE` only for the intended camera on the isolated LAN. This trusts the observed certificate for the run. Supply a separately verified `--pin` if required.
2. Type `192.168.0.150` to confirm the target is unused and reserved, then enter the shared admin password twice.
3. The CLI confirms factory state over pinned HTTPS, submits account creation, and verifies the new password with a fresh login. It reads the time zone and frequency, applies the profile if needed, then verifies the resulting settings.
4. ONVIF checks the current interface MAC and token, writes the gateway first, and sets static IPv4 and prefix with DHCP disabled. A fresh authenticated read at the new address verifies the assignment.

## 5. Check the result

The live TOML-driven test reported:

```text
Verified English, UTC+02:00, Europe/Vilnius, 50hz.
Country/Region readback: (empty)
ONVIF writes: acknowledged. Reboot needed: False.
Verified eth0: 192.168.0.150/24, DHCP disabled, gateway 192.168.0.1.
Provisioning complete. Recovery email was submitted during activation.
```

The recovery email was submitted during activation and was not independently read back. The inventory remains read-only. If execution stops after activation or an ONVIF write, check the current camera state and address before attempting another run.

## Protocol and source documentation

- [Provisioning workflow and component map](docs/provisioning-workflow.md)
- [TP-Link UDP discovery](docs/tplink-discovery.md)
- [Factory camera HTTPS initialization](docs/https-initialization.md)
- [ONVIF network settings and readback](docs/onvif-network.md)
- [Every Python file](docs/python-reference.md)
- [Project layout](docs/project-layout.md)
