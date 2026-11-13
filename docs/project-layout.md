# Project layout and Ubuntu handoff

- `src/vigi_provisioner/` contains the importable modules. Import modules as
  `vigi_provisioner.<module>`.
- `tests/` contains self-contained protocol checks and transport lease tests.
- `scripts/check_offline.py` runs the checks from a checkout.
- The original directory retains diagnostic scripts, packet captures, backup
  files, database state, certificates and keys, and live probes.

Camera operations are exposed as library functions. For Ubuntu testing, use a
dedicated camera network and pass the actual source interface address to the
functions that accept one. Several modules retain the original lab subnet
defaults. Create fresh local inventory and pin state through the library and
keep that state outside the checkout. Confirm the camera identity before
initialization or static-IP changes.

The consolidation was checked offline. The Ubuntu host and physical camera
still need integration testing.

Pass the approved MAC addresses explicitly via `inspect_device(..., authorized_macs=...)`.
For HTTPS dry runs, load a trusted TP-Link root bundle from outside the checkout
with `create_vigi_ssl_context(pem_path)` and pass the resulting context to
`VigiHttpsTransport(ssl_context=context)`.
