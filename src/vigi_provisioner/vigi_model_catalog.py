"""Editable model/hardware firmware catalog; never authorizes camera upgrades."""
import json
import os
import re
import tempfile
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import requests

FIELDS = ("id", "model", "hardware_version", "region", "support_url", "firmware_url", "firmware_version", "last_checked", "check_status")

def official_url(value, *, firmware=False):
    parts = urlsplit(value)
    hosts = {"static.tp-link.com"} if firmware else {"www.tp-link.com", "www.vigi.com"}
    if parts.scheme != "https" or parts.hostname not in hosts or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError("Use an official HTTPS TP-Link/VIGI URL.")
    if firmware and (not parts.path.startswith("/upload/firmware/") or not parts.path.lower().endswith(".zip")):
        raise ValueError("Use an official firmware ZIP URL.")
    if not firmware and "/support/download/" not in parts.path:
        raise ValueError("Use an official model download page.")
    return value

def validate_model(row):
    result = {field: str(row.get(field, "")).strip() for field in FIELDS}
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}", result["id"]):
        raise ValueError("Model ID must use lowercase letters, digits, dots, underscores or hyphens.")
    for field in ("model", "hardware_version", "region"):
        if not result[field] or len(result[field]) > 100:
            raise ValueError("Model, hardware version and region are required (up to 100 characters).")
    official_url(result["support_url"])
    if result["firmware_url"]:
        official_url(result["firmware_url"], firmware=True)
    candidates = row.get("available_firmware_urls", [])
    if not isinstance(candidates, list) or len(candidates) > 100:
        raise ValueError("Invalid firmware candidate list.")
    result["available_firmware_urls"] = [official_url(str(u), firmware=True) for u in candidates]
    return result

def load_catalog(path):
    document = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("schema_version") != 1:
        raise ValueError("Unsupported model catalog schema.")
    rows = [validate_model(row) for row in document.get("models", [])]
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate model catalog ID.")
    return rows

def save_catalog(path, rows):
    rows = [validate_model(row) for row in rows]
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate model catalog ID.")
    text = "# Model catalog. Firmware links do not establish tested provisioning or upgrade support.\nschema_version = 1\n"
    for row in rows:
        text += "\n[[models]]\n"
        for key in FIELDS:
            text += key + " = " + json.dumps(row[key], ensure_ascii=True) + "\n"
        text += "available_firmware_urls = " + json.dumps(row["available_firmware_urls"]) + "\n"
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
            file.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

class FirmwareLinks(HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.base, self.links = base, []
    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        url = urljoin(self.base, href)
        try:
            official_url(url, firmware=True)
        except ValueError:
            return
        if url not in self.links:
            self.links.append(url)

def check_firmware(row):
    """Fetch only the support HTML. Return candidates without changing approved URL."""
    row = validate_model(row)
    url = official_url(row["support_url"])
    with requests.Session() as session:
        session.trust_env = False
        for attempt in range(4):
            with session.get(url, timeout=(5, 15), allow_redirects=False, stream=True,
                             headers={"User-Agent": "VIGI-Provisioner/1.0"}) as response:
                if response.is_redirect:
                    url = official_url(urljoin(url, response.headers["Location"]))
                    continue
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 4_000_000:
                        raise ValueError("Support page exceeds size limit.")
                    chunks.append(chunk)
                parser = FirmwareLinks(url)
                parser.feed(b"".join(chunks).decode("utf-8", errors="replace"))
                if not parser.links:
                    raise ValueError("No firmware ZIP links found. Keep recorded URL and inspect the page manually.")
                row["available_firmware_urls"] = parser.links[:100]
                row["last_checked"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                row["check_status"] = "Official page checked; review candidates for hardware and region."
                return row
        raise ValueError("Too many support page redirects.")
