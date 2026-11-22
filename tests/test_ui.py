# Mira's voice window server: guard, and turning Claude Code's stream into steps for the page (fake Mira).
import json, os, subprocess, sys, tempfile, time, unittest, urllib.request, urllib.error
from pathlib import Path
SERVER = str(Path(__file__).resolve().parents[1] / "ui" / "server.py")
FAKE = r'''#!/usr/bin/env python3
import json, sys
print(json.dumps({"_args": sys.argv[1:]}), flush=True)
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "ls -la"}}]}}), flush=True)
print(json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "content": "file1 file2"}]}}), flush=True)
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "mcp__computer__mouse_click", "input": {"x": 10, "y": 20}}]}}), flush=True)
print(json.dumps({"type": "result", "result": "Done: 2 files.", "is_error": False}), flush=True)
open(sys.argv[0] + ".args", "a").write(json.dumps(sys.argv[1:]) + "\n")
'''
PORT = 3917


class UiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(); cls.fake = os.path.join(cls.dir, "mira"); open(cls.fake, "w").write(FAKE); os.chmod(cls.fake, 0o755)
        env = {**os.environ, "MIRA_BIN": cls.fake, "MIRA_UI_PORT": str(PORT), "MIRA_WORKDIR": cls.dir, "MIRA_HOME": cls.dir}
        cls.p = subprocess.Popen([sys.executable, SERVER], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try: urllib.request.urlopen(f"http://localhost:{PORT}/api/status", timeout=1); break
            except Exception: time.sleep(0.1)

    @classmethod
    def tearDownClass(cls): cls.p.terminate()

    def req(self, path, body=None, headers=None):
        h = {"content-type": "application/json", **(headers or {})}
        r = urllib.request.Request(f"http://localhost:{PORT}{path}", data=json.dumps(body).encode() if body is not None else None, headers=h)
        try:
            with urllib.request.urlopen(r, timeout=20) as x: return x.status, x.read().decode()
        except urllib.error.HTTPError as e: return e.code, e.read().decode()

    def events(self, text):
        code, raw = self.req("/api/ask", {"text": text})
        self.assertEqual(code, 200)
        return [json.loads(l[5:]) for l in raw.split("\n\n") if l.startswith("data:")]

    def test_page_and_status(self):
        self.assertIn("MIRA", self.req("/")[1]); self.assertIn('"busy": false', self.req("/api/status")[1])

    def test_steps_stream_to_the_page(self):
        ev = self.events("list my files")
        self.assertEqual(ev[0], {"kind": "step", "tool": "Bash", "text": "ls -la"})
        self.assertEqual(ev[1]["kind"], "result"); self.assertIn("file1", ev[1]["text"])
        self.assertEqual(ev[2], {"kind": "step", "tool": "mouse click", "text": "10, 20"})
        self.assertEqual(ev[-1], {"kind": "done", "text": "Done: 2 files.", "error": False})

    def test_follow_up_continues_the_conversation(self):
        self.req("/api/new", {}); self.events("one"); self.events("two")
        calls = [json.loads(l) for l in open(self.fake + ".args")][-2:]
        self.assertNotIn("--continue", calls[0]); self.assertIn("--continue", calls[1])
        self.assertEqual(calls[1][:3], ["code", "-p", "two"])

    def test_other_websites_are_refused(self):
        self.assertEqual(self.req("/api/ask", {"text": "x"}, {"origin": "https://evil.example"})[0], 403)
        r = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/ask", data=b"text=x", headers={"content-type": "text/plain"})
        with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(r, timeout=5)
        self.assertEqual(e.exception.code, 403)
        r = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/status", headers={"host": "evil.example"})
        with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(r, timeout=5)
        self.assertEqual(e.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
