"""P0.2.2 check: cockpit health, PM2 saved list, Port Registry entry."""
import json, pathlib, urllib.request
h = urllib.request.urlopen("http://127.0.0.1:6795/health", timeout=5)
print("GET /health ->", h.status, h.read().decode())
dump = json.loads(pathlib.Path(r"C:\ProgramData\pm2\home\dump.pm2").read_text(encoding="utf-8"))
saved = [a["name"] for a in dump if a["name"] == "phasedoc-carbonmint"]
print("pm2 saved list contains:", saved)
reg = [l for l in pathlib.Path(r"C:\whitenoise\WhiteNoise\04-Docs\SOPs\Port Registry.md").read_text(encoding="utf-8").splitlines() if l.startswith("| 6795")]
print("Port Registry:", reg)
ok = h.status == 200 and saved and reg and "active" in reg[0]
print("RESULT", "PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
