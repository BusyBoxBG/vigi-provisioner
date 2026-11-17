"""Provision one factory-state VIGI C320I using the tested lab workflow."""

import argparse
import base64
import http.client
import ipaddress
import json
import re
from getpass import getpass
from urllib.parse import quote, unquote

from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_der_public_key

from .vigi_certificate_pin import normalize_sha256_pin
from .vigi_discovery import discover
from .vigi_initialization_config import VigiInitializationConfig
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
TIME_ZONE = "UTC+02:00"
ZONE_ID = "Europe/Vilnius"
FREQUENCY = "50hz"


class ProvisioningError(RuntimeError):
    pass


class CameraHTTPS(http.client.HTTPConnection):
    def __init__(self, pin):
        super().__init__(CAMERA_IP, 443, timeout=10)
        self.pin = pin

    def connect(self):
        self.sock = connect_pinned_tls(CAMERA_IP, 443, SOURCE_IP, self.pin, timeout=10)

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


def activation_payload(password, email):
    return {
        "method": "do",
        "set_password": {
            "username": USERNAME,
            "ciphertext": quote(encrypt_ipc_password(password), safe=""),
            "reset_pwd_email": quote(encrypt_ipc_password(email), safe=""),
            "pwd_sec_type": "1",
            "language": "English",
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
        return settings, basic.get("language"), basic.get("country_region")
    except (KeyError, TypeError, AttributeError):
        raise ProvisioningError("Unexpected regional settings response.") from None


def configure_region(camera, path):
    target = (TIME_ZONE, ZONE_ID, FREQUENCY)
    actual, language, country = read_regional_settings(camera, path)
    if actual != target:
        config = VigiInitializationConfig(
            time_zone=TIME_ZONE, zone_id=ZONE_ID, power_line_frequency=FREQUENCY
        )
        camera.post(
            "Write regional settings",
            config.timezone_request() | config.frequency_request(),
            path=path,
        )
        actual, language, country = read_regional_settings(camera, path)
    if actual != target or language != "English":
        raise ProvisioningError("Regional readback differs from the requested settings.")
    print(f"Verified English, {TIME_ZONE}, {ZONE_ID}, {FREQUENCY}.")
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
    selected_interface(ENDPOINT, password, plan["mac"])
    transport = make_live_transport(username=USERNAME, password=password)
    result = execute_with_transport(plan=plan, transport=transport)
    print(f"ONVIF writes: {result['status']}. Reboot needed: {result['reboot_needed']}.")

    target = plan["target_ip"]
    endpoint = f"http://{target}:80/onvif/device_service"
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


def provision(args):
    compact_mac = normalize_mac(args.mac)
    mac = "-".join(compact_mac[i:i + 2] for i in range(0, 12, 2))
    pin = normalize_sha256_pin(args.pin)
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
    if not any(
        item.get("ip") == CAMERA_IP
        and (item.get("mac") or "").lower().replace(":", "-") == mac
        and (item.get("model") or "").upper() == "VIGI C320I"
        and item.get("factory_flag") == 0
        for item in devices
    ):
        raise ProvisioningError("Expected factory-state VIGI C320I was not discovered.")
    camera = CameraHTTPS(pin)
    confirm_factory(camera)

    print(f"Camera {mac} at {CAMERA_IP} will move to {target}/{args.prefix}, gateway {gateway['gateway']}.")
    if input(f"Confirm {target} is unused and reserved for this camera by typing it: ").strip() != target:
        raise ProvisioningError("Confirmation did not match. No settings written.")
    email = getpass("Recovery email: ").strip()
    password = getpass("New camera admin password: ")
    if not email or not password or password != getpass("Confirm new password: "):
        raise ProvisioningError("A recovery email and matching passwords are required.")
    payload = activation_payload(password, email)
    confirm_factory(camera)
    try:
        camera.post("Factory activation", payload)
    except ProvisioningError as exc:
        raise ProvisioningError(f"{exc} Check camera state before another activation attempt.") from None

    try:
        path = login(camera, password)
        configure_region(camera, path)
        configure_network(plan, password)
    except (ProvisioningError, OSError, ValueError) as exc:
        detail = str(exc) if isinstance(exc, ProvisioningError) else type(exc).__name__
        raise ProvisioningError(
            f"Activation was acknowledged. {detail} Check the current state before resuming."
        ) from None
    print("Provisioning complete. Recovery email was submitted during activation.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mac", required=True, help="Expected factory camera MAC")
    parser.add_argument("--pin", required=True, help="Verified post-reset SHA-256 certificate fingerprint")
    parser.add_argument("--target-ip", required=True, help="Unused IPv4 address approved for this camera")
    parser.add_argument("--prefix", type=int, default=24)
    parser.add_argument("--gateway", default="192.168.0.1")
    args = parser.parse_args()
    try:
        provision(args)
    except ProvisioningError as exc:
        parser.exit(1, f"{exc}\n")
    except (OSError, ValueError, EOFError) as exc:
        parser.exit(1, f"Provisioning stopped ({type(exc).__name__}). Check camera state before retrying.\n")


if __name__ == "__main__":
    main()
