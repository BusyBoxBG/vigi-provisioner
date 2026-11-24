"""Provision one factory-state VIGI C320I using the tested lab workflow."""

import argparse
import base64
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import sqlite3
import ssl
import time
from contextlib import closing
from getpass import getpass
from pathlib import Path
from urllib.parse import quote, unquote

from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_der_public_key

from .vigi_certificate_pin import CertificatePinError, normalize_sha256_pin
from .vigi_discovery import discover
from .vigi_initialization_config import VigiInitializationConfig, load_provisioning_profile
from .vigi_onvif_gateway_config import prepare_default_gateway
from .vigi_onvif_live_transport import ENDPOINT, SOURCE_IP, make_live_transport
from .vigi_onvif_network import get_network_default_gateway, get_network_interfaces
from .vigi_onvif_static_ip import prepare_static_ipv4
from .vigi_password import vigi_md5_password
from .vigi_pin_inventory import normalize_mac
from .vigi_pinned_tls import connect_pinned_tls
from .vigi_rsa import encrypt_ipc_password
from .vigi_static_ip_coordinator import execute_with_transport

CAMERA_IP = "192.168.0.60"
USERNAME = "admin"
INTERFACE = "eth0"


class ProvisioningError(RuntimeError):
    pass


class CameraHTTPS(http.client.HTTPConnection):
    def __init__(self, pin, camera_ip=CAMERA_IP):
        super().__init__(camera_ip, 443, timeout=10)
        self.pin = pin

    def connect(self):
        self.sock = connect_pinned_tls(self.host, 443, SOURCE_IP, self.pin, timeout=10)

    def post(self, stage, payload, *, path="/", challenge=False):
        try:
            self.request(
                "POST", path,
                body=json.dumps(payload, separators=(",", ":")).encode(),
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            response = self.getresponse()
            status = response.status
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError("Oversized response")
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError("Expected a JSON object")
        except Exception as exc:
            raise ProvisioningError(f"{stage}: request failed ({type(exc).__name__}).") from None
        finally:
            self.close()

        code = body.get("error_code")
        detail = code if type(code) is int else "unexpected"
        print(f"{stage}: HTTP {status}, camera code {detail}", flush=True)
        if challenge:
            if status not in (200, 401):
                raise ProvisioningError(f"{stage}: unexpected HTTP status.")
        elif status != 200 or type(code) is not int or code != 0:
            raise ProvisioningError(f"{stage}: camera did not confirm success.")
        return status, body


def confirm_factory(camera):
    status, body = camera.post(
        "Factory-state check", {"method": "get", "system": {"basic": {}}}, challenge=True
    )
    data = body.get("data")
    if (
        status != 401 or body.get("error_code") != -40401
        or not isinstance(data, dict) or data.get("code") != -40405
    ):
        raise ProvisioningError("HTTPS did not confirm factory state.")


# Exact resources inspected from factory-state HAR captures. Unknown builds stop.
ACTIVATION_RESOURCES = (
    ("/pc/Initial.htm", "170a83d3dc6bde88c886b5aab43b4a6a78f733a23ab3a6fc837c13341bb291e3", "legacy-2.0.4"),
    ("/index.f129addb.js", "7d8169187aa8feb9fbb9a0aa77641e29c58989a92854db773688ca5617ffba33", "modern"),
)


def detect_activation_format(camera):
    """Read known web resources over pinned HTTPS; never execute JavaScript."""
    matches = set()
    for path, expected_hash, activation_format in ACTIVATION_RESOURCES:
        try:
            camera.request("GET", path, headers={"Accept-Encoding": "identity"})
            response = camera.getresponse()
            raw = response.read(4_000_001)
            if response.status == 200 and len(raw) <= 4_000_000:
                if hashlib.sha256(raw).hexdigest() == expected_hash:
                    matches.add(activation_format)
        except Exception as exc:
            raise ProvisioningError(
                f"Activation detection request failed ({type(exc).__name__}). No activation sent."
            ) from None
        finally:
            camera.close()
    if len(matches) != 1:
        raise ProvisioningError(
            "Activation format is unknown or conflicting. No activation sent; inspect the factory web resources."
        )
    selected = matches.pop()
    print(f"Detected activation format: {selected} (verified web-resource signature).", flush=True)
    return selected


def activation_payload(password, email, language, activation_format="modern"):
    if activation_format not in ("modern", "legacy-2.0.4"):
        raise ValueError("Unknown activation format")
    if activation_format == "legacy-2.0.4":
        # Captured from the 2.0.4 wizard: email is encoded, not RSA encrypted.
        return {
            "method": "do",
            "set_password": {
                "username": USERNAME,
                "password": vigi_md5_password(password),
                "passwdType": "md5",
                "ciphertext": quote(encrypt_ipc_password(password), safe=""),
                "reset_pwd_email": quote(email, safe=""),
                "language": language,
            },
        }
    return {
        "method": "do",
        "set_password": {
            "username": USERNAME,
            "ciphertext": quote(encrypt_ipc_password(password), safe=""),
            "reset_pwd_email": quote(encrypt_ipc_password(email), safe=""),
            "pwd_sec_type": "1",
            "language": language,
            "sec_question_1": "father_name",
            "sec_question_2": "mother_name",
            "sec_question_3": "senior_teacher_name",
            "sec_answer_1": "",
            "sec_answer_2": "",
            "sec_answer_3": "",
        },
    }


def login(camera, password):
    _, body = camera.post(
        "Login challenge", {"method": "do", "user_management": {"get_encrypt_info": None}},
        challenge=True,
    )
    data = body.get("data")
    if not isinstance(data, dict):
        raise ProvisioningError("Missing encryption parameters.")
    modes = data.get("encrypt_type")
    nonce = data.get("nonce")
    encoded_key = data.get("key_2") or data.get("key")
    if (
        not isinstance(modes, list) or "2" not in modes or data.get("passwdType") != "md5"
        or not isinstance(nonce, str) or not nonce
        or not isinstance(encoded_key, str) or not encoded_key
    ):
        raise ProvisioningError("Expected mode 2 / md5 login parameters.")
    try:
        key = load_der_public_key(base64.b64decode(unquote(encoded_key), validate=True))
        if not isinstance(key, rsa.RSAPublicKey):
            raise ValueError("Expected RSA key")
        message = f"{vigi_md5_password(password)}:{nonce}".encode()
        ciphertext = key.encrypt(message, padding.PKCS1v15())
    except ValueError:
        raise ProvisioningError("Unable to build the encrypted login.") from None

    fields = {
        "username": USERNAME,
        "encrypt_type": "2",
        "passwdType": "md5",
        "password": quote(base64.b64encode(ciphertext).decode("ascii"), safe=""),
    }
    if data.get("key_2"):
        fields["keyType"] = "1"
    _, body = camera.post("Login", {"method": "do", "login": fields})
    token = body.get("stok")
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9._~!*'()-]{1,256}", token):
        raise ProvisioningError("Login did not return a usable session token.")
    return f"/stok={token}/ds"


def read_regional_settings(camera, path):
    _, system = camera.post(
        "Read time zone",
        {"method": "get", "system": {"name": ["basic", "ntp", "dst", "dst_manual"]}},
        path=path,
    )
    _, image = camera.post(
        "Read frequency", {"method": "get", "image": {"name": "switch"}}, path=path
    )
    try:
        basic = system["system"]["basic"]
        settings = (
            unquote(basic["timezone"]),
            unquote(basic["zone_id"]),
            image["image"]["switch"]["flicker"],
        )
        return settings, basic.get("language"), basic.get("country_region"), system["system"]
    except (KeyError, TypeError, AttributeError):
        raise ProvisioningError("Unexpected regional settings response.") from None


def settings_match(system, expected):
    for section, fields in expected.items():
        observed = system.get(section)
        if not isinstance(observed, dict):
            return False
        if any(str(observed.get(field)) != str(value) for field, value in fields.items()):
            return False
    return True


def configure_region(camera, path, config, *, legacy_clock=False):
    target = (config.time_zone, config.zone_id, config.power_line_frequency)
    actual, language, country, system = read_regional_settings(camera, path)
    if actual != target:
        camera.post(
            "Write regional settings",
            config.timezone_request() | config.frequency_request(),
            path=path,
        )
        actual, language, country, system = read_regional_settings(camera, path)
    if config.clock is not None:
        settings_request = config.clock.settings_request(config)
        ntp_request = config.clock.ntp_request()
        unsupported_formats = legacy_clock and all(
            field not in system.get("basic", {})
            for field in ("date_format", "time_format")
        )
        if unsupported_formats:
            for field in ("date_format", "time_format"):
                settings_request["system"]["basic"].pop(field, None)
            print("Unsupported on legacy firmware: date_format and time_format; omitted from writes and verification.", flush=True)
        expected_clock = {
            "basic": {
                field: value for field, value in settings_request["system"]["basic"].items()
                if field not in {"timezone", "zone_id"}
            },
            "dst_manual": settings_request["system"]["dst_manual"],
        }
        expected_ntp = ntp_request["system"]
        needs_clock_write = not settings_match(system, expected_clock)
        if needs_clock_write:
            camera.post("Write date and DST settings", settings_request, path=path)
        if needs_clock_write or not settings_match(system, expected_ntp):
            camera.post("Write custom NTP settings", ntp_request, path=path)
        actual, language, country, system = read_regional_settings(camera, path)
        if not settings_match(system, expected_clock | expected_ntp):
            raise ProvisioningError("Date, DST or NTP readback differs from the requested settings.")
        if unsupported_formats:
            print("Verified manual DST and custom NTP; date/time formats unsupported.")
        else:
            print("Verified date format, manual DST and custom NTP configuration.")
    if actual != target or language != config.language:
        raise ProvisioningError("Regional readback differs from the requested settings.")
    print(f"Verified {config.language}, {config.time_zone}, {config.zone_id}, {config.power_line_frequency}.")
    print(f"Country/Region readback: {country or '(empty)'}")


def selected_interface(endpoint, password, mac):
    interfaces = get_network_interfaces(endpoint, USERNAME, password)
    matches = [
        item for item in interfaces
        if item.get("token") == INTERFACE
        and (item.get("mac") or "").lower().replace(":", "-") == mac
    ]
    if len(matches) != 1:
        raise ProvisioningError("ONVIF did not confirm the expected MAC and eth0 interface.")
    return matches[0]


def configure_network(plan, password):
    port = plan.get("onvif_port", 80)
    if type(port) is not int or port not in (80, 2020):
        raise ProvisioningError("Unexpected ONVIF port.")
    source_endpoint = f"http://{CAMERA_IP}:{port}/onvif/device_service"
    selected_interface(source_endpoint, password, plan["mac"])
    transport = make_live_transport(username=USERNAME, password=password, endpoint=source_endpoint)
    result = execute_with_transport(plan=plan, transport=transport)
    print(f"ONVIF writes: {result['status']}. Reboot needed: {result['reboot_needed']}.")

    target = plan["target_ip"]
    endpoint = f"http://{target}:{port}/onvif/device_service"
    try:
        actual = selected_interface(endpoint, password, plan["mac"])
        gateways = get_network_default_gateway(endpoint, USERNAME, password)
    except Exception as exc:
        failed = result["failed_or_unknown_operation"]
        raise ProvisioningError(
            f"ONVIF readback at {target} failed ({type(exc).__name__}). "
            f"Unconfirmed operation: {failed or 'none'}. Check both addresses before retrying."
        ) from None
    if not (
        actual.get("enabled") is True
        and actual.get("dhcp") is False
        and {"address": target, "prefix_length": plan["prefix_length"]} in (actual.get("manual") or [])
        and plan["gateway"] in gateways
    ):
        raise ProvisioningError("ONVIF readback differs from the requested settings.")
    print(f"Verified {INTERFACE}: {target}/{plan['prefix_length']}, DHCP disabled, gateway {plan['gateway']}.")


def configure_login_error(camera, path, target):
    def read():
        _, result = camera.post(
            "Read login-error exception",
            {"method": "get", "unusual_detection": {"name": ["login_error"]}}, path=path,
        )
        observed = result.get("unusual_detection", {}).get("login_error")
        if not isinstance(observed, dict):
            raise ProvisioningError("Missing login-error exception readback.")
        return observed

    actual = read()
    if any(str(actual.get(key)) != str(value) for key, value in target.items()):
        camera.post(
            "Write login-error exception",
            {"method": "set", "unusual_detection": {"login_error": dict(target)}}, path=path,
        )
        actual = read()
    if any(str(actual.get(key)) != str(value) for key, value in target.items()):
        raise ProvisioningError("Login-error exception readback differs from the profile.")
    print("Verified login-error exception: off, max_num_err 5.")


def configure_motion_detection(camera, path, target, *, legacy=False):
    target = {section: dict(fields) for section, fields in target.items()}
    table = "polygon_region_info" if legacy else "md_polygon_region_info"
    query = {"name": ["motion_det", "motion_notif_list"], "table": [table]}
    if not legacy:
        query["name"].append("feature")
        query["version"] = "1"

    def read():
        _, result = camera.post(
            "Read motion detection",
            {"method": "get", "motion_detection": query}, path=path,
        )
        _, schedule = camera.post(
            "Read motion schedule",
            {"method": "get", "motion_detection": {"name": "arming_schedule"}}, path=path,
        )
        try:
            motion = result["motion_detection"]
            region = motion[table]
            expected_region = [{f"{table}_1": {
                "points_num": 4, "points_x": [0, 10000, 10000, 0],
                "points_y": [0, 0, 10000, 10000],
            }}]
            if region != expected_region:
                raise ProvisioningError("Motion region differs from the verified full-image layout.")
            return motion | {"arming_schedule": schedule["motion_detection"]["arming_schedule"]}
        except (KeyError, TypeError):
            raise ProvisioningError("Unexpected motion detection readback.") from None

    def matches(actual):
        if not settings_match(actual, {key: target[key] for key in ("motion_det", "motion_notif_list")}):
            return False
        try:
            return all(
                json.loads(unquote(actual["arming_schedule"][day])) == ["0000-2400"]
                for day in target["arming_schedule"]
            )
        except (KeyError, TypeError, ValueError):
            return False

    actual = read()
    if legacy:
        for section, field in (("motion_det", "obj_filter_enabled"),
                               ("motion_notif_list", "report_server_enabled")):
            if field not in actual.get(section, {}):
                target[section].pop(field, None)
                print(f"Unavailable in legacy motion schema: {section}.{field}; omitted from writes and verification.", flush=True)
    if not matches(actual):
        camera.post(
            "Write motion detection",
            {"method": "set", "motion_detection": target}, path=path,
        )
        actual = read()
    if not matches(actual):
        raise ProvisioningError("Motion configuration or arming schedule readback differs.")
    print("Verified motion detection and 24/7 schedule; full-image region confirmed.")


def configure_audio(camera, path, target):
    def read():
        _, result = camera.post(
            "Read microphone",
            {"method": "get", "audio_config": {"name": ["microphone"]}}, path=path,
        )
        microphone = result.get("audio_config", {}).get("microphone")
        if not isinstance(microphone, dict):
            raise ProvisioningError("Missing microphone readback.")
        return microphone

    actual = read()
    if any(str(actual.get(key)) != str(value) for key, value in target.items()):
        camera.post(
            "Write microphone",
            {"method": "set", "audio_config": {"microphone": dict(target)}}, path=path,
        )
        actual = read()
    if any(str(actual.get(key)) != str(value) for key, value in target.items()):
        raise ProvisioningError("Microphone readback differs from the audio profile.")
    print(f"Verified microphone: mute {target['mute']}, noise cancellation {target['noise_cancelling']}, volume {target['volume']}.")


def configure_osd(camera, path, serial):
    def read():
        _, result = camera.post(
            "Read OSD",
            {"method": "get", "OSD": {"name": ["font", "week", "date"], "table": "label_info"}},
            path=path,
        )
        try:
            osd = result["OSD"]
            labels = {}
            for row in osd["label_info"]:
                for key, value in row.items():
                    if key in labels:
                        raise ValueError("Duplicate OSD label")
                    labels[key] = value
            if set(labels) != {"label_info_1", "label_info_2", "label_info_3"}:
                raise ValueError("Unexpected labels")
            return osd, labels
        except (KeyError, TypeError, AttributeError, ValueError):
            raise ProvisioningError("Unexpected OSD readback.") from None

    def matches(osd, labels):
        return (
            settings_match(osd, {
                "date": {"enabled": "on", "x_coor": "7749", "y_coor": "0"},
                "week": {"enabled": "off"},
                "font": {"display": "ntnb", "size": "auto", "color_type": "adapt", "color": "white"},
            })
            and all(label.get("enabled") == "off" for label in labels.values())
            and unquote(labels["label_info_1"].get("text", "")) == serial
        )

    osd, labels = read()
    if not matches(osd, labels):
        payload = {
            "date": {"enabled": "on", "x_coor": "7749", "y_coor": "0"},
            "week": {"enabled": "off"},
            "font": {"display": "ntnb", "size": "auto", "color_type": "adapt", "color": "white"},
        }
        for key, label in labels.items():
            try:
                payload[key] = {
                    "enabled": "off", "x_coor": str(label["x_coor"]),
                    "y_coor": str(label["y_coor"]), "text": label["text"],
                }
            except KeyError:
                raise ProvisioningError("OSD label fields are missing.") from None
        payload["label_info_1"]["text"] = quote(serial, safe="")
        camera.post("Write OSD", {"method": "set", "OSD": payload}, path=path)
        osd, labels = read()
    if not matches(osd, labels):
        raise ProvisioningError("OSD layout or inventory serial readback differs.")
    print(f"Verified OSD: date upper right, weekday and labels off, label 1 text {serial}.")


def configure_platform_access(camera, path, enabled):
    target = "on" if enabled else "off"

    def read():
        _, result = camera.post(
            "Read Platform Access",
            {"method": "get", "cloud_config": {"name": ["cloud_connect"]}},
            path=path,
        )
        return result.get("cloud_config", {}).get("cloud_connect", {}).get("enable")

    actual = read()
    if actual not in {"on", "off"}:
        raise ProvisioningError("Unexpected Platform Access readback.")
    if actual != target:
        camera.post(
            "Write Platform Access",
            {"method": "set", "cloud_config": {"cloud_connect": {"enable": target}}},
            path=path,
        )
        actual = read()
    if actual != target:
        raise ProvisioningError("Platform Access readback differs from the profile.")
    print(f"Verified Platform Access: {target}.")


def configure_video(camera, path, target):
    def read():
        _, result = camera.post(
            "Read main-stream video",
            {"method": "get", "video": {"name": ["main"]}}, path=path,
        )
        main = result.get("video", {}).get("main")
        if not isinstance(main, dict):
            raise ProvisioningError("Missing main-stream video readback.")
        return main

    actual = read()
    if any(str(actual.get(field)) != str(value) for field, value in target.items()):
        camera.post(
            "Write main-stream video",
            {"method": "set", "video": {"main": dict(target)}}, path=path,
        )
        actual = read()
    if any(str(actual.get(field)) != str(value) for field, value in target.items()):
        raise ProvisioningError("Main-stream video readback differs from the requested profile.")
    print("Verified main stream: H265, smart codec off, 1920x1080, 15 fps, VBR High, 2048 kbps.")


def read_dns(camera, path, plan):
    _, result = camera.post(
        "Read DNS settings",
        {
            "method": "get",
            "protocol": {"name": ["wan", "static", "dhcp"]},
            "network": {"name": ["wan_status"]},
            "uhttpd": {"name": ["main"]},
        },
        path=path,
    )
    try:
        saved = result["protocol"]["static"]
        active = result["network"]["wan_status"]
        mac = normalize_mac(active["mac"])
    except (KeyError, TypeError, ValueError):
        raise ProvisioningError("Unexpected DNS or WAN readback.") from None
    netmask = str(ipaddress.IPv4Network(f"0.0.0.0/{plan['prefix_length']}").netmask)
    expected = (plan["target_ip"], netmask, plan["gateway"])
    if mac != normalize_mac(plan["mac"]) or active.get("proto") != "static":
        raise ProvisioningError("DNS readback did not confirm the expected static camera.")
    for section in (saved, active):
        if not isinstance(section, dict) or tuple(
            section.get(field) for field in ("ipaddr", "netmask", "gateway")
        ) != expected:
            raise ProvisioningError("Saved or active network assignment differs from the approved plan.")
    return (
        (saved.get("pri_dns"), saved.get("snd_dns")),
        (active.get("pri_dns"), active.get("snd_dns")),
    )


def configure_dns(pin, password, plan, target):
    camera = CameraHTTPS(pin, plan["target_ip"])
    path = login(camera, password)
    saved, active = read_dns(camera, path, plan)
    if saved != target or active != target:
        camera.post(
            "Write DNS settings",
            {"method": "set", "protocol": {"static": {"pri_dns": target[0], "snd_dns": target[1]}}},
            path=path,
        )
        deadline = time.monotonic() + 60
        while True:
            saved, active = read_dns(camera, path, plan)
            if saved == active == target:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if saved == target:
                    raise ProvisioningError("DNS was saved, but the active pair did not match before timeout.")
                raise ProvisioningError("DNS readback did not confirm the saved and active pair.")
            time.sleep(min(3, remaining))
    print(f"Verified saved and active DNS: {target[0]} and {target[1]}.")


def configure_device_alias(camera, path, alias):
    _, result = camera.post(
        "Read device name", {"method": "get", "system": {"name": ["sys", "basic"]}},
        path=path,
    )
    actual = result.get("system", {}).get("sys", {}).get("dev_alias")
    if not isinstance(actual, str):
        raise ProvisioningError("Device name is missing from camera readback.")
    if unquote(actual) != alias:
        camera.post(
            "Write device name",
            {"method": "set", "system": {"sys": {"dev_alias": quote(alias, safe="")}}},
            path=path,
        )
        _, result = camera.post(
            "Verify device name",
            {"method": "get", "system": {"name": ["sys", "basic"]}}, path=path,
        )
        actual = result.get("system", {}).get("sys", {}).get("dev_alias")
    if not isinstance(actual, str) or unquote(actual) != alias:
        raise ProvisioningError("Device name readback differs from the inventory serial.")
    print(f"Verified device name: {alias}.")


def load_inventory_alias(database, device_id):
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(camera_inventory)")}
        if "label_serial" not in columns:
            return None
        row = db.execute(
            "SELECT label_serial FROM camera_inventory WHERE device_id=?", (device_id,)
        ).fetchone()
    alias = row[0] if row else None
    if alias is None or alias == "":
        return None
    if not isinstance(alias, str) or len(alias.encode("utf-8")) > 128 or any(ord(c) < 32 for c in alias):
        raise ProvisioningError("Inventory label serial is invalid for the device name.")
    return alias


def load_inventory_assignment(database, device_id):
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        row = db.execute(
            """SELECT mac_address, approved_ipv4, prefix_length, gateway_ipv4
               FROM camera_inventory WHERE device_id = ? AND model = 'VIGI C320I'""",
            (device_id,),
        ).fetchone()
    if row is None:
        raise ProvisioningError("No approved C320I assignment for that Device ID.")
    return row


def approve_observed_pin(camera_ip=CAMERA_IP):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with socket.create_connection((camera_ip, 443), 10, (SOURCE_IP, 0)) as raw:
        with context.wrap_socket(raw) as connection:
            pin = hashlib.sha256(connection.getpeercert(binary_form=True)).hexdigest()
    print(f"Observed SHA-256 fingerprint at {camera_ip}: {pin}")
    if input("On the isolated provisioning LAN, type APPROVE to trust this certificate: ").strip() != "APPROVE":
        raise ProvisioningError("Certificate approval declined.")
    return pin


def pin_after_network_move(camera_ip, original_pin, *, independently_verified):
    try:
        with connect_pinned_tls(camera_ip, 443, SOURCE_IP, original_pin, timeout=10):
            pass
    except CertificatePinError:
        print(f"HTTPS certificate differs at {camera_ip}. Original fingerprint: {original_pin}")
        if independently_verified:
            replacement = input(
                f"Enter the independently verified SHA-256 fingerprint at {camera_ip}: "
            ).strip()
            return normalize_sha256_pin(replacement)
        return approve_observed_pin(camera_ip)
    print(f"Original HTTPS certificate pin verified at {camera_ip}.")
    return original_pin


def provision(args):
    profile_path = Path(args.config or "provisioning.toml")
    profile = (
        load_provisioning_profile(profile_path)
        if args.config is not None or profile_path.exists()
        else None
    )
    config = profile or VigiInitializationConfig(zone_id="Europe/Vilnius")
    override = getattr(args, "firmware_file", None)
    if override:
        from dataclasses import replace
        config = replace(config, firmware_file=str(Path(override).resolve()))
    skip_firmware = getattr(args, "skip_firmware", False)
    if skip_firmware:
        print("Firmware upgrade disabled for this run.", flush=True)
    if config.firmware_file is not None and not skip_firmware:
        from .vigi_firmware_upgrade import inspect_firmware
        try:
            inspect_firmware(config.firmware_file)
        except RuntimeError as exc:
            raise ProvisioningError(str(exc)) from None
    print(f"Regional profile country: {config.country} (inventory intent).")
    alias = load_inventory_alias(args.inventory, args.device_id) if args.inventory else None
    if config.osd and not alias:
        raise ProvisioningError("OSD profile requires an inventory label serial before activation.")
    compact_mac = normalize_mac(args.mac)
    mac = "-".join(compact_mac[i:i + 2] for i in range(0, 12, 2))
    pin = normalize_sha256_pin(args.pin) if args.pin else None
    target = str(ipaddress.IPv4Address(args.target_ip))
    if target in {CAMERA_IP, SOURCE_IP}:
        raise ProvisioningError("Target must differ from the camera and Ubuntu source addresses.")
    interface = prepare_static_ipv4(
        interface_token=INTERFACE, ip_address=target,
        prefix_length=args.prefix, gateway=args.gateway,
    )
    if ipaddress.IPv4Address(target) not in ipaddress.IPv4Network(f"{SOURCE_IP}/24", strict=False):
        raise ProvisioningError("Target must be on the Ubuntu lab subnet for readback.")
    target_network = ipaddress.IPv4Network(f"{target}/{args.prefix}", strict=False)
    if ipaddress.IPv4Address(SOURCE_IP) not in target_network.hosts():
        raise ProvisioningError("The target prefix must keep Ubuntu on the camera subnet.")
    gateway = prepare_default_gateway(gateway=interface["gateway"])
    plan = {
        "mac": mac, "current_ip": CAMERA_IP, "target_ip": target,
        "prefix_length": args.prefix, "gateway": gateway["gateway"],
        "interface_token": INTERFACE, "dhcp": False, "transmitted": False,
        "set_network_interfaces_soap": interface["soap"],
        "set_network_default_gateway_soap": gateway["soap"],
    }

    devices = discover(local_ip=SOURCE_IP, timeout=5)
    matches = [
        item for item in devices
        if item.get("ip") == CAMERA_IP
        and (item.get("mac") or "").lower().replace(":", "-") == mac
        and (item.get("model") or "").upper() == "VIGI C320I"
        and item.get("factory_flag") == 0
    ]
    if args.device_id:
        expected_qr = f"TP1{args.device_id}020"
        if not matches or any((item.get("serial") or "").upper() != expected_qr for item in matches):
            raise ProvisioningError("Discovery did not confirm the approved MAC and Device ID.")
        # Repeated identical observations can be returned by a single probe.
        if any(
            item.get("ip") != CAMERA_IP
            and ((item.get("serial") or "").upper() == expected_qr
                 or (item.get("mac") or "").lower().replace(":", "-") == mac)
            for item in devices
        ):
            raise ProvisioningError("Discovery reported conflicting camera identity.")
        print(f"Inventory matched Device ID {args.device_id}, MAC {mac}: {target}/{args.prefix}, gateway {gateway['gateway']}.")
    elif not matches:
        raise ProvisioningError("Expected factory-state VIGI C320I was not discovered.")
    if pin is None:
        pin = approve_observed_pin()
    camera = CameraHTTPS(pin)
    confirm_factory(camera)
    activation_format = getattr(args, "activation_format", "auto")
    if activation_format == "auto":
        activation_format = detect_activation_format(camera)

    print(f"Camera {mac} at {CAMERA_IP} will move to {target}/{args.prefix}, gateway {gateway['gateway']}.")
    if input(f"Confirm {target} is unused and reserved for this camera by typing it: ").strip() != target:
        raise ProvisioningError("Confirmation did not match. No settings written.")
    email = profile.email if profile is not None else getpass("Recovery email: ").strip()
    password = getpass("New camera admin password: ")
    if not email or not password or password != getpass("Confirm new password: "):
        raise ProvisioningError("A recovery email and matching passwords are required.")
    payload = activation_payload(password, email, config.language, activation_format)
    confirm_factory(camera)
    try:
        camera.post("Factory activation", payload)
    except ProvisioningError as exc:
        raise ProvisioningError(f"{exc} Check camera state before another activation attempt.") from None

    try:
        path = login(camera, password)
        if config.firmware_file is not None and not skip_firmware:
            from .vigi_firmware_upgrade import upgrade_after_activation
            try:
                upgraded = upgrade_after_activation(
                    camera, path, password, mac, args.device_id or "camera",
                    config.firmware_file, input,
                )
            except Exception as exc:
                from .vigi_firmware_upgrade import ProvisioningError as FirmwareError
                if isinstance(exc, FirmwareError):
                    raise ProvisioningError(str(exc)) from None
                raise
            if upgraded:
                pin = pin_after_network_move(
                    CAMERA_IP, pin, independently_verified=args.pin is not None
                )
                camera = CameraHTTPS(pin)
                path = login(camera, password)
        if alias is not None:
            configure_device_alias(camera, path, alias)
        legacy_settings = (activation_format == "legacy-2.0.4"
                           and (skip_firmware or config.firmware_file is None))
        configure_region(camera, path, config, legacy_clock=legacy_settings)
        if config.video is not None:
            configure_video(camera, path, config.video)
        if config.platform_access is not None:
            configure_platform_access(camera, path, config.platform_access)
        if config.osd:
            configure_osd(camera, path, alias)
        if config.audio is not None:
            configure_audio(camera, path, config.audio)
        if config.motion_detection is not None:
            configure_motion_detection(camera, path, config.motion_detection, legacy=legacy_settings)
        if config.login_error is not None:
            configure_login_error(camera, path, config.login_error)
        plan["onvif_port"] = 2020 if legacy_settings else 80
        configure_network(plan, password)
        if config.dns is not None:
            dns_pin = pin_after_network_move(
                target, pin, independently_verified=args.pin is not None
            )
            configure_dns(dns_pin, password, plan, config.dns)
    except (ProvisioningError, OSError, ValueError) as exc:
        detail = str(exc) if isinstance(exc, ProvisioningError) else type(exc).__name__
        raise ProvisioningError(
            f"Activation was acknowledged. {detail} Check the current state before resuming."
        ) from None
    print("Provisioning complete. Recovery email was submitted during activation.")


def initialize_only(args):
    """Inventory-bound activation experiment; never enters site or firmware stages."""
    if not args.inventory or not re.fullmatch(r"[0-9A-F]{17}", (args.device_id or "").upper()):
        raise ProvisioningError("Initialization-only requires inventory and a scanned Device ID.")
    device_id = args.device_id.upper()
    uri = Path(args.inventory).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        row = db.execute("SELECT model,mac_address,hardware_version,label_serial FROM camera_inventory WHERE device_id=?", (device_id,)).fetchone()
    if row is None or row[0] not in {"VIGI C320I", "VIGI C340S"}:
        raise ProvisioningError("Initialization-only is limited to the inspected C320I/C340S activation flows.")
    from .vigi_discovery import decode_device_id
    devices = discover(local_ip=SOURCE_IP, timeout=5)
    at_ip = [d for d in devices if d.get("ip") == CAMERA_IP]
    if not at_ip or any(
        normalize_mac(d.get("mac", "")) != normalize_mac(row[1])
        or decode_device_id(d.get("serial")) != device_id
        or d.get("model") != row[0] or d.get("factory_flag") != 0
        for d in at_ip
    ):
        raise ProvisioningError("Factory discovery did not confirm the inventory MAC, Device ID and model.")
    print(f"Initialization only: {row[0]}, Device ID {device_id}, MAC {row[1]} at {CAMERA_IP}.", flush=True)
    print("Firmware upgrade, site settings and network changes are disabled.", flush=True)
    pin = normalize_sha256_pin(args.pin) if args.pin else approve_observed_pin()
    camera = CameraHTTPS(pin)
    confirm_factory(camera)
    activation_format = detect_activation_format(camera)
    profile_path = Path(args.config or "provisioning.toml")
    config = load_provisioning_profile(profile_path) if profile_path.exists() else VigiInitializationConfig()
    email = config.email
    if not email:
        raise ProvisioningError("Recovery email is required in the profile.")
    password = getpass("New camera admin password: ")
    if not password or password != getpass("Confirm new password: "):
        raise ProvisioningError("Matching nonempty passwords are required.")
    if input(f"Type INITIALIZE {device_id} to activate this camera only: ").strip() != f"INITIALIZE {device_id}":
        raise ProvisioningError("Initialization cancelled before activation.")
    confirm_factory(camera)
    try:
        camera.post("Factory activation", activation_payload(password, email, config.language, activation_format))
        path = login(camera, password)
    except ProvisioningError as exc:
        raise ProvisioningError(f"Initialization stopped: {exc} Check camera state before another attempt.") from None
    # Only authenticated reads follow successful activation/login.
    metadata = {"last_verified_ipv4": CAMERA_IP, "initialization_only": True}
    try:
        _, response = camera.post("Read initialized device metadata", {"method": "get", "device_info": {"name": "info"}}, path=path)
        info = response.get("device_info", {}).get("info", {})
        metadata.update({"firmware": unquote(info.get("sw_version", "")),
                         "onvif_model": unquote(info.get("device_model", "")),
                         "hardware_id": unquote(info.get("hw_version", ""))})
        print(f"Observed firmware: {metadata['firmware'] or 'unavailable'}; hardware: {metadata['hardware_id'] or 'unavailable'}.", flush=True)
    except ProvisioningError:
        print("Device metadata unavailable; authenticated login was verified.", flush=True)
    print("Initialization complete. Fresh login verified; no firmware, site configuration or network writes sent.", flush=True)
    print("Recovery email was submitted during activation; independent email readback is not verified.", flush=True)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initialize-only", action="store_true", help="Activate inventory camera and verify login, then stop")
    parser.add_argument("--activation-format", choices=("auto", "modern", "legacy-2.0.4"), default="auto",
                        help="Default auto verifies a known factory web-resource signature before activation")
    parser.add_argument("--firmware-file", help="Explicit approved local firmware image, overriding the profile file")
    parser.add_argument("--skip-firmware", action="store_true",
                        help="Skip firmware inspection and upgrade even when enabled in the profile")
    parser.add_argument("--config", help="Shared TOML profile (default: local provisioning.toml if present)")
    parser.add_argument("--inventory", help="Read-only SQLite inventory path")
    parser.add_argument("--device-id", help="Scanned C320I Device ID")
    parser.add_argument("--mac", help="Expected factory camera MAC")
    parser.add_argument("--pin", help="Verified post-reset SHA-256 certificate fingerprint")
    parser.add_argument("--target-ip", help="Unused IPv4 address approved for this camera")
    parser.add_argument("--prefix", type=int)
    parser.add_argument("--gateway")
    args = parser.parse_args()
    try:
        if args.initialize_only:
            if args.firmware_file or any(value is not None for value in (args.mac, args.target_ip, args.prefix, args.gateway)):
                parser.error("Initialization-only takes identity from inventory and accepts no firmware or network overrides.")
            initialize_only(args)
            return
        if args.inventory:
            if any(value is not None for value in (args.mac, args.target_ip, args.prefix, args.gateway)):
                parser.error("Inventory mode takes its network assignment only from SQLite.")
            args.device_id = (args.device_id or "").strip().upper()
            if not re.fullmatch(r"[0-9A-F]{17}", args.device_id):
                parser.error("Inventory mode requires a 17-character hexadecimal Device ID.")
            args.mac, args.target_ip, args.prefix, args.gateway = load_inventory_assignment(
                args.inventory, args.device_id
            )
        else:
            if args.device_id or not all((args.mac, args.pin, args.target_ip)):
                parser.error("Supply --inventory and --device-id, or --mac, --pin and --target-ip.")
            args.prefix = 24 if args.prefix is None else args.prefix
            args.gateway = args.gateway or "192.168.0.1"
        provision(args)
    except ProvisioningError as exc:
        parser.exit(1, f"{exc}\n")
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    except (OSError, EOFError, sqlite3.Error) as exc:
        parser.exit(1, f"Provisioning stopped ({type(exc).__name__}). Check camera state before retrying.\n")


if __name__ == "__main__":
    main()
