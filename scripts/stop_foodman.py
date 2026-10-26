"""
Food Man Stop Controller
Stops Waitress server and Cloudflare tunnel processes,
cleans up PID files, and removes .public_url.
"""
import os
import sys
import subprocess
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PUBLIC_URL_FILE = os.path.join(PROJECT_DIR, '.public_url')
SERVER_PID_FILE = os.path.join(PROJECT_DIR, '.server.pid')
TUNNEL_PID_FILE = os.path.join(PROJECT_DIR, '.tunnel.pid')

def kill_pid(pid):
    if not pid: return
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def kill_by_file(filepath):
    if os.path.isfile(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                pid = f.read().strip()
                if pid:
                    kill_pid(int(pid))
        except Exception:
            pass
        try:
            os.remove(filepath)
        except Exception:
            pass


def kill_port_5000():
    try:
        res = subprocess.run(["netstat", "-ano"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        for line in res.stdout.splitlines():
            if ":5000 " in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = parts[-1]
                if pid.isdigit() and int(pid) > 0:
                    kill_pid(int(pid))
    except Exception:
        pass


def stop_all():
    print("Stopping Food Man services...")

    # 1. Kill Tunnel PID
    kill_by_file(TUNNEL_PID_FILE)

    # 2. Kill Server PID
    kill_by_file(SERVER_PID_FILE)

    # 3. Kill any remaining listeners on Port 5000
    kill_port_5000()

    # 4. Clean up .public_url and .tunnel_cred.json
    if os.path.isfile(PUBLIC_URL_FILE):
        try:
            os.remove(PUBLIC_URL_FILE)
        except Exception:
            pass
    cred_file = os.path.join(PROJECT_DIR, '.tunnel_cred.json')
    if os.path.isfile(cred_file):
        try:
            os.remove(cred_file)
        except Exception:
            pass

    print("✓ Food Man server and Cloudflare tunnel have been stopped successfully.")


if __name__ == "__main__":
    stop_all()
