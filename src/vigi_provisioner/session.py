import secrets

def generate_session_credentials():
    key = secrets.token_bytes(32)
    iv = secrets.token_bytes(16)
    return key, iv
