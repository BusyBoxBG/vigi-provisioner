"""Download approved official ZIPs and cache one firmware image. No camera I/O."""
import hashlib
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, unquote, urlsplit
import requests
from .vigi_model_catalog import official_url, validate_model

MAX_ZIP = 512 * 1024 * 1024
MAX_IMAGE = 512 * 1024 * 1024

def version_from_url(url):
    name = unquote(urlsplit(url).path).rsplit("/", 1)[-1]
    match = re.search(r"_(\d+\.\d+\.\d+)[ _]+Build[ _]+(\d+)", name, re.I)
    return f"{match[1]} Build {match[2]}" if match else ""

def approve_download(row, url, version, root):
    row = validate_model(row)
    official_url(url, firmware=True)
    if url not in [row["firmware_url"], *row["available_firmware_urls"]]:
        raise ValueError("Choose the recorded firmware or a checked candidate first.")
    if not isinstance(version, str) or not version.strip() or len(version) > 128:
        raise ValueError("Enter the firmware version to approve (up to 128 characters).")
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="download-", dir=root) as temporary:
        archive = Path(temporary) / "firmware.zip"
        digest = hashlib.sha256()
        size = 0
        with requests.Session() as session:
            session.trust_env = False
            for attempt in range(4):
                with session.get(url, timeout=(5, 30), stream=True, allow_redirects=False) as response:
                    if response.is_redirect:
                        url = official_url(urljoin(url, response.headers["Location"]), firmware=True)
                        continue
                    response.raise_for_status()
                    with archive.open("wb") as output:
                        for chunk in response.iter_content(65536):
                            size += len(chunk)
                            if size > MAX_ZIP:
                                raise ValueError("Firmware ZIP exceeds 512 MiB limit.")
                            digest.update(chunk)
                            output.write(chunk)
                    break
            else:
                raise ValueError("Too many firmware download redirects.")
        zip_hash = digest.hexdigest()
        with zipfile.ZipFile(archive) as package:
            images = [i for i in package.infolist() if not i.is_dir() and i.filename.lower().endswith(".bin")]
            if len(images) != 1:
                raise ValueError("Expected exactly one .bin image; inspect this package manually.")
            image = images[0]
            name = PurePosixPath(image.filename).name
            if not re.fullmatch(r"[A-Za-z0-9_.()-]+\.bin", name) or image.file_size > MAX_IMAGE:
                raise ValueError("Unexpected firmware image name or size.")
            image_path = Path(temporary) / name
            image_hash = hashlib.sha256()
            with package.open(image) as source, image_path.open("wb") as output:
                count = 0
                while chunk := source.read(65536):
                    count += len(chunk)
                    if count > MAX_IMAGE:
                        raise ValueError("Firmware image exceeds size limit.")
                    image_hash.update(chunk)
                    output.write(chunk)
        destination = root / row["id"] / zip_hash
        destination.mkdir(parents=True, exist_ok=True)
        os.replace(image_path, destination / name)
        os.replace(archive, destination / "firmware.zip")
    row.update(firmware_url=url, firmware_version=version.strip(),
               approved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               approved_image=str(destination / name), approved_sha256=image_hash.hexdigest(),
               approved_zip=str(destination / "firmware.zip"), approved_zip_sha256=zip_hash)
    return row

def approved_image(row, root):
    """Reject moved, edited or missing files before a workflow can start."""
    row = validate_model(row)
    if not row["approved_at"] or not row["approved_image"]:
        raise ValueError("Download and approve default firmware for this model first.")
    file = Path(row["approved_image"]).resolve()
    if not file.is_relative_to(Path(root).resolve()) or not file.is_file():
        raise ValueError("Approved firmware file is missing or outside the cache folder.")
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    if digest != row["approved_sha256"]:
        raise ValueError("Approved firmware file checksum changed. Download and approve again.")
    return file


def import_c340s_latest(row, package, root):
    """Import the already-inspected target ZIP from local disk, without Internet."""
    from .vigi_c340s_upgrade import inspect_package, STAGES
    import shutil
    row = validate_model(row)
    if row["model"] != "VIGI C340S" or row["hardware_version"] not in {"1", "1.0"} or row["region"] != "UN":
        raise ValueError("Local import currently supports the inspected C340S V1 UN target only.")
    source = Path(package).expanduser().resolve()
    if source.stat().st_size > MAX_ZIP:
        raise ValueError("Firmware ZIP exceeds size limit.")
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    stage = STAGES["latest"]
    with tempfile.TemporaryDirectory(prefix="import-", dir=root) as temporary:
        archive = Path(temporary) / "firmware.zip"
        shutil.copyfile(source, archive)
        image = inspect_package(archive, stage)
        destination = root / row["id"] / stage.zip_sha256
        destination.mkdir(parents=True, exist_ok=True)
        local_image = Path(temporary) / stage.filename
        local_image.write_bytes(image)
        os.replace(local_image, destination / stage.filename)
        os.replace(archive, destination / "firmware.zip")
    row.update(firmware_url="https://static.tp-link.com/upload/firmware/2026/202605/20260512/VIGI%20C340S(UN)%201.0_3.2.1%20Build%20260320.zip",
               firmware_version=stage.target,
               approved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               approved_image=str(destination / stage.filename), approved_sha256=stage.image_sha256,
               approved_zip=str(destination / "firmware.zip"), approved_zip_sha256=stage.zip_sha256)
    return row
