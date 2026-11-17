# VIGI C320I provisioning workflow

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
4. The browser also sent the device alias and clock in separate requests. The six-field workflow requires the time-zone configuration. Reproducing the browser's clock, name, telemetry and audio writes is a separate scope decision.

See [TP-Link UDP discovery](tplink-discovery.md) for packet framing and the distinction from the legacy UDP code.

## 2. Inventory and set static IPv4 over ONVIF

1. Use the confirmed ONVIF endpoint and working credentials to read device information, interface token, interface MAC, current IPv4 and prefix, DHCP state and gateway. Use these observations to identify the inventory entry and the intended interface.
2. Retrieve the approved static assignment. Build and validate both ONVIF SOAP requests against it. The IPv4 prefix encodes the netmask, so a prefix of `24` corresponds to `255.255.255.0`.
3. Send `SetNetworkDefaultGateway` first and `SetNetworkInterfaces` second. Stop the sequence at an unconfirmed operation. If the interface changes address before replying, check the new address before attempting another write.
4. At the new address, read back the same MAC and interface token, IPv4 and prefix, DHCP disabled and intended gateway. Store acknowledgement and verification separately if using the SQLite provisioning state manager.

See [ONVIF network management](onvif-network.md) for SOAP structure, transport limits and result handling.

## Hardware evidence and integration status

| Evidence | Result |
| --- | --- |
| Steps 807 and 810/810B | Historical test record reports successful real-camera discovery and factory initialization. The exact activation launcher is unavailable in the surviving transcript. |
| Steps 815 and 817 | Historical record reports discovery-to-ONVIF integration and automatic inventory. |
| Step 838 | Historical record reports the reusable HTTPS client passed on hardware. The exact test operations are unavailable in the surviving transcript. |
| Step 880 | The saved result records acknowledgement of both ONVIF writes to move the camera to `192.168.0.150/24` with gateway `192.168.0.1`. |
| Ubuntu, C320I firmware `2.2.1 Build 260605 Rel.12620n` | Live discovery passed. After browser activation, a standalone Python script passed certificate-pinned HTTPS login and the combined regional write. Separate browser reads confirmed time zone and frequency. Live ONVIF reads and writes passed, with authenticated readback at `.150` confirming static IPv4, DHCP disabled and the gateway. |

A later factory-reset Ubuntu run passed pinned HTTPS activation, fresh login, regional write and readback, and ONVIF static IPv4 readback at the new address. These were separate commands. The one-command CLI subsequently passed on a factory-reset C320I with the SQLite inventory and local TOML profile. Terminal approval replaced the browser fingerprint step. The CLI read the recovery email from TOML and verified English, UTC+02:00 / Europe/Vilnius, 50 Hz and the approved static address through authenticated readback. Country/Region read back empty. The recovery email was submitted without independent readback.

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
