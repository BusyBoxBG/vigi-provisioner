# Python file reference

For the role of each component in the live sequence, see [Provisioning workflow](provisioning-workflow.md#files-used-by-each-stage).

All 105 Python files in the packaged project are listed below. The linked source is the reference for function signatures and supported inputs.

## Package and verification

### check_offline.py

Loads source from the checkout, imports all package modules and runs selected offline tests with socket connect and sendto blocked. [Source](../scripts/check_offline.py)

Public definitions: `main`.


### __init__.py

Marks the source directory as the importable package. [Source](../src/vigi_provisioner/__init__.py)


## Discovery, inventory and camera identity

### vigi_authorized_gateway.py

Approves enrolled bindings, rechecks the intended identity and connects through the bound TLS path. [Source](../src/vigi_provisioner/vigi_authorized_gateway.py)

Public definitions: `VigiAuthorizedGateway`.

Direct package dependencies: `vigi_camera_binding`, `vigi_enrollment_binding`, `vigi_pin_inventory`.


### vigi_camera_binding.py

Tracks expiring MAC-to-IPv4 bindings and requires a current binding for the approved connection path. [Source](../src/vigi_provisioner/vigi_camera_binding.py)

Public definitions: `CameraBindingError`, `normalize_ipv4`, `CameraBindingRegistry`, `connect_bound_camera`.

Direct package dependencies: `vigi_pin_inventory`, `vigi_tls_authorization`.


### vigi_camera_gateway.py

Joins camera inventory, fresh discovery and the authorized gateway to open a connection. [Source](../src/vigi_provisioner/vigi_camera_gateway.py)

Public definitions: `CameraGatewayError`, `connect_inventory_camera`.

Direct package dependencies: `vigi_authorized_gateway`, `vigi_discovery`, `vigi_discovery_adapter`, `vigi_inventory`, `vigi_pin_inventory`.


### vigi_camera_http.py

Reads a camera homepage over a gateway-provided connection. [Source](../src/vigi_provisioner/vigi_camera_http.py)

Public definitions: `CameraHTTPError`, `get_camera_homepage`.

Direct package dependencies: `vigi_camera_gateway`.


### vigi_camera_inventory.py

Persists camera records and combines UDP discovery and ONVIF enrichment during inventory sync. [Source](../src/vigi_provisioner/vigi_camera_inventory.py)

Public definitions: `save_camera_record`, `discover_enrich_save`, `sync_discovered_cameras`.

Direct package dependencies: `vigi_device_record`, `vigi_discovery`, `vigi_inventory`, `vigi_onvif`.


### vigi_certificate_pin.py

Normalizes, computes and compares DER certificate SHA-256 fingerprints. [Source](../src/vigi_provisioner/vigi_certificate_pin.py)

Public definitions: `CertificatePinError`, `normalize_sha256_pin`, `certificate_sha256`, `verify_certificate_pin`.


### vigi_device_record.py

Builds one camera record from UDP identity and optional ONVIF metadata. [Source](../src/vigi_provisioner/vigi_device_record.py)

Public definitions: `build_device_record`.

Direct package dependencies: `vigi_discovery`, `vigi_onvif`.


### vigi_discovery.py

Broadcasts the vendor UDP 5001 probe and parses accepted replies into camera observations. [Source](../src/vigi_provisioner/vigi_discovery.py)

Public definitions: `parse_discovery`, `discover`.


### vigi_discovery_adapter.py

Converts a UDP observation into normalized, timestamped, explicitly untrusted evidence. [Source](../src/vigi_provisioner/vigi_discovery_adapter.py)

Public definitions: `DiscoveryAdapterError`, `adapt_udp_discovery`.

Direct package dependencies: `vigi_camera_binding`, `vigi_discovery_evidence`, `vigi_pin_inventory`.


### vigi_discovery_evidence.py

Validates discovery evidence and exposes the registration helper for camera bindings. [Source](../src/vigi_provisioner/vigi_discovery_evidence.py)

Public definitions: `DiscoveryEvidenceError`, `DiscoveryEvidence`, `validate_discovery_evidence`, `register_discovered_camera`.

Direct package dependencies: `vigi_camera_binding`, `vigi_pin_inventory`.


### vigi_enrollment_binding.py

Checks discovery evidence against enrollment approval and independently approved certificate pin data. [Source](../src/vigi_provisioner/vigi_enrollment_binding.py)

Public definitions: `EnrollmentBindingError`, `approve_discovered_binding`.

Direct package dependencies: `vigi_camera_binding`, `vigi_certificate_pin`, `vigi_discovery_evidence`, `vigi_pin_inventory`.


### vigi_inventory.py

Normalizes inventory MAC strings and checks membership with a supplied SQLite connection. [Source](../src/vigi_provisioner/vigi_inventory.py)

Public definitions: `normalize_mac`, `inventory_contains_mac`.


### vigi_pin_inventory.py

Persists approved certificate pins by normalized MAC in SQLite. [Source](../src/vigi_provisioner/vigi_pin_inventory.py)

Public definitions: `normalize_mac`, `VigiPinInventory`.

Direct package dependencies: `vigi_certificate_pin`.


### vigi_pinned_tls.py

Opens source-bound TLS and verifies the peer certificate against the expected pin. [Source](../src/vigi_provisioner/vigi_pinned_tls.py)

Public definitions: `VigiPinnedTLSError`, `connect_pinned_tls`.

Direct package dependencies: `vigi_certificate_pin`.


### vigi_tls.py

Validates a supplied root certificate bundle and creates a verified TLS context. [Source](../src/vigi_provisioner/vigi_tls.py)

Public definitions: `VigiTLSConfigurationError`, `validate_root_bundle`, `create_vigi_ssl_context`.


### vigi_tls_authorization.py

Requires an approved camera pin before invoking pinned TLS. [Source](../src/vigi_provisioner/vigi_tls_authorization.py)

Public definitions: `CameraNotApprovedError`, `connect_approved_camera`.

Direct package dependencies: `vigi_pin_inventory`, `vigi_pinned_tls`.


## HTTPS initialization and HTTP processing

### vigi_activation.py

Constructs the vendor activation JSON with derived password, RSA ciphertext and recovery settings. [Source](../src/vigi_provisioner/vigi_activation.py)

Public definitions: `build_activation_request`.

Direct package dependencies: `vigi_password`, `vigi_rsa`.


### vigi_activation_guard.py

Checks an observed device with the activation predicate before building its request. [Source](../src/vigi_provisioner/vigi_activation_guard.py)

Public definitions: `prepare_activation`.

Direct package dependencies: `vigi_activation`, `vigi_activation_safety`.


### vigi_activation_safety.py

Requires inventory match, factory-state hint and HTTPS application code before allowing preparation. [Source](../src/vigi_provisioner/vigi_activation_safety.py)

Public definitions: `DeviceObservation`, `activation_allowed`.


### vigi_deadline_stream.py

Adapts recv on a supplied transport to an absolute deadline and per-read timeout. [Source](../src/vigi_provisioner/vigi_deadline_stream.py)

Public definitions: `DeadlineStreamError`, `DeadlineStream`.

Direct package dependencies: `vigi_socket_deadline`.


### vigi_factory_workflow.py

Single-camera CLI that connects inventory-matched UDP discovery, pinned HTTPS activation, inventory label serial as Device Name, regional/clock settings, main-stream video, Platform Access, OSD date placement and serial label text, microphone settings, motion detection, login-error exceptions, ONVIF static IPv4 verification and HTTPS DNS readback. [Source](../src/vigi_provisioner/vigi_factory_workflow.py)

### vigi_fixed_initialization_attempt.py

Runs a bounded write and strict read on injected transport, validates the result and owns cleanup. [Source](../src/vigi_provisioner/vigi_fixed_initialization_attempt.py)

Public definitions: `perform_fixed_initialization_attempt`.

Direct package dependencies: `vigi_deadline_stream`, `vigi_http_stream`, `vigi_initialization_attempt`, `vigi_initialization_result`, `vigi_write_deadline`.


### vigi_gateway_transport_lease.py

Transfers a supplied transport to one matching plan owner or closes it while still unclaimed. [Source](../src/vigi_provisioner/vigi_gateway_transport_lease.py)

Public definitions: `GatewayTransportLeaseError`, `GatewayTransportLease`, `create_gateway_transport_lease`.

Direct package dependencies: `vigi_initialization_execution_plan`.


### vigi_http_encoder.py

Encodes the validated initialization request as HTTP bytes. [Source](../src/vigi_provisioner/vigi_http_encoder.py)

Public definitions: `HttpEncodingError`, `encode_initialization_http`.

Direct package dependencies: `vigi_initialization_validator`.


### vigi_http_reader.py

Assembles HTTP response fragments before structured parsing. [Source](../src/vigi_provisioner/vigi_http_reader.py)

Public definitions: `HttpReadError`, `assemble_http_response`.

Direct package dependencies: `vigi_http_response`.


### vigi_http_request.py

Serializes prepared initialization data after identity and request validation. [Source](../src/vigi_provisioner/vigi_http_request.py)

Public definitions: `HttpRequestSerializationError`, `serialize_initialization_request`.

Direct package dependencies: `vigi_initialization_validator`.


### vigi_http_response.py

Parses a bounded HTTP response and checks framing, header consistency and JSON syntax. [Source](../src/vigi_provisioner/vigi_http_response.py)

Public definitions: `HttpResponseError`, `ParsedHttpResponse`, `parse_http_response`.


### vigi_http_sender.py

Builds initialization send plans and exposes the disabled transmission boundary. [Source](../src/vigi_provisioner/vigi_http_sender.py)

Public definitions: `InitializationTransmissionDisabled`, `InitializationSendPlan`, `prepare_initialization_send`, `send_initialization`.

Direct package dependencies: `vigi_http_request`.


### vigi_http_stream.py

Reads bounded HTTP response framing from an injected stream under a deadline. [Source](../src/vigi_provisioner/vigi_http_stream.py)

Public definitions: `HttpStreamError`, `read_http_stream`.

Direct package dependencies: `vigi_http_reader`.


### vigi_https_client.py

Performs diagnostic JSON HTTPS requests with certificate verification disabled. [Source](../src/vigi_provisioner/vigi_https_client.py)

Public definitions: `VigiHttpsClient`.


### vigi_https_init.py

Builds the port 443 activation POST and exposes a summary that omits the request body. [Source](../src/vigi_provisioner/vigi_https_init.py)

Public definitions: `PreparedInitialization`, `prepare_initialization`, `dry_run`.

Direct package dependencies: `vigi_activation`.


### vigi_https_transport.py

Validates a TLS context and reports dry-run request metadata. Rejects live mode. [Source](../src/vigi_provisioner/vigi_https_transport.py)

Public definitions: `TransmissionDisabledError`, `VigiHttpsTransport`.

Direct package dependencies: `vigi_https_init`, `vigi_tls`.


### vigi_identity_bound_transport.py

Carries a transport together with normalized approved identity metadata. [Source](../src/vigi_provisioner/vigi_identity_bound_transport.py)

Public definitions: `IdentityBoundTransport`.

Direct package dependencies: `vigi_camera_binding`, `vigi_pin_inventory`.


### vigi_initialization_attempt.py

Defines attempt outcomes and a single-attempt helper for a supplied transport. [Source](../src/vigi_provisioner/vigi_initialization_attempt.py)

Public definitions: `AttemptStatus`, `AttemptResult`, `perform_single_attempt`.


### vigi_initialization_authorization.py

Reserves, readies and consumes an approved serialized request with owner and identity checks. [Source](../src/vigi_provisioner/vigi_initialization_authorization.py)

Public definitions: `InitializationAuthorizationError`, `ConsumedInitializationRequest`, `InitializationAuthorization`.

Direct package dependencies: `vigi_camera_binding`, `vigi_http_request`, `vigi_pin_inventory`.


### vigi_initialization_config.py

Loads and validates the shared TOML profile with camera defaults, clock/DST/NTP, DNS, video, Platform Access, OSD, audio, motion detection and login-error exception settings. Builds regional and clock request objects. [Source](../src/vigi_provisioner/vigi_initialization_config.py)

Public definitions: `VigiInitializationConfig`.


### vigi_initialization_coordinator.py

Mediates validation, dry-run and send-plan preparation after checking gateway identity. [Source](../src/vigi_provisioner/vigi_initialization_coordinator.py)

Public definitions: `InitializationCoordinatorError`, `VigiInitializationCoordinator`.

Direct package dependencies: `vigi_authorized_gateway`, `vigi_initialization_validator`.


### vigi_initialization_dry_run.py

Builds a local activation/settings plan and redacts sensitive fields for display. [Source](../src/vigi_provisioner/vigi_initialization_dry_run.py)

Public definitions: `redact_activation_request`, `build_initialization_plan`, `main`.

Direct package dependencies: `vigi_activation`, `vigi_initialization_config`.


### vigi_initialization_execution.py

Reserves initialization authorization, renews target approval and stops at the disabled live boundary. [Source](../src/vigi_provisioner/vigi_initialization_execution.py)

Public definitions: `InitializationExecutionDisabled`, `VigiInitializationExecution`.

Direct package dependencies: `vigi_authorized_gateway`, `vigi_camera_binding`, `vigi_initialization_authorization`, `vigi_initialization_execution_plan`, `vigi_pin_inventory`.


### vigi_initialization_execution_plan.py

Normalizes immutable destination MAC, IP, port and provisioning source IPv4. [Source](../src/vigi_provisioner/vigi_initialization_execution_plan.py)

Public definitions: `InitializationExecutionPlan`.

Direct package dependencies: `vigi_camera_binding`, `vigi_pin_inventory`.


### vigi_initialization_result.py

Accepts a parsed initialization response only with HTTP 200 and integer camera code zero. [Source](../src/vigi_provisioner/vigi_initialization_result.py)

Public definitions: `InitializationResultError`, `InitializationResult`, `validate_initialization_result`.

Direct package dependencies: `vigi_http_response`.


### vigi_initialization_validator.py

Checks prepared URL, approved destination, headers and activation JSON structure. [Source](../src/vigi_provisioner/vigi_initialization_validator.py)

Public definitions: `InitializationValidationError`, `validate_initialization`.

Direct package dependencies: `vigi_https_init`.


### vigi_inventory_initialization.py

Reads inventory, prepares and summarizes requests, and checks authorization and live discovery prerequisites. [Source](../src/vigi_provisioner/vigi_inventory_initialization.py)

Public definitions: `InventoryInitializationError`, `prepare_inventory_initialization`, `safe_initialization_summary`, `authorize_inventory_initialization`, `dry_run_inventory_initialization`, `verify_live_initialization_target`.

Direct package dependencies: `vigi_camera_inventory`, `vigi_https_init`, `vigi_initialization_validator`, `vigi_inventory`.


### vigi_password.py

Computes the vendor MD5 representation used by activation. [Source](../src/vigi_provisioner/vigi_password.py)

Public definitions: `vigi_md5_password`.


### vigi_preflight.py

Combines caller-provided inventory approval, discovery factory state and diagnostic HTTPS state. [Source](../src/vigi_provisioner/vigi_preflight.py)

Public definitions: `inspect_device`.

Direct package dependencies: `vigi_activation_safety`, `vigi_https_client`.


### vigi_preflight_diagnostics.py

Produces individual inventory, factory-state and HTTPS-state diagnostic flags. [Source](../src/vigi_provisioner/vigi_preflight_diagnostics.py)

Public definitions: `diagnostic_checks`.

Direct package dependencies: `vigi_discovery`, `vigi_preflight`.


### vigi_response_pipeline.py

Coordinates bounded stream reception, HTTP parsing and initialization result validation. [Source](../src/vigi_provisioner/vigi_response_pipeline.py)

Public definitions: `ResponsePipelineError`, `read_initialization_response`.

Direct package dependencies: `vigi_deadline_stream`, `vigi_http_stream`, `vigi_initialization_result`.


### vigi_rsa.py

Encrypts the activation password using the embedded vendor public key. [Source](../src/vigi_provisioner/vigi_rsa.py)

Public definitions: `encrypt_ipc_password`.


### vigi_socket_deadline.py

Sets a timeout based on the remaining absolute read budget and the per-read limit. [Source](../src/vigi_provisioner/vigi_socket_deadline.py)

Public definitions: `SocketDeadlineError`, `configure_read_timeout`.


### vigi_write_deadline.py

Loops over partial sends while enforcing a write deadline and per-call timeout. [Source](../src/vigi_provisioner/vigi_write_deadline.py)

Public definitions: `WriteDeadlineError`, `send_with_deadline`.


## ONVIF and provisioning state

### vigi_onvif.py

Reads ONVIF device identity with authenticated SOAP and parses descriptive fields. [Source](../src/vigi_provisioner/vigi_onvif.py)

Public definitions: `get_device_information`.


### vigi_onvif_config_response.py

Classifies ONVIF write responses, faults and uncertain outcomes and extracts the reboot hint. [Source](../src/vigi_provisioner/vigi_onvif_config_response.py)

Public definitions: `ONVIFConfigurationResponseError`, `classify_configuration_response`.


### vigi_onvif_config_transport.py

Provides the test configuration transport and its constrained request handling. [Source](../src/vigi_provisioner/vigi_onvif_config_transport.py)

Public definitions: `ONVIFTransportError`, `make_test_configuration_transport`.


### vigi_onvif_gateway_config.py

Builds the SOAP request for an IPv4 default gateway. [Source](../src/vigi_provisioner/vigi_onvif_gateway_config.py)

Public definitions: `GatewayPreparationError`, `prepare_default_gateway`.


### vigi_onvif_live_transport.py

Constructs the fixed lab HTTP Digest writer with source binding and operation allowlisting. [Source](../src/vigi_provisioner/vigi_onvif_live_transport.py)

Public definitions: `LiveONVIFTransportError`, `SourceBoundAdapter`, `validate_operation`, `make_live_transport`.


### vigi_onvif_network.py

Sends interface and gateway read operations and converts XML into IPv4 observations. [Source](../src/vigi_provisioner/vigi_onvif_network.py)

Public definitions: `ONVIFNetworkError`, `get_network_interfaces`, `get_network_default_gateway`.


### vigi_onvif_soap_strict.py

Checks exact SOAP hierarchy and compares operation values with approved plan fields. [Source](../src/vigi_provisioner/vigi_onvif_soap_strict.py)

Public definitions: `StrictSOAPValidationError`, `tag`, `require_structure`, `require_text`, `soap_operation`, `validate_strict_soap`.


### vigi_onvif_static_ip.py

Validates target IPv4, prefix, gateway and interface token and builds the interface write XML. [Source](../src/vigi_provisioner/vigi_onvif_static_ip.py)

Public definitions: `StaticIPPreparationError`, `prepare_static_ipv4`.


### vigi_provisioning_evidence.py

Checks acknowledgement history and readback evidence and binds reported application to the approved assignment. [Source](../src/vigi_provisioner/vigi_provisioning_evidence.py)

Public definitions: `ProvisioningEvidenceError`, `validate_application_evidence`, `validate_readback_evidence`, `validate_bound_application_evidence`.

Direct package dependencies: `vigi_inventory`, `vigi_static_ip_verification`.


### vigi_provisioning_state.py

Persists guarded pending, applied and verified provisioning transitions in SQLite. [Source](../src/vigi_provisioner/vigi_provisioning_state.py)

Public definitions: `ProvisioningStateError`, `initialize_pending`, `record_applied`, `record_verified`.

Direct package dependencies: `vigi_inventory`, `vigi_provisioning_evidence`.


### vigi_static_ip_assignments.py

Validates and records approved static IP assignments and checks inventory conflicts. [Source](../src/vigi_provisioner/vigi_static_ip_assignments.py)

Public definitions: `StaticIPAssignmentError`, `approve_static_ip_assignment`.

Direct package dependencies: `vigi_inventory`.


### vigi_static_ip_coordinator.py

Runs the approved gateway then interface writes through injected transport and tracks acknowledgements. [Source](../src/vigi_provisioner/vigi_static_ip_coordinator.py)

Public definitions: `StaticIPCoordinatorError`, `execute_with_transport`.

Direct package dependencies: `vigi_onvif_config_response`, `vigi_onvif_soap_strict`, `vigi_static_ip_execution_plan`.


### vigi_static_ip_execution_plan.py

Validates structural and addressing constraints before the static IP plan is executed. [Source](../src/vigi_provisioner/vigi_static_ip_execution_plan.py)

Public definitions: `StaticIPExecutionPlanError`, `validate_static_ip_execution_plan`.


### vigi_static_ip_plan.py

Reads a camera and approved assignment and generates both SOAP requests for the selected interface. [Source](../src/vigi_provisioner/vigi_static_ip_plan.py)

Public definitions: `StaticIPPlanError`, `prepare_inventory_static_ip_plan`.

Direct package dependencies: `vigi_inventory`, `vigi_onvif_gateway_config`, `vigi_onvif_static_ip`, `vigi_static_ip_assignments`.


### vigi_static_ip_verification.py

Checks rediscovery and ONVIF readback against the intended assignment. [Source](../src/vigi_provisioner/vigi_static_ip_verification.py)

Public definitions: `StaticIPVerificationError`, `verify_static_ip_readback`.

Direct package dependencies: `vigi_inventory`.


## Legacy UDP

### coordinator.py

Routes legacy read-only operations through retry policy and reports uncertain state-changing outcomes. [Source](../src/vigi_provisioner/coordinator.py)

Public definitions: `execute_read_only`, `UncertainOperationError`, `execute_state_change`.

Direct package dependencies: `transport`.


### crypto.py

Provides older UDP AES JSON encryption and RSA session-key and password encryption with public-key validation. [Source](../src/vigi_provisioner/crypto.py)

Public definitions: `encrypt_json`, `decrypt_json`, `encrypt_session_key`, `encrypt_ipc_password`.


### discovery.py

Decodes legacy discovery packets and extracts camera fields using the strict common packet codec. [Source](../src/vigi_provisioner/discovery.py)

Public definitions: `DiscoveryPacket`, `parse_discovery`, `DiscoveredCamera`, `extract_camera`.

Direct package dependencies: `packets`.


### handshake.py

Builds legacy key, session and encrypted application request packets. [Source](../src/vigi_provisioner/handshake.py)

Public definitions: `build_key_request`, `build_session_request`, `build_encrypted_request`.

Direct package dependencies: `crypto`, `packets`.


### init_payload.py

Builds legacy account and basic-settings requests and selects the vendor password transformation. [Source](../src/vigi_provisioner/init_payload.py)

Public definitions: `transform_password`, `build_set_password`, `build_basic_settings`.

Direct package dependencies: `password_constants`.


### live_transport.py

Implements the opt-in legacy UDP socket exchange and response source checks. [Source](../src/vigi_provisioner/live_transport.py)

Public definitions: `LiveUdpTransport`.

Direct package dependencies: `packets`, `transport`.


### packets.py

Encodes and validates legacy frame headers, checksums and TLV fields. [Source](../src/vigi_provisioner/packets.py)

Public definitions: `checksum`, `encode_tlv`, `decode_tlvs`, `encode_packet`, `decode_packet`.


### password_constants.py

Holds vendor lookup and salt constants consumed by legacy password transformation. [Source](../src/vigi_provisioner/password_constants.py)


### responses.py

Parses typed legacy responses and validates identity, field shape and encrypted JSON. [Source](../src/vigi_provisioner/responses.py)

Public definitions: `UdpResponse`, `validate_camera_mac`, `parse_response`, `parse_json_response`, `parse_encrypted_response`.

Direct package dependencies: `packets`.


### session.py

Generates random legacy session credentials. [Source](../src/vigi_provisioner/session.py)

Public definitions: `generate_session_credentials`.


### transport.py

Provides mock and retry transports and checks reply source against destination. [Source](../src/vigi_provisioner/transport.py)

Public definitions: `UdpTransport`, `MockUdpTransport`, `RetryTransport`, `transport_for_operation`, `validate_response_source`.


### workflow.py

Tracks legacy key exchange, session establishment and encrypted request sequencing. [Source](../src/vigi_provisioner/workflow.py)

Public definitions: `Stage`, `InitializationWorkflow`.

Direct package dependencies: `handshake`, `responses`.


## Solar session protocol

### vigi_solar_aes.py

Provides AES helpers for the legacy and GCM variants of Solar encryption. [Source](../src/vigi_provisioner/vigi_solar_aes.py)

Public definitions: `encrypt_legacy`, `encrypt_gcm`.


### vigi_solar_auth.py

Builds proprietary Solar exchange and login data with nonce and hash helpers. [Source](../src/vigi_provisioner/vigi_solar_auth.py)

Public definitions: `random_nonce`, `uppercase_hash`, `build_exchange_key`, `build_solar_exchange_request`, `build_solar_login_request`.


### vigi_solar_authenticator.py

Orchestrates the Solar challenge and login exchange to produce session context. [Source](../src/vigi_provisioner/vigi_solar_authenticator.py)

Public definitions: `authenticate_solar`.

Direct package dependencies: `vigi_password`, `vigi_solar_auth`, `vigi_solar_crypto`, `vigi_solar_login`, `vigi_solar_login_response`, `vigi_solar_response`, `vigi_solar_session`.


### vigi_solar_client.py

Uses per-device session state, authentication and lockout handling for read-only calls. [Source](../src/vigi_provisioner/vigi_solar_client.py)

Public definitions: `SolarLockoutError`, `SolarClient`.

Direct package dependencies: `vigi_solar_readonly`, `vigi_solar_retry`, `vigi_solar_session`, `vigi_solar_transport`.


### vigi_solar_crypto.py

Derives Solar key, IV and addition values and verifies exchange digests. [Source](../src/vigi_provisioner/vigi_solar_crypto.py)

Public definitions: `hash_upper`, `verify_response_digest`, `derive_aes_key`, `derive_aes_iv`, `derive_addition`.


### vigi_solar_exchange_adapter.py

Adapts an injected transport to the Solar exchange callback interface. [Source](../src/vigi_provisioner/vigi_solar_exchange_adapter.py)

Public definitions: `SolarExchangeAdapter`.


### vigi_solar_http.py

Validates destination and headers for the Solar HTTP transport and manages its session. [Source](../src/vigi_provisioner/vigi_solar_http.py)

Public definitions: `SolarHTTPTransport`.


### vigi_solar_login.py

Builds Solar login data using the selected encryption path. [Source](../src/vigi_provisioner/vigi_solar_login.py)

Public definitions: `build_solar_login`.

Direct package dependencies: `vigi_solar_aes`.


### vigi_solar_login_response.py

Parses Solar login results into a structured outcome. [Source](../src/vigi_provisioner/vigi_solar_login_response.py)

Public definitions: `SolarLoginResult`, `parse_solar_login_response`.


### vigi_solar_readonly.py

Checks whether an input Solar request fits the supported read-only shape. [Source](../src/vigi_provisioner/vigi_solar_readonly.py)

Public definitions: `validate_readonly_solar_request`.


### vigi_solar_request.py

Builds the authenticated Solar application request using the session token. [Source](../src/vigi_provisioner/vigi_solar_request.py)

Public definitions: `build_authenticated_solar_request`.


### vigi_solar_response.py

Parses Solar authentication response fields and verifies the challenge response. [Source](../src/vigi_provisioner/vigi_solar_response.py)

Public definitions: `SolarAuthResponse`, `parse_solar_response`, `validate_solar_response`.

Direct package dependencies: `vigi_solar_crypto`.


### vigi_solar_retry.py

Implements the Solar retry decision for an authenticated read request. [Source](../src/vigi_provisioner/vigi_solar_retry.py)

Public definitions: `execute_with_solar_retry`.

Direct package dependencies: `vigi_solar_request`.


### vigi_solar_session.py

Stores session contexts, TTL state, per-device locks and lockout deadlines. [Source](../src/vigi_provisioner/vigi_solar_session.py)

Public definitions: `SolarAuthContext`, `SolarSessionCache`.


### vigi_solar_transport.py

Prepares encrypted Solar application requests and decrypts the responses. [Source](../src/vigi_provisioner/vigi_solar_transport.py)

Public definitions: `PreparedSolarRequest`, `prepare_solar_request`, `decrypt_solar_response`.

Direct package dependencies: `vigi_solar_aes`.


## Tests

### test_gateway_transport_lease.py

Exercises matching and mismatched claims, ownership transfer and terminal cleanup after a close failure. [Source](../tests/test_gateway_transport_lease.py)


### test_handshake_identity.py

Checks legacy handshake responses with valid, absent, mismatched and malformed identity data. [Source](../tests/test_handshake_identity.py)


### test_identity_extended.py

Exercises duplicate fields, invalid error-code lengths and identity normalization in legacy responses. [Source](../tests/test_identity_extended.py)


### test_identity_validation.py

Checks response camera identity matching and malformed or missing identity fields. [Source](../tests/test_identity_validation.py)


### test_live_disabled.py

Checks that the legacy transport refuses exchange unless explicitly enabled. [Source](../tests/test_live_disabled.py)


### test_mock_source.py

Checks exact mock source matching and legacy mock compatibility. [Source](../tests/test_mock_source.py)


### test_packet_validation.py

Checks valid packet decoding and rejects corrupt framing, reserved bytes and checksums. [Source](../tests/test_packet_validation.py)


### test_password_validation.py

Covers supported password transformations and invalid algorithms or empty inputs. [Source](../tests/test_password_validation.py)


### test_rsa_validation.py

Uses synthetic keys to check RSA key sizes, invalid key input and long-password handling. [Source](../tests/test_rsa_validation.py)

### vigi_test_gui.py

Local HTTP server with a configurable bind address, inventory form, serial editor, confirmed deletion, read-only factory camera discovery and live provisioning console. A child worker runs the factory workflow and exchanges prompt responses over pipes. Adds inventory metadata columns, merges discovery and authenticated ONVIF information, and records run status. [Source](../src/vigi_provisioner/vigi_test_gui.py)

### vigi_firmware_upgrade.py

Experimental bench CLI for the identified older-firmware C320I. Checks the exact file checksum and camera identity, requests the local upgrade URL, uploads once through pinned HTTPS, then observes authenticated firmware readback on ONVIF 2020 and 80. [Source](../src/vigi_provisioner/vigi_firmware_upgrade.py)

## vigi_model_catalog.py

Reads and atomically saves the model/hardware/region TOML catalog. Validates official URLs, extracts firmware ZIP links, and checks bounded official support-page responses. Camera inventory linkage is implemented in vigi_test_gui.py. No camera or firmware upload operations are performed. See [catalog details](model-catalog.md).

## vigi_firmware_cache.py

Downloads selected official firmware ZIPs, validates size and single-image layout, stores the ZIP and image with SHA-256 hashes, and validates approved local image files before GUI provisioning. No camera requests are issued. The GUI supplies model approval and links the selected image to the factory workflow through --firmware-file. See [firmware cache](model-catalog.md#default-approved-firmware-and-local-downloads).

## vigi_c340s_upgrade.py

Standalone staged C340S V1 firmware-upgrade experiment. Holds exact package/image hashes and source/target rules, reads inventory and initialized discovery identity, verifies authenticated ONVIF identity, supports preflight-only by default and a confirmed single upload with target-version polling. It reuses the existing HTTPS login and multipart transport and never runs provisioning or the next upgrade automatically. See [C340S staged upgrade](firmware-upgrade.md#c340s-v1-staged-upgrade-experiment).

The C340S module also exposes inspect_latest_image, read_identity and upgrade_stage for the integrated factory workflow. The GUI checks both files before spawning its worker, passes --c340s-bridge-package alongside --firmware-file, and stores prerequisite cache metadata in the model catalog. vigi_firmware_cache.import_c340s_latest implements offline target ZIP import with the known package checks.

## vigi_motion_actions.py

Targets an already-configured inventory camera to disable motion-event processing actions only. It can update the nine action booleans in the local motion profile, verifies authenticated model/MAC (and Device ID where returned), writes only motion_notif_list, then verifies all exposed actions off and unchanged detector/schedule readback. It does not run firmware, network or full provisioning stages. Use --legacy only for the inspected legacy motion read format.

### vigi_c540s_upgrade.py

C540S V1 UN upgrade support: the hardware-confirmed 3.2.0 to 3.2.1 route and an offline-tested older-stock intermediate route. `upgrade_route` selects bridge/latest, skips bridge for 2.5.0 and eligible newer sources, skips an installed target and rejects unsupported versions. `require_stage` prevents wrong-stage uploads and downgrades. Defines source, target, filename and SHA-256 values; checks the ZIP/image, inventory, discovery identity and authenticated ONVIF model/hardware/MAC; performs one pinned HTTPS upload after typed confirmation; polls target firmware without resending. Standalone defaults to preflight. The GUI workflow calls the image inspector, identity reader and upgrade stage before configuration. No PTZ movement commands are sent.

`vigi_firmware_cache.import_c540s_latest` imports the inspected local ZIP atomically and records the cached image paths and hashes without camera I/O.

### vigi_label_scan.py

Pure, bounded parser for one camera QR/barcode stream. `parse_label_stream` explores supported token boundaries, collapses repeated identity values and reports fields, readiness and a review message. It recognizes the inspected TP1 wrappers, compact MAC and initial 13-character serial shape. Conflicting values, multiple valid interpretations and viable incomplete tails cannot be accepted. No scanner SDK, inventory persistence or camera communication is involved. `vigi_test_gui.py` exposes the parser through its existing authenticated local `/api/scan` endpoint and provides the buffer, pause, accept, reset and manual-entry controls. `tests/test_label_scan.py` covers permutations, concatenation, repeats, partial input, conflict/ambiguity rejection, wrapper variants and limits.
