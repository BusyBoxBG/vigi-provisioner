# ONVIF device management and static IPv4

The project implements SOAP 1.2 device-management operations, using the device namespace `http://www.onvif.org/ver10/device/wsdl` and data types from `http://www.onvif.org/ver10/schema`. An operation appears as the qualified child under the SOAP Envelope's Body. The repository uses HTTP Digest for its authenticated HTTP transport. Digest authentication does not encrypt the HTTP connection or SOAP payload. The camera endpoint used by the fixed live writer is the source-coded HTTP port 80 device service. The discovery response may provide an ONVIF endpoint for the caller to validate and use with read helpers. [ONVIF DeviceBinding reference](https://www.onvif.org/yaml/wsdl-viewer2.php)

## Read the camera before planning

| Operation | Use in this project |
| --- | --- |
| `GetDeviceInformation` | Enrich the discovery record with manufacturer, model, firmware, serial and hardware information. |
| `GetNetworkInterfaces` | Read interface tokens, MAC addresses, enabled state, and IPv4 configuration including manual addresses and DHCP. |
| `GetNetworkDefaultGateway` | Read the reported IPv4 gateway list. |

Read the interface token from the target device. The token is an opaque value scoped to the camera, independent of the Windows or Ubuntu interface name. Preserve the pre-change settings so that a response or readback can be evaluated in context.

## Approve an assignment and build a plan

`approve_static_ip_assignment` requires an inventory camera and validates the reserved IPv4 address, prefix and gateway before writing an approval row. The target and gateway must be usable and distinct, and the target cannot equal the provisioning host address. Conflict checks inspect local inventory and previously approved assignments under a SQLite write transaction. These checks do not establish that the address is free on the physical network.

`prepare_inventory_static_ip_plan` combines the known camera, approved assignment, and current interface token with the two XML builders. The static interface builder supports prefixes 1–30 and requires both address and gateway to be usable hosts in the same subnet. The strict SOAP validator checks the namespace, element hierarchy, cardinality, and expected values against the plan.

| Order | Operation | Body fields generated |
| --- | --- | --- |
| 1 | `SetNetworkDefaultGateway` | Device namespace `IPv4Address` holding the approved gateway. |
| 2 | `SetNetworkInterfaces` | Device namespace `InterfaceToken` and `NetworkInterface`. The schema namespace `IPv4` element holds `Enabled=true`, one `Manual` address and prefix, and `DHCP=false`. |

Gateway comes first because the interface write can move the camera off the old IP and interrupt the connection. The order is repository policy. The workflow does not provide a transaction across the two device requests.

## Execute through the chosen transport

`execute_with_transport` validates the plan and SOAP before invoking the supplied callable as `transport(operation, soap)`. The callable returns a mapping with `http_status` and `response_body`. The test transport is separate from the live writer. The live writer opens a fresh source-bound Requests session for each operation, disables environment proxies, redirects and transport retries, and uses HTTP Digest. Its factory currently accepts only its fixed lab source address and device endpoint, with the expected administrator username. Passing a different endpoint fails locally. Ubuntu testing of a different subnet requires a separately reviewed adaptation of that transport.

The coordinator proceeds to the interface operation only after a positive gateway acknowledgement. A failed or unconfirmed step stops the sequence and retains its classification. A gateway may already have changed if the interface step fails.

## Classify and verify

A confirmed acknowledgement requires HTTP 200 and the expected qualified SOAP response in a one-operation body. The gateway response must have no children or attributes. The interface response may contain a single `RebootNeeded` field, with XML boolean values `true`/`1` or `false`/`0`. An absent field yields `None`. The code records the hint without rebooting. SOAP faults, HTTP errors, and unrecognized replies receive separate classifications. A connection interruption is unknown, since the device can apply the new IP before returning a response.

An acknowledgement means the device reported acceptance. Verify persistence separately by rediscovering the planned MAC at the planned new IP and reading the ONVIF network settings there. The verifier requires exactly one matching interface token, a matching MAC, an enabled interface, DHCP disabled, the intended manual IPv4/prefix pair, and the intended gateway in the returned list. It returns individual mismatch reasons.

The state layer tracks `pending`, `applied`, and `verified` separately. Application evidence must bind to the approved assignment and contain positive acknowledgement for both operations in order. Readback evidence must match that assignment. Evidence binding is a consistency check, so its provenance still depends on the caller's trusted execution path. The coordinator and verifier do not themselves update inventory.
