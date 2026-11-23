"""Bench upgrade for the identified C320I UN 1.20 and inspected firmware file."""

import argparse
import hashlib
import json
import re
import secrets
import time
from getpass import getpass
from pathlib import Path

import requests

from .vigi_discovery import discover
from .vigi_factory_workflow import CameraHTTPS, ProvisioningError, approve_observed_pin, login
from .vigi_onvif import get_device_information
from .vigi_onvif_network import get_network_interfaces
from .vigi_pin_inventory import normalize_mac

CAMERA = "192.168.0.60"
MAC = "503dd1460ab7"
DEVICE_ID = "5B7292F5C6C4C44E2"
SHA256 = "151087aabf05b5b0f052c4d5bcb18fdacd8b8aaca085c3b80d0d7ddd612932a8"
VERSION = "2.2.1 Build 260605 Rel.12620n"


def check_identity(password, port, expected_mac=MAC):
    endpoint = f"http://{CAMERA}:{port}/onvif/device_service"
    interfaces = get_network_interfaces(endpoint, "admin", password)
    if not any(normalize_mac(item.get("mac", "")) == normalize_mac(expected_mac) for item in interfaces):
        raise ProvisioningError("ONVIF MAC differs from the upgrade test camera.")
    info = get_device_information(endpoint, "admin", password)
    if info.get("Model") != "VIGI C320I" or info.get("HardwareId") not in {"1.2", "1.20"}:
        raise ProvisioningError("Expected the test C320I hardware 1.20.")
    return info


def multipart(image, filename, boundary):
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: multipart/form-data\r\n\r\n"
    ).encode("ascii")
    return header + image + f"\r\n--{boundary}--\r\n".encode("ascii")


def upload_uri(result):
    value = result.get("url")
    if not isinstance(value, str):
        raise ProvisioningError("Upload response has no URL string. No file uploaded.")
    # RetUrlResp.getUrl in the factory tool converts encoded path separators.
    value = re.sub("%2f", "/", value, flags=re.IGNORECASE)
    if not re.fullmatch(r"/[A-Za-z0-9_./?=&%+-]+", value) or ".." in value or value.startswith("//"):
        raise ProvisioningError("Unexpected upload URL. No file uploaded.")
    return value


def inspect_firmware(file):
    file = Path(file)
    if file.name != "Cx20I_en_2.2.1_Build_260605_Rel.12620n_up_boot_signed.bin":
        raise ProvisioningError("Select the inspected Cx20I firmware filename.")
    image = file.read_bytes()
    if hashlib.sha256(image).hexdigest() != SHA256:
        raise ProvisioningError("Firmware checksum differs from the inspected file.")
    return image


def upgrade_after_activation(camera, path, password, expected_mac, device_id, file, confirm):
    before = None
    for port in (80, 2020):
        try:
            before = check_identity(password, port, expected_mac)
            break
        except requests.RequestException:
            continue
    if before is None:
        raise ProvisioningError("Unable to read camera firmware on ONVIF 80 or 2020.")
    current = before.get("FirmwareVersion")
    print(f"Firmware check: current {current}; target {VERSION}.", flush=True)
    if current == VERSION:
        print("Target firmware already installed. Upgrade skipped.", flush=True)
        return False
    if current != "2.0.4 Build 241101 Rel.52842n":
        raise ProvisioningError("This upgrade path currently supports the tested 2.0.4 source version.")
    image = inspect_firmware(file)
    expected = f"UPGRADE {device_id}"
    if confirm(f"Type {expected} to install firmware before site configuration: ").strip() != expected:
        raise ProvisioningError("Upgrade cancelled before upload.")
    print("Starting firmware upgrade. Keep power and Ethernet connected.", flush=True)
    _, result = camera.post(
        "Request firmware upload URL",
        {"method": "do", "system": {"firmware_upgrade": {"type": "0"}}}, path=path,
    )
    upload_file(camera, path, upload_uri(result), image, Path(file).name)
    wait_for_upgrade(password, expected_mac)
    return True


def run(args):
    file = Path(args.file)
    if file.name != "Cx20I_en_2.2.1_Build_260605_Rel.12620n_up_boot_signed.bin":
        raise ProvisioningError("Select the inspected Cx20I firmware filename.")
    image = file.read_bytes()
    if hashlib.sha256(image).hexdigest() != SHA256:
        raise ProvisioningError("Firmware checksum differs from the inspected file.")
    cameras = discover(local_ip="192.168.0.10", timeout=5)
    matches = [
        item for item in cameras if item.get("ip") == CAMERA
        and normalize_mac(item.get("mac", "")) == MAC
        and (item.get("serial") or "").upper() == f"TP1{DEVICE_ID}020"
        and item.get("factory_flag") == 1
    ]
    if not matches:
        raise ProvisioningError("Expected initialized upgrade test camera was not discovered.")
    password = getpass("Camera admin password: ")
    if not password:
        raise ProvisioningError("Password is empty.")
    before = check_identity(password, 2020)
    print(f"Current firmware: {before.get('FirmwareVersion')}")
    print(f"Target firmware: {VERSION}")
    print(f"File SHA-256 verified: {SHA256}")
    if before.get("FirmwareVersion") == VERSION:
        print("Target version already installed. Upgrade skipped.")
        return
    if before.get("FirmwareVersion") != "2.0.4 Build 241101 Rel.52842n":
        raise ProvisioningError("This bench test expects the recorded 2.0.4 source firmware.")
    if not args.execute and not args.prepare_only:
        print("Preflight passed. Run again with --execute to start the confirmed upgrade.")
        return

    pin = approve_observed_pin(CAMERA)
    camera = CameraHTTPS(pin, CAMERA)
    path = login(camera, password)
    if input(f"Type UPGRADE {DEVICE_ID} to upload and install firmware: ").strip() != f"UPGRADE {DEVICE_ID}":
        raise ProvisioningError("Upgrade cancelled.")
    print("Starting upgrade. Keep camera power and Ethernet connected.", flush=True)
    _, result = camera.post(
        "Request firmware upload URL",
        {"method": "do", "system": {"firmware_upgrade": {"type": "0"}}},
        path=path,
    )
    uri = upload_uri(result)
    print("Upload URL decoded and validated.", flush=True)
    if args.prepare_only:
        print("Upload preparation passed. No file uploaded.")
        return
    upload_file(camera, path, uri, image, file.name)
    wait_for_upgrade(password, MAC)


def upload_file(camera, path, uri, image, filename):
    token_prefix = path.removesuffix("/ds")
    boundary = "VigiUpload" + secrets.token_hex(16)
    body = multipart(image, filename, boundary)
    try:
        camera.connect()
        camera.sock.settimeout(180)
        camera.request(
            "POST", token_prefix + uri, body=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Disposition": f"attachment; filename={filename}",
            },
        )
        camera.sock.settimeout(180)
        response = camera.getresponse()
        raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("Oversized response")
        result = json.loads(raw)
        code = result.get("error_code")
        if response.status != 200 or type(code) is not int or code != 0:
            raise ProvisioningError(f"Upload was not confirmed: HTTP {response.status}, camera code {code}.")
        print("Firmware upload acknowledged. Waiting for firmware-version readback.", flush=True)
    except ProvisioningError:
        raise
    except Exception as exc:
        print(f"Upload response interrupted ({type(exc).__name__}); checking outcome without resending.", flush=True)
    finally:
        camera.close()



def wait_for_upgrade(password, expected_mac):
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        time.sleep(10)
        for port in (2020, 80):
            try:
                info = check_identity(password, port, expected_mac)
            except (requests.RequestException, ProvisioningError, ValueError):
                continue
            version = info.get("FirmwareVersion")
            print(f"ONVIF port {port}: firmware {version}", flush=True)
            if version == VERSION:
                print("Upgrade verified on the expected camera.")
                return
    raise ProvisioningError("Upgrade outcome unverified after 10 minutes. Inspect the camera before another upload.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True)
    parser.add_argument("--prepare-only", action="store_true", help="Request and validate upload URL without uploading")
    parser.add_argument("--execute", action="store_true", help="Start the upgrade after explicit confirmation")
    args = parser.parse_args()
    if args.execute and args.prepare_only:
        parser.error("Choose either --execute or --prepare-only.")
    try:
        run(args)
    except (ProvisioningError, OSError, ValueError, requests.RequestException, EOFError) as exc:
        parser.exit(1, f"Upgrade stopped: {exc}\n")


if __name__ == "__main__":
    main()
