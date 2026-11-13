from .vigi_solar_aes import (
    encrypt_legacy,
    encrypt_gcm,
)


def build_solar_login(
    username,
    password_hash,
    aes_key,
    aes_iv,
    addition=None,
    encrypted=True,
):
    if encrypted:
        if addition is None:
            raise ValueError(
                "AES-GCM requires additional authenticated data"
            )

        user_result = encrypt_gcm(
            aes_key,
            aes_iv,
            addition,
            username,
        )

        password_result = encrypt_gcm(
            aes_key,
            aes_iv,
            addition,
            password_hash,
        )

        login = {
            "username": user_result["ciphertext"],
            "password": password_result["ciphertext"],
            "username_tag": user_result["auth_tag"],
            "password_tag": password_result["auth_tag"],
        }

    else:
        login = {
            "username": encrypt_legacy(
                aes_key,
                aes_iv,
                username,
            ),
            "password": encrypt_legacy(
                aes_key,
                aes_iv,
                password_hash,
            ),
        }

    return {
        "method": "do",
        "access": {
            "login": login,
        },
    }
