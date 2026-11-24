"""Explicit C340S V1 upgrade experiments. No activation or site configuration."""
import argparse
import hashlib
import re
import sqlite3
import time
import zipfile
from contextlib import closing
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
import requests
from .vigi_discovery import discover, decode_device_id
from .vigi_factory_workflow import CameraHTTPS, ProvisioningError, approve_observed_pin, login
from .vigi_firmware_upgrade import upload_file, upload_uri
from .vigi_onvif import get_device_information
from .vigi_onvif_network import get_network_interfaces
from .vigi_pin_inventory import normalize_mac

CAMERA = "192.168.0.60"
SOURCE = "2.0.3 Build 240412 Rel.42481n"

@dataclass(frozen=True)
class UpgradeStage:
    source: str
    target: str
    filename: str
    image_sha256: str
    zip_sha256: str

STAGES = {
    "bridge": UpgradeStage(SOURCE, "2.5.1 Build 250327 Rel.67051n",
        "C340S_1.0_en_2.5.1_Build_250327_Rel.67051n_up_boot-signed.bin",
        "e991185eee0c34eb6a532fe343fb8392aa62631968fdbfb43d5c2bf75d4b82c5",
        "b5268042e1a3abff9039b4fa06f0f816632ad82c579310ac1926f59b295ba2ce"),
    "latest": UpgradeStage("2.5.1 Build 250327 Rel.67051n", "3.2.1 Build 260320 Rel.22146n",
        "C340S_1.0_en_3.2.1_Build_260320_Rel.22146n_up_boot_signed.bin",
        "44e06b69c44d96bbd103deba5097bcbd8be4774e500dfc8159dcae65140816a2",
        "e54840807895ee61eceaf830c6474e90a7c263620278ab16497f6d1617f5cbc4"),
}

def inspect_package(path, stage):
    path = Path(path)
    if path.stat().st_size > 512 * 1024 * 1024:
        raise ProvisioningError("Package exceeds size limit.")
    if hashlib.sha256(path.read_bytes()).hexdigest() != stage.zip_sha256:
        raise ProvisioningError("ZIP checksum differs from the inspected official C340S package.")
    with zipfile.ZipFile(path) as package:
        images = [i for i in package.infolist() if Path(i.filename).name == stage.filename]
        if len(images) != 1 or images[0].file_size > 512 * 1024 * 1024:
            raise ProvisioningError("Expected one inspected firmware image in the ZIP.")
        image = package.read(images[0])
    if hashlib.sha256(image).hexdigest() != stage.image_sha256:
        raise ProvisioningError("Image checksum differs from the inspected firmware.")
    return image

def inspect_latest_image(path):
    stage = STAGES["latest"]
    path = Path(path)
    if path.name != stage.filename or path.stat().st_size > 512 * 1024 * 1024:
        raise ProvisioningError("Select the inspected C340S 3.2.1 image.")
    image = path.read_bytes()
    if hashlib.sha256(image).hexdigest() != stage.image_sha256:
        raise ProvisioningError("C340S target image checksum differs.")
    return image


def upgrade_stage(camera, path, password, mac, device_id, stage, image, confirm):
    info, _ = read_identity(password, mac)
    current = info.get("FirmwareVersion")
    if current == stage.target:
        print(f"Target {stage.target} already installed; stage skipped.", flush=True)
        return False
    if current != stage.source:
        raise ProvisioningError(f"Upgrade stage requires {stage.source}; observed {current}.")
    confirmation = f"UPGRADE {device_id} TO {stage.target.split()[0]}"
    if confirm(f"Type {confirmation} to install firmware (downgrade may be unavailable): ").strip() != confirmation:
        raise ProvisioningError("Confirmation did not match. No upload sent.")
    fresh, _ = read_identity(password, mac)
    if fresh.get("FirmwareVersion") != stage.source:
        raise ProvisioningError("Source firmware changed during confirmation. No upload sent.")
    print(f"Starting C340S upgrade to {stage.target}. Keep power and Ethernet connected.", flush=True)
    _, result = camera.post("Request firmware upload URL", {"method": "do", "system": {"firmware_upgrade": {"type": "0"}}}, path=path)
    upload_file(camera, path, upload_uri(result), image, stage.filename)
    wait_for_target(password, mac, stage)
    return True


def inventory_camera(database, device_id):
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        row = db.execute("SELECT model,hardware_version,mac_address FROM camera_inventory WHERE device_id=?", (device_id,)).fetchone()
    if row is None or row[0] != "VIGI C340S" or (row[1] and row[1] not in {"1", "1.0"}):
        raise ProvisioningError("Expected a C340S V1 inventory record.")
    return normalize_mac(row[2])

def confirm_discovery(device_id, mac):
    observations = discover(local_ip="192.168.0.10", timeout=5)
    matches = [d for d in observations if d.get("ip") == CAMERA]
    if not matches or any(d.get("model") != "VIGI C340S"
            or normalize_mac(d.get("mac", "")) != mac
            or decode_device_id(d.get("serial")) != device_id
            or d.get("factory_flag") != 1 for d in matches):
        raise ProvisioningError("Discovery did not confirm the initialized inventory camera at .60.")
    if any(d.get("ip") != CAMERA and (normalize_mac(d.get("mac", "")) == mac
           or decode_device_id(d.get("serial")) == device_id) for d in observations):
        raise ProvisioningError("Discovery reported conflicting camera identity.")

def read_identity(password, mac):
    for port in (80, 2020):
        endpoint = f"http://{CAMERA}:{port}/onvif/device_service"
        try:
            info = get_device_information(endpoint, "admin", password)
            interfaces = get_network_interfaces(endpoint, "admin", password)
        except requests.RequestException:
            continue
        if (info.get("Model") != "VIGI C340S" or info.get("HardwareId") not in {"1", "1.0"}
                or not any(normalize_mac(i.get("mac", "")) == mac for i in interfaces)):
            raise ProvisioningError("Authenticated camera model, hardware or MAC differs.")
        return info, port
    raise ProvisioningError("Cannot verify C340S through ONVIF 2020 or 80.")

def wait_for_target(password, mac, stage):
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        time.sleep(10)
        try:
            info, port = read_identity(password, mac)
        except (requests.RequestException, ProvisioningError, ValueError):
            continue
        print(f"ONVIF port {port}: firmware {info.get('FirmwareVersion')}", flush=True)
        if info.get("FirmwareVersion") == stage.target:
            print("Upgrade verified on the expected C340S. No settings changed by this command.", flush=True)
            return
    raise ProvisioningError("Upgrade outcome unverified after 10 minutes. Do not resend; inspect camera state.")

def run(args):
    stage = STAGES[args.stage]
    device_id = args.device_id.strip().upper()
    if not re.fullmatch(r"[0-9A-F]{17}", device_id):
        raise ProvisioningError("Enter the scanned 17-character Device ID.")
    image = inspect_package(args.package, stage)
    mac = inventory_camera(args.inventory, device_id)
    confirm_discovery(device_id, mac)
    password = getpass("Camera admin password: ")
    if not password:
        raise ProvisioningError("Password is required.")
    info, port = read_identity(password, mac)
    current = info.get("FirmwareVersion")
    print(f"Inventory Device ID {device_id}; MAC {mac}; C340S hardware {info.get('HardwareId')}.")
    print(f"Current firmware: {current}\nTarget firmware: {stage.target}")
    print(f"ZIP and image SHA-256 verified. ONVIF port: {port}.", flush=True)
    if current == stage.target:
        print("Stage target already installed. No upload sent.")
        return
    if current != stage.source:
        raise ProvisioningError(f"This stage requires source firmware {stage.source}. No upload sent.")
    if not args.execute:
        print("Preflight passed. No firmware uploaded. Repeat with --execute for a real upgrade.")
        return
    camera = CameraHTTPS(approve_observed_pin())
    path = login(camera, password)
    confirmation = f"UPGRADE {device_id} TO {stage.target.split()[0]}"
    if input(f"Type {confirmation} to install firmware (downgrade may be unavailable): ").strip() != confirmation:
        raise ProvisioningError("Confirmation did not match. No upload sent.")
    fresh, _ = read_identity(password, mac)
    if fresh.get("FirmwareVersion") != stage.source:
        raise ProvisioningError("Source firmware changed during confirmation. No upload sent.")
    print("Starting real C340S firmware upgrade. Keep power and Ethernet connected.", flush=True)
    _, result = camera.post("Request firmware upload URL", {"method": "do", "system": {"firmware_upgrade": {"type": "0"}}}, path=path)
    upload_file(camera, path, upload_uri(result), image, stage.filename)
    wait_for_target(password, mac, stage)
    print("Stopped after firmware verification. No automatic next upgrade or site provisioning.", flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--package", required=True, help="Original inspected official ZIP")
    parser.add_argument("--stage", choices=tuple(STAGES), default="bridge")
    parser.add_argument("--execute", action="store_true", help="Perform a real upgrade after typed confirmation")
    args = parser.parse_args()
    try:
        run(args)
    except (ProvisioningError, ValueError, OSError, sqlite3.Error, EOFError, zipfile.BadZipFile, requests.RequestException) as exc:
        parser.exit(1, f"C340S upgrade stopped: {exc}\n")

if __name__ == "__main__":
    main()
