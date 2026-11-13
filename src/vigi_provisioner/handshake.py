# handshake.py

from .crypto import encrypt_session_key
from .packets import encode_packet, encode_tlv


def build_key_request(camera_mac: str) -> bytes:
    """Build UDP packet type 8."""
    payload = encode_tlv(5, camera_mac.encode("utf-8"))
    return encode_packet(8, payload)


def build_session_request(
    camera_mac: str,
    client_mac: str,
    cipher_name: str,
    aes_key: str,
    aes_iv: str,
    camera_public_key: str,
) -> bytes:
    """Build UDP packet type 10."""

    iv_bytes = aes_iv.encode("utf-8") if isinstance(aes_iv, str) else bytes(aes_iv)
    if len(iv_bytes) != 16:
        raise ValueError("AES IV must be 16 bytes")

    encrypted_key = encrypt_session_key(
        aes_key,
        camera_public_key,
    )

    payload = b"".join(
        [
            encode_tlv(5, camera_mac.encode("utf-8")),
            encode_tlv(56, cipher_name.encode("utf-8")),
            encode_tlv(59, encrypted_key.encode("ascii")),
            encode_tlv(68, client_mac.encode("utf-8")),
            encode_tlv(67, iv_bytes),
        ]
    )

    return encode_packet(10, payload)


from .crypto import encrypt_json


def build_encrypted_request(
    camera_mac: str,
    client_mac: str,
    json_payload: str,
    aes_key: str,
    aes_iv: str,
) -> bytes:
    """Build UDP packet type 13."""

    encrypted_json = encrypt_json(
        json_payload,
        aes_key,
        aes_iv,
    )

    payload = b"".join(
        [
            encode_tlv(5, camera_mac.encode("utf-8")),
            encode_tlv(68, client_mac.encode("utf-8")),
            encode_tlv(69, encrypted_json.encode("ascii")),
        ]
    )

    return encode_packet(13, payload)
