import json
from getpass import getpass
from urllib.parse import quote_plus

from .vigi_password import vigi_md5_password
from .vigi_rsa import encrypt_ipc_password


def build_activation_request(
    password: str,
    username: str = "admin",
    email: str = "",
    language: str = "English",
):
    if not password:
        raise ValueError("Password cannot be empty")

    if not username:
        raise ValueError("Username cannot be empty")

    return {
        "method": "do",
        "set_password": {
            "password": vigi_md5_password(password),
            "username": username,
            "passwdType": "md5",
            "reset_pwd_email": quote_plus(email),
            "preset_ipc_passwd": None,
            "preset_ipc_email": None,
            "ciphertext": encrypt_ipc_password(password),
            "language": language,
        },
    }
