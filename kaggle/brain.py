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
        # Always read the whole body first: the tunnel reuses connections, and an unread body would be taken as the
        # start of the next request (found on the first live run: '{}POST' -> 501).
        n = int(self.headers.get("content-length") or 0); body = self.rfile.read(n) if n else None
        if not self.path.startswith("/v1/"): return self._send(404, {"error": "not found"})
        if not self._ok(): return self._send(401, {"type": "error", "error": {"type": "authentication_error", "message": "wrong Mira password"}})
        Gate.last[0] = time.time()
        if self.path == "/v1/audio/speech": return self._speech(body)
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

    def _speech(self, body):
        """Mira's voice: Kokoro (free, Apache-2.0) on the same GPU. {"input": text, "voice": "af_heart", "speed": 1} -> WAV."""
        if VOICE["pipe"] is None: return self._send(503, {"error": "voice not ready: " + VOICE["status"]})
        try: j = json.loads(body or b"{}")
        except ValueError: return self._send(400, {"error": "bad json"})
        text = str(j.get("input", "")).strip()[:2000]
        if not text: return self._send(400, {"error": "no text"})
        wav = VOICE["say"](text, str(j.get("voice") or VOICE_NAME), float(j.get("speed") or 1.0))
        self.send_response(200); self.send_header("content-type", "audio/wav"); self.send_header("content-length", str(len(wav)))
        self.end_headers(); self.wfile.write(wav)

    do_GET = do_POST = _relay


VOICE_NAME = os.environ.get("MIRA_VOICE", "af_heart")       # Kokoro's warm, sweet American female voice (its best-rated)
VOICE = {"pipe": None, "status": "loading", "say": None}


def load_voice():
    """Loads in the background, so the brain is usable even if the voice fails."""
    try:
        subprocess.run("(apt-get install -y -qq espeak-ng >/dev/null 2>&1 || true) && pip install -q 'kokoro>=0.9' soundfile >/dev/null 2>&1",
                       shell=True, check=True)
        import io, threading as th
        import numpy as np, soundfile as sf
        from kokoro import KPipeline
        pipe, lock = KPipeline(lang_code="a"), th.Lock()
        def say(text, voice, speed):
            with lock: parts = [a for _, _, a in pipe(text, voice=voice, speed=max(0.6, min(speed, 1.6))) if a is not None]
            audio = np.concatenate([np.asarray(p, dtype=np.float32) for p in parts]) if parts else np.zeros(2400, np.float32)
            buf = io.BytesIO(); sf.write(buf, audio, 24000, format="WAV"); return buf.getvalue()
        say("Hi.", VOICE_NAME, 1.0)                                # warm up (downloads the voice once)
        VOICE.update(pipe=pipe, say=say, status="ready"); print("Mira's voice is ready (Kokoro, " + VOICE_NAME + ").", flush=True)
    except Exception as e:
        VOICE["status"] = f"failed: {e}"; print(f"Mira's voice could not load ({e}); the page will use Chrome's voice.", flush=True)


def sh(cmd, **kw): return subprocess.run(cmd, shell=True, check=True, **kw)


def main():
    if shutil.which("ollama") is None:
        print("Installing Ollama...", flush=True)
        # One download stream from GitHub crawls on Kaggle (~12% in 15 minutes), so fetch with 16 parallel streams.
        sh("apt-get install -y -qq zstd aria2 >/dev/null 2>&1 || pip install -q aria2 >/dev/null 2>&1 || true")
        url = "https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tar.zst"
        if shutil.which("aria2c"):
            sh(f"aria2c -q -x16 -s16 -k4M --file-allocation=none -d /tmp -o ollama.tar.zst {url} && "
               "tar --use-compress-program=unzstd -xf /tmp/ollama.tar.zst -C /usr/local && rm -f /tmp/ollama.tar.zst")
        else:
            sh("curl -fsSL https://ollama.com/install.sh | sh >/dev/null")
        print("Ollama installed.", flush=True)
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

    threading.Thread(target=load_voice, daemon=True).start()
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
