# TP-Link VIGI provisioning workflow

## Run the workflow on Ubuntu

The CLI targets one factory-state C320I at `192.168.0.60` using the existing lab transport on Ubuntu `192.168.0.10`. Verify the fresh post-reset certificate fingerprint in the browser, leave the wizard unsubmitted, and reserve the intended static address before starting. From the project checkout with its existing virtual environment active, run:

```bash
PYTHONPATH=src python -m vigi_provisioner.vigi_factory_workflow \
  --mac 18-69-45-9f-31-f7 \
  --pin YOUR_VERIFIED_SHA256_FINGERPRINT \
  --target-ip 192.168.0.150 --prefix 24 --gateway 192.168.0.1
```

Type the target IP to confirm it is unused and reserved. Enter the shared admin password at the prompt. Enter the recovery email if you have no site profile. The CLI checks factory state before activation, verifies the new password and regional settings, then reads back the ONVIF settings at the new address. If it stops after a write, inspect the current camera state before continuing. Restarting the command requires confirmed factory state. The workflow leaves SQLite records alone.

### Shared site settings

Copy [provisioning.example.toml](../provisioning.example.toml) to `provisioning.toml` and set the site's recovery email. The CLI reads this file from its working directory or accepts an explicit `--config /path/to/provisioning.toml`. The local file is ignored by Git. An explicit missing or invalid file stops the run before discovery. Without a site file, the CLI keeps its existing defaults and prompts for the recovery email.

The C320I workflow requires `admin`. The profile supplies the language and regional settings. The country is local profile metadata, while the camera's Country/Region value is reported separately. Enter the shared password at the hidden prompt for each run. The profile has no password field.

The example's optional `[clock]` section configures DD-MM-YYYY, 24-hour time, manual DST (+60 minutes from the last Sunday in March at 03:00 to the last Sunday in October at 04:00), and NTP at `84.54.128.102:123` every 60 minutes. Copy the clock tables into an existing local profile to enable them. The CLI applies date/DST and custom NTP in separate HTTPS writes and checks their readback before ONVIF. Readback verifies configuration. The camera needs network access to the NTP server to synchronize.

The optional `[dns]` table supplies primary and secondary IPv4 resolvers. After ONVIF verifies the new address, the CLI opens a fresh HTTPS session at that address and checks the original certificate pin. If it differs, inventory runs using terminal trust show the new fingerprint and require approval before DNS login. Runs started with an independently verified `--pin` require a newly verified fingerprint. It writes only `protocol.static.pri_dns` and `snd_dns` and checks both saved and active values while checking the approved IP, netmask and gateway. The active values can lag behind the saved values. The C320I bench test confirmed both DNS fields via HTTPS. ONVIF SetDNS changed only the primary in that test.

### Inventory-driven bench test

Supply a local SQLite database with a `camera_inventory` table containing `device_id`, `mac_address`, `model`, `approved_ipv4`, `prefix_length`, and `gateway_ipv4`. Store the printed ID and MAC. The database is opened read-only. For the tested C320I, UDP field `0x0018` contains `TP1` plus the printed ID plus `020`. The workflow checks this value and the MAC before fetching a certificate.

```bash
PYTHONPATH=src python -m vigi_provisioner.vigi_factory_workflow \
  --inventory "$HOME/vigi-test-inventory.sqlite3" \
  --device-id 1326062CFD849E902
```

On the isolated provisioning segment, review the inventory match and observed SHA-256 fingerprint and type `APPROVE` to trust the observed certificate for that run. This is first-use trust. A separately verified `--pin` can be supplied instead. The workflow pins subsequent HTTPS requests and does not persist the observed certificate.

## 1. Discover over TP-Link UDP and initialize over HTTPS

1. Broadcast the TP-Link discovery probe on UDP port 5001 from the camera-facing interface. Record the reply source IPv4, MAC, model, factory flag and advertised ONVIF endpoint. Match the MAC to the intended camera. A factory flag of `0` is a hint from discovery.
2. On a confirmed factory-state camera, create the `admin` account over HTTPS port 443 with the chosen password, recovery email and language. The browser uses `POST /` with `method: do` and a `set_password` object. See the [HTTPS guide](https-initialization.md) for the difference between the captured browser request and the current packaged builder.
3. Authenticate with the new credentials, then apply the combined time-zone and frequency settings through the authenticated HTTPS session. Check both settings with separate reads. For the Bulgaria profile, the verified values are English, `UTC+02:00`, `Europe/Vilnius` and `50hz`. Keep `BG` as a provisioning input. The camera's `system.basic.country_region` read back empty.
4. After login, the workflow applies a nonempty inventory label serial to `system.sys.dev_alias` and verifies its readback. The browser's separate clock, telemetry and audio writes are outside the current factory workflow.

See [TP-Link UDP discovery](tplink-discovery.md) for packet framing and the distinction from the legacy UDP code.

## 2. Inventory and set static IPv4 over ONVIF

1. Use the confirmed ONVIF endpoint and working credentials to read device information, interface token, interface MAC, current IPv4 and prefix, DHCP state and gateway. Use these observations to identify the inventory entry and the intended interface.
2. Retrieve the approved static assignment. Build and validate both ONVIF SOAP requests against it. The IPv4 prefix encodes the netmask, so a prefix of `24` corresponds to `255.255.255.0`.
3. Send `SetNetworkDefaultGateway` first and `SetNetworkInterfaces` second. Stop the sequence at an unconfirmed operation. If the interface changes address before replying, check the new address before attempting another write.
4. At the new address, read back the same MAC and interface token, IPv4 and prefix, DHCP disabled and intended gateway. Store acknowledgement and verification separately if using the SQLite provisioning state manager.

See [ONVIF network management](onvif-network.md) for SOAP structure, transport limits and result handling.

## 3. Apply DNS at the verified static address

The factory-to-configured Ubuntu run verified the optional clock and DNS profiles on the C320I. HTTPS clock readback matched the date format, manual DST, and custom NTP configuration before the ONVIF address move. The camera presented a different HTTPS certificate at `192.168.0.150` than at `192.168.0.60`. After terminal approval of the new fingerprint, the CLI logged in and verified saved and active DNS at `84.54.128.100` and `8.8.8.8`. The IP, netmask, and gateway matched the approved assignment during DNS readback. The firmware trigger for the certificate change is unknown.

## Files used by each stage

| Area | Python files and their roles |
| --- | --- |
| Active discovery | `vigi_discovery.py` broadcasts and parses replies. `vigi_discovery_adapter.py` normalizes observations. `vigi_discovery_evidence.py` validates their shape and freshness. |
| Identity and TLS | `vigi_camera_binding.py` maintains expiring bindings. `vigi_enrollment_binding.py` joins fresh evidence to approval. `vigi_pin_inventory.py` stores approved pins. `vigi_certificate_pin.py` compares fingerprints. `vigi_pinned_tls.py` opens and verifies a TLS connection. `vigi_tls_authorization.py` and `vigi_authorized_gateway.py` enforce approval. `vigi_camera_gateway.py` combines discovery, inventory and the gateway. `vigi_tls.py` builds the separate CA-bundle context. |
| Activation preparation | `vigi_activation.py` builds the existing account payload with helpers `vigi_password.py` and `vigi_rsa.py`. `vigi_activation_safety.py` and `vigi_activation_guard.py` check prerequisites. `vigi_preflight.py` and `vigi_preflight_diagnostics.py` expose diagnostic observations. `vigi_https_client.py` is the older diagnostic client, which disables certificate validation. `vigi_https_init.py` packages the request. `vigi_initialization_config.py` and `vigi_initialization_dry_run.py` prepare offline settings. `vigi_inventory_initialization.py` looks up the selected camera. |
| Activation execution boundary | `vigi_initialization_validator.py`, `vigi_http_request.py` and `vigi_http_encoder.py` validate and serialize. `vigi_initialization_coordinator.py`, `vigi_http_sender.py`, `vigi_https_transport.py` and `vigi_initialization_execution.py` expose preparation or disabled live entry points. `vigi_initialization_authorization.py` owns single-use approval. `vigi_initialization_execution_plan.py`, `vigi_identity_bound_transport.py` and `vigi_gateway_transport_lease.py` bind identity and transport ownership. |
| Attempt and response helpers | `vigi_initialization_attempt.py` and `vigi_fixed_initialization_attempt.py` handle supplied transports. `vigi_write_deadline.py`, `vigi_socket_deadline.py` and `vigi_deadline_stream.py` bound I/O. `vigi_http_stream.py`, `vigi_http_reader.py` and `vigi_http_response.py` read and parse HTTP. `vigi_initialization_result.py` checks camera success. `vigi_response_pipeline.py` composes the read and validation steps. |
| ONVIF reads and inventory | `vigi_onvif.py` reads device identity. `vigi_onvif_network.py` reads interfaces and gateways. `vigi_device_record.py` merges observations. `vigi_inventory.py` provides MAC lookup and normalization. `vigi_camera_inventory.py` maintains inventory records. |
| ONVIF plan and write | `vigi_static_ip_assignments.py` records approval. `vigi_static_ip_plan.py` builds an inventory-backed plan. `vigi_onvif_gateway_config.py` and `vigi_onvif_static_ip.py` construct SOAP. `vigi_static_ip_execution_plan.py` and `vigi_onvif_soap_strict.py` validate the request. `vigi_static_ip_coordinator.py` orders the writes. `vigi_onvif_live_transport.py` sends them to its fixed lab endpoint. `vigi_onvif_config_transport.py` supplies the separate test transport. |
| ONVIF readback and evidence | `vigi_onvif_config_response.py` classifies acknowledgements. `vigi_static_ip_verification.py` compares fresh observations with the plan. `vigi_provisioning_evidence.py` binds evidence to the assignment. `vigi_provisioning_state.py` records SQLite state transitions. |

See the [Python file reference](python-reference.md) for links to every package file, legacy UDP and Solar modules, scripts and tests.

### Inventory serial as Device Name

When the inventory has a nonempty `label_serial`, the workflow applies that exact value to `system.sys.dev_alias` after login and verifies the URL-decoded readback. For the test camera, enter `22630k7001456` in the GUI serial field. Existing inventories without a serial retain their current naming behavior. A live authenticated HTTPS test on the configured camera at 192.168.0.150 set and read back `22630k7001456` successfully without a factory reset. The complete factory workflow includes this step after login. A subsequent factory-reset GUI run confirmed the intended configuration after deleting and re-adding the test record.

### Main-stream video profile

Copy the optional [video] table from provisioning.example.toml into the site profile. The current implementation accepts the tested H265, 1920x1080, 15 fps, VBR High (quality 5), 2048 kbps profile with smart codec disabled. It writes the complete observed video.main payload over pinned HTTPS after regional settings and before the ONVIF IP move, then verifies every requested field. The firmware encodes 15 fps as 65551. ONVIF configured the base encoder successfully but the UI showed H265+ until smart_codec was disabled through HTTPS. The complete HTTPS request and readback passed on hardware. The subsequent full factory-reset and provisioning cycle confirmed the intended video configuration.

### Platform Access

The optional `[platform_access]` table has a boolean `enabled` setting. Set it to `false` to disable Platform Access. The workflow reads `cloud_config.cloud_connect.enable`, writes `off` if required, and verifies the result before the ONVIF network move. The browser write and subsequent readback returned code zero with `enable: off` on the test camera. The subsequent full factory-reset and reconfiguration cycle confirmed that Platform Access remained disabled.

### OSD layout and inventory serial

The optional [osd] table applies the tested date-only layout at x=7749, y=0 with automatic font size and adaptive white color. The weekday and three text labels are disabled. Label 1's stored text is the exact inventory label serial, even while its overlay is disabled. An inventory serial is required before activation when this section is present. The workflow preserves the other labels' coordinates and text and verifies all requested OSD fields after writing. The date-only layout passed browser write/readback on the test camera; the integrated serial-text write passed CLI and GUI hardware runs.

The OSD coordinates are camera values captured from the web UI, rather than pixel positions. Factory values such as x=312 and y=9222 suggest a normalized scale near 0–10000, but the scale and anchor point have not been confirmed in firmware. On that assumed scale, x=7749 is 77.49 percent across the image, about 1488 pixels at 1920 width. The UI-selected position accommodates the date text extending toward the right edge. Use the captured coordinates for the tested 1920x1080 layout and verify placement visually when testing another resolution or font.

### Microphone profile

The optional [audio] table sets microphone mute on, noise cancellation off and volume 75, using G711alaw, sampling rate 8, one channel and MicIn. The workflow writes audio_config.microphone and verifies the returned fields before the network move. Numeric fields may be strings in the camera readback. Bitrate 64 and echo cancellation off were observed but are omitted from the write, matching the browser payload. This profile does not configure audio recording. The browser and integrated CLI/GUI write/readback passed on hardware.

### Basic event motion detection

The optional [motion_detection] table enables sensitivity 85, object filtering off, people and vehicle flags on, medium target validity and 24/7 arming. Recording and snapshots are on; push messages, server reporting, email, FTP, light/sound alarms and AO1 are off. Target tracking is omitted from the write, matching the observed browser payload; its existing flag was on in the test readback.

The workflow uses separate configuration and schedule reads, normalizes numeric strings and URL-decoded daily schedules, and verifies the full-image polygon before changing settings. It stops if a different region is observed because polygon writes have not been tested. The browser writes and all seven schedule readbacks passed on the test camera. The integrated motion profile passed live GUI runs, including all processing actions off on the current C340S run.

### Login-error exception

The optional [login_error] table reproduces the verified disabled configuration with max_num_err=5. The workflow reads unusual_detection.login_error, sends enabled off and numeric max_num_err 5 if needed, and verifies readback before the network move. The camera returned max_num_err as a string. Push and light-alarm settings are omitted from the write; both were off in the observed readback. The browser write and reload confirmed enabled off. The precise effect of this exception setting on login lockout has not been tested. The integrated profile passed CLI and GUI hardware runs.

### Firmware stage before configuration

Enable the optional [firmware] table to check and upgrade immediately after account activation and login. See [firmware upgrade](firmware-upgrade.md) for the inspected package and currently supported source version. The GUI asks for separate upload confirmation, verifies the target firmware through ONVIF after reboot, and completes certificate approval and fresh HTTPS login before applying the site settings. If the target version is already installed, it skips the upload. The combined factory workflow passed activation, an actual 2.0.4-to-2.2.1 upgrade, fresh login and complete site configuration on hardware.

## Preserved C340S test path

Inventory-driven full provisioning also accepts the inspected C340S V1 flow only with firmware upgrading disabled. The `040` discovery QR wrapper, legacy-2024 activation signature, and authenticated ONVIF model/MAC/hardware/firmware are checked. The source firmware must be 2.0.3 Build 240412 Rel.42481n on hardware 1.0. Staged account, site settings, static network and DNS tests passed; the preserved-firmware and continuous two-stage-upgrade GUI cycles passed hardware readback. See [C340S mode](test-gui.md#c340s-v1-full-provisioning-with-existing-firmware).

### Motion event processing actions disabled

The current desired motion profile uses `record = false`, mapping to `motion_detection.motion_notif_list.record_enabled = "off"`. This unchecks Event → Basic Event → Motion Detection → Processing mode → Record. Prior hardware tests used record enabled; those results describe the earlier profile. Existing local `provisioning.toml` files must be updated explicitly because Git updates do not overwrite them. The workflow verifies the requested flag after writing, for both legacy and modern motion schemas. Snapshot capture is also disabled with `snapshots = false`; the current desired profile has all motion processing actions off. This field controls motion-triggered recording only; it does not configure continuous recording, recording schedules, NVR recording or audio recording.

The all-off processing profile disables record, snapshot capture, FTP, push, alarm-server reporting, email, sound, light and alarm output. When all configured notification actions are off, the workflow also disables the observed client/app notification and target-tracking action flags if present. It refuses to claim all-off if another unrecognized enabled action remains. Motion detection itself, sensitivity, people/vehicle selection, full-image region and the 24/7 arming schedule remain configured. This is specific to motion-event processing; other event pages and continuous/NVR recording are separate settings.
