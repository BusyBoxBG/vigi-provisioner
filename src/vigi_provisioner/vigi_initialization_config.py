from dataclasses import dataclass
from urllib.parse import quote_plus
from ipaddress import IPv4Address


@dataclass(frozen=True)
class ClockProfile:
    ntp: dict
    dst_manual: dict

    def settings_request(self, config):
        request = config.timezone_request()
        request["system"]["basic"].update(
            date_format=2, time_format=0, timing_mode="ntp"
        )
        request["system"]["dst_manual"] = dict(self.dst_manual)
        return request

    def ntp_request(self):
        return {"method": "set", "system": {"ntp": dict(self.ntp)}}


@dataclass(frozen=True)
class VigiInitializationConfig:
    username: str = "admin"
    email: str = "support@comnet.bg"
    country: str = "BG"
    language: str = "English"
    power_line_frequency: str = "50hz"
    zone_id: str = "Europe/Athens"
    time_zone: str = "UTC+02:00"
    clock: ClockProfile | None = None
    dns: tuple[str, str] | None = None
    video: dict | None = None
    platform_access: bool | None = None

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
    if set(document) - {"camera_defaults", "clock", "dns", "video", "platform_access"} or not isinstance(defaults, dict):
        raise ValueError("Expected [camera_defaults] and optional [clock] and [dns] tables.")
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
    clock = load_clock_profile(document["clock"]) if "clock" in document else None
    dns = load_dns_profile(document["dns"]) if "dns" in document else None
    video = load_video_profile(document["video"]) if "video" in document else None
    platform_access = None
    if "platform_access" in document:
        section = document["platform_access"]
        if not isinstance(section, dict) or set(section) != {"enabled"} or type(section["enabled"]) is not bool:
            raise ValueError("Expected a boolean enabled field in [platform_access].")
        platform_access = section["enabled"]
    return VigiInitializationConfig(
        email=email, clock=clock, dns=dns, video=video,
        platform_access=platform_access, **values,
    )


def load_video_profile(video):
    expected = {
        "codec": "H265", "width": 1920, "height": 1080, "fps": 15,
        "bitrate_mode": "vbr", "quality": "high", "max_bitrate_kbps": 2048,
        "smart_codec": False,
    }
    if not isinstance(video, dict) or set(video) != set(expected):
        raise ValueError("Expected all video fields from provisioning.example.toml.")
    if any(type(video[key]) is not type(value) or video[key] != value for key, value in expected.items()):
        raise ValueError("Video profile currently supports the verified H265, 1080p, 15 fps, VBR High, 2048 kbps settings.")
    return {
        "encode_type": "H265", "resolution": "1920*1080", "frame_rate": "65551",
        "quality": "5", "bitrate_type": "vbr", "bitrate": 2048, "smart_codec": "off",
    }


def load_dns_profile(dns):
    if not isinstance(dns, dict) or set(dns) != {"primary", "secondary"}:
        raise ValueError("Expected primary and secondary in [dns].")
    addresses = []
    for field in ("primary", "secondary"):
        value = dns[field]
        if not isinstance(value, str):
            raise ValueError(f"DNS {field} must be an IPv4 address string.")
        address = IPv4Address(value)
        if address.is_unspecified or address.is_multicast or int(address) == 0xffffffff:
            raise ValueError(f"DNS {field} must be a unicast IPv4 address.")
        addresses.append(str(address))
    return addresses[0], addresses[1]


def load_clock_profile(clock):
    if not isinstance(clock, dict) or set(clock) != {"date_format", "time_format", "ntp", "dst_manual"}:
        raise ValueError("Expected date_format, time_format, ntp and dst_manual in [clock].")
    if clock["date_format"] != "DD-MM-YYYY" or clock["time_format"] != "24-hour":
        raise ValueError("The verified clock profile requires DD-MM-YYYY and 24-hour.")

    ntp = clock["ntp"]
    if not isinstance(ntp, dict) or set(ntp) != {"server", "port", "interval"}:
        raise ValueError("Expected server, port and interval in [clock.ntp].")
    if not isinstance(ntp["server"], str):
        raise ValueError("NTP server must be an IPv4 address string.")
    server = IPv4Address(ntp["server"])
    if server.is_unspecified or server.is_multicast or int(server) == 0xffffffff:
        raise ValueError("NTP server must be a unicast IPv4 address.")
    if type(ntp["port"]) is not int or not 1 <= ntp["port"] <= 65535:
        raise ValueError("NTP port must be between 1 and 65535.")
    if type(ntp["interval"]) is not int or ntp["interval"] < 1:
        raise ValueError("NTP interval must be a positive number of minutes.")

    bounds = {"dst_savings": (1, 120)}
    for edge in ("start", "end"):
        for field, limit in {"month": (1, 12), "week": (1, 5), "day": (0, 6), "hour": (0, 23)}.items():
            bounds[f"{edge}_{field}"] = limit
    dst = clock["dst_manual"]
    if not isinstance(dst, dict) or set(dst) != bounds.keys():
        raise ValueError("Expected DST savings and a complete start and end schedule.")
    for field, (low, high) in bounds.items():
        if type(dst[field]) is not int or not low <= dst[field] <= high:
            raise ValueError(f"Invalid manual DST field: {field}.")
    return ClockProfile(
        ntp=dict(ntp, server=str(server)),
        dst_manual={"enabled": "on", **{field: str(value) for field, value in dst.items()}},
    )
