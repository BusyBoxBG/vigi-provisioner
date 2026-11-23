# Firmware bench upgrade

The experimental module vigi_firmware_upgrade traces the local-file IPC upgrade in vms-tools.jar. It is scoped to C320I hardware 1.20, Device ID 5B7292F5C6C4C44E2, MAC 50:3D:D1:46:0A:B7 at 192.168.0.60, source version 2.0.4 Build 241101 Rel.52842n and target 2.2.1 Build 260605 Rel.12620n. Its first live upload remains pending.

Run with --file pointing to the inspected Cx20I binary for a preflight. The module compares the exact SHA-256, checks initialized UDP identity and authenticated ONVIF identity/model/hardware on port 2020. Add --execute for explicit upload confirmation and approval of the observed certificate on the isolated LAN.

The IPC builder in common.passthrough.d.a.g requests system.firmware_upgrade with type "0". Local upgrade service basic.service.i.d reads the returned url and supplies it to common.passthrough.b. That transport prefixes the URI with /stok=<session> and uses a multipart file part named file, preserving the filename. The HTTP helper uses multipart/form-data for the part and an attachment filename header. The implementation follows those details and validates the returned relative URI before upload.

The factory tool estimates part of its displayed progress from wait_time. This test module instead checks authenticated ONVIF firmware readback for up to ten minutes on 2020 and 80 after the single upload. An interrupted upload response leads to observation, without an automatic resend. The live camera needs uninterrupted power and Ethernet until completion. The final success condition is the expected MAC, model/hardware and target firmware readback.

TP-Link documents older ONVIF port 2020 and the newer default 80, with compatibility access on 2020 retained: https://www.tp-link.com/bg/support/faq/4201/
