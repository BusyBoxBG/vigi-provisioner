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

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>VIGI Provisioner</title>
<style>
body{font:16px "Segoe UI",sans-serif;background:#f0f3f5;color:#182f3b;margin:0}
header{background:#143b43;color:white;padding:24px 5%}main{max-width:1200px;margin:28px auto;padding:0 20px}
.grid{display:grid;grid-template-columns:360px 1fr;gap:24px}section{background:white;border:1px solid #d7e0e4;border-radius:12px;padding:24px;margin-bottom:20px}
label{display:block;margin:12px 0 5px}input{box-sizing:border-box;width:100%;padding:10px;border:1px solid #a9b9c1;border-radius:5px}
button{background:#087b70;color:white;border:0;border-radius:5px;padding:11px 16px;cursor:pointer;margin:12px 4px 0 0}
button:disabled{opacity:.5}table{width:100%;border-collapse:collapse;font-size:14px}td,th{text-align:left;padding:9px;border-bottom:1px solid #ddd}
pre{white-space:pre-wrap;overflow:auto;background:#10242c;color:#cfe5df;padding:18px;min-height:260px;max-height:450px}
#prompt{background:#edf8f4;padding:16px}small{color:#536b78}@media(max-width:800px){.grid{display:block}}
</style></head><body><header><h1>VIGI Provisioner</h1>Inventory and factory setup Р вЂ™Р’В· Ubuntu test console</header>
<main><div class="grid"><section><h2>Add camera</h2><form id="add">
<label>Device ID</label><input name="device_id" required>
<label>MAC address</label><input name="mac_address" required>
<label>Label serial number</label><input name="label_serial" required>
<label>Model</label><input name="model" value="VIGI C320I" required>
<label>Approved IP address</label><input name="approved_ipv4" value="192.168.0.150" required>
<label>Netmask or prefix</label><input name="prefix" value="255.255.255.0" required>
<label>Gateway</label><input name="gateway_ipv4" value="192.168.0.1" required>
<button>Save inventory</button></form><p><small>The current provisioning engine supports the tested C320I lab addresses. Other models can be recorded for future testing.</small></p></section>
<div><section><h2>Camera inventory</h2><div style="overflow:auto"><table><thead><tr><th>Select</th><th>Device ID / MAC</th><th>Model / firmware</th><th>Serial / target</th><th>State</th></tr></thead><tbody id="rows"></tbody></table></div>
<button id="start" onclick="start()">Start provisioning</button><p id="message" role="status"></p></section>
<section><h2>Provisioning steps</h2><pre id="log"></pre><div id="prompt" hidden>
<label id="question"></label><input id="answer" autocomplete="off"><button onclick="answer()">Confirm / Continue</button></div></section></div></div></main>
<script>
const token="__TOKEN__";let pending=null;
async function api(path,data){let r=await fetch(path,{method:data?"POST":"GET",headers:{"Content-Type":"application/json","X-GUI-Token":token},body:data?JSON.stringify(data):undefined});let j=await r.json();if(!r.ok)throw Error(j.error);return j}
function cell(row,text){let td=document.createElement("td");td.textContent=text;row.append(td)}
async function refresh(){try{let s=await api("/api/state");document.getElementById("log").textContent=s.log.join("\n");document.getElementById("start").disabled=s.running;
let table=document.getElementById("rows");let selected=document.querySelector("input[name=selected]:checked")?.value;table.replaceChildren();
for(let c of s.cameras){let row=document.createElement("tr"),td=document.createElement("td"),radio=document.createElement("input");radio.type="radio";radio.name="selected";radio.value=c.device_id;radio.checked=c.device_id===selected;td.append(radio);row.append(td);cell(row,c.device_id+" / "+c.mac_address);cell(row,c.model+" / "+(c.firmware||"unobserved"));cell(row,c.label_serial+" / "+c.approved_ipv4+"/"+c.prefix_length);cell(row,c.status);table.append(row)}
pending=s.prompt;document.getElementById("prompt").hidden=!pending;if(pending){document.getElementById("question").textContent=pending.text;document.getElementById("answer").type=pending.secret?"password":"text"}
}catch(e){document.getElementById("message").textContent=e.message}}
document.getElementById("add").onsubmit=async e=>{e.preventDefault();try{await api("/api/camera",Object.fromEntries(new FormData(e.target)));document.getElementById("message").textContent="Inventory saved";refresh()}catch(e){document.getElementById("message").textContent=e.message}};
async function start(){try{let id=document.querySelector("input[name=selected]:checked")?.value;if(!id)throw Error("Select a camera");await api("/api/start",{device_id:id});refresh()}catch(e){document.getElementById("message").textContent=e.message}}
async function answer(){try{await api("/api/answer",{id:pending.id,value:document.getElementById("answer").value});document.getElementById("answer").value="";refresh()}catch(e){document.getElementById("message").textContent=e.message}}
refresh();setInterval(refresh,1000);
</script></body></html>"""


def initialize_inventory(path):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS camera_inventory (
            device_id TEXT PRIMARY KEY, mac_address TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL, approved_ipv4 TEXT NOT NULL UNIQUE,
            prefix_length INTEGER NOT NULL, gateway_ipv4 TEXT NOT NULL)""")
        existing = {row[1] for row in db.execute("PRAGMA table_info(camera_inventory)")}
        for name, declaration in {
            "label_serial": "TEXT", "firmware": "TEXT", "status": "TEXT DEFAULT 'ready'",
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
            (device_id,mac_address,label_serial,model,approved_ipv4,prefix_length,gateway_ipv4)
            VALUES (?,?,?,?,?,?,?)""",
            (device_id,mac,serial,model,str(interface.ip),interface.network.prefixlen,str(gateway)))


class Application:
    def __init__(self, database, config):
        self.database, self.config = database, config
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.process = None
        self.log = []
        self.prompt = None
        self.running = False

    def state(self):
        with self.lock, closing(sqlite3.connect(self.database)) as db:
            db.row_factory = sqlite3.Row
            cameras = [dict(row) for row in db.execute("SELECT * FROM camera_inventory ORDER BY device_id")]
            return dict(cameras=cameras, log=list(self.log), prompt=self.prompt, running=self.running)

    def start(self, device_id):
        with self.lock, closing(sqlite3.connect(self.database)) as db, db:
            if self.running:
                raise ValueError("A provisioning run is already active.")
            row = db.execute("SELECT model FROM camera_inventory WHERE device_id=?", (device_id,)).fetchone()
            if row is None or row[0] != "VIGI C320I":
                raise ValueError("Select a VIGI C320I inventory record for this test engine.")
            self.process = subprocess.Popen(
                [sys.executable, "-u", "-m", "vigi_provisioner.vigi_test_gui", "--worker",
                 "--inventory", self.database, "--config", self.config, "--device-id", device_id],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", bufsize=1,
            )
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
                        db.execute("UPDATE camera_inventory SET firmware=?,observed_metadata=? WHERE device_id=?",
                                   (observations.get("firmware"), json.dumps(observations), device_id))
                else:
                    self.log.append(line.rstrip())
        code = self.process.wait()
        with self.lock, closing(sqlite3.connect(self.database)) as db, db:
            self.running, self.prompt = False, None
            self.log.append("Run completed." if code == 0 else "Run stopped. Check camera state before retrying.")
            db.execute("UPDATE camera_inventory SET status=? WHERE device_id=?",
                       ("verified" if code == 0 else "stopped",device_id))

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
        wanted = workflow.load_inventory_assignment(args.inventory,args.device_id)[0]
        matches = [c for c in cameras if normalize_mac(c["mac"]) == normalize_mac(wanted)]
        if len(matches) == 1:
            print("GUI_OBSERVATION " + json.dumps(matches[0]), flush=True)
        return cameras
    workflow.discover = observe
    sys.argv = [sys.argv[0],"--inventory",args.inventory,"--config",args.config,"--device-id",args.device_id]
    workflow.main()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--bind", default="127.0.0.1", help="Local IPv4 interface address to serve on")
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
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
    app = Application(database,config)

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
            if self.path == "/":
                body = PAGE.replace("__TOKEN__",app.token).encode()
                self.send_response(200)
                self.send_header("Content-Type","text/html; charset=utf-8")
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
                if self.path == "/api/camera":
                    with app.lock:
                        if app.running:
                            raise ValueError("Wait for the active run before editing inventory.")
                        save_camera(database,data)
                elif self.path == "/api/start":
                    app.start(data["device_id"])
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
