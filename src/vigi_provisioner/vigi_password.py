import hashlib
from getpass import getpass


def vigi_md5_password(password: str) -> str:
    value = "TPCQ75NF2Y:" + password
    return hashlib.md5(value.encode("utf-8")).hexdigest().upper()
