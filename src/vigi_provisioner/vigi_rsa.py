import base64
from getpass import getpass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding


IPC_PUBLIC_KEY_B64 = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC4D6i0oD/Ga5qb"
    "//RfSe8MrPVIrMIGecCxkcGWGj9kxxk74qQNq8XUuXoy2PczQ30"
    "BpiRHrlkbtBEPeWLpq85tfubTUjhBz1NPNvWrC88uaYVGvzNpgz"
    "ZOqDC35961uPTuvdUa8vztcUQjEZy16WbmetRjURFIiWJgFCme"
    "myYVbQIDAQAB"
)


def encrypt_ipc_password(password: str) -> str:
    public_key_der = base64.b64decode(IPC_PUBLIC_KEY_B64)

    public_key = serialization.load_der_public_key(public_key_der)

    encrypted = public_key.encrypt(
        password.encode("utf-8"),
        padding.PKCS1v15(),
    )

    return base64.b64encode(encrypted).decode("ascii")
