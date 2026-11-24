# Local test GUI

Start on Ubuntu with the existing virtual environment active:

```bash
cd /opt/vigi-provisioner
PYTHONPATH=src python -m vigi_provisioner.vigi_test_gui \
  --inventory "$HOME/vigi-test-inventory.sqlite3" \
  --config provisioning.toml
```

Open http://127.0.0.1:8765 in the Ubuntu browser. From Windows, forward the local port with `ssh -L 8765:127.0.0.1:8765 USER@UBUNTU_ADDRESS`, then open the same local URL. The default bind address is Ubuntu loopback. To serve the GUI on the VM management interface, add `--bind 192.168.10.143` and open http://192.168.10.143:8765 from Windows. Requests must use that configured address. The service has no user login, so this listener gives management-LAN clients access to the provisioning controls and credential prompts. Camera traffic continues to use the existing camera-facing interface at 192.168.0.10.

Enter scanned Device ID, MAC and label serial, model and the approved IP/netmask/gateway. The form adds inventory records and enforces unique IDs, MACs and target IPs. Existing records are displayed. Use Edit serial on a row to add or correct its label serial. Use Delete on a row and accept the confirmation showing the Device ID to remove the inventory record. The camera keeps its configured settings. Deletion is blocked while a provisioning run is active. General record editing is still pending. Additional models can be recorded. The current provisioning engine supports the tested C320I and C340S paths on the lab subnet.

Select a factory-state camera and start provisioning. The step log streams output from the existing CLI. Answer fingerprint approval and target-IP confirmation prompts with the values requested. Password and recovery-email inputs are hidden and sent to the worker in memory. Credentials are not put in the database or log.

The GUI adds label serial, firmware, status, observation metadata and last-run time columns to the inventory. UDP discovery observations are retained with the selected record. After ONVIF verifies the static address, an authenticated GetDeviceInformation query collects firmware, model, manufacturer, serial and hardware ID in observation metadata. Firmware is displayed in the table. Missing observations remain unknown. The label serial is operator-supplied and is used as the HTTPS device name (system.sys.dev_alias), preserving the entered capitalization. The workflow reads the name back after writing it. The serial is independent of the QR identity field. The engine authorizes the camera using its MAC and Device ID.

One run can be active at a time. Keep the GUI server running through completion. Closing the browser allows reconnection to the current prompts. The interface uses the existing provisioning engine and its site TOML, certificate approval and ONVIF/HTTPS verification.

The GUI completed a live factory-to-configured Ubuntu run, including certificate confirmation at both addresses, regional and clock configuration, ONVIF network verification and saved/active DNS verification. A separate HTTPS test verified setting Device Name to the inventory label serial. Firmware metadata collection was added after that GUI run and remains to be verified in a subsequent GUI run.

New inventory records show `unverified` until a provisioning run checks the camera. Entering a label does not establish factory state. Existing records retain their stored status, including `ready`. Deleting a camera removes its inventory row and status. Re-adding that camera creates a new `unverified` record. Completed runs show `verified`, active runs show `running`, and interrupted runs show `stopped`.

The shared profile includes video and Platform Access settings. The full factory-reset GUI cycle confirmed the intended main-stream configuration and disabled Platform Access. Existing inventory statuses are preserved, and new records start unverified.

With [osd] enabled in the site profile, the selected inventory row must contain a label serial. Use Edit serial before starting provisioning if needed. The workflow stores that serial in OSD label 1 while leaving its overlay disabled, shows only the date at the saved upper-right position, and checks readback before the network move.

The same site profile can enable microphone, motion detection and login-error exception provisioning. Copy their tables from provisioning.example.toml to the local provisioning.toml before restarting the GUI. The step log reports each read, required write and verification. A missing table skips that optional stage. These profile stages have passed integrated CLI and GUI hardware runs; unavailable fields on the preserved legacy path are reported explicitly.

The Connected factory default cameras panel contains Discover uninitialized cameras for a read-only UDP probe from the camera-facing 192.168.0.10 interface. It shows all fields decoded by the current parser for factory_flag 0 replies, including MAC, source IP, model, firmware when present, manufacturer, device name, ONVIF endpoint and advertised password/digest capabilities. The tested QR wrapper is decoded into Device ID and also shown raw. Label serial must still be scanned; the legacy parser's serial field actually carries the QR data. Identical replies are deduplicated. The probe does not add inventory records or send credentials. Discovery and provisioning cannot run at the same time.

Confirmation and password inputs appear above the Provisioning steps log. The current question identifies whether to approve a fingerprint, confirm the reserved IP, or enter credentials. Responses are submitted with Confirm / Continue.

The optional firmware stage runs after activation. Its UPGRADE confirmation uses the same input above the log. Firmware upload and subsequent ONVIF version observations appear in the step log. A changed post-upgrade certificate requires approval before the workflow sends credentials again. Site settings follow fresh login.

## Existing firmware and automatic compatibility

The Firmware handling selector now defaults to **Update to default approved firmware after initialization**. This requires an exact catalog link and an approved cached image; see [firmware downloads](model-catalog.md#default-approved-firmware-and-local-downloads). Select **Keep existing firmware (no upgrade)** to preserve stock firmware. The server also defaults missing upgrade choices to false and validates the choice as a boolean. This passes `--skip-firmware` through the GUI worker to the common workflow, even when the site profile enables upgrades. Select **Allow firmware upgrade configured in provisioning.toml** to permit the configured upgrade stage; existing firmware identity, file verification and typed UPGRADE confirmation remain required. The selector cannot be changed during a run.

Both choices use automatic activation-format detection. On the tested C320I hardware 1.20 with 2.0.4 preserved, the workflow uses legacy activation, the older motion table and ONVIF port 2020. Absent date/time-format fields and the two unavailable motion fields are reported explicitly in the log. Capture, the full-image region, 24/7 schedule, other supported settings, static addressing and saved/active DNS still require readback. The complete preserved-2.0.4 CLI cycle passed automated readback and operator visual inspection. The new GUI firmware selector passed a complete hardware run with Keep existing firmware selected; firmware upgrading was disabled, all supported stages passed readback, and ONVIF inventory metadata was collected. This evidence does not establish compatibility with untested models or firmware builds.

## Model catalog

The model/hardware selector and Camera models and firmware panel use local `models.toml`. See [catalog operations](model-catalog.md). Existing inventory databases receive nullable catalog/hardware columns without rewriting existing records. Keep the local catalog alongside the inventory backup. Firmware-page checks only read official web pages and preserve the recorded firmware choice.

## Initialization-only compatibility tests

Select **Initialize only (no update, settings or IP change)** for the inspected C340S/C320I activation flows. This is an explicit mode, not the default approved-update mode. Inventory Device ID, MAC, model and factory-state discovery must match. The recognized activation resource is fetched through pinned HTTPS before credentials are submitted. Type `INITIALIZE <Device ID>` at the confirmation prompt.

Only account activation (admin password, recovery-email submission and language) and fresh login are performed, followed by an optional authenticated read of device model/hardware/firmware. Regional, date/DST/NTP, alias, video, cloud, OSD, audio, motion, exceptions, network and DNS configuration are not performed. No firmware preparation/upload stage can be entered. Inventory status becomes `initialized`, not `verified`. The desired static address in inventory is left unapplied; the camera remains at the discovered factory address.

The factory-new C340S probe confirmed the printed/inventory/discovery identity and the exact legacy Initial.htm hash. Initialization-only simulations and worker argument checks passed. Real C340S account activation, fresh login and metadata readback passed on firmware 2.0.3 Build 240412 Rel.42481n, hardware 1.0. Full provisioning supports the tested preserved C340S hardware 1.0 paths on 2.0.3 and 3.2.1, with approved updating available through the inspected route below. Approved updating is now available through the inspected two-stage route. No additional model support is inferred from a shared page signature.

## C340S V1 full provisioning with existing firmware

The C340S hardware 1.0 test passed staged hardware checks: initialization-only in the GUI, site-profile writes/readback, and ONVIF port-2020 static addressing followed by HTTPS saved/active DNS verification at 192.168.0.160/24. Firmware remained 2.0.3 Build 240412 Rel.42481n. No reboot was requested, and the original HTTPS certificate remained valid after the network move in that test.

For the combined GUI test, factory-reset the camera, select its inventory row, choose **Keep existing firmware (no upgrade)**, and start provisioning. The engine checks the inventory model and accepted hardware revision, MAC, Device ID and exact QR suffix (`040` for this model). After account activation/login it confirms the authenticated ONVIF model, MAC, hardware and exact tested firmware before site writes. Unknown versions stop; catalog-approved C340S upgrading is now supported, while profile-controlled C340S updating remains blocked. The requested static address comes from inventory. Normal certificate/IP confirmations and password entry still apply. Successful full runs use status `verified` and collect ONVIF firmware/hardware metadata.

Legacy limitations remain explicit: date/time format fields are absent, and object-filter/report-server motion fields are unavailable in the observed schema. All other configured fields require matching readback. Country BG is intent only where camera readback is empty, and recovery-email submission has no independent readback. The combined factory-to-configured GUI run passed all supported-setting, network, DNS and metadata readbacks; these staged results do not imply support for other C340S firmware or models.

## C340S approved update and provisioning

The combined GUI sequence is now **discover → activate → identify current firmware → intermediate 2.5.1 if needed → target 3.2.1 if needed → choose actual configuration schema → site settings → static network → DNS**. Each real upgrade retains its typed device-ID/version confirmation. After each upgrade, authenticated ONVIF version verification must pass, the HTTPS certificate is checked again, and a fresh login is made before proceeding. An unverified upgrade stops the run before site settings. The combined automatic chain has offline coverage; its first hardware run is pending. The individual upgrades, modern settings and port-80 network/DNS stages have passed hardware tests.

Preparation:

1. Link the camera to the exact **VIGI C340S V1 UN** catalog entry.
2. Download and approve its inspected **3.2.1 Build 260320** default target image.
3. Use **Prepare intermediate 2.5.1** to cache the inspected intermediate ZIP without changing the default target. On offline systems, the previously transferred `$HOME/vigi-c340s-2.5.1.zip` is the default fallback; `--c340s-bridge-package /path/to/package.zip` overrides it when launching the GUI.
4. Choose **Update to default approved firmware after initialization** and start a factory-state run. Both image/package checks occur before activation, including when the camera is already at the target version.

The intermediate package path/hash are stored as `bridge_package` / `bridge_sha256` in the model catalog. The exact known ZIP and image hashes are enforced independently of those editable fields. Current source 2.0.3 uses both stages, 2.5.1 skips the first stage, and 3.2.1 skips both. Unsupported firmware stops. Preserve mode supports the verified legacy 2.0.3 and modern 3.2.1 settings; configuration on intermediate 2.5.1 remains intentionally blocked.

Actual firmware selects the settings path, not the activation family or build year: legacy 2.0.3 omits its four unavailable fields; 3.2.1 uses complete clock verification and the modern versioned motion query. The latter is important because the legacy motion read still succeeds but hides object-filter state on 3.2.1. ONVIF is probed on 80 first, then 2020 for connection failures; the verified port is retained for network changes, readback and inventory metadata. The known 3.2.1 web bundle signature was verified read-only against the upgraded camera and is accepted as a modern activation builder; the first factory-reset activation test on that firmware is pending.

Do not upgrade the preserved 2024 reference camera merely to repeat the combined chain. Factory-resetting the upgraded camera retains 3.2.1 and can test the already-installed-target branch, activation and modern provisioning. A fresh older-stock unit would be needed to repeat both real upgrades without consuming the reference unit.

For an offline Ubuntu host, import the already-transferred 3.2.1 ZIP from the C340S catalog row instead of downloading again. Leave the 2.5.1 ZIP at its default home-directory path or pass --c340s-bridge-package. Local browser testing passed both target import and intermediate preparation, preserving the approved 3.2.1 target. No camera upgrade was performed during these GUI preparation tests.
