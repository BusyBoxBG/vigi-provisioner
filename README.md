# VIGI Provisioner

Factory-to-static-IP provisioning for TP-Link VIGI cameras on an isolated corporate LAN. The Ubuntu workflow matches a scanned Device ID and MAC against SQLite, activates the camera over certificate-pinned HTTPS, applies a shared TOML profile, configures and verifies static IPv4 over ONVIF, then applies and verifies both DNS addresses over HTTPS.

## Tested camera models

| Camera model | Hardware revision | Hardware-tested firmware paths | Verified result |
| --- | --- | --- | --- |
| TP-Link VIGI C320I | V1.20 (device may report 1.20 or 1.2) | Preserve 2.0.4 Build 241101; upgrade 2.0.4 → 2.2.1 Build 260605; provision 2.2.1 | Activation, supported configuration, static IPv4/gateway and DNS; preserved-firmware GUI and upgrade/configuration hardware runs passed |
| TP-Link VIGI C340S | V1 (device reports 1.0) | Preserve 2.0.3 Build 240412; provision installed 3.2.1 Build 260320; continuous GUI 2.0.3 → 2.5.1 Build 250327 → 3.2.1 | Complete GUI initialization, both real upgrades, configuration, ONVIF networking, DNS and inventory metadata passed |

C540S V1 (hardware 1.0), firmware **3.2.0 Build 251111 Rel.66535n**, has now passed initialization, all site settings, ONVIF port-80 networking and saved/active DNS verification as separate hardware stages. Its GUI path is enabled with **Keep existing firmware**; one continuous factory-reset GUI run remains to be confirmed. C540S firmware upgrading is blocked.

C320I V1, C420I, C330, C430 and InSight S345S/S445S entries remain catalog-only until separately tested. Tested revisions do not establish support for other revisions or firmware versions.

The latest C340S continuous GUI run also verified motion detection with **all processing actions off**, with its full-image region and 24/7 schedule retained. Earlier C320I runs used the previous motion-action profile. Legacy date/time-format limitations and missing motion fields are explicitly reported; country BG remains profile intent when the camera readback is empty, and recovery email is submitted without independent readback.

## Verified test setup

| Parameter | Value |
| --- | --- |
| Camera | TP-Link VIGI C320I, firmware `2.2.1 Build 260605 Rel.12620n` |
| Scanned Device ID | `1326062CFD849E902` |
| Label serial / Device Name | `22630k7001456` |
| Scanned MAC | `18:69:45:9F:31:F7` |
| Ubuntu camera-facing IPv4 | `192.168.0.10/24` |
| Windows camera-facing IPv4, if connected | `192.168.0.100/24` |
| Factory camera IPv4 | `192.168.0.60` |
| Approved IPv4 and netmask | `192.168.0.150/24`, `255.255.255.0` |
| Gateway | `192.168.0.1` |
| DNS (primary / secondary) | `84.54.128.100` / `8.8.8.8` |
| Custom NTP | `84.54.128.102:123` (UDP), every 60 minutes |
| Protocols | TP-Link UDP discovery on 5001, HTTPS on 443, ONVIF on HTTP 80 with 2020 fallback on the inspected paths |

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

An existing virtual environment can be reused. The offline check imports the package and runs the regression suite without contacting a camera.

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
    gateway_ipv4 TEXT NOT NULL,
    label_serial TEXT
);
INSERT INTO camera_inventory VALUES
    ('1326062CFD849E902', '1869459F31F7', 'VIGI C320I',
     '192.168.0.150', 24, '192.168.0.1', '22630k7001456');
SQL
```

The GUI's Edit serial button can fill an existing record. The workflow uses the label serial exactly as entered, including capitalization, as the camera Device Name (`system.sys.dev_alias`). Missing serials preserve the existing device name.

The CLI opens the database read-only. The factory camera must report both identifiers before HTTPS activation. The C320I Device ID comes from TP-Link discovery TLV `0x0018`, whose observed value wraps the printed ID as `TP1<device-id>020`.

## 3. Set the shared camera profile

Copy [provisioning.example.toml](provisioning.example.toml) to `provisioning.toml` and set your recovery email. The successful run used these settings:

```toml
# Copy to provisioning.toml and set the site recovery email.
# Enter the shared password at the hidden runtime prompt.
# Per-camera identity, serial and network assignment come from SQLite.

[camera_defaults]
username = "admin"
recovery_email = "camera-support@example.com"
language = "English"
# Intended country; the test camera reports an empty country_region.
country = "BG"
time_zone = "UTC+02:00"
zone_id = "Europe/Vilnius"
power_line_frequency = "50hz"

[clock]
date_format = "DD-MM-YYYY"
time_format = "24-hour"

[clock.ntp]
server = "84.54.128.102"
port = 123
interval = 60

[clock.dst_manual]
dst_savings = 60
# Week 5 is Last and day 0 is Sunday.
start_month = 3
start_week = 5
start_day = 0
start_hour = 3
end_month = 10
end_week = 5
end_day = 0
end_hour = 4

[dns]
primary = "84.54.128.100"
secondary = "8.8.8.8"

[video]
codec = "H265"
width = 1920
height = 1080
fps = 15
bitrate_mode = "vbr"
quality = "high"
max_bitrate_kbps = 2048
# false maps to the camera string "off" for plain H265.
smart_codec = false

# false maps to cloud_config.cloud_connect.enable = "off".
[platform_access]
enabled = false

# Verified 1920x1080 layout. Label 1 text comes from the inventory serial.
[osd]
date_enabled = true
date_x = 7749
date_y = 0
weekday_enabled = false
labels_enabled = false
label_1_text = "inventory_serial"

# Microphone settings; audio recording is configured separately.
[audio]
muted = true
noise_cancelling = false
volume = 75
codec = "G711alaw"
sampling_rate = 8
channels = 1
input_device_type = "MicIn"

# Full-image motion region is checked; daily arming is 24/7.
[motion_detection]
enabled = true
sensitivity = 85
object_filter = false
people = true
vehicles = true
target_validity = "medium"
schedule = "24/7"
record = false
snapshots = false
push_messages = false
report_server = false
email = false
ftp = false
light_alarm = false
sound_alarm = false
alarm_output_1 = false

# Disable the login-error exception; this is not a tested lockout control.
[login_error]
enabled = false
max_num_err = 5

# Optional firmware check after activation, before site settings.
# Enable once the inspected file is present on the Ubuntu host.
[firmware]
enabled = false
file = "/root/Cx20I_en_2.2.1_Build_260605_Rel.12620n_up_boot_signed.bin"
```

Copy the optional clock and DNS tables into an existing local profile to enable them. The clock profile uses DD-MM-YYYY, 24-hour time, and manual DST with a 60-minute adjustment from the last Sunday in March at 03:00 to the last Sunday in October at 04:00.

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
3. The CLI confirms factory state over pinned HTTPS, submits account creation, and verifies the new password with a fresh login. When the inventory has a label serial, it writes and reads back the Device Name. When the optional firmware stage is enabled, it checks and upgrades firmware before applying site settings, then verifies the version and logs in again. It reads the time zone and frequency, applies the profile if needed, then verifies the resulting settings. With video and Platform Access enabled in the site profile, it verifies the main stream and disables Platform Access before the ONVIF move. With the optional OSD table enabled, it places the date at the saved upper-right coordinates, disables weekday and text overlays, and stores the inventory label serial in label 1.
4. ONVIF checks the current interface MAC and token, writes the gateway first, and sets static IPv4 and prefix with DHCP disabled. A fresh authenticated read at the new address verifies the assignment.
5. With the DNS profile enabled, the CLI checks the HTTPS certificate at the new address. In the live test it had changed, so the operator approved the newly observed fingerprint before DNS login. When using a separately verified `--pin`, enter a newly verified fingerprint if it changes.
6. The CLI writes only the two DNS fields over pinned HTTPS and waits for both saved and active WAN values to match the profile. It checks the approved IP, netmask, and gateway during readback.

## 5. Check the result

The verified factory-to-configured settings include these completion messages:

```text
Verified device name: 22630k7001456.
Verified date format, manual DST and custom NTP configuration.
Verified English, UTC+02:00, Europe/Vilnius, 50hz.
Country/Region readback: (empty)
Verified main stream: H265, smart codec off, 1920x1080, 15 fps, VBR High, 2048 kbps.
Verified Platform Access: off.
ONVIF writes: acknowledged. Reboot needed: False.
Verified eth0: 192.168.0.150/24, DHCP disabled, gateway 192.168.0.1.
Verified saved and active DNS: 84.54.128.100 and 8.8.8.8.
Provisioning complete. Recovery email was submitted during activation.
```

The recovery email was submitted during activation and was not independently read back. NTP readback verifies the saved configuration. Actual clock synchronization and DNS resolution were outside this test. The inventory remains read-only. If execution stops after activation or an ONVIF write, check the current camera state and address before attempting another run.

The full factory-reset and reconfiguration cycle also confirmed Platform Access disabled. The test camera uses the inventory label serial as Device Name and the configured plain H265 video profile.

See [firmware upgrade](docs/firmware-upgrade.md) for the optional post-activation upgrade stage. Both the standalone upgrade and a complete factory activation, 2.0.4-to-2.2.1 upgrade and site-configuration run passed on the tested hardware.

## Additional shared profiles

The optional audio profile mutes the microphone, disables noise cancellation and sets volume 75 with G711alaw, sampling rate 8 and one MicIn channel. Audio recording is a separate setting.

Motion detection uses sensitivity 85, object filtering off and a full-image region, armed 24/7. Recording and snapshots are enabled; push messages, server reporting, email, FTP, light/sound alarms and AO1 are disabled. The workflow checks the existing full-image polygon and reads the schedule separately. Target tracking is omitted from the write, matching the captured browser request.

The login-error exception profile sets enabled off and retains max_num_err 5. The effect of this exception setting on account lockout has not been tested.

Audio, motion, login-error and OSD serial-label configuration passed integrated hardware runs. The preserved-2.0.4 path was also verified through the GUI, with unavailable legacy fields explicitly reported.

## Test GUI

Use the [local browser GUI](docs/test-gui.md) to add inventory records, select a camera, follow the live step log and answer provisioning prompts. It runs on the Ubuntu host with the same TOML profile and SQLite inventory. The Connected factory default cameras panel provides a read-only discovery probe and shows all currently decoded factory-state details. Confirmation inputs appear above the step log. Inventory rows support serial editing and confirmed deletion.

## Protocol and source documentation

- [Provisioning workflow and component map](docs/provisioning-workflow.md)
- [TP-Link UDP discovery](docs/tplink-discovery.md)
- [Factory camera HTTPS initialization](docs/https-initialization.md)
- [ONVIF network settings and readback](docs/onvif-network.md)
- [Every Python file](docs/python-reference.md)
- [Project layout](docs/project-layout.md)

Automatic activation detection is shared by CLI and GUI. It recognizes the exact inspected legacy and modern web-resource signatures and stops before activation for unknown builds. See [activation compatibility](docs/https-initialization.md#automatic-activation-selection). To preserve stock firmware during CLI tests, pass `--skip-firmware`; for GUI tests choose **Keep existing firmware (no upgrade)**.

The GUI offers **Keep existing firmware (no upgrade)** for stock-firmware tests, **Update to default approved firmware after initialization** as the default mode, and a separate profile-controlled upgrade option. Both modes share automatic activation detection. Preserved 2.0.4 provisioning on the tested C320I 1.20 completed with readback and visual verification, with unavailable settings reported in the log. See [GUI firmware handling](docs/test-gui.md#existing-firmware-and-automatic-compatibility).

### Hardware verification and current workflow

The C320I V1.20 paths and C340S V1 paths are listed in the tested-model table above. The continuous C340S GUI run completed on 2026-11-24: factory 2.0.3 activation, verified 2.5.1 upgrade, verified 3.2.1 upgrade, fresh certificate approval/login after both upgrades, all modern site settings, ONVIF port-80 static addressing, inventory metadata and HTTPS saved/active DNS verification. Final address was `192.168.0.160/24`, gateway `192.168.0.1`, DHCP disabled, DNS `84.54.128.100` / `8.8.8.8`. A separate factory-reset 3.2.1 GUI run passed at `.161` and correctly skipped both already-installed firmware stages.

The current motion profile keeps detection configured while disabling all motion-event processing actions, including recording and snapshot capture. The targeted action-only command passed hardware readback with detector/schedule unchanged; the subsequent continuous GUI run verified the same all-off policy. Existing site profiles must have their action booleans set to false. See [motion processing actions](docs/test-gui.md#motion-processing-actions).

### Model and firmware catalog

The GUI includes an editable **Camera models and firmware** catalog seeded with 12 model/hardware combinations. `models.toml` is separate from individual camera inventory and can be edited over the terminal. Add/edit models in the GUI and link cameras to the exact model/hardware/region. Checks list official firmware candidates; choosing and approving a candidate prepares the local default. A catalog entry does not establish provisioning or upgrade compatibility. See [model catalog](docs/model-catalog.md).

Approved packages are cached under `firmware/` beside the site profile, with checksums and approval metadata in `models.toml`. Offline C340S target import and the intermediate 2.5.1 package are supported. The GUI defaults to **Update to default approved firmware after initialization**; **Keep existing firmware** is available for the inspected preserved-firmware paths. **Initialize only** activates an inspected camera and verifies login without site, firmware or network writes.

The integrated C340S workflow selects the required upgrades and actual configuration schema from authenticated firmware readback. Each real upgrade has its own confirmation and verification; already-installed stages are skipped, and unknown source versions or unverified outcomes stop the run. See [C340S GUI workflow](docs/test-gui.md#c340s-approved-update-and-provisioning) and [firmware packages and prerequisites](docs/firmware-upgrade.md#c340s-v1-staged-upgrade-experiment).

Both C340S test units now run 3.2.1. The earlier preserved 2024 unit was used for the successful continuous two-stage GUI test. Its earlier preserved-firmware results remain valid, but repeating the actual old-to-new upgrade route requires another older-stock unit.
