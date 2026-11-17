from dataclasses import dataclass
from urllib.parse import quote_plus
import json


@dataclass(frozen=True)
class VigiInitializationConfig:
    username: str = "admin"
    email: str = "support@comnet.bg"
    country: str = "BG"
    language: str = "English"
    power_line_frequency: str = "50hz"
    zone_id: str = "Europe/Athens"
    time_zone: str = "UTC+02:00"

    def timezone_request(self):
        return {
            "method": "set",
            "system": {
                "basic": {
                    "timezone": quote_plus(self.time_zone),
                    "zone_id": quote_plus(self.zone_id),
                }
            },
        }

    def frequency_request(self):
        return {
            "method": "set",
            "image": {
                "switch": {
                    "flicker": self.power_line_frequency
                }
            },
        }

    def validate(self):
        assert self.username == "admin"
        assert self.country == "BG"
        assert self.power_line_frequency == "50hz"
        assert self.zone_id == "Europe/Athens"
        assert self.time_zone == "UTC+02:00"


def load_provisioning_profile(path):
    """Load and validate the shared C320I settings before discovery."""
    from pathlib import Path
    import re
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib

    with Path(path).open("rb") as file:
        try:
            document = tomllib.load(file)
        except tomllib.TOMLDecodeError:
            raise ValueError("Invalid provisioning TOML syntax.") from None

    fields = {
        "username", "recovery_email", "language", "country",
        "time_zone", "zone_id", "power_line_frequency",
    }
    defaults = document.get("camera_defaults")
    if set(document) != {"camera_defaults"} or not isinstance(defaults, dict):
        raise ValueError("Expected a single [camera_defaults] table.")
    if set(defaults) != fields:
        raise ValueError("Expected exactly the seven nonsecret fields from provisioning.example.toml.")
    if any(not isinstance(value, str) or not value.strip() for value in defaults.values()):
        raise ValueError("All profile settings must be nonempty strings.")

    values = {key: value.strip() for key, value in defaults.items()}
    if values["username"] != "admin":
        raise ValueError("The C320I activation and ONVIF workflow requires username admin.")
    email = values.pop("recovery_email")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+", email) or len(email.encode("utf-8")) > 117:
        raise ValueError("Recovery email is invalid or too long for activation.")
    if not re.fullmatch(r"[A-Z]{2}", values["country"]):
        raise ValueError("Country must be a two-letter uppercase code.")
    if not re.fullmatch(r"UTC[+-](?:0[0-9]|1[0-4]):[0-5][0-9]", values["time_zone"]):
        raise ValueError("Time zone must use the UTC+HH:MM or UTC-HH:MM format.")
    if not re.fullmatch(r"[A-Za-z0-9_+.-]+(?:/[A-Za-z0-9_+.-]+)+", values["zone_id"]):
        raise ValueError("Zone ID must use an Area/Location format.")
    if values["power_line_frequency"] not in {"50hz", "60hz"}:
        raise ValueError("Power-line frequency must be 50hz or 60hz.")
    return VigiInitializationConfig(email=email, **values)
