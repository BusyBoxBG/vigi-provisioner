"""Disable motion processing actions without changing the detector or network."""
import argparse
import re
from getpass import getpass
from pathlib import Path
from urllib.parse import unquote
from .vigi_factory_workflow import CameraHTTPS, ProvisioningError, approve_observed_pin, login, load_inventory_details
from .vigi_initialization_config import load_provisioning_profile
from .vigi_pin_inventory import normalize_mac

PROFILE_ACTIONS = ("record", "snapshots", "push_messages", "report_server", "email", "ftp", "light_alarm", "sound_alarm", "alarm_output_1")
ACTION_FIELDS = frozenset(("record_enabled", "capture_enabled", "msg_push_enabled", "report_server_enabled", "email_enabled", "ftp_enabled", "light_alarm_enabled", "sound_alarm_enabled", "AO1_enabled", "client_enabled", "app_enabled", "target_track_enabled"))

def update_profile(path):
    path = Path(path)
    load_provisioning_profile(path)
    original = path.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^\[motion_detection\][ \t]*\r?\n(.*?)(?=^\[|\Z)", original)
    if not match:
        raise ValueError("The local profile needs a motion_detection table.")
    body = match[1]
    for field in PROFILE_ACTIONS:
        expression = r"(?m)^([ \t]*" + re.escape(field) + r"[ \t]*=[ \t]*)(?:true|false)([ \t]*(?:#.*)?)$"
        body, count = re.subn(expression, lambda m: m[1]+"false"+m[2], body)
        if count != 1:
            raise ValueError("Expected exactly one boolean motion setting: " + field)
    updated = original[:match.start(1)] + body + original[match.end(1):]
    path.write_text(updated, encoding="utf-8")
    print("Local profile updated: all motion processing actions false.", flush=True)

def disable_actions(camera, path, *, legacy=False):
    def read():
        query = {"name": ["motion_det", "motion_notif_list", "arming_schedule"]}
        if not legacy:
            query["version"] = "1"
        _, result = camera.post("Read motion state", {"method":"get", "motion_detection":query}, path=path)
        motion = result.get("motion_detection", {})
        if not all(isinstance(motion.get(k),dict) for k in ("motion_det","motion_notif_list","arming_schedule")):
            raise ProvisioningError("Unexpected motion readback. Stop and inspect the camera.")
        return motion
    before = read()
    flags = before["motion_notif_list"]
    unknown = [k for k,v in flags.items() if k.endswith("_enabled") and k not in ACTION_FIELDS and str(v).lower() in {"on","true","1"}]
    if unknown:
        raise ProvisioningError("Unrecognized active motion actions: " + ", ".join(sorted(unknown)))
    target = {k:"off" for k in ACTION_FIELDS if k in flags}
    if not target:
        raise ProvisioningError("No recognized processing action fields were returned.")
    if any(str(flags[k]) != "off" for k in target):
        camera.post("Disable motion processing actions", {"method":"set", "motion_detection":{"motion_notif_list":target}}, path=path)
    after = read()
    if any(k.endswith("_enabled") and str(v).lower() in {"on","true","1"} for k,v in after["motion_notif_list"].items()) or any(after["motion_notif_list"].get(k)!="off" for k in target):
        raise ProvisioningError("Not all motion processing actions were verified off.")
    if after["motion_det"] != before["motion_det"] or after["arming_schedule"] != before["arming_schedule"]:
        raise ProvisioningError("Detector or schedule readback differs. Inspect current state; no automatic rollback.")
    print("Verified all motion processing actions off. Detector settings and schedule unchanged.", flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory",required=True)
    parser.add_argument("--device-id",required=True)
    parser.add_argument("--config",default="provisioning.toml")
    parser.add_argument("--update-profile",action="store_true")
    parser.add_argument("--legacy",action="store_true",help="Use the inspected legacy motion read format")
    args = parser.parse_args()
    try:
        row = load_inventory_details(args.inventory,args.device_id.upper())
        if args.update_profile:
            update_profile(args.config)
        ip = row["approved_ipv4"]
        camera = CameraHTTPS(approve_observed_pin(ip),ip)
        path = login(camera,getpass("Camera admin password: "))
        _, result = camera.post("Verify camera identity", {"method":"get","device_info":{"name":"info"},"network":{"name":["wan_status"]}},path=path)
        info = result.get("device_info",{}).get("info",{})
        mac = result.get("network",{}).get("wan_status",{}).get("mac","")
        device_id = info.get("devcode")
        if unquote(info.get("device_model",""))!=row["model"] or normalize_mac(mac)!=normalize_mac(row["mac_address"]) or (device_id and device_id.upper()!=args.device_id.upper()):
            raise ProvisioningError("Authenticated camera identity differs. No action settings sent.")
        disable_actions(camera,path,legacy=args.legacy)
    except (ValueError,OSError,RuntimeError,EOFError) as exc:
        parser.exit(1,str(exc)+"\n")

if __name__=="__main__":
    main()
