# crypto.py
import base64

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def _cipher(key: str, iv: str) -> Cipher:
    key_bytes = key.encode(chr(34)+chr(117)+chr(116)+chr(102)+chr(45)+chr(56)+chr(34)) if isinstance(key, str) else bytes(key)
    iv_bytes = iv.encode(chr(34)+chr(117)+chr(116)+chr(102)+chr(45)+chr(56)+chr(34)) if isinstance(iv, str) else bytes(iv)

    if len(key_bytes) != 32:
        raise ValueError("AES-256 key must be exactly 32 bytes")

    if len(iv_bytes) != 16:
        raise ValueError("AES CTR IV must be exactly 16 bytes")

    return Cipher(
        algorithms.AES(key_bytes),
        modes.CTR(iv_bytes),
    )


def encrypt_json(plaintext: str, key: str, iv: str) -> str:
    encryptor = _cipher(key, iv).encryptor()
    ciphertext = encryptor.update(plaintext.encode("utf-8"))
    ciphertext += encryptor.finalize()
    return base64.b64encode(ciphertext).decode("ascii")


def decrypt_json(encoded: str, key: str, iv: str) -> str:
    ciphertext = base64.b64decode(encoded, validate=True)
    decryptor = _cipher(key, iv).decryptor()
    plaintext = decryptor.update(ciphertext)
    plaintext += decryptor.finalize()
    return plaintext.decode("utf-8")



from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding




from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


MIN_RSA_KEY_SIZE = 2048


def _validate_rsa_public_key(public_key):
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise ValueError("Expected RSA public key")

    if public_key.key_size < MIN_RSA_KEY_SIZE:
        raise ValueError(
            f"RSA key must be at least {MIN_RSA_KEY_SIZE} bits"
        )

    return public_key


def encrypt_session_key(aes_key: str, public_key_pem: str) -> str:
    key_bytes = (
        aes_key.encode("utf-8")
        if isinstance(aes_key, str)
        else bytes(aes_key)
    )

    if len(key_bytes) != 32:
        raise ValueError("AES session key must be 32 bytes")

    if not isinstance(public_key_pem, str):
        raise ValueError("PEM public key must be a string")

    try:
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode("ascii")
        )
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise ValueError("Invalid PEM public key") from exc

    public_key = _validate_rsa_public_key(public_key)

    ciphertext = public_key.encrypt(
        key_bytes,
        padding.PKCS1v15(),
    )

    return base64.b64encode(ciphertext).decode("ascii")


def encrypt_ipc_password(password: str, public_key_der: bytes) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")

    if not isinstance(public_key_der, bytes) or not public_key_der:
        raise ValueError("DER public key must be non-empty bytes")

    try:
        public_key = serialization.load_der_public_key(public_key_der)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid DER public key") from exc

    public_key = _validate_rsa_public_key(public_key)

    block_size = public_key.key_size // 8 - 11
    plaintext = password.encode("utf-8")

    encrypted = b"".join(
        public_key.encrypt(
            plaintext[offset:offset + block_size],
            padding.PKCS1v15(),
        )
        for offset in range(0, len(plaintext), block_size)
    )

    return base64.b64encode(encrypted).decode("ascii")
