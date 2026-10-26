"""
Cloudflare Tunnel Background Service with SOCKS5 DNS Fallback
Ensures cloudflared can always reach api.trycloudflare.com regardless of ISP DNS restrictions.
"""
import os
import sys
import re
import time
import socket
import select
import struct
import threading
import subprocess

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PUBLIC_URL_FILE = os.path.join(PROJECT_DIR, '.public_url')
TUNNEL_PID_FILE = os.path.join(PROJECT_DIR, '.tunnel.pid')
LOG_FILE = os.path.join(PROJECT_DIR, 'tunnel_service.log')

def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass

def resolve_via_8888(hostname):
    """Resolve hostname using 8.8.8.8 over UDP."""
    try:
        parts = hostname.split('.')
        qname = b''.join([bytes([len(p)]) + p.encode('ascii') for p in parts]) + b'\x00'
        pkt = b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00' + qname + b'\x00\x01\x00\x01'
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.5)
        sock.sendto(pkt, ('8.8.8.8', 53))
        resp, _ = sock.recvfrom(1024)
        sock.close()
        
        pos = 12
        while resp[pos] != 0:
            pos += resp[pos] + 1
        pos += 5
        
        while pos < len(resp):
            if (resp[pos] & 0xc0) == 0xc0:
                pos += 2
            else:
                while resp[pos] != 0:
                    pos += resp[pos] + 1
                pos += 1
            rtype, rclass, ttl, rdlen = struct.unpack('>HHIH', resp[pos:pos+10])
            pos += 10
            if rtype == 1 and rdlen == 4:
                return socket.inet_ntoa(resp[pos:pos+4])
            pos += rdlen
    except Exception:
        pass
    try:
        return socket.gethostbyname(hostname)
    except Exception:
        return None

def handle_socks5(client):
    try:
        data = client.recv(257)
        if not data or data[0] != 5:
            client.close()
            return
        client.sendall(b'\x05\x00')
        
        data = client.recv(1024)
        if not data or len(data) < 7 or data[0] != 5 or data[1] != 1:
            client.close()
            return
            
        atyp = data[3]
        if atyp == 1:
            dest_ip = socket.inet_ntoa(data[4:8])
            dest_port = struct.unpack('>H', data[8:10])[0]
        elif atyp == 3:
            domain_len = data[4]
            dest_host = data[5:5+domain_len].decode('latin1')
            dest_port = struct.unpack('>H', data[5+domain_len:7+domain_len])[0]
            dest_ip = resolve_via_8888(dest_host)
            if not dest_ip:
                client.sendall(b'\x05\x04\x00\x01\x00\x00\x00\x00\x00\x00')
                client.close()
                return
        else:
            client.close()
            return
            
        dest_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dest_sock.settimeout(8.0)
        dest_sock.connect((dest_ip, dest_port))
        client.sendall(b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00')
        
        dest_sock.setblocking(False)
        client.setblocking(False)
        sockets = [client, dest_sock]
        running = True
        while running:
            r, _, _ = select.select(sockets, [], [], 30.0)
            if not r: break
            for s in r:
                other = dest_sock if s is client else client
                try:
                    chunk = s.recv(16384)
                    if not chunk:
                        running = False
                        break
                    other.sendall(chunk)
                except Exception:
                    running = False
                    break
        dest_sock.close()
    except Exception:
        pass
    finally:
        try: client.close()
        except Exception: pass

def start_socks_proxy():
    for port in [1080, 1081, 1082, 1083]:
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(('127.0.0.1', port))
            server.listen(20)
            def loop():
                while True:
                    c, _ = server.accept()
                    threading.Thread(target=handle_socks5, args=(c,), daemon=True).start()
            threading.Thread(target=loop, daemon=True).start()
            log(f"SOCKS5 DNS proxy listening on 127.0.0.1:{port}")
            return port
        except Exception:
            continue
    return None

def find_cloudflared():
    candidates = [
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
        r"C:\Program Files\cloudflared\cloudflared.exe",
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Links\cloudflared.exe")
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return "cloudflared"

def run_tunnel():
    log("=== Starting Cloudflare Tunnel Service ===")
    socks_port = start_socks_proxy()
    if not socks_port:
        log("ERROR: Could not bind SOCKS5 proxy port.")
        return

    cf_path = find_cloudflared()
    log(f"Using cloudflared executable: {cf_path}")

    env = os.environ.copy()
    proxy_url = f"socks5://127.0.0.1:{socks_port}"
    env['ALL_PROXY'] = proxy_url
    env['all_proxy'] = proxy_url

    cmd = [cf_path, "tunnel", "--url", "http://localhost:5000"]
    log(f"Launching cloudflared with {proxy_url}...")

    creation_flags = 0
    if os.name == 'nt':
        creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)

    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_DIR,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        creationflags=creation_flags
    )

    with open(TUNNEL_PID_FILE, 'w', encoding='utf-8') as f:
        f.write(str(proc.pid))

    url_pattern = re.compile(r'https://([a-zA-Z0-9-]+)\.trycloudflare\.com')
    extracted_url = None
    t0 = time.time()

    # Read output to capture the URL
    while time.time() - t0 < 20.0:
        line = proc.stderr.readline()
        if not line:
            if proc.poll() is not None:
                log(f"Process terminated prematurely with exit code {proc.poll()}")
                break
            time.sleep(0.1)
            continue

        log(f"[CF] {line.strip()}")
        m = url_pattern.search(line)
        if m and m.group(1).lower() != 'api':
            extracted_url = m.group(0).strip()
            log(f">>> PUBLIC TUNNEL URL ESTABLISHED: {extracted_url}")
            with open(PUBLIC_URL_FILE, 'w', encoding='utf-8') as f:
                f.write(extracted_url)
            break

    if not extracted_url:
        log("Failed to capture public URL from cloudflared.")
        return

    # Keep process running and streaming logs
    while proc.poll() is None:
        line = proc.stderr.readline()
        if line:
            # Filter verbose metrics
            if "ERR" in line or "WRN" in line or "Registered tunnel" in line:
                log(f"[CF] {line.strip()}")
        time.sleep(0.1)

    log(f"Cloudflared exited with code {proc.poll()}")

if __name__ == '__main__':
    run_tunnel()
