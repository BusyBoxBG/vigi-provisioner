import base64

from cryptography.hazmat.primitives.ciphers import (
    Cipher,
    algorithms,
    modes,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import padding


def encrypt_legacy(key, iv, plaintext):
    padder = padding.PKCS7(128).padder()

    data = plaintext.encode("utf-8")
    padded = padder.update(data) + padder.finalize()

    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
    )

    encryptor = cipher.encryptor()

    encrypted = (
        encryptor.update(padded)
        + encryptor.finalize()
    )

    return base64.b64encode(encrypted).decode("ascii")


def encrypt_gcm(key, iv, aad, plaintext):
    encrypted = AESGCM(key).encrypt(
        iv,
        plaintext.encode("utf-8"),
        aad,
    )

    ciphertext = encrypted[:-16]
    auth_tag = encrypted[-16:]

    return {
        "ciphertext": base64.b64encode(
            ciphertext
        ).decode("ascii"),
        "auth_tag": base64.b64encode(
            auth_tag
        ).decode("ascii"),
    }
