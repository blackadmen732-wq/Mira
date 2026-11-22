# Mira's brain on a free Kaggle GPU (owner: Mark, Nov 22 2026).
# Runs an uncensored ("abliterated") model with Ollama, which speaks Claude Code's language (Anthropic Messages API),
# puts a password in front of it, and opens a private https link with a Cloudflare quick tunnel.
# On your computer: `mira connect <link> <password>`, then `mira`.
#
# Kaggle settings: Accelerator = GPU T4 x2, Internet = on. Free quota is about 30 GPU hours a week; a session
# can last up to 12 hours. To save that quota, the brain switches itself off after IDLE_MINUTES with no requests.
import hmac, http.client, json, os, re, secrets, shutil, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODELS = {                                                   # the two best uncensored models that fit 2 x T4 (30 GB)
    "code": "huihui_ai/qwen3-coder-abliterated:30b",         # coding agent (Qwen3 Coder, 30B, only 3B active: fast)
    "think": "huihui_ai/qwen3-abliterated:30b",              # general / reasoning
}
PULL = os.environ.get("MIRA_MODELS", "code,think").split(",")
IDLE_MINUTES = float(os.environ.get("MIRA_IDLE_MINUTES", "30"))
CONTEXT = os.environ.get("MIRA_CONTEXT", "32768")            # Claude Code's own instructions alone are ~20k tokens
OLLAMA = ("127.0.0.1", 11434)
PORT = 8000


class Gate(BaseHTTPRequestHandler):
    """Password check, then pass the request to Ollama and stream the answer back. Only /v1/ is reachable."""
    token = ""
    last = [time.time()]
    protocol_version = "HTTP/1.1"

    def log_message(self, *a): pass

    def _ok(self):
        key = self.headers.get("x-api-key") or ""
        auth = self.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "): key = key or auth[7:]
        return bool(self.token) and hmac.compare_digest(key.strip().encode(), self.token.encode())

    def _send(self, code, body):
        b = json.dumps(body).encode()
        self.send_response(code); self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _relay(self):
        if not self.path.startswith("/v1/"): return self._send(404, {"error": "not found"})
        if not self._ok(): return self._send(401, {"type": "error", "error": {"type": "authentication_error", "message": "wrong Mira password"}})
        Gate.last[0] = time.time()
        n = int(self.headers.get("content-length") or 0); body = self.rfile.read(n) if n else None
        up = http.client.HTTPConnection(*OLLAMA, timeout=900)
        try:
            up.request(self.command, self.path, body, {"content-type": self.headers.get("content-type", "application/json"),
                                                       "anthropic-version": self.headers.get("anthropic-version", "2023-06-01")})
            r = up.getresponse()
            self.send_response(r.status)
            for k in ("content-type", "cache-control"):
                if r.getheader(k): self.send_header(k, r.getheader(k))
            self.send_header("transfer-encoding", "chunked"); self.end_headers()
            while True:
                chunk = r.read1(65536)
                if not chunk: break
                self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk)); self.wfile.flush()
                Gate.last[0] = time.time()
            self.wfile.write(b"0\r\n\r\n")
        except (BrokenPipeError, ConnectionResetError): pass
        except Exception as e:
            try: self._send(502, {"type": "error", "error": {"type": "api_error", "message": f"brain error: {e}"}})
            except Exception: pass
        finally: up.close()

    do_GET = do_POST = _relay


def sh(cmd, **kw): return subprocess.run(cmd, shell=True, check=True, **kw)


def main():
    if shutil.which("ollama") is None:
        print("Installing Ollama...", flush=True)
        sh("(apt-get install -y -qq zstd >/dev/null 2>&1 || true) && curl -fsSL https://ollama.com/install.sh | sh >/dev/null")
    env = {**os.environ, "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_CONTEXT_LENGTH": CONTEXT, "OLLAMA_KEEP_ALIVE": "-1",
           "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_MODELS": "/tmp/ollama-models"}
    subprocess.Popen(["ollama", "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)
    for i, k in enumerate(PULL):
        name = MODELS.get(k.strip(), k.strip())
        if i and shutil.disk_usage("/tmp").free < 25e9:
            print(f"Not enough disk for a second model, skipping {name}.", flush=True); continue
        print(f"Downloading {name} (about 18 GB, a few minutes)...", flush=True)
        sh(f"ollama pull {name} >/dev/null", env=env)
    first = MODELS.get(PULL[0].strip(), PULL[0].strip())
    sh(f"curl -s http://127.0.0.1:11434/api/generate -d '{json.dumps({'model': first, 'prompt': 'hi', 'stream': False})}' >/dev/null", env=env)

    Gate.token = secrets.token_urlsafe(24)
    threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", PORT), Gate).serve_forever, daemon=True).start()
    if not os.path.exists("/tmp/cloudflared"):
        sh("curl -fsSL -o /tmp/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x /tmp/cloudflared")
    tun = subprocess.Popen(["/tmp/cloudflared", "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{PORT}"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url = None
    for line in tun.stdout:
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if m: url = m.group(0); break
    if not url: sys.exit("Could not open the tunnel.")
    threading.Thread(target=lambda: [None for _ in tun.stdout], daemon=True).start()
    print("\n" + "=" * 70)
    print("MIRA'S BRAIN IS ON. On your computer, run this once:\n")
    print(f"    mira connect {url} {Gate.token}\n")
    print("then start coding with:  mira        (or: mira think)")
    print(f"It switches off by itself after {IDLE_MINUTES:.0f} minutes with no requests.")
    print("=" * 70 + "\n", flush=True)
    Gate.last[0] = time.time()
    while time.time() - Gate.last[0] < IDLE_MINUTES * 60: time.sleep(20)
    print("No requests for a while: switching off to save your free GPU hours.", flush=True)
    tun.terminate()


if __name__ == "__main__":
    main()
