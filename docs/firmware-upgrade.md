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

## C340S V1 staged upgrade experiment

A second C340S hardware 1.0 camera passed initialization-only with current firmware `2.0.3 Build 240412 Rel.42481n`. The first camera was initially the preserved-2024 reference; it was subsequently upgraded during the successful continuous GUI test. Both C340S units now run 3.2.1. The official 3.2.1 release notes require at least 2.5.0, and 2.5.1 permits upgrading from older versions except 2.5.0. The controlled route implemented here is exactly **2.0.3 → 2.5.1 → 3.2.1**. Other source versions are not inferred compatible. Vendor notes say that downgrading after 2.5.1 is unavailable.

Sources: [3.2.1 release notes](https://static.tp-link.com/upload/firmware/2026/202605/20260512/Release%20Note%20VIGI%20C340S%28UN%29%201.0_3.2.1%20Build%20260320.pdf), [2.5.1 release notes](https://static.tp-link.com/upload/firmware/2025/202504/20250418/Release%20note%20VIGI%20C340S%28UN%29_V1_2.5.1%20Build%20250327%20Rel.67051n.pdf).

`vigi_c340s_upgrade.py` is a separate explicit experiment. It requires a C340S inventory record, initialized discovery at the lab factory address, matching MAC and Device ID, authenticated ONVIF model/hardware/MAC and the exact source version. It verifies both the inspected ZIP hash and image hash. Preflight is the default. `--execute` additionally requires certificate approval, HTTPS login, a typed device-ID/target-version confirmation and a fresh source-version read before upload. One upload is sent; an interrupted response is followed by readback, never an automatic resend. ONVIF ports 2020 and 80 are checked for the expected target version. It stops after each upgrade and does not activate, configure site/network settings, update inventory, or automatically run the next stage. An already-installed stage target skips uploading.

| Stage | Target image | Image SHA-256 | ZIP SHA-256 |
| --- | --- | --- | --- |
| bridge | C340S_1.0_en_2.5.1_Build_250327_Rel.67051n_up_boot-signed.bin | e991185eee0c34eb6a532fe343fb8392aa62631968fdbfb43d5c2bf75d4b82c5 | b5268042e1a3abff9039b4fa06f0f816632ad82c579310ac1926f59b295ba2ce |
| latest | C340S_1.0_en_3.2.1_Build_260320_Rel.22146n_up_boot_signed.bin | 44e06b69c44d96bbd103deba5097bcbd8be4774e500dfc8159dcae65140816a2 | e54840807895ee61eceaf830c6474e90a7c263620278ab16497f6d1617f5cbc4 |

The original official packages and both image hashes were inspected locally. Offline tests cover package/image changes, preflight without upload, forbidden direct old-to-latest upgrades, cancelled confirmation, identity mismatch and target readback. Both C340S stages passed real upload and authenticated target-version verification. Site settings and port-80 static network/DNS configuration then passed on 3.2.1. These tested stages are now integrated into the GUI approved-update path; the combined automatic chain passed a continuous real-hardware GUI run, including both uploads and final configuration.

Example first-stage preflight:

```bash
PYTHONPATH=src python -m vigi_provisioner.vigi_c340s_upgrade \
  --inventory "$HOME/vigi-test-inventory.sqlite3" \
  --device-id 3B27D0E000E0AF692 \
  --stage bridge --package "$HOME/vigi-c340s-2.5.1.zip"
```

Only after reviewing preflight, repeat with `--execute` for a real upgrade. For the latest stage, use its inspected original ZIP and `--stage latest`. Each stage requires its own confirmation and hardware verification.

The continuous C340S GUI chain is now hardware-verified: both actual upgrades, certificate reapproval/fresh login after each, modern configuration selection, static networking and DNS completed in one run on 2026-11-24. The first target-already-installed 3.2.1 factory-reset GUI branch also passed, without repeating uploads. See [completed GUI evidence](test-gui.md#completed-continuous-c340s-hardware-run) and [tested model revisions](../README.md#tested-camera-models).
