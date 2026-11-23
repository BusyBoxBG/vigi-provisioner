# Firmware bench upgrade

The experimental module vigi_firmware_upgrade traces the local-file IPC upgrade in vms-tools.jar. It is scoped to C320I hardware 1.20, Device ID 5B7292F5C6C4C44E2, MAC 50:3D:D1:46:0A:B7 at 192.168.0.60, source version 2.0.4 Build 241101 Rel.52842n and target 2.2.1 Build 260605 Rel.12620n. The standalone upload passed on the expected test camera: authenticated ONVIF port 2020 read back target 2.2.1 Build 260605 Rel.12620n after upload.

Run with --file pointing to the inspected Cx20I binary for a preflight. The module compares the exact SHA-256, checks initialized UDP identity and authenticated ONVIF identity/model/hardware on port 2020. Add --execute for explicit upload confirmation and approval of the observed certificate on the isolated LAN.

The IPC builder in common.passthrough.d.a.g requests system.firmware_upgrade with type "0". Local upgrade service basic.service.i.d reads the returned url and supplies it to common.passthrough.b. That transport prefixes the URI with /stok=<session> and uses a multipart file part named file, preserving the filename. The HTTP helper uses multipart/form-data for the part and an attachment filename header. The implementation follows those details and validates the returned relative URI before upload.

The factory tool estimates part of its displayed progress from wait_time. This test module instead checks authenticated ONVIF firmware readback for up to ten minutes on 2020 and 80 after the single upload. An interrupted upload response leads to observation, without an automatic resend. The live camera needs uninterrupted power and Ethernet until completion. The final success condition is the expected MAC, model/hardware and target firmware readback.

TP-Link documents older ONVIF port 2020 and the newer default 80, with compatibility access on 2020 retained: https://www.tp-link.com/bg/support/faq/4201/

The first live attempt authenticated and obtained a successful upload-preparation response but stopped before file transfer because the URL validator omitted encoded path separators. The factory RetUrlResp.getUrl replaces %2f with /. The module now performs that normalization, rejects non-relative URLs and supports --prepare-only to validate preparation without transferring firmware.

## Factory workflow integration

The optional [firmware] profile contains enabled and file. Set enabled=true to check firmware immediately after activation and login, before device name and site settings. The file path resolves relative to the TOML profile, and the exact inspected binary checksum is checked before activation. The example keeps this optional upgrade disabled until the local file is prepared.

The stage reads authenticated identity and hardware through ONVIF 80 or 2020. It skips the target version and currently accepts only the tested 2.0.4 Build 241101 Rel.52842n source version on C320I hardware 1.20. In the GUI, a separate UPGRADE <Device ID> prompt precedes upload. After firmware readback matches, the workflow checks the HTTPS certificate again, obtains approval for a changed pin, and confirms a fresh login with the provisioned credentials before site configuration.

The standalone upgrade and combined factory activation, upgrade, fresh login and complete site-configuration run are verified on hardware. The current provisioning engine remains C320I-specific even though the official target package is listed for C420I hardware 1.20 as well.
