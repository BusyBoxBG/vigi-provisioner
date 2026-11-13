from getpass import getpass
from pathlib import Path
import json

from .vigi_activation import build_activation_request
from .vigi_initialization_config import VigiInitializationConfig


def redact_activation_request(request):
    """Return a safe structural preview without credentials."""
    if not isinstance(request, dict):
        raise TypeError("Activation request must be a dictionary")

    return {
        "method": request.get("method"),
        "set_password": {
            key: (
                "<REDACTED>"
                if key in {
                    "password",
                    "ciphertext",
                    "preset_ipc_passwd",
                }
                else value
            )
            for key, value in request.get(
                "set_password", {}
            ).items()
        },
    }


def build_initialization_plan(password):
    config = VigiInitializationConfig()
    config.validate()

    activation = build_activation_request(
        password=password,
        username=config.username,
        email=config.email,
        language=config.language,
    )

    return {
        "activation": activation,
        "timezone": config.timezone_request(),
        "frequency": config.frequency_request(),
    }


def main():
    config = VigiInitializationConfig()
    config.validate()

    print("VIGI INITIALIZATION DRY RUN")
    print("=" * 45)
    print("Target country:", config.country)
    print("Zone ID:", config.zone_id)
    print("Time zone:", config.time_zone)
    print("Frequency:", config.power_line_frequency)
    print()

    password = getpass("Enter camera admin password: ")

    if not password:
        raise ValueError("Password cannot be empty")

    plan = build_initialization_plan(password)

    safe_plan = {
        "activation": redact_activation_request(
            plan["activation"]
        ),
        "timezone": plan["timezone"],
        "frequency": plan["frequency"],
    }

    print()
    print("INITIALIZATION PLAN")
    print(json.dumps(safe_plan, indent=2))

    print()
    print("Stages prepared:", len(plan))
    print("Network requests sent: 0")
    print("Camera configuration changes: 0")
