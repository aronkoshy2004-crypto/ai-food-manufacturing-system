"""
Food Man Desktop Launcher Engine
Handles:
1. Health check & Waitress WSGI server startup (if not already running)
2. Cloudflare tunnel execution & URL extraction to .public_url
3. Port conflict resolution & friendly warnings
4. Cloudflared missing / no internet fallbacks
5. Browser startup in app mode (--app=http://localhost:5000)
"""
import os
import sys
import re
import time
import socket
import urllib.request
import urllib.error
import subprocess

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PUBLIC_URL_FILE = os.path.join(PROJECT_DIR, '.public_url')
SERVER_PID_FILE = os.path.join(PROJECT_DIR, '.server.pid')
TUNNEL_PID_FILE = os.path.join(PROJECT_DIR, '.tunnel.pid')
LOG_FILE = os.path.join(PROJECT_DIR, 'launcher.log')

def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def is_port_in_use(port=5000, host='127.0.0.1'):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        try:
            s.connect((host, port))
            return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False


def check_health(url="http://localhost:5000/health", timeout=1.0):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FoodMan-Launcher'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def wait_for_health(url="http://localhost:5000/health", timeout_seconds=15.0):
    start = time.time()
    while time.time() - start < timeout_seconds:
        if check_health(url):
            return True
        time.sleep(0.3)
    return False


def find_cloudflared():
    candidates = [
        "cloudflared",
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
        r"C:\Program Files\cloudflared\cloudflared.exe",
        os.path.join(PROJECT_DIR, "cloudflared.exe"),
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Links\cloudflared.exe")
    ]
    for c in candidates:
        try:
            res = subprocess.run([c, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
            if res.returncode == 0:
                return c
        except Exception:
            continue
    return None


def test_internet():
    # Test DNS resolution for Cloudflare API or standard host
    for host in ["api.trycloudflare.com", "cloudflare.com", "1.1.1.1"]:
        try:
            socket.gethostbyname(host)
            return True
        except Exception:
            continue
    return False


def start_waitress():
    if check_health():
        log("Server is already running and healthy on http://localhost:5000.")
        return None

    if is_port_in_use(5000):
        log("WARNING: Port 5000 is occupied, but /health did not respond. Attempting reuse or restart.")

    log("Starting Waitress production WSGI server on port 5000...")
    creation_flags = 0
    if os.name == 'nt':
        # CREATE_NO_WINDOW (0x08000000) | DETACHED_PROCESS (0x00000008) | CREATE_NEW_PROCESS_GROUP (0x00000200)
        creation_flags = 0x08000000 | 0x00000008 | 0x00000200

    # Use sys.executable to run waitress on wsgi:app
    cmd = [sys.executable, "-m", "waitress", "--host=0.0.0.0", "--port=5000", "--threads=8", "wsgi:app"]
    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_DIR,
        creationflags=creation_flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    with open(SERVER_PID_FILE, 'w', encoding='utf-8') as f:
        f.write(str(proc.pid))

    if wait_for_health():
        log(f"Waitress server ready (PID: {proc.pid}) on http://localhost:5000.")
        return proc
    else:
        log("Waitress startup timed out waiting for /health.")
        return proc


def request_quick_tunnel_direct():
    """Bypasses local ISP DNS blocking of api.trycloudflare.com by connecting directly to Cloudflare edge IP with SNI."""
    try:
        import ssl, json
        ctx = ssl.create_default_context()
        raw = socket.socket()
        raw.settimeout(6.0)
        raw.connect(('104.16.230.132', 443))
        ssl_sock = ctx.wrap_socket(raw, server_hostname='api.trycloudflare.com')
        ssl_sock.sendall(b'POST /tunnel HTTP/1.1\r\nHost: api.trycloudflare.com\r\nUser-Agent: cloudflared\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
        resp = b''
        while True:
            d = ssl_sock.recv(4096)
            if not d: break
            resp += d
        ssl_sock.close()
        _, _, body = resp.partition(b'\r\n\r\n')
        data = json.loads(body.decode('utf-8'))
        return data.get('result')
    except Exception as e:
        log(f"Direct quick tunnel request notice: {e}")
        return None


def start_tunnel():
    cf_path = find_cloudflared()
    if not cf_path:
        log("INFO: Cloudflare tunnel (cloudflared) is not installed.")
        log("  -> Install with: winget install --id Cloudflare.cloudflared")
        log("  -> Falling back to LAN address with camera HTTPS advisory.")
        # Ensure stale .public_url is removed
        if os.path.exists(PUBLIC_URL_FILE):
            try:
                os.remove(PUBLIC_URL_FILE)
            except Exception:
                pass
        return None

    if not test_internet():
        log("INFO: No internet connectivity detected. Falling back to LAN link.")
        if os.path.exists(PUBLIC_URL_FILE):
            try:
                os.remove(PUBLIC_URL_FILE)
            except Exception:
                pass
        return None

    log(f"Starting Cloudflare tunnel using {cf_path}...")
    creation_flags = 0
    if os.name == 'nt':
        creation_flags = 0x08000000 | 0x00000008 | 0x00000200

    env = os.environ.copy()
    # Check if direct DNS to Cloudflare API works
    needs_proxy = False
    try:
        socket.gethostbyname("api.trycloudflare.com")
    except Exception:
        needs_proxy = True

    if needs_proxy:
        try:
            from scripts.tunnel_service import start_socks_proxy
            socks_port = start_socks_proxy()
            if socks_port:
                proxy_url = f"socks5://127.0.0.1:{socks_port}"
                env['ALL_PROXY'] = proxy_url
                env['all_proxy'] = proxy_url
                log(f"Configured SOCKS5 DNS proxy for cloudflared: {proxy_url}")
        except Exception:
            pass

    tunnel_log_path = os.path.join(PROJECT_DIR, 'tunnel_service.log')
    try:
        tunnel_log_file = open(tunnel_log_path, 'a', encoding='utf-8')
    except Exception:
        tunnel_log_file = subprocess.DEVNULL

    try:
        log_start_pos = 0
        if os.path.exists(tunnel_log_path):
            log_start_pos = os.path.getsize(tunnel_log_path)

        proc = subprocess.Popen(
            [cf_path, "tunnel", "--url", "http://localhost:5000"],
            cwd=PROJECT_DIR,
            env=env,
            stderr=tunnel_log_file,
            stdout=subprocess.DEVNULL,
            creationflags=creation_flags
        )
        with open(TUNNEL_PID_FILE, 'w', encoding='utf-8') as f:
            f.write(str(proc.pid))

        # Tail tunnel log to capture public URL
        url_pattern = re.compile(r'https://([a-zA-Z0-9-]+)\.trycloudflare\.com')
        extracted_url = None
        t0 = time.time()

        while time.time() - t0 < 12.0:
            if os.path.exists(tunnel_log_path):
                with open(tunnel_log_path, 'r', encoding='utf-8', errors='ignore') as rf:
                    rf.seek(log_start_pos)
                    chunk = rf.read()
                    if "lookup api.trycloudflare.com: no such host" in chunk or "failed to request quick Tunnel" in chunk:
                        log("Tunnel notice: Quick tunnel DNS failed.")
                        break
                    m = url_pattern.search(chunk)
                    if m and m.group(1).lower() != 'api':
                        extracted_url = m.group(0).strip()
                        break
            if proc.poll() is not None:
                break
            time.sleep(0.3)

        if not extracted_url:
            log("Standard quick tunnel request blocked by ISP DNS. Attempting direct Cloudflare edge connection...")
            qt = request_quick_tunnel_direct()
            if qt and qt.get('hostname'):
                tunnel_id = qt['id']
                hostname = qt['hostname']
                extracted_url = f"https://{hostname}"
                cred_file = os.path.join(PROJECT_DIR, '.tunnel_cred.json')
                with open(cred_file, 'w', encoding='utf-8') as f:
                    import json
                    json.dump({
                        'AccountTag': qt.get('account_tag'),
                        'TunnelID': tunnel_id,
                        'TunnelName': qt.get('name'),
                        'TunnelSecret': qt.get('secret')
                    }, f)
                
                # Kill previous failed proc if any
                try:
                    proc.terminate()
                except Exception:
                    pass

                proc = subprocess.Popen(
                    [cf_path, "tunnel", "--cred-file", cred_file, "run", "--url", "http://localhost:5000", tunnel_id],
                    cwd=PROJECT_DIR,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creation_flags
                )
                with open(TUNNEL_PID_FILE, 'w', encoding='utf-8') as f:
                    f.write(str(proc.pid))
                log(f"Direct Cloudflare Edge Tunnel Established: {extracted_url}")

        if extracted_url:
            log(f"Cloudflare Tunnel Public URL: {extracted_url}")
            with open(PUBLIC_URL_FILE, 'w', encoding='utf-8') as f:
                f.write(extracted_url)
            return proc
        else:
            log("Cloudflare tunnel could not assign public URL. Falling back to LAN address.")
            if os.path.exists(PUBLIC_URL_FILE):
                try:
                    os.remove(PUBLIC_URL_FILE)
                except Exception:
                    pass
            return proc

    except Exception as e:
        log(f"Error starting Cloudflare tunnel: {e}")
        return None


def open_browser_app_mode(url="http://localhost:5000"):
    # Look for Edge or Chrome
    browser_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    ]
    target_browser = None
    for b in browser_candidates:
        if os.path.isfile(b):
            target_browser = b
            break

    if target_browser:
        log(f"Opening app window via {os.path.basename(target_browser)} (--app={url})...")
        try:
            subprocess.Popen([target_browser, f"--app={url}"])
            return
        except Exception as e:
            log(f"Error launching {target_browser}: {e}")

    # Fallback to standard web browser
    log(f"Opening default browser to {url}...")
    import webbrowser
    webbrowser.open(url)


def main():
    log("=== Food Man Desktop Launcher Starting ===")
    
    # 1. Start Waitress (if not already running)
    start_waitress()

    # 2. Start Cloudflare Tunnel (if available) & write .public_url
    start_tunnel()

    # 3. Ensure health check passes
    if wait_for_health(timeout_seconds=5.0):
        log("Health check verified: http://localhost:5000/health (200 OK)")
    else:
        log("Warning: /health check slow to respond. Opening browser anyway.")

    # 4. Open Edge or Chrome in app mode
    open_browser_app_mode("http://localhost:5000")
    log("=== Food Man Launcher Finished Launch Sequence ===")


if __name__ == "__main__":
    main()
