#!/usr/bin/env python3
"""
Kate Heartbeat — Surveillance continue façon OpenClaw.
Vérifie tous les services, expose un statut, alerte en cas de panne.

Usage:
  python3 heartbeat.py              # Check unique
  python3 heartbeat.py --watch      # Mode continu (toutes les 60s)
  python3 heartbeat.py --json       # Sortie JSON
"""

import json, os, sys, subprocess, time
from datetime import datetime

SERVICES = {
    "hermes_gateway": {
        "check": "curl -s -o /dev/null -w '%{http_code}' --max-time 5 -u 'DELSOL-AI-HERMES:bLerLxqJ32fOUV15EXZ9fAZvhddDSubM' http://localhost:4860 2>/dev/null",
        "expect": "200",
        "critical": True
    },
    "voice_interface": {
        "check": "curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:8765/ 2>/dev/null",
        "expect": "200",
        "critical": False
    },
    "mempalace": {
        "check": "test -f /opt/data/mempalace/mempalace.db && echo '200' || echo '000'",
        "expect": "200",
        "critical": True
    },
    "ruflo_mcp": {
        # Robust check: Ruflo's supervised HTTP bridge listens on :3001 and
        # returns 404 at root when alive. Fallback to non-defunct process scan;
        # include cwd because the bridge command may be just `node index.js`.
        "check": "code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://localhost:3001/ 2>/dev/null); if [ \"$code\" = \"404\" ] || [ \"$code\" = \"200\" ]; then echo 200; else python3 - <<'PY'\nimport os\nfound=False\nfor pid in filter(str.isdigit, os.listdir('/proc')):\n    try:\n        stat=open(f'/proc/{pid}/stat').read().split()[2]\n        cmd=open(f'/proc/{pid}/cmdline','rb').read().replace(b'\\0',b' ').decode().lower()\n        cwd=os.readlink(f'/proc/{pid}/cwd').lower()\n    except Exception:\n        continue\n    hay=cmd+' '+cwd\n    if stat != 'Z' and 'ruflo' in hay and 'heartbeat.py' not in hay:\n        found=True; break\nprint('200' if found else '000')\nPY\nfi",
        "expect": "200",
        "critical": False
    },
    "disk": {
        "check": "df / | tail -1 | awk '{print $5}' | sed 's/%//'",
        "expect": None,
        "critical": True,
        "warn_above": 85
    },
    "memory": {
        "check": "free | grep Mem | awk '{printf \"%.0f\", $3/$2*100}'",
        "expect": None,
        "critical": True,
        "warn_above": 90
    }
}

HEARTBEAT_LOG = "/opt/data/kate_evolution/heartbeat_log.jsonl"


def check_service(name, config):
    try:
        result = subprocess.run(config["check"], shell=True, capture_output=True, text=True, timeout=10)
        value = result.stdout.strip()
        
        status = "healthy"
        if config.get("expect") and value != config["expect"]:
            status = "down"
        elif config.get("warn_above"):
            try:
                if int(value) > config["warn_above"]:
                    status = "warning"
            except ValueError:
                status = "unknown"
        
        return {
            "service": name,
            "status": status,
            "value": value,
            "critical": config.get("critical", False)
        }
    except Exception as e:
        return {
            "service": name,
            "status": "down",
            "value": str(e)[:100],
            "critical": config.get("critical", False)
        }


def heartbeat():
    results = []
    critical_failures = []
    
    for name, config in SERVICES.items():
        r = check_service(name, config)
        results.append(r)
        if r["status"] in ("down", "warning") and r["critical"]:
            critical_failures.append(r)

    overall = "critical" if critical_failures else ("degraded" if any(r["status"] != "healthy" for r in results) else "healthy")
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "overall": overall,
        "services": {r["service"]: r["status"] for r in results},
        "details": results,
        "critical_failures": [r["service"] for r in critical_failures]
    }
    
    # Log
    os.makedirs(os.path.dirname(HEARTBEAT_LOG), exist_ok=True)
    with open(HEARTBEAT_LOG, "a") as f:
        f.write(json.dumps(report, ensure_ascii=False) + "\n")
        f.flush()
    
    return report


def print_heartbeat(report):
    symbols = {"healthy": "✅", "warning": "⚠️", "down": "❌", "unknown": "❓"}
    status_color = {"healthy": "OK", "degraded": "DEGRADED", "critical": "CRITICAL"}
    
    print(f"\n💓 KATE HEARTBEAT — {report['timestamp'][:19]}")
    print(f"   Status: {status_color.get(report['overall'], report['overall'])}")
    print("─" * 40)
    for r in report["details"]:
        s = symbols.get(r["status"], "?")
        crit = " 🔴" if r["critical"] else ""
        print(f"  {s} {r['service']:20s} {r['status']:8s} [{r['value']}]{crit}")


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(heartbeat(), ensure_ascii=False, indent=2))
    elif "--watch" in sys.argv:
        interval = 60
        print("💓 Heartbeat continu — Ctrl+C pour arrêter")
        while True:
            try:
                print_heartbeat(heartbeat())
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\nArrêt.")
                break
    else:
        print_heartbeat(heartbeat())
