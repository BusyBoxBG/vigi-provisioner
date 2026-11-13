from urllib.parse import quote_plus
import hashlib
from .password_constants import LOOKUP_K, SALT_L

def transform_password(password: str, password_type: str) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")

    if password_type != "md5":
        raise ValueError("Unsupported password type: " + str(password_type))

    return hashlib.md5(
        ("TPCQ75NF2Y:" + password).encode("utf-8")
    ).hexdigest().upper()

    units = [int.from_bytes(password.encode("utf-16-be")[i:i+2], "big") for i in range(0, len(password.encode("utf-16-be")), 2)]
    result = []
    for i in range(max(len(units), len(SALT_L))):
        a = units[i] if i < len(units) else 187
        b = ord(SALT_L[i]) if i < len(SALT_L) else 187
        result.append(LOOKUP_K[(a ^ b) % len(LOOKUP_K)])
    return "".join(result)

def build_set_password(username, password, password_type, email, language, ipc_public_key_der, security_questions=None):
    from .crypto import encrypt_ipc_password

    if not isinstance(username, str) or not username.strip():
        raise ValueError("Username must be a non-empty string")

    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")

    if not isinstance(password_type, str) or password_type != "md5":
        raise ValueError("Unsupported password type")

    if email is not None and not isinstance(email, str):
        raise ValueError("Email must be a string or None")

    if not isinstance(language, str) or not language.strip():
        raise ValueError("Language must be a non-empty string")

    if not isinstance(ipc_public_key_der, bytes) or not ipc_public_key_der:
        raise ValueError("IPC public key must be non-empty DER bytes")

    if security_questions is not None:
        if not isinstance(security_questions, dict):
            raise ValueError("Security questions must be a dictionary")

        names = (
            "sec_question_1", "sec_question_2", "sec_question_3",
            "sec_answer_1", "sec_answer_2", "sec_answer_3"
        )

        if any(
            name not in security_questions
            or not isinstance(security_questions[name], str)
            or not security_questions[name].strip()
            for name in names
        ):
            raise ValueError("All six security-question fields must be non-empty strings")

    fields = {
        "password": transform_password(password, password_type),
        "username": username,
        "passwdType": password_type,
        "reset_pwd_email": None if email is None else quote_plus(email, encoding="utf-8"),
        "preset_ipc_passwd": None,
        "preset_ipc_email": None,
        "ciphertext": encrypt_ipc_password(password, ipc_public_key_der),
        "language": language,
    }
    if security_questions is not None:
        fields.update({name: security_questions[name] for name in names})
    return {"method": "do", "set_password": fields}


def build_basic_settings(timezone, zone_id, flicker):
    return {
        "method": "set",
        "system": {"basic": {
            "timezone": None if timezone is None else quote_plus(timezone, encoding="utf-8"),
            "zone_id": None if zone_id is None else quote_plus(zone_id, encoding="utf-8"),
        }},
        "image": {"switch": {"flicker": flicker}},
    }
