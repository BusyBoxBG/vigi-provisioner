# Provisioning workflow

| Phase | Primary entry point | Result and boundary |
| --- | --- | --- |
| Locate | `vigi_discovery.discover` | LAN observations with a discovery MAC, IPv4, and factory-state hint. |
| Identify | `vigi_discovery_adapter.adapt_udp_discovery` and enrollment helpers | Normalize evidence and check it against independently approved identity and pin state. |
| Prepare | `vigi_inventory_initialization.prepare_inventory_initialization` and `vigi_https_init.prepare_initialization` | Construct the factory initialization request for the selected inventory camera. Use redacted summaries when inspecting it. |
| Authorize | `VigiInitializationExecution` | Check gateway identity and reserve the request. Live initialization remains disabled. |
| Establish credentials | Operator-approved activation outside the disabled entry point | Confirm the camera accepts ONVIF authentication before continuing. |
| Read | `get_network_interfaces` and `get_network_default_gateway` | Obtain the current token, MAC, IP configuration and gateway. |
| Plan | `approve_static_ip_assignment` and `prepare_inventory_static_ip_plan` | Persist the intended assignment and prepare two SOAP bodies without sending them. |
| Apply | `vigi_static_ip_coordinator.execute_with_transport` | Send via the supplied transport. Keep per-operation acknowledgement and any reboot hint. |
| Verify | `verify_static_ip_readback` and `record_verified` | Compare fresh discovery and ONVIF readback with the approved assignment. |

Start Ubuntu validation with the offline checks in the [README](../README.md). Then verify the camera-facing interface and perform discovery on the test LAN. Track the installed firmware, camera model, approved identity, initial and target addresses, and verification results in local operator records. Keep credentials, certificate material, captures, and live databases outside the repository.

Read the [discovery protocol](tplink-discovery.md), [HTTPS initialization](https-initialization.md), [ONVIF static IPv4 workflow](onvif-network.md), and [Python file reference](python-reference.md) for the implementation details.
