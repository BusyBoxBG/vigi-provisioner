# Factory camera initialization over HTTPS

The project implements request preparation, target approval, and transport-independent attempt handling. **Use the [factory workflow CLI](provisioning-workflow.md#run-the-workflow-on-ubuntu) for live factory activation.** The older initialization entry points described below remain dry-run or disabled. Running a dry run does not set the camera password. The ONVIF guide starts with a camera that already has working credentials. Historical Step 810B reports successful hardware activation. The exact launcher behind that pass is unavailable. A later Ubuntu run verified activation and fresh login with standalone commands. The consolidated CLI also passed factory activation and fresh login on the C320I using the SQLite inventory and TOML profile. The recovery email was submitted during activation. The test did not independently read it back.

## 1. Find the camera and establish the target

Use [TP-Link discovery](tplink-discovery.md) from the camera-facing interface. The activation predicate in `vigi_activation_safety.py` requires all three of the following.

| Evidence | Required value |
| --- | --- |
| Inventory identity | Expected MAC match |
| Discovery factory flag | Integer `0` |
| HTTPS application state | `-40405` |

The diagnostic preflight calls the proprietary `get` for `system.basic` and reads the nested camera code. Its legacy HTTPS client disables certificate verification, so this observation cannot establish identity. A connection failure or missing code is insufficient. Treat discovery state and the HTTPS code as observations tied to firmware behavior.

The separate gateway path uses an approved MAC, destination IPv4 and port, source IPv4, current binding, and approved certificate pin. The pin is a SHA-256 digest of the DER certificate. Compare it with an independently approved value. This is distinct from the CA bundle helper that establishes a trust store for the dry-run transport. Use fresh local inventory and pin state, outside the checkout.

## 2. Build the initialization request

`prepare_initialization` validates an IPv4 address, a non-boolean TCP port in 1–65535, a nonempty password, and a string recovery email. The normal endpoint is `https://<approved-camera-ip>:443/`. The request is an HTTP POST whose body is compact UTF-8 JSON, with JSON Content-Type and Accept headers.

| JSON field | Purpose |
| --- | --- |
| `method` | `do`, the vendor action selector |
| `set_password.username` | Configured first account, default `admin` |
| `set_password.password` | Vendor MD5-derived password field |
| `set_password.passwdType` | `md5`, the vendor field format |
| `set_password.ciphertext` | Separate RSA-protected password representation |
| `set_password.reset_pwd_email` | URL-encoded recovery email |
| `set_password.preset_ipc_passwd`, `preset_ipc_email` | JSON null placeholders |
| `set_password.language` | Language setting, default `English` |

These transformations implement camera compatibility. Treat the prepared bytes, derived password field, ciphertext and recovery email as sensitive. `PreparedInitialization.summary()` exposes field presence, request metadata and size without returning the body. The separate config and dry-run helpers also build timezone and line-frequency requests. Those helpers do not schedule or transmit them.

## 3. Validate, serialize and approve

`vigi_initialization_validator` checks the prepared URL, method, headers and JSON field types against the approved identity and allowed payload shape. `vigi_http_request` and `vigi_http_encoder` produce fixed HTTP request bytes from validated data. `vigi_http_sender` exposes a send plan and blocks its send entry point.

The execution object reserves the single-use authorization to itself, checks the approved identity again on `execute()`, marks a matching authorization ready, and raises `InitializationExecutionDisabled`. Consuming the approved bytes is a separate operation with renewed gateway validation. `InitializationExecutionPlan` is immutable identity metadata. `GatewayTransportLease` holds a supplied closeable transport for that plan, transfers it on one matching claim, and closes an unclaimed transport at most once. The lease itself does not authenticate TLS or open a connection.

## 4. Understand attempt outcomes

The fixed attempt helper operates on an injected object supporting `send`, `recv`, `settimeout` and `close`. With valid request and transport inputs, it limits the write and read phases to ten seconds each, applies shorter per-call limits, and closes the transport even on error. The helper can be exercised with an in-memory fake. It has no camera connection factory and is not wired to the disabled public send API.

HTTP success requires parsed status `200` and a JSON object with integer `error_code: 0`. The parser rejects ambiguous or unsupported framing, and uses bounded reads. If a write was attempted and the result is missing, malformed, or fails validation, the fixed helper returns `UNKNOWN_OUTCOME`. A connection interruption can occur after the camera has acted. Recheck observed camera state before deciding how to proceed. A cleanup failure is recorded independently of the response result.

## 5. Hand off to ONVIF

When the camera has been initialized and the operator has confirmed that ONVIF credentials work, read its device information and network settings. Use the interface token and MAC returned by that camera to prepare the [static IPv4 workflow](onvif-network.md). This handoff is an operator boundary in the current project.

## C320I browser capture and Ubuntu hardware results

The first browser `POST /` used `method: do` with `set_password`. The captured field names include `username`, `language`, `ciphertext`, `reset_pwd_email`, `pwd_sec_type`, and three security-question and answer pairs. The observed question identifiers were `father_name`, `mother_name`, and `senior_teacher_name`. The existing packaged activation builder above has a different field set. The capture also showed separate requests for `system.boot_set_date.seconds_from_1970` and `system.sys.dev_alias`.

### Verified post-activation HTTPS sequence

A standalone Ubuntu Python test checked the approved SHA-256 certificate fingerprint before sending requests. The camera responded as follows.

| Stage | Request | Hardware result |
| --- | --- | --- |
| Challenge | `POST /` with `method: do` and `user_management.get_encrypt_info: null` | HTTP 401 with `error_code: -40401` and usable mode, key and nonce under `data`. |
| Login | `POST /` with `method: do` and `login` | HTTP 200, `error_code: 0`, top-level `stok`. |
| Regional write | `POST /stok=<redacted>/ds` with `method: set`, `system.basic.timezone: UTC%2B02%3A00`, `system.basic.zone_id: Europe%2FVilnius` and `image.switch.flicker: 50hz` | HTTP 200 and `error_code: 0`. |
| Time-zone read | `method: get`, `system.name: ["basic", "ntp", "dst", "dst_manual"]` | Browser read returned code 0, the expected decoded zone, English, and an empty country field. |
| Frequency read | `method: get`, `image.name: "switch"` | Browser read returned code 0 and `image.switch.flicker: 50hz`. |

The successful mode 2 login used the URL-decoded RSA public key from `key_2` and `keyType: "1"`. The encrypted message was the project's uppercase vendor MD5 value followed by a colon and the fresh nonce. RSA PKCS#1 v1.5 ciphertext was Base64-encoded and then URL-encoded for the password field. Login used `passwdType: "md5"`. Keep live credential values, challenge values and tokens out of logs. The existing Solar modules use a separate HTTP session protocol. The combined speculative GET with empty `system.basic` and `image.switch` returned `-40106`, so use the two observed read shapes.

### Clock and DNS profile readback

The shared TOML clock profile sends a date and DST write under `system.basic` and `system.dst_manual`, followed by a separate `system.ntp` write. The C320I accepted and read back `date_format: 2` (DD-MM-YYYY), `time_format: 0` (24-hour), the configured manual DST schedule, and NTP at `84.54.128.102`, UDP port `123`, interval `60` minutes. Readback verifies configuration. Synchronization depends on reachability of the server.

After live ONVIF readback at the new static IP, the CLI verifies the original certificate pin or obtains explicit approval for a changed certificate. It then sends a DNS-only `set` under `protocol.static` with `pri_dns: "84.54.128.100"` and `snd_dns: "8.8.8.8"`. Success requires those values in both `protocol.static` and `network.wan_status`, with the approved network assignment intact. Active DNS lagged saved DNS during testing.

### Device Name from inventory

The workflow reads the optional inventory `label_serial` before activation. After a fresh login, it reads the current alias with:

```json
{"method":"get","system":{"name":["sys","basic"]}}
```

If it differs, it sends `{"method":"set","system":{"sys":{"dev_alias":"22630k7001456"}}}` for the test record and repeats the read. The alias is URL-encoded for the write and URL-decoded for comparison. The live test at 192.168.0.150 returned code zero for login, the write and verification, with `22630k7001456` read back exactly. This can also be tested on an initialized camera without a reset.

### Country mapping from the Config Tool

The saved Java disassembly copies `country` to the initialization DTO. Its IPC settings builders emit time zone, zone ID and flicker. The NVR branch emits country as `system.basic.location`. A separate European-country branch queries initialization module support. The C320I browser capture showed no country write and returned empty `system.basic.country_region`. Keep `BG` in input metadata and report device-side Country/Region as unverified.

Evidence is from the saved local Config Tool disassembly excerpts `vigi_init_dto_complete.txt`, `vigi_init_json_builders.txt`, and `passthrough_init_service.txt`, plus the C320I browser capture and Ubuntu hardware test. These source artifacts are kept outside the repo.

## Video and Platform Access

The optional [video] profile sets the main stream to plain H265, 1920x1080, 15 fps, VBR High and maximum 2048 kbps. The camera fields are encode_type H265, resolution 1920*1080, frame_rate 65551, bitrate_type vbr, quality 5, bitrate 2048 and smart_codec off. ONVIF reported H265 while the UI showed H265+, so the HTTPS readback explicitly checks smart_codec.

The workflow reads video.name ["main"], writes the requested fields under video.main, then verifies each field. The optional [platform_access] enabled=false maps to a set request under cloud_config.cloud_connect with enable off. The read request uses cloud_config.name ["cloud_connect"]; verification requires enable off. Both stages run before the ONVIF network move. The full factory-reset and reconfiguration cycle confirmed the intended video settings and disabled Platform Access.

## OSD settings

The case-sensitive OSD object is read with method get and OSD containing name ["font", "week", "date"] and table "label_info". The date-only layout was accepted and read back on the test camera with date enabled on at x_coor "7749", y_coor "0", week enabled off, and all three labels enabled off. Font settings are display ntnb, size auto, color_type adapt and color white.

The response returns label_info as an array of objects keyed label_info_1 through label_info_3. Writes place those named objects directly under OSD. Label 1 text is URL-encoded from the inventory label serial. The workflow preserves the other label text and positions, then verifies the date coordinates, font, disabled states and decoded label 1 text. Updating the disabled label text passed integrated CLI and GUI hardware runs. The captured upper-right coordinate is a firmware value; the suspected normalized coordinate scale remains unconfirmed.

## Audio, motion and exception profiles

The optional audio table maps to audio_config.microphone. The verified write uses channels 1, encode_type G711alaw, mute on, noise_cancelling off, input_device_type MicIn, sampling_rate 8 and volume "75". The read request is method get with audio_config.name ["microphone"]. Numeric values may return as strings. Bitrate and echo cancellation are omitted from the write, matching the browser capture. Audio recording is a separate setting.

The motion_detection table maps to motion_det, motion_notif_list and arming_schedule under motion_detection. The write uses digital_sensitivity "85", enabled on, object filtering off, people and vehicles on and medium target validity. Recording and snapshots are on. The captured push, server reporting, email, FTP, light/sound and AO1 actions are off. Other action flags are omitted from the write.

Configuration readback requests motion_det, motion_notif_list and feature with table ["md_polygon_region_info"] and version "1". Schedule readback separately requests name "arming_schedule". Each daily URL-encoded JSON value must decode to ["0000-2400"]. The workflow confirms the existing full-image polygon before writing settings and stops if another region is present. Sensitivity 85 returned as digital_sensitivity 85 and sensitivity high. Target tracking remained on in the browser readback but was omitted from the captured write and the provisioning write.

The login_error profile maps to unusual_detection.login_error with enabled off and numeric max_num_err 5. Readback uses unusual_detection.name ["login_error"] and may return max_num_err as a string. The captured push and light-alarm flags remained off. The profile does not establish the camera's account-lockout behavior.

Browser and integrated workflow write/readback passed for all three profiles, including the preserved-2.0.4 GUI run. The workflow applies and checks them before ONVIF changes the IP.

### Older firmware 2.0.4 activation

The three-page initialization wizard on firmware `2.0.4 Build 241101 Rel.52842n` sends no requests between its pages. Its final activation request includes `username`, `password` (the vendor uppercase MD5 digest), `passwdType: "md5"`, RSA `ciphertext`, URL-encoded `reset_pwd_email`, and `language`. It omits `pwd_sec_type` and the security-question fields. Manual activation with this payload returned `error_code: 0`. The modern workflow payload was rejected with `-50934`; the exact meaning of that code is not established.

For a factory-reset older camera, explicitly pass `--activation-format legacy-2024` to the factory workflow CLI. Explicit format overrides remain available. A complete activation, upgrade from 2.0.4 to 2.2.1, and configuration cycle has since passed hardware readback and operator inspection. Login already uses the returned `key` when `key_2` is absent and omits `keyType` in that case. Regional settings use the same payload as newer firmware and were acknowledged on 2.0.4. Do not store captured password digests, ciphertext or session tokens in the repository.

### Automatic activation selection

CLI and GUI now default to `--activation-format auto`. After inventory matching, certificate approval and factory-state confirmation, the workflow downloads two known web resources with pinned HTTPS GET requests. It compares their full SHA-256 digests with the inspected factory-state HAR captures: `/pc/Initial.htm` for the legacy activation builder and `/index.f129addb.js` for the modern builder. Exactly one recognized signature is required. JavaScript is never executed. Missing, changed or conflicting signatures stop before activation; no alternate activation request is retried. This identifies the supported payload implementation, not a universal firmware-version rule. Other firmware builds require inspection and an additional reviewed signature.

The automatic selector has been verified offline against both supplied HAR captures. Legacy automatic selection passed complete CLI and GUI hardware runs; modern signature selection has offline HAR coverage and still needs a live automatic-selection test. Use `--skip-firmware` for repeat activation tests on stock cameras; this skips firmware-file inspection and upload even if the shared profile enables upgrades. GUI users can select **Keep existing firmware (no upgrade)** to override the profile for that run.

### Clock formats on stock legacy firmware

The preserved-stock camera confirms automatic legacy detection and activation. Its legacy Date page has no date/time-format controls, and `system.basic` omits both `date_format` and `time_format`. For a detected or explicitly selected legacy activation flow that skips firmware upgrading, the workflow omits these two fields from the clock write and verification only when both are absent. It explicitly logs them as unsupported. NTP, manual DST and all remaining settings still require matching readback. Partial absence, present-but-wrong values, and missing fields on the modern/upgraded path remain errors. Upgrading first retains complete format verification on the newer firmware. A factory reset preserves stock firmware for repeated tests.

### Preserved legacy motion configuration

Firmware 2.0.4 reads `motion_det` and `motion_notif_list` with table `polygon_region_info`, omitting the modern `feature` name and `version` field. The full-image polygon remains verified before and after writes; the workflow does not call `add_md_polygon_regions`. On the preserved legacy path only, absent `obj_filter_enabled` and `report_server_enabled` are explicitly reported as unavailable and omitted. Other requested fields still require matching readback. A targeted hardware write verified `capture_enabled` changing from off to on on 2.0.4. The combined legacy writer passed complete CLI and GUI provisioning cycles, including capture on, full-image region and the 24/7 schedule.

The preserved legacy path now uses ONVIF port 2020 for identity checks, the IP/gateway writes, readback and GUI metadata. Modern/upgraded runs retain port 80. The live transport still restricts writes to the factory camera IP, the two allowed network operations, and source interface address. Firmware skipping remains explicit; broader models and unknown web builds are not automatically declared compatible.

### Activation family naming

The activation format formerly logged as `legacy-2.0.4` is now `legacy-2024`, reflecting the 2024-build firmware samples inspected so far. C320I 2.0.4 Build 241101 and C340S 2.0.3 Build 240412 share the recognized activation page. This is a family label, not an inferred firmware version or a rule that every 2024 build uses this format. Selection still uses the verified web-resource signature. The old `--activation-format legacy-2.0.4` spelling remains a compatibility alias. After authenticated metadata readback, initialization-only logs the actual firmware build year separately when the firmware contains a six- or eight-digit Build date.

The C340S hardware 1.0 initialization-only GUI test passed on 2.0.3 Build 240412 Rel.42481n: account activation, fresh login and authenticated metadata readback succeeded. No upgrade, site configuration or network write occurred. Preserved-firmware configuration subsequently passed a complete GUI run, and both inspected upgrades plus modern configuration/network stages passed separate hardware tests. The integrated automatic two-stage upgrade and provisioning GUI run subsequently passed on real C340S hardware.

The C340S 3.2.1 public web bundle `/index.d6a35dd0.js` was read using the independently approved current certificate pin. Its inspected builder sends the modern encrypted-password/email payload. Its exact SHA-256 `e62d34449bab77ee22e1256864de71d9a50dfa191639bff2d1f24482fc3e59e3` is now recognized. The read-only selector passed on the running upgraded camera; actual factory-reset activation with this bundle passed in the complete 3.2.1 GUI run, with both installed firmware stages skipped.

### Motion event processing actions disabled

The current desired motion profile uses `record = false`, mapping to `motion_detection.motion_notif_list.record_enabled = "off"`. This unchecks Event → Basic Event → Motion Detection → Processing mode → Record. Prior hardware tests used record enabled; those results describe the earlier profile. Existing local `provisioning.toml` files must be updated explicitly because Git updates do not overwrite them. The workflow verifies the requested flag after writing, for both legacy and modern motion schemas. Snapshot capture is also disabled with `snapshots = false`; the current desired profile has all motion processing actions off. This field controls motion-triggered recording only; it does not configure continuous recording, recording schedules, NVR recording or audio recording.

The all-off processing profile disables record, snapshot capture, FTP, push, alarm-server reporting, email, sound, light and alarm output. When all configured notification actions are off, the workflow also disables the observed client/app notification and target-tracking action flags if present. It refuses to claim all-off if another unrecognized enabled action remains. Motion detection itself, sensitivity, people/vehicle selection, full-image region and the 24/7 arming schedule remain configured. This is specific to motion-event processing; other event pages and continuous/NVR recording are separate settings.
