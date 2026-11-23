# Local test GUI

Start on Ubuntu with the existing virtual environment active:

```bash
cd /opt/vigi-provisioner
PYTHONPATH=src python -m vigi_provisioner.vigi_test_gui \
  --inventory "$HOME/vigi-test-inventory.sqlite3" \
  --config provisioning.toml
```

Open http://127.0.0.1:8765 in the Ubuntu browser. From Windows, forward the local port with `ssh -L 8765:127.0.0.1:8765 USER@UBUNTU_ADDRESS`, then open the same local URL. The default bind address is Ubuntu loopback. To serve the GUI on the VM management interface, add `--bind 192.168.10.143` and open http://192.168.10.143:8765 from Windows. Requests must use that configured address. The service has no user login, so this listener gives management-LAN clients access to the provisioning controls and credential prompts. Camera traffic continues to use the existing camera-facing interface at 192.168.0.10.

Enter scanned Device ID, MAC and label serial, model and the approved IP/netmask/gateway. The form adds inventory records and enforces unique IDs, MACs and target IPs. Existing records are displayed. Use Edit serial on a row to add or correct its label serial. Use Delete on a row and accept the confirmation showing the Device ID to remove the inventory record. The camera keeps its configured settings. Deletion is blocked while a provisioning run is active. General record editing is still pending. Additional models can be recorded. The current provisioning engine still requires the tested VIGI C320I and lab subnet.

Select a factory-state camera and start provisioning. The step log streams output from the existing CLI. Answer fingerprint approval and target-IP confirmation prompts with the values requested. Password and recovery-email inputs are hidden and sent to the worker in memory. Credentials are not put in the database or log.

The GUI adds label serial, firmware, status, observation metadata and last-run time columns to the inventory. UDP discovery observations are retained with the selected record. After ONVIF verifies the static address, an authenticated GetDeviceInformation query collects firmware, model, manufacturer, serial and hardware ID in observation metadata. Firmware is displayed in the table. Missing observations remain unknown. The label serial is operator-supplied and is used as the HTTPS device name (system.sys.dev_alias), preserving the entered capitalization. The workflow reads the name back after writing it. The serial is independent of the QR identity field. The engine authorizes the camera using its MAC and Device ID.

One run can be active at a time. Keep the GUI server running through completion. Closing the browser allows reconnection to the current prompts. The interface uses the existing provisioning engine and its site TOML, certificate approval and ONVIF/HTTPS verification.

The GUI completed a live factory-to-configured Ubuntu run, including certificate confirmation at both addresses, regional and clock configuration, ONVIF network verification and saved/active DNS verification. A separate HTTPS test verified setting Device Name to the inventory label serial. Firmware metadata collection was added after that GUI run and remains to be verified in a subsequent GUI run.

New inventory records show `unverified` until a provisioning run checks the camera. Entering a label does not establish factory state. Existing records retain their stored status, including `ready`. Deleting a camera removes its inventory row and status. Re-adding that camera creates a new `unverified` record. Completed runs show `verified`, active runs show `running`, and interrupted runs show `stopped`.

The shared profile includes video and Platform Access settings. The full factory-reset GUI cycle confirmed the intended main-stream configuration and disabled Platform Access. Existing inventory statuses are preserved, and new records start unverified.

With [osd] enabled in the site profile, the selected inventory row must contain a label serial. Use Edit serial before starting provisioning if needed. The workflow stores that serial in OSD label 1 while leaving its overlay disabled, shows only the date at the saved upper-right position, and checks readback before the network move.

The same site profile can enable microphone, motion detection and login-error exception provisioning. Copy their tables from provisioning.example.toml to the local provisioning.toml before restarting the GUI. The step log reports each read, required write and verification. A missing table skips that optional stage. Newly added profile stages have browser write/readback evidence and offline simulation coverage; their integrated live run remains pending.

The Connected factory default cameras panel contains Discover uninitialized cameras for a read-only UDP probe from the camera-facing 192.168.0.10 interface. It shows all fields decoded by the current parser for factory_flag 0 replies, including MAC, source IP, model, firmware when present, manufacturer, device name, ONVIF endpoint and advertised password/digest capabilities. The tested QR wrapper is decoded into Device ID and also shown raw. Label serial must still be scanned; the legacy parser's serial field actually carries the QR data. Identical replies are deduplicated. The probe does not add inventory records or send credentials. Discovery and provisioning cannot run at the same time.

Confirmation and password inputs appear above the Provisioning steps log. The current question identifies whether to approve a fingerprint, confirm the reserved IP, or enter credentials. Responses are submitted with Confirm / Continue.

The optional firmware stage runs after activation. Its UPGRADE confirmation uses the same input above the log. Firmware upload and subsequent ONVIF version observations appear in the step log. A changed post-upgrade certificate requires approval before the workflow sends credentials again. Site settings follow fresh login.

## Existing firmware and automatic compatibility

The Firmware handling selector defaults to **Keep existing firmware (no upgrade)** for each page load. The server also defaults missing upgrade choices to false and validates the choice as a boolean. This passes `--skip-firmware` through the GUI worker to the common workflow, even when the site profile enables upgrades. Select **Allow firmware upgrade configured in provisioning.toml** to permit the configured upgrade stage; existing firmware identity, file verification and typed UPGRADE confirmation remain required. The selector cannot be changed during a run.

Both choices use automatic activation-format detection. On the tested C320I hardware 1.20 with 2.0.4 preserved, the workflow uses legacy activation, the older motion table and ONVIF port 2020. Absent date/time-format fields and the two unavailable motion fields are reported explicitly in the log. Capture, the full-image region, 24/7 schedule, other supported settings, static addressing and saved/active DNS still require readback. The complete preserved-2.0.4 CLI cycle passed automated readback and operator visual inspection. The new GUI firmware selector awaits its first hardware run. This evidence does not establish compatibility with untested models or firmware builds.
