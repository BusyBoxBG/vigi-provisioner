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

Adding a catalog entry does not grant camera-write or upgrade support. GUI provisioning is restricted to tested C320I hardware 1.20 (1.2 alias) and C340S hardware V1/1.0 paths. Existing rows without a recorded hardware revision preserve prior behavior. Other listed models and C320I V1 can be inventoried but require capability testing before provisioning. The existing firmware uploader still enforces its inspected package/checksum/source-version rules. The catalog selects a local approved image for the GUI worker but does not expand upload compatibility. Never select a package solely because its filename resembles another model.

## Python implementation

`vigi_model_catalog.py` validates model rows and official URLs, reads/writes TOML, extracts firmware ZIP anchors using HTMLParser, and checks official pages with bounded requests. It never contacts a camera or runs downloaded code. `vigi_test_gui.py` supplies the catalog controls and HTTP endpoints, persists new camera catalog/hardware fields with additive SQLite migration, and blocks untested known hardware at GUI provisioning start. `test_model_catalog.py` covers catalog round trips, URL rejection, link extraction and recorded-firmware preservation. Existing GUI firmware-mode tests continue to check upgrade opt-in behavior.

## Default approved firmware and local downloads

The former recorded firmware version/URL are now labeled **Default initial update firmware**. Existing `firmware_version` and `firmware_url` TOML keys are retained to preserve local catalogs. A default URL is not considered locally approved until download succeeds. Checks still only list candidates and never silently switch the default.

1. Use **Download and approve default** for the current default, or check for firmware and choose **Use as default and download** on a candidate.
2. Review the model, exact hardware, region, package and version in the inline approval form, then confirm. The server downloads the official ZIP, requires exactly one `.bin` image, extracts only that image to a controlled folder, calculates ZIP/image SHA-256 digests and atomically records the approval. Failure retains the previous catalog default.
3. **Download and approve all listed defaults** performs those downloads sequentially for the current recorded defaults without starting any camera upgrades. Per-model errors are shown; successful approvals remain available.
4. Link existing camera rows using **Link selected catalog model**, after selecting the exact catalog model/hardware in Add camera. Newly added cameras can be linked at creation.
5. Start provisioning in **Update to default approved firmware after initialization**, the new GUI default. The local image, model/hardware/region binding and checksum are checked before the worker starts. After activation, authenticated device checks, current/target firmware checks, typed upgrade confirmation and post-upgrade verification remain in force. If the known target is already installed, uploading is skipped.

The Ubuntu default cache is `/opt/vigi-provisioner/firmware` when the profile is `/opt/vigi-provisioner/provisioning.toml`. Override it with `--firmware-dir /path/to/firmware`. Each model ID has a directory containing a ZIP-hash subdirectory, `firmware.zip` and the original `.bin` filename. The catalog stores approval time, image/ZIP paths and both hashes in `approved_at`, `approved_image`, `approved_zip`, `approved_sha256` and `approved_zip_sha256`. Images are rehashed before use. Cache files and local approval state are not committed to Git.

A 512 MiB ZIP/image size limit and exactly-one-image rule apply. ZIP content is never executed. Downloaded bytes from HTTPS and stored checksums establish repeatable local content, not a new vendor-signature verification mechanism. Known upgrade images still require the previously inspected hardcoded checksum. Multi-image packages require manual inspection and are not automatically approved. Editing a model in the GUI clears its approval and requires a new download/approval.

Internet access is required only to check or download; previously approved local images can be used offline. Merely adding a camera to inventory does not change the camera. Start provisioning initiates activation and the approved upgrade-before-configuration path. The preserved-stock test camera must use **Keep existing firmware**. The older profile-controlled upgrade option remains available separately.

Downloads and approvals are available for all catalog entries. Actual upgrades support the inspected C320I hardware 1.20 UN package/source path and C340S V1 UN two-stage route described below. A newer catalog approval or another model does not bypass these limits; the GUI explains an unsupported image before activation.

`vigi_firmware_cache.py` performs bounded official downloads, safe single-image extraction, checksum recording and cache-file validation. It never contacts a camera. Offline cache tests cover successful approval, unchanged previous rows, multiple-image rejection, unselected URLs and altered cached files. An official Cx20I download and GUI approval passed locally with the previously verified image hash; no camera upgrade was performed during this feature test.

The GUI also permits an explicit initialization-only experiment for C340S using the inspected factory activation page. This does not authorize full provisioning or firmware upload; see [initialization-only tests](test-gui.md#initialization-only-compatibility-tests).

C340S V1 can now run the staged-tested full configuration path in Keep existing firmware mode, with authenticated checks for hardware 1.0 and firmware 2.0.3 Build 240412 Rel.42481n before site writes. The preserved-firmware combined GUI cycle passed. Catalog-approved upgrades now use the separately inspected two-stage route; arbitrary catalog packages remain blocked.

## C340S intermediate package

**Prepare intermediate 2.5.1** downloads and verifies the inspected prerequisite ZIP, saves its local path/hash in `bridge_package` and `bridge_sha256`, and leaves the approved default target unchanged. This is a package preparation action and never contacts a camera. The GUI preflights that package and the approved 3.2.1 image before a C340S full update run. See [integrated workflow](test-gui.md#c340s-approved-update-and-provisioning).

### Offline C340S target import

Use **Import local 3.2.1 ZIP** on the C340S V1 model row and enter `/root/vigi-c340s-3.2.1.zip` (or its actual server path). The server copies it to a temporary cache location, checks the exact inspected ZIP and image hashes, then records it as the approved default. No Internet or camera access is involved. This importer supports only the inspected C340S V1 UN 3.2.1 package; arbitrary imports remain unsupported. Failed imports retain the previous default.

For the intermediate package, the existing `/root/vigi-c340s-2.5.1.zip` is sufficient as a checked fallback when launching the GUI as root; override its location with `--c340s-bridge-package`. Online systems can instead use Prepare intermediate 2.5.1. Both package paths are checked before a C340S approved-update worker starts.
