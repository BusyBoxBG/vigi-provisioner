import base64
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers import (
    Cipher,
    algorithms,
    modes,
)
from cryptography.hazmat.primitives import padding

from .vigi_solar_aes import encrypt_gcm


@dataclass(frozen=True)
class PreparedSolarRequest:
    body: bytes
    headers: dict


def prepare_solar_request(
    json_text,
    *,
    encrypted=False,
    digest_type=None,
    aes_key=None,
    aes_iv=None,
    addition=None,
):
    if not isinstance(json_text, str):
        raise TypeError("JSON body must be a string")

    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json",
        "Connection": "close",
        "If-encrypt": "1" if encrypted else "0",
    }

    if not encrypted:
        return PreparedSolarRequest(
            body=json_text.encode("utf-8"),
            headers=headers,
        )

    if aes_key is None or aes_iv is None:
        raise ValueError(
            "Encrypted requests require AES key and IV"
        )

    if digest_type == 17:
        if addition is None:
            raise ValueError(
                "AES-GCM requires additional authenticated data"
            )

        result = encrypt_gcm(
            aes_key,
            aes_iv,
            addition,
            json_text,
        )

        headers["Auth-Tag"] = result["auth_tag"]

        return PreparedSolarRequest(
            body=base64.b64decode(result["ciphertext"]),
            headers=headers,
        )

    padder = padding.PKCS7(128).padder()

    padded = (
        padder.update(json_text.encode("utf-8"))
        + padder.finalize()
    )

    cipher = Cipher(
        algorithms.AES(aes_key),
        modes.CBC(aes_iv),
    )

    encryptor = cipher.encryptor()

    return PreparedSolarRequest(
        body=encryptor.update(padded)
        + encryptor.finalize(),
        headers=headers,
    )



def decrypt_solar_response(
    response_body,
    *,
    if_encrypt,
    auth_tag=None,
    aes_key=None,
    aes_iv=None,
    addition=None,
):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if isinstance(response_body, bytes):
        ciphertext = response_body
    elif isinstance(response_body, str):
        ciphertext = response_body.encode("iso-8859-1")
    else:
        raise TypeError(
            "Response body must be bytes or ISO-8859-1 string"
        )

    if not isinstance(if_encrypt, str) or if_encrypt not in ("0", "1"):
        raise ValueError("Invalid Solar response encryption flag")

    if if_encrypt == "0":
        if auth_tag is not None:
            raise ValueError(
                "Plaintext Solar response must not contain Auth-Tag"
            )
        return ciphertext.decode("utf-8")

    if addition is not None and auth_tag is None:
        raise ValueError(
            "AES-GCM Solar response requires Auth-Tag"
        )

    if addition is None and auth_tag is not None:
        raise ValueError(
            "Legacy AES-CBC response must not contain Auth-Tag"
        )

    if aes_key is None or aes_iv is None:
        raise ValueError(
            "Encrypted response requires AES key and IV"
        )

    if auth_tag is not None:
        if addition is None:
            raise ValueError(
                "AES-GCM response requires additional data"
            )

        tag = base64.b64decode(
            auth_tag,
            validate=True,
        )

        if len(tag) != 16:
            raise ValueError(
                "AES-GCM authentication tag must be 16 bytes"
            )

        plaintext = AESGCM(aes_key).decrypt(
            aes_iv,
            ciphertext + tag,
            addition,
        )

        return plaintext.decode("utf-8")

    if len(ciphertext) == 0 or len(ciphertext) % 16:
        raise ValueError(
            "Invalid AES-CBC ciphertext length"
        )

    cipher = Cipher(
        algorithms.AES(aes_key),
        modes.CBC(aes_iv),
    )

    decryptor = cipher.decryptor()

    padded = (
        decryptor.update(ciphertext)
        + decryptor.finalize()
    )

    unpadder = padding.PKCS7(128).unpadder()

    plaintext = (
        unpadder.update(padded)
        + unpadder.finalize()
    )

    return plaintext.decode("utf-8")
