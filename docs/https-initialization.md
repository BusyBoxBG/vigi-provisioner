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
