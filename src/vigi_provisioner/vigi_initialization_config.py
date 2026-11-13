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
