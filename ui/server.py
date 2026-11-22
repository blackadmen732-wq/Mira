#!/usr/bin/env python3
# Mira's voice window (owner's request, Nov 22 2026): a page you talk to instead of the terminal.
# `mira ui` starts this on http://localhost:3005 and opens it. The page listens (Chrome's speech recognition), sends
# what you said here, and this runs Mira (Claude Code with the uncensored brain + terminal + screen tools) in the
# background, streaming every step back to the page, which shows them and speaks the answer.
# Python standard library only. Listens on 127.0.0.1 only, and only answers pages opened from this computer.
import json, os, signal, subprocess, sys, threading, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(os.environ.get("MIRA_UI_PORT", "3005"))
HERE = Path(__file__).resolve().parent
MIRA = os.environ.get("MIRA_BIN") or str(Path.home() / ".local/bin/mira")
WORK = Path(os.environ.get("MIRA_WORKDIR", str(Path.home()))).expanduser()
TOOLS = "Bash Read Write Edit Glob Grep WebFetch WebSearch TodoWrite mcp__computer"
LEAN_PROMPT = ("You are Mira, Mark's own assistant on his Linux computer (a Chromebook's Linux side). You have his terminal (Bash), "
               "his files (Read/Write/Edit/Glob/Grep) and, through the computer tools, his screen, mouse and keyboard: call screen_look "
               "before clicking. Do what he asks directly, step by step, and check the result. Your answer is spoken aloud: reply in "
               "1-3 short, warm sentences, no markdown, no code blocks unless he asks for code.")
STATE = {"proc": None, "started": False}
LOCK = threading.Lock()


def allowed(h):
    """Same guard as Jarvis: right Host (no DNS rebinding), no foreign Origin, JSON posts only."""
    host = (h.headers.get("host") or "").lower()
    if host not in (f"localhost:{PORT}", f"127.0.0.1:{PORT}", f"[::1]:{PORT}"): return False
    origin = h.headers.get("origin")
    if origin is not None and origin not in (f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"): return False
    if h.command == "POST" and not (h.headers.get("content-type") or "").startswith("application/json"): return False
    return True


def brain():
    """The brain's link + password, saved by `mira connect`."""
    env, out = Path(os.environ.get("MIRA_HOME", str(Path.home() / ".mira"))) / "brain.env", {}
    try:
        for line in env.read_text().splitlines():
            k, _, v = line.partition("="); out[k.strip()] = v.strip().strip("'\"")
    except OSError: pass
    return out.get("MIRA_URL"), out.get("MIRA_TOKEN")


def steps(line):
    """One line of Claude Code's stream-json -> simple events for the page."""
    try: ev = json.loads(line)
    except ValueError: return []
    out = []
    if ev.get("type") == "assistant":
        for b in (ev.get("message") or {}).get("content") or []:
            if b.get("type") == "text" and b.get("text", "").strip(): out.append({"kind": "say", "text": b["text"]})
            elif b.get("type") == "tool_use":
                name, inp = b.get("name", ""), b.get("input") or {}
                what = inp.get("command") or inp.get("file_path") or inp.get("url") or inp.get("text") or inp.get("keys") or inp.get("pattern") or ""
                if name.startswith("mcp__computer__"): name = name.split("__")[-1].replace("_", " ")
                if "x" in inp and "y" in inp: what = f"{inp['x']}, {inp['y']}"
                out.append({"kind": "step", "tool": name, "text": str(what)[:300]})
    elif ev.get("type") == "user":
        for b in (ev.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                c = b.get("content"); c = " ".join(x.get("text", "") for x in c if isinstance(x, dict)) if isinstance(c, list) else str(c or "")
                out.append({"kind": "result", "error": bool(b.get("is_error")), "text": c.strip()[:400]})
    elif ev.get("type") == "result":
        out.append({"kind": "done", "text": ev.get("result") or "", "error": bool(ev.get("is_error"))})
    return out


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _json(self, code, body):
        b = json.dumps(body).encode(); self.send_response(code)
        self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if not allowed(self): return self._json(403, {"error": "forbidden"})
        if self.path in ("/", "/index.html"):
            b = (HERE / "index.html").read_bytes(); self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8"); self.send_header("content-length", str(len(b))); self.end_headers(); self.wfile.write(b)
        elif self.path == "/api/status":
            env = Path(os.environ.get("MIRA_HOME", str(Path.home() / ".mira"))) / "brain.env"
            self._json(200, {"brain": env.exists(), "busy": STATE["proc"] is not None, "workdir": str(WORK)})
        else: self._json(404, {"error": "not found"})

    def do_POST(self):
        if not allowed(self): return self._json(403, {"error": "forbidden"})
        try: body = json.loads(self.rfile.read(int(self.headers.get("content-length") or 0)) or b"{}")
        except ValueError: return self._json(400, {"error": "bad json"})
        if self.path == "/api/stop":
            p = STATE["proc"]
            if p: os.killpg(p.pid, signal.SIGTERM)
            return self._json(200, {"stopped": bool(p)})
        if self.path == "/api/new": STATE["started"] = False; return self._json(200, {"ok": True})
        if self.path == "/api/tts":                                         # Mira's own voice (Kokoro on the brain's GPU)
            url, tok = brain()
            if not url: return self._json(503, {"error": "no brain linked"})
            req = urllib.request.Request(url + "/v1/audio/speech", data=json.dumps({"input": str(body.get("text", ""))[:2000],
                                         "voice": body.get("voice") or "af_heart", "speed": body.get("speed") or 1.0}).encode(),
                                         headers={"content-type": "application/json", "x-api-key": tok})
            try:
                with urllib.request.urlopen(req, timeout=60) as r: wav = r.read()
            except (urllib.error.URLError, OSError) as e: return self._json(502, {"error": f"voice unavailable: {e}"})
            self.send_response(200); self.send_header("content-type", "audio/wav"); self.send_header("content-length", str(len(wav)))
            self.end_headers(); self.wfile.write(wav); return
        if self.path != "/api/ask": return self._json(404, {"error": "not found"})
        text, mode = str(body.get("text", "")).strip()[:8000], "think" if body.get("mode") == "think" else "code"
        if not text: return self._json(400, {"error": "say something"})
        with LOCK:
            if STATE["proc"]: return self._json(409, {"error": "Mira is still working. Say stop first."})
            # LEAN: Claude Code's full instructions + every tool are ~30k tokens, which the free GPU needs ~70 s to read each
            # new conversation. The voice window sends a short prompt and only the tools it needs (~4k tokens, ~7x less).
            args = [MIRA, mode, "-p", text, "--output-format", "stream-json", "--verbose", "--allowedTools", TOOLS,
                    "--tools", "Bash,Read,Write,Edit,Glob,Grep", "--strict-mcp-config", "--system-prompt", LEAN_PROMPT]
            if STATE["started"]: args.append("--continue")                 # same conversation
            WORK.mkdir(parents=True, exist_ok=True)
            p = subprocess.Popen(args, cwd=str(WORK), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            STATE["proc"], STATE["started"] = p, True
        self.send_response(200); self.send_header("content-type", "text/event-stream"); self.send_header("cache-control", "no-cache"); self.end_headers()
        def send(ev):
            try: self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode()); self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError): pass
        done = False
        try:
            for line in p.stdout:
                for ev in steps(line):
                    done = done or ev["kind"] == "done"; send(ev)
            p.wait()
            if not done:
                err = (p.stderr.read() or "").strip().splitlines()
                send({"kind": "done", "error": True, "text": (err[-1] if err else "Mira stopped.")[:400]})
        finally:
            STATE["proc"] = None


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"Mira's voice window: http://localhost:{PORT}  (Ctrl+C to close)", flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: pass


if __name__ == "__main__":
    main()
