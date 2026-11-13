import hashlib
import re
import ssl
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes


EXPECTED_ROOT_FINGERPRINTS = frozenset({
    "81735976c574b68df2ad14f513a158f78018ee292e95d8d1e05fff3039f4fba1",
    "7632deaa7470ef4168884a00efa01aead37a79f82a3db13cafb0656c66bb6deb",
})


class VigiTLSConfigurationError(RuntimeError):
    pass


def validate_root_bundle(pem_path):
    path = Path(pem_path)

    if not path.is_file():
        raise VigiTLSConfigurationError(
            f"Missing TP-Link root CA bundle: {path}"
        )

    data = path.read_bytes()

    blocks = re.findall(
        rb"-----BEGIN CERTIFICATE-----.*?"
        rb"-----END CERTIFICATE-----",
        data,
        flags=re.DOTALL,
    )

    if len(blocks) != 2:
        raise VigiTLSConfigurationError(
            f"Expected 2 root certificates, found {len(blocks)}"
        )

    fingerprints = set()

    for block in blocks:
        cert = x509.load_pem_x509_certificate(block)

        fingerprint = cert.fingerprint(
            hashes.SHA256()
        ).hex()

        fingerprints.add(fingerprint)

        try:
            basic = cert.extensions.get_extension_for_class(
                x509.BasicConstraints
            ).value
        except x509.ExtensionNotFound as exc:
            raise VigiTLSConfigurationError(
                "Root certificate lacks BasicConstraints"
            ) from exc

        if not basic.ca:
            raise VigiTLSConfigurationError(
                "Root certificate is not a CA"
            )

        try:
            usage = cert.extensions.get_extension_for_class(
                x509.KeyUsage
            ).value
        except x509.ExtensionNotFound as exc:
            raise VigiTLSConfigurationError(
                "Root certificate lacks KeyUsage"
            ) from exc

        if not usage.key_cert_sign:
            raise VigiTLSConfigurationError(
                "Root certificate cannot sign certificates"
            )

    if fingerprints != EXPECTED_ROOT_FINGERPRINTS:
        raise VigiTLSConfigurationError(
            "TP-Link root certificate fingerprints do not match"
        )

    return tuple(sorted(fingerprints))


def create_vigi_ssl_context(pem_path=None):
    if pem_path is None:
        pem_path = (
            Path(__file__).resolve().parent
            / "vigi_tp_link_roots.pem"
        )

    validate_root_bundle(pem_path)

    context = ssl.SSLContext(
        ssl.PROTOCOL_TLS_CLIENT
    )

    context.minimum_version = ssl.TLSVersion.TLSv1_2

    context.load_verify_locations(
        cafile=str(pem_path)
    )

    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED

    return context
