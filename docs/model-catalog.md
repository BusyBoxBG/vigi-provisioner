# Camera models and firmware catalog

`models.toml` is the editable model catalog. The SQLite inventory continues to store individual scanned cameras and approved network assignments. Each catalog entry identifies one model, hardware revision and region. Hardware V1 and V1.20 are separate entries even where an official package is shared.

On first GUI startup, `models.toml` is created beside `provisioning.toml` from the tracked `models.example.toml`. The 12 supplied model/hardware combinations are seeded. Their official support pages were checked on 2026-11-24. Recorded ZIP URLs use the actual links published on those pages, including six-digit firmware build dates. Original supplied URLs with eight-digit build dates were corrected. This is support-page verification, not firmware binary integrity or camera compatibility verification.

The local file is ignored by Git and never overwritten by an update. Back it up before editing. Edit it using `nano /opt/vigi-provisioner/models.toml`, then use the GUI catalog controls to reload it (or refresh the browser). The server reads it on demand. Invalid TOML is reported without replacing the file. `--models /path/to/models.toml` selects another location. If the packaged example is unavailable when starting outside the repository, the GUI creates an empty catalog that can be populated manually.

```toml
schema_version = 1

[[models]]
id = "vigi-c320i-v1.20"
model = "VIGI C320I"
hardware_version = "1.20"
region = "UN"
support_url = "https://www.tp-link.com/en/support/download/vigi-c320i/v1.20/#Firmware"
firmware_url = "https://static.tp-link.com/upload/firmware/2026/202607/20260720/VIGI%20Cx20I(UN)_V1.20_2.2.1%20Build%20260605.zip"
firmware_version = "2.2.1 Build 260605"
```

The optional check fields are `last_checked`, `check_status` and `available_firmware_urls`. The GUI writes TOML through an atomic file replacement. Use unique stable IDs; changing an ID creates a separate entry. Existing camera references are not rewritten when a catalog entry is edited or renamed.

## GUI actions

- **Add or edit model** saves a catalog entry. Reusing an ID updates that entry. Edit fills the form from an existing row. Models do not require a firmware URL if no upgrade is available.
- **Catalog model / hardware** on Add camera fills the model and hardware fields and stores `catalog_id` and `hardware_version` with that new camera. Existing inventory rows remain unchanged and may have unknown hardware/catalog linkage.
- **Check for new firmware** retrieves only the official support-page HTML. It lists firmware ZIP candidates in page order with a UTC check time. It does not infer that every candidate is newer or compatible, does not replace the recorded firmware version/URL, and does not fetch or install binaries. Review the official release notes, region and hardware revision, then explicitly edit the recorded version/URL as appropriate.

Checking requires Internet access from the GUI host. With an offline Ubuntu instance, the seeded catalog, manual edits and inventory selection still work; checks show an error and retain recorded firmware. Support-page layout changes or missing links also retain the recorded values. Only HTTPS model download pages on www.tp-link.com/www.vigi.com and firmware ZIP links under static.tp-link.com/upload/firmware are accepted. Redirects are bounded and validated, response size is bounded, and environment proxies are ignored.

## Provisioning compatibility is separate

Adding a catalog entry does not grant camera-write or upgrade support. GUI provisioning remains restricted to the tested VIGI C320I engine, with known hardware 1.20 (1.2 alias). Existing rows without a recorded hardware revision preserve prior behavior. Other listed models and C320I V1 can be inventoried but require capability testing before provisioning. The existing firmware uploader still enforces its inspected package/checksum/source-version rules; the catalog is not connected to upload authorization or package selection. Never select a package solely because its filename resembles another model.

## Python implementation

`vigi_model_catalog.py` validates model rows and official URLs, reads/writes TOML, extracts firmware ZIP anchors using HTMLParser, and checks official pages with bounded requests. It never contacts a camera or runs downloaded code. `vigi_test_gui.py` supplies the catalog controls and HTTP endpoints, persists new camera catalog/hardware fields with additive SQLite migration, and blocks untested known hardware at GUI provisioning start. `test_model_catalog.py` covers catalog round trips, URL rejection, link extraction and recorded-firmware preservation. Existing GUI firmware-mode tests continue to check upgrade opt-in behavior.
