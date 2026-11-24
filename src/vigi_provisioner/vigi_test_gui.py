"""Local browser interface for the inventory-driven factory workflow."""

import argparse
import ipaddress
import json
import secrets
import sqlite3
import subprocess
import sys
import threading
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .vigi_pin_inventory import normalize_mac
from .vigi_onvif import get_device_information
from .vigi_discovery import discover, decode_device_id
from .vigi_onvif_live_transport import SOURCE_IP
from .vigi_model_catalog import load_catalog, save_catalog, validate_model, check_firmware
from .vigi_firmware_cache import approve_download, approved_image

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>VIGI Provisioner</title>
<style>
body{font:16px "Segoe UI",sans-serif;background:#f0f3f5;color:#182f3b;margin:0}
header{background:#143b43;color:white;padding:24px 5%}main{max-width:1200px;margin:28px auto;padding:0 20px}
.grid{display:grid;grid-template-columns:360px 1fr;gap:24px}section{background:white;border:1px solid #d7e0e4;border-radius:12px;padding:24px;margin-bottom:20px}
label{display:block;margin:12px 0 5px}input{box-sizing:border-box;width:100%;padding:10px;border:1px solid #a9b9c1;border-radius:5px}
button{background:#087b70;color:white;border:0;border-radius:5px;padding:11px 16px;cursor:pointer;margin:12px 4px 0 0}
button:disabled{opacity:.5}table{width:100%;border-collapse:collapse;font-size:14px}td,th{text-align:left;padding:9px;border-bottom:1px solid #ddd}
pre{white-space:pre-wrap;overflow:auto;background:#10242c;color:#cfe5df;padding:18px;min-height:260px;max-height:450px}
#prompt{background:#edf8f4;padding:16px}small{color:#536b78}@media(max-width:800px){.grid{display:block}}
</style></head><body><header><h1>VIGI Provisioner</h1>Inventory and factory setup &middot; Ubuntu test console</header>
<main><section><h2>Connected factory default cameras</h2>
<button id="probe" onclick="probe()">Discover uninitialized cameras</button>
<p id="probeStatus" role="status"></p><pre id="probeDetails" hidden></pre>
</section><div class="grid"><section><h2>Add camera</h2><form id="add">
<label>Device ID</label><input name="device_id" required>
<label>MAC address</label><input name="mac_address" required>
<label>Label serial number</label><input name="label_serial" required>
<label>Catalog model / hardware</label><select id="catalogChoice" name="catalog_id" onchange="chooseModel()" style="width:100%;padding:10px"><option value="">Manual entry / not linked</option></select>
<label>Model</label><input id="cameraModel" name="model" value="VIGI C320I" required>
<label>Hardware version</label><input id="cameraHardware" name="hardware_version" placeholder="1.20">
<label>Approved IP address</label><input name="approved_ipv4" value="192.168.0.150" required>
<label>Netmask or prefix</label><input name="prefix" value="255.255.255.0" required>
<label>Gateway</label><input name="gateway_ipv4" value="192.168.0.1" required>
<button>Save inventory</button></form><p><small>Full provisioning: tested C320I hardware 1.20, and C340S V1 with Keep existing firmware. Other models can be recorded for future testing.</small></p></section>
<div><section><h2>Camera inventory</h2><div style="overflow:auto"><table><thead><tr><th>Select</th><th>Device ID / MAC</th><th>Model / firmware</th><th>Serial / target</th><th>State</th><th>Actions</th></tr></thead><tbody id="rows"></tbody></table></div>
<label for="firmwareMode">Firmware handling</label>
<select id="firmwareMode" style="width:100%;padding:10px">
<option value="initialize">Initialize only (no update, settings or IP change)</option>
<option value="approved" selected>Update to default approved firmware after initialization</option>
<option value="preserve">Keep existing firmware (no upgrade)</option>
<option value="profile">Allow firmware upgrade configured in provisioning.toml</option>
</select><p><small>Activation format is detected automatically. Unsupported legacy settings are listed in the step log. Supported settings still require readback verification.</small></p>
<button id="start" onclick="start()">Start provisioning</button><p id="message" role="status"></p></section>
<section><div id="prompt" hidden>
<label id="question"></label><input id="answer" autocomplete="off"><button onclick="answer()">Confirm / Continue</button></div>
<h2>Provisioning steps</h2><pre id="log"></pre></section></div></div><section><h2>Camera models and firmware</h2>
<p>Catalog entries describe model, hardware and region. They do not enable untested provisioning or authorize firmware uploads. Checks require Internet access and download only support-page text.</p>
<button onclick="downloadDefaults()">Download and approve all listed defaults</button>
<div style="overflow:auto"><table><thead><tr><th>Model / hardware / region</th><th>Default initial update firmware</th><th>Check / sources</th></tr></thead><tbody id="modelRows"></tbody></table></div>
<form id="approveForm" hidden><h3>Approve default firmware</h3><p id="approveTarget"></p><label for="approveVersion">Version to approve</label><input id="approveVersion" required><button>Confirm default and download</button><button type="button" onclick="document.getElementById('approveForm').hidden=true">Cancel</button></form>
<details><summary>Add or edit model</summary><form id="modelForm">
<label>Catalog ID (reuse an ID to update it)</label><input name="id" required placeholder="vigi-c320i-v1.20">
<label>Model</label><input name="model" required placeholder="VIGI C320I">
<label>Hardware version</label><input name="hardware_version" required placeholder="1.20">
<label>Region</label><input name="region" required value="UN">
<label>Official firmware support page</label><input name="support_url" type="url" required>
<label>Default initial update firmware version</label><input name="firmware_version">
<label>Default initial update firmware ZIP URL</label><input name="firmware_url" type="url">
<button>Save model</button></form></details><p id="modelMessage" role="status"></p></section>
</main>
<script>
const token="__TOKEN__";let pending=null;
async function api(path,data){let r=await fetch(path,{method:data?"POST":"GET",headers:{"Content-Type":"application/json","X-GUI-Token":token},body:data?JSON.stringify(data):undefined});let j=await r.json();if(!r.ok)throw Error(j.error);return j}
function cell(row,text){let td=document.createElement("td");td.textContent=text;row.append(td)}
async function refresh(){try{let s=await api("/api/state");document.getElementById("log").textContent=s.log.join("\n");document.getElementById("start").disabled=s.running;document.getElementById("firmwareMode").disabled=s.running;
let table=document.getElementById("rows");let selected=document.querySelector("input[name=selected]:checked")?.value;table.replaceChildren();
for(let c of s.cameras){let row=document.createElement("tr"),td=document.createElement("td"),radio=document.createElement("input");radio.type="radio";radio.name="selected";radio.value=c.device_id;radio.checked=c.device_id===selected;td.append(radio);row.append(td);cell(row,c.device_id+" / "+c.mac_address);cell(row,c.model+(c.hardware_version?" V"+c.hardware_version:"")+" / "+(c.firmware||"unobserved"));let serialCell=document.createElement("td");let serialText=document.createElement("span");serialText.textContent=(c.label_serial||"Not entered")+" / "+c.approved_ipv4+"/"+c.prefix_length;serialCell.append(serialText);let edit=document.createElement("button");edit.textContent="Edit serial";edit.disabled=s.running;edit.onclick=async()=>{let value=prompt("Label serial number",c.label_serial||"");if(value===null)return;try{await api("/api/serial",{device_id:c.device_id,label_serial:value});refresh()}catch(e){document.getElementById("message").textContent=e.message}};serialCell.append(edit);let link=document.createElement("button");link.textContent="Link selected catalog model";link.disabled=s.running;link.onclick=async()=>{try{let id=document.getElementById("catalogChoice").value;if(!id)throw Error("Choose the exact model/hardware in Add camera first");await api("/api/camera/model",{device_id:c.device_id,catalog_id:id});refresh()}catch(e){document.getElementById("message").textContent=e.message}};serialCell.append(link);row.append(serialCell);cell(row,c.status||"unverified");
let actions=document.createElement("td"),remove=document.createElement("button");
remove.textContent="Delete";remove.style.background="#a33838";remove.disabled=s.running;
remove.onclick=async()=>{
if(!confirm("Delete inventory record for "+c.device_id+"? The camera settings will stay as configured."))return;
try{await api("/api/delete",{device_id:c.device_id});document.getElementById("message").textContent="Inventory record deleted";await refresh()}
catch(e){document.getElementById("message").textContent=e.message}};
actions.append(remove);row.append(actions);table.append(row)}
document.getElementById("probe").disabled=s.running||s.probing;
document.getElementById("probeStatus").textContent=s.probe_status;
let details=document.getElementById("probeDetails");details.hidden=s.discovered.length===0;
details.textContent=JSON.stringify(s.discovered,null,2);
pending=s.prompt;document.getElementById("prompt").hidden=!pending;if(pending){document.getElementById("question").textContent=pending.text;document.getElementById("answer").type=pending.secret?"password":"text"}
}catch(e){document.getElementById("message").textContent=e.message}}
document.getElementById("add").onsubmit=async e=>{e.preventDefault();try{await api("/api/camera",Object.fromEntries(new FormData(e.target)));document.getElementById("message").textContent="Inventory saved";refresh()}catch(e){document.getElementById("message").textContent=e.message}};
async function probe(){try{await api("/api/discover",{});refresh()}catch(e){document.getElementById("probeStatus").textContent=e.message}}
async function start(){try{let id=document.querySelector("input[name=selected]:checked")?.value;if(!id)throw Error("Select a camera");await api("/api/start",{device_id:id,firmware_mode:document.getElementById("firmwareMode").value});refresh()}catch(e){document.getElementById("message").textContent=e.message}}
async function answer(){try{await api("/api/answer",{id:pending.id,value:document.getElementById("answer").value});document.getElementById("answer").value="";refresh()}catch(e){document.getElementById("message").textContent=e.message}}
async function downloadDefaults(){let failures=[];for(let m of catalogModels){if(!m.firmware_url||!m.firmware_version)continue;document.getElementById("modelMessage").textContent="Downloading default for "+m.model+" V"+m.hardware_version+"...";try{await api("/api/model/approve",{id:m.id,url:m.firmware_url,version:m.firmware_version})}catch(e){failures.push(m.id+": "+e.message)}}await loadModels();document.getElementById("modelMessage").textContent=failures.length?"Completed with errors: "+failures.join("; "):"All listed defaults downloaded and approved locally. No cameras upgraded."}
let pendingFirmware=null;
async function approveFirmware(m,url,version){let name=decodeURIComponent(url.split("/").pop()),match=name.match(/_(\d+\.\d+\.\d+)[ _]+Build[ _]+(\d+)/i);pendingFirmware={id:m.id,url:url};document.getElementById("approveTarget").textContent=m.model+" V"+m.hardware_version+" ("+m.region+"): "+name+". Downloads locally; no camera upgrade is started.";document.getElementById("approveVersion").value=version||(match?match[1]+" Build "+match[2]:"");document.getElementById("approveForm").hidden=false;document.getElementById("approveForm").scrollIntoView({block:"center"})}
document.getElementById("approveForm").onsubmit=async e=>{e.preventDefault();if(!pendingFirmware)return;document.getElementById("modelMessage").textContent="Downloading firmware ZIP and preparing approved local image...";try{await api("/api/model/approve",{...pendingFirmware,version:document.getElementById("approveVersion").value});document.getElementById("approveForm").hidden=true;pendingFirmware=null;await loadModels();document.getElementById("modelMessage").textContent="Default approved firmware downloaded. Camera upgrade still checks supported model, hardware and image."}catch(error){document.getElementById("modelMessage").textContent=error.message}};
let catalogModels=[];
function chooseModel(){let m=catalogModels.find(x=>x.id===document.getElementById("catalogChoice").value);if(m){document.getElementById("cameraModel").value=m.model;document.getElementById("cameraHardware").value=m.hardware_version}}
function sourceLink(parent,url,label){if(!url)return;let a=document.createElement("a");a.href=url;a.textContent=label;a.target="_blank";a.rel="noopener noreferrer";parent.append(a,document.createElement("br"))}
async function loadModels(){try{let result=await api("/api/models",{});catalogModels=result.models;let body=document.getElementById("modelRows");body.replaceChildren();let select=document.getElementById("catalogChoice"),selected=select.value;select.replaceChildren(new Option("Manual entry / not linked",""));for(let m of catalogModels){select.add(new Option(m.model+" V"+m.hardware_version+" ("+m.region+")",m.id));let row=document.createElement("tr");cell(row,m.model+" V"+m.hardware_version+" / "+m.region);let recorded=document.createElement("td");recorded.textContent=m.firmware_version||"Not recorded";sourceLink(recorded,m.firmware_url,"Default ZIP");let cached=document.createElement("div");cached.textContent=m.approved_image?"Approved local image: "+m.approved_image:"Not downloaded / not approved";recorded.append(cached);let download=document.createElement("button");download.textContent="Download and approve default";download.disabled=!m.firmware_url;download.onclick=()=>approveFirmware(m,m.firmware_url,m.firmware_version);recorded.append(download);row.append(recorded);let actions=document.createElement("td");sourceLink(actions,m.support_url,"Official support page");let note=document.createElement("div");note.textContent=(m.last_checked?m.last_checked+" ":"")+m.check_status;actions.append(note);let check=document.createElement("button");check.textContent="Check for new firmware";check.onclick=async()=>{check.disabled=true;document.getElementById("modelMessage").textContent="Checking official page...";try{await api("/api/model/check",{id:m.id});await loadModels();document.getElementById("modelMessage").textContent="Check complete. Choose a candidate to download and approve; the current default was not changed."}catch(e){document.getElementById("modelMessage").textContent=e.message}finally{check.disabled=false}};let edit=document.createElement("button");edit.textContent="Edit";edit.onclick=()=>{let f=document.getElementById("modelForm");for(let key of ["id","model","hardware_version","region","support_url","firmware_version","firmware_url"])f.elements[key].value=m[key]||"";f.parentElement.open=true};actions.append(check,edit);let candidates=m.available_firmware_urls||[];if(candidates.length){let details=document.createElement("details"),summary=document.createElement("summary");summary.textContent="Firmware candidates ("+candidates.length+")";details.append(summary);for(let url of candidates){sourceLink(details,url,decodeURIComponent(url.split("/").pop()));let approve=document.createElement("button");approve.textContent="Use as default and download";approve.onclick=()=>approveFirmware(m,url,"");details.append(approve)}actions.append(details)}row.append(actions);body.append(row)}select.value=selected;document.getElementById("modelMessage").textContent="Catalog: "+result.path}catch(e){document.getElementById("modelMessage").textContent=e.message}}
document.getElementById("modelForm").onsubmit=async e=>{e.preventDefault();try{await api("/api/model/save",Object.fromEntries(new FormData(e.target)));await loadModels()}catch(error){document.getElementById("modelMessage").textContent=error.message}};
loadModels();refresh();setInterval(refresh,1000);
</script></body></html>"""


def initialize_inventory(path):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS camera_inventory (
            device_id TEXT PRIMARY KEY, mac_address TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL, approved_ipv4 TEXT NOT NULL UNIQUE,
            prefix_length INTEGER NOT NULL, gateway_ipv4 TEXT NOT NULL)""")
        existing = {row[1] for row in db.execute("PRAGMA table_info(camera_inventory)")}
        for name, declaration in {
            "catalog_id": "TEXT", "hardware_version": "TEXT",
            "label_serial": "TEXT", "firmware": "TEXT", "status": "TEXT DEFAULT 'unverified'",
            "observed_metadata": "TEXT", "last_run_at": "TEXT",
        }.items():
            if name not in existing:
                db.execute(f"ALTER TABLE camera_inventory ADD COLUMN {name} {declaration}")


def save_camera(path, data):
    device_id = data["device_id"].strip().upper()
    import re
    if not re.fullmatch(r"[0-9A-F]{17}", device_id):
        raise ValueError("Expected the printed 17-character Device ID.")
    mac = normalize_mac(data["mac_address"])
    interface = ipaddress.IPv4Interface(f"{data['approved_ipv4']}/{data['prefix']}")
    gateway = ipaddress.IPv4Address(data["gateway_ipv4"])
    if not 1 <= interface.network.prefixlen <= 30 or interface.ip not in interface.network.hosts():
        raise ValueError("Invalid target address or prefix.")
    if gateway not in interface.network.hosts() or gateway == interface.ip:
        raise ValueError("Gateway must be a different usable host in the target subnet.")
    serial, model = data["label_serial"].strip(), data["model"].strip()
    if not serial or not model:
        raise ValueError("Label serial and model are required.")
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("""INSERT INTO camera_inventory
            (device_id,mac_address,label_serial,model,approved_ipv4,prefix_length,gateway_ipv4,status,catalog_id,hardware_version)
            VALUES (?,?,?,?,?,?,?,'unverified',?,?)""",
            (device_id,mac,serial,model,str(interface.ip),interface.network.prefixlen,str(gateway),
             data.get("catalog_id") or None, data.get("hardware_version", "").strip() or None))


class Application:
    def __init__(self, database, config):
        self.database, self.config = database, config
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.process = None
        self.log = []
        self.prompt = None
        self.running = False
        self.probing = False
        self.discovered = []
        self.probe_status = "Probe the camera-facing LAN before adding a camera."

    def state(self):
        with self.lock, closing(sqlite3.connect(self.database)) as db:
            db.row_factory = sqlite3.Row
            cameras = [dict(row) for row in db.execute("SELECT * FROM camera_inventory ORDER BY device_id")]
            return dict(cameras=cameras, log=list(self.log), prompt=self.prompt, running=self.running,
                        probing=self.probing, discovered=list(self.discovered), probe_status=self.probe_status)

    def discover_cameras(self):
        with self.lock:
            if self.running or self.probing:
                raise ValueError("Wait for the current operation to finish.")
            self.probing = True
            self.discovered = []
            self.probe_status = f"Probing factory cameras from {SOURCE_IP}..."
        threading.Thread(target=self.collect_discovery, daemon=True).start()

    def collect_discovery(self):
        try:
            cameras = discover(local_ip=SOURCE_IP, timeout=5)
            observations = {}
            for camera in cameras:
                if camera.get("factory_flag") != 0:
                    continue
                observation = dict(camera)
                raw_qr = observation.get("serial")
                observation["device_id"] = decode_device_id(raw_qr)
                observation["qr_wrapper_suffix"] = raw_qr[-3:] if observation["device_id"] else None
                observation["qr_code_raw"] = raw_qr
                observation["serial"] = None
                observation["serial_note"] = "Label serial is not established by this discovery field."
                observations[json.dumps(observation, sort_keys=True)] = observation
            with self.lock:
                self.discovered = list(observations.values())
                self.probe_status = f"Found {len(self.discovered)} distinct factory-state camera observations."
        except Exception as exc:
            with self.lock:
                self.probe_status = f"Discovery failed ({type(exc).__name__}). Check the camera-facing interface."
        finally:
            with self.lock:
                self.probing = False

    def start(self, device_id, allow_firmware_upgrade=False, firmware_mode=None):
        if type(allow_firmware_upgrade) is not bool:
            raise ValueError("Firmware upgrade choice must be true or false.")
        if firmware_mode not in (None, "approved", "preserve", "profile", "initialize"):
            raise ValueError("Unknown firmware handling mode.")
        with self.lock, closing(sqlite3.connect(self.database)) as db, db:
            if self.running or self.probing:
                raise ValueError("Wait for discovery or provisioning to finish.")
            row = db.execute("SELECT model,hardware_version,catalog_id FROM camera_inventory WHERE device_id=?", (device_id,)).fetchone()
            if firmware_mode == "initialize":
                if row is None or row[0] not in {"VIGI C320I", "VIGI C340S"}:
                    raise ValueError("Initialization-only currently supports the inspected C320I/C340S flows.")
            elif row and row[0] == "VIGI C340S":
                if firmware_mode != "preserve" or (row[1] and row[1] not in {"1", "1.0"}):
                    raise ValueError("C340S V1 currently supports full provisioning only with Keep existing firmware selected. Firmware upgrades remain blocked.")
            elif row is None or row[0] != "VIGI C320I" or (row[1] and row[1] not in ("1.20", "1.2")):
                raise ValueError("Provisioning is currently tested for VIGI C320I hardware 1.20. Other entries are inventory-only.")
            firmware_args = []
            if firmware_mode == "initialize":
                firmware_args = ["--initialize-only"]
                allow_firmware_upgrade = False
            elif firmware_mode == "approved":
                rows = load_catalog(self.catalog_path)
                selected = next((r for r in rows if r["id"] == row[2]), None)
                if selected is None or selected["model"] != row[0] or selected["hardware_version"] != row[1] or selected["region"] != "UN":
                    raise ValueError("Link this camera to its exact catalog model/hardware before approved-firmware provisioning.")
                image = approved_image(selected, self.firmware_dir)
                # Catalog approval never bypasses the existing inspected-image restriction.
                from .vigi_firmware_upgrade import inspect_firmware
                try:
                    inspect_firmware(image)
                except Exception as exc:
                    raise ValueError(f"Approved image is cached, but this upgrade engine does not support it: {exc}") from None
                firmware_args = ["--firmware-file", str(image)]
                allow_firmware_upgrade = True
            elif firmware_mode is not None:
                allow_firmware_upgrade = firmware_mode == "profile"
            self.process = subprocess.Popen(
                [sys.executable, "-u", "-m", "vigi_provisioner.vigi_test_gui", "--worker",
                 "--inventory", self.database, "--config", self.config, "--device-id", device_id]
                + firmware_args + ([] if allow_firmware_upgrade else ["--skip-firmware"]),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", bufsize=1,
            )
            self.initialization_only_run = firmware_mode == "initialize"
            self.running, self.log, self.prompt = True, [], None
            db.execute("UPDATE camera_inventory SET status='running',last_run_at=datetime('now') WHERE device_id=?", (device_id,))
        threading.Thread(target=self.collect, args=(device_id,), daemon=True).start()

    def collect(self, device_id):
        for line in self.process.stdout:
            with self.lock:
                if line.startswith("GUI_PROMPT "):
                    self.prompt = json.loads(line[len("GUI_PROMPT "):])
                elif line.startswith("GUI_OBSERVATION "):
                    observations = json.loads(line[len("GUI_OBSERVATION "):])
                    with closing(sqlite3.connect(self.database)) as db, db:
                        previous = db.execute(
                            "SELECT observed_metadata FROM camera_inventory WHERE device_id=?", (device_id,)
                        ).fetchone()
                        merged = json.loads(previous[0]) if previous and previous[0] else {}
                        merged.update({key: value for key, value in observations.items() if value is not None})
                        db.execute(
                            "UPDATE camera_inventory SET firmware=?,observed_metadata=? WHERE device_id=?",
                            (merged.get("firmware"), json.dumps(merged), device_id),
                        )
                else:
                    self.log.append(line.rstrip())
        code = self.process.wait()
        with self.lock, closing(sqlite3.connect(self.database)) as db, db:
            self.running, self.prompt = False, None
            self.log.append("Run completed." if code == 0 else "Run stopped. Check camera state before retrying.")
            db.execute("UPDATE camera_inventory SET status=? WHERE device_id=?",
                       ("initialized" if code == 0 and getattr(self, "initialization_only_run", False) else "verified" if code == 0 else "stopped",device_id))

    def delete_camera(self, device_id):
        with self.lock, closing(sqlite3.connect(self.database)) as db, db:
            if self.running:
                raise ValueError("Wait for the active run before deleting inventory.")
            result = db.execute(
                "DELETE FROM camera_inventory WHERE device_id=?", (device_id,)
            )
            if result.rowcount != 1:
                raise ValueError("Camera record not found.")

    def answer(self, data):
        with self.lock:
            if not self.prompt or data.get("id") != self.prompt["id"]:
                raise ValueError("This prompt has expired.")
            self.process.stdin.write(json.dumps(str(data["value"])) + "\n")
            self.process.stdin.flush()
            self.prompt = None


def worker(args):
    from . import vigi_factory_workflow as workflow

    def prompt(text, secret=False):
        print("GUI_PROMPT " + json.dumps(dict(id=secrets.token_hex(8),text=text,secret=secret)), flush=True)
        line = sys.stdin.readline()
        if not line:
            raise EOFError("GUI input closed")
        return json.loads(line)

    workflow.input = prompt
    workflow.getpass = lambda text: prompt(text, True)
    discover = workflow.discover
    def observe(*a, **kw):
        cameras = discover(*a, **kw)
        uri = Path(args.inventory).resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as db:
            row = db.execute("SELECT mac_address FROM camera_inventory WHERE device_id=?", (args.device_id,)).fetchone()
        if row is None:
            raise ValueError("Selected camera inventory record not found.")
        wanted = row[0]
        matches = [c for c in cameras if normalize_mac(c["mac"]) == normalize_mac(wanted)]
        if matches:
            print("GUI_OBSERVATION " + json.dumps(matches[0]), flush=True)
        return cameras
    workflow.discover = observe
    configure_network = workflow.configure_network

    def configure_and_observe(plan, password):
        configure_network(plan, password)
        endpoint = f"http://{plan['target_ip']}:{plan.get('onvif_port', 80)}/onvif/device_service"
        try:
            info = get_device_information(endpoint, "admin", password)
            observations = {
                "firmware": info.get("FirmwareVersion"),
                "onvif_model": info.get("Model"),
                "manufacturer": info.get("Manufacturer"),
                "onvif_serial": info.get("SerialNumber"),
                "hardware_id": info.get("HardwareId"),
                "last_verified_ipv4": plan["target_ip"],
            }
            print("GUI_OBSERVATION " + json.dumps(observations), flush=True)
            print("ONVIF inventory metadata collected.", flush=True)
        except Exception as exc:
            print(f"Device information read failed ({type(exc).__name__}). Network verification passed.", flush=True)

    workflow.configure_network = configure_and_observe
    initialize_only = workflow.initialize_only
    def initialize_and_observe(arguments):
        metadata = initialize_only(arguments)
        print("GUI_OBSERVATION " + json.dumps(metadata), flush=True)
        return metadata
    workflow.initialize_only = initialize_and_observe
    sys.argv = [sys.argv[0],"--inventory",args.inventory,"--config",args.config,"--device-id",args.device_id]
    if args.initialize_only:
        sys.argv.append("--initialize-only")
    if args.skip_firmware:
        sys.argv.append("--skip-firmware")
    if args.firmware_file:
        sys.argv.extend(["--firmware-file", args.firmware_file])
    workflow.main()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--initialize-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--firmware-dir", help="Firmware cache folder (default: firmware beside profile)")
    parser.add_argument("--firmware-file", help=argparse.SUPPRESS)
    parser.add_argument("--models", help="Editable model catalog TOML (default: models.toml beside profile)")
    parser.add_argument("--bind", default="127.0.0.1", help="Local IPv4 interface address to serve on")
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--skip-firmware",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--device-id",help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.bind = str(ipaddress.IPv4Address(args.bind))
    if args.bind == "0.0.0.0":
        parser.error("Choose a specific interface IPv4 address for --bind.")
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")
    if args.worker:
        worker(args)
        return
    database = str(Path(args.inventory).resolve())
    config = str(Path(args.config).resolve())
    from .vigi_initialization_config import load_provisioning_profile
    load_provisioning_profile(config)
    initialize_inventory(database)
    catalog_path = Path(args.models).resolve() if args.models else Path(config).with_name("models.toml")
    if not catalog_path.exists():
        example = Path(__file__).resolve().parents[2] / "models.example.toml"
        save_catalog(catalog_path, load_catalog(example) if example.exists() else [])
    load_catalog(catalog_path)
    app = Application(database,config)
    app.catalog_path = catalog_path
    app.firmware_dir = Path(args.firmware_dir).resolve() if args.firmware_dir else Path(config).with_name("firmware")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, value):
            payload = json.dumps(value).encode()
            self.send_response(code)
            self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def authorized(self):
            return self.headers.get("Host") == f"{args.bind}:{args.port}"

        def do_GET(self):
            if not self.authorized():
                self.reply(403,dict(error="Use the configured GUI address."))
                return
            if self.path.split("?", 1)[0] == "/":
                body = PAGE.replace("__TOKEN__",app.token).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","text/html; charset=utf-8")
                self.send_header("Content-Length",str(len(body)))
                self.send_header("Cache-Control","no-store")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/state" and self.headers.get("X-GUI-Token") == app.token:
                self.reply(200,app.state())
            else:
                self.reply(404,dict(error="Not found"))

        def do_POST(self):
            if not self.authorized() or self.headers.get("X-GUI-Token") != app.token:
                self.reply(403,dict(error="Invalid GUI session"))
                return
            try:
                size = int(self.headers.get("Content-Length","0"))
                if not 0 < size <= 16384:
                    raise ValueError("Invalid request size")
                data = json.loads(self.rfile.read(size))
                if self.path == "/api/models":
                    with app.lock:
                        rows = load_catalog(catalog_path)
                    self.reply(200, dict(models=rows, path=str(catalog_path)))
                    return
                elif self.path == "/api/model/save":
                    row = validate_model(data)
                    with app.lock:
                        if app.running:
                            raise ValueError("Wait for provisioning before editing the catalog.")
                        rows = load_catalog(catalog_path)
                        previous = next((r for r in rows if r["id"] == row["id"]), None)
                        if previous:
                            row["last_checked"] = ""
                            row["check_status"] = "Edited; check official page again."
                        save_catalog(catalog_path, [r for r in rows if r["id"] != row["id"]] + [row])
                elif self.path == "/api/model/approve":
                    with app.lock:
                        if app.running or app.probing:
                            raise ValueError("Wait for active operations before downloading firmware.")
                        rows = load_catalog(catalog_path)
                        original = next((r for r in rows if r["id"] == data["id"]), None)
                    if original is None:
                        raise ValueError("Model catalog entry not found.")
                    try:
                        approved = approve_download(original, data["url"], data["version"], app.firmware_dir)
                    except Exception as exc:
                        raise ValueError(f"Firmware download/approval failed: {exc}. Previous default unchanged.") from None
                    with app.lock:
                        rows = load_catalog(catalog_path)
                        if app.running or next((r for r in rows if r["id"] == data["id"]), None) != original:
                            raise ValueError("Catalog or provisioning state changed. Approval not saved; retry.")
                        save_catalog(catalog_path, [approved if r["id"] == data["id"] else r for r in rows])
                elif self.path == "/api/camera/model":
                    with app.lock, closing(sqlite3.connect(database)) as db, db:
                        if app.running:
                            raise ValueError("Wait for provisioning before linking a camera.")
                        selected = next((r for r in load_catalog(catalog_path) if r["id"] == data["catalog_id"]), None)
                        if selected is None:
                            raise ValueError("Select a catalog model first.")
                        result = db.execute("UPDATE camera_inventory SET catalog_id=?,model=?,hardware_version=? WHERE device_id=?", (selected["id"], selected["model"], selected["hardware_version"], data["device_id"]))
                        if result.rowcount != 1:
                            raise ValueError("Camera record not found.")
                elif self.path == "/api/model/check":
                    with app.lock:
                        if app.running:
                            raise ValueError("Wait for provisioning before checking firmware.")
                        rows = load_catalog(catalog_path)
                        original = next((r for r in rows if r["id"] == data["id"]), None)
                    if original is None:
                        raise ValueError("Model catalog entry not found.")
                    try:
                        checked = check_firmware(original)
                    except Exception as exc:
                        raise ValueError(f"Firmware check failed ({type(exc).__name__}). Default initial update firmware unchanged; check Internet access or inspect the support page.") from None
                    with app.lock:
                        rows = load_catalog(catalog_path)
                        current = next((r for r in rows if r["id"] == data["id"]), None)
                        if current != original:
                            raise ValueError("Catalog changed during check. Retry.")
                        save_catalog(catalog_path, [checked if r["id"] == data["id"] else r for r in rows])
                elif self.path == "/api/camera":
                    with app.lock:
                        if app.running:
                            raise ValueError("Wait for the active run before editing inventory.")
                        if data.get("catalog_id"):
                            selected = next((r for r in load_catalog(catalog_path) if r["id"] == data["catalog_id"]), None)
                            if selected is None:
                                raise ValueError("Catalog model not found.")
                            data["model"], data["hardware_version"] = selected["model"], selected["hardware_version"]
                        save_camera(database,data)
                elif self.path == "/api/serial":
                    serial = str(data["label_serial"]).strip()
                    if not serial or len(serial) > 128:
                        raise ValueError("Enter a label serial number of up to 128 characters.")
                    with app.lock, closing(sqlite3.connect(database)) as db, db:
                        if app.running:
                            raise ValueError("Wait for the active run before editing inventory.")
                        result = db.execute(
                            "UPDATE camera_inventory SET label_serial=? WHERE device_id=?",
                            (serial, data["device_id"]),
                        )
                        if result.rowcount != 1:
                            raise ValueError("Camera record not found.")
                elif self.path == "/api/discover":
                    app.discover_cameras()
                elif self.path == "/api/delete":
                    app.delete_camera(data["device_id"])
                elif self.path == "/api/start":
                    app.start(data["device_id"], data.get("allow_firmware_upgrade", False), data.get("firmware_mode"))
                elif self.path == "/api/answer":
                    app.answer(data)
                else:
                    raise ValueError("Unknown operation")
                self.reply(200,dict(ok=True))
            except (ValueError,KeyError,sqlite3.Error,OSError) as exc:
                self.reply(400,dict(error=str(exc)))

    server = ThreadingHTTPServer((args.bind,args.port),Handler)
    print(f"Open http://{args.bind}:{args.port} in your browser.",flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
