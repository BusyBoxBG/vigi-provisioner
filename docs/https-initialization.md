# Factory camera initialization over HTTPS

The project implements request preparation, target approval, and transport-independent attempt handling. **The public live initialization entry points are disabled in this checkout.** Running a dry run does not set the camera password. The ONVIF guide starts with a camera that already has working credentials.

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
