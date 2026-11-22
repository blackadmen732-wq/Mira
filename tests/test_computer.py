# Mira's eyes and hands (computer/computer_mcp.py), with fake xdotool/scrot/tesseract so it runs anywhere.
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
SERVER = str(Path(__file__).resolve().parents[1] / "computer" / "computer_mcp.py")
PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

FAKES = {
    "xdotool": 'echo "$@" >> "$LOG"; case "$1" in getmouselocation) echo "x:$MOUSE_X y:$MOUSE_Y screen:0 window:1";; '
               'search) echo 111;; getwindowname) echo "Terminal";; esac',
    "scrot": 'echo "$PNG" | base64 -d > "$2"',
    "identify": 'echo 2560',
    "convert": 'true',
    "tesseract": 'printf "level\\tpage_num\\tblock_num\\tpar_num\\tline_num\\tword_num\\tleft\\ttop\\twidth\\theight\\tconf\\ttext\\n'
                 '5\\t1\\t1\\t1\\t1\\t1\\t100\\t200\\t40\\t20\\t95\\tSave\\n5\\t1\\t1\\t1\\t1\\t2\\t150\\t200\\t40\\t20\\t96\\tFile\\n"',
}


class ComputerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(); self.log = os.path.join(self.dir, "log")
        for name, body in FAKES.items():
            p = os.path.join(self.dir, name); open(p, "w").write("#!/bin/sh\n" + body + "\n"); os.chmod(p, 0o755)
        self.env = {**os.environ, "PATH": self.dir + ":" + os.environ["PATH"], "LOG": self.log, "PNG": PNG, "MOUSE_X": "500", "MOUSE_Y": "500"}

    def rpc(self, *msgs, **env):
        inp = "".join(json.dumps({"jsonrpc": "2.0", **m}) + "\n" for m in msgs)
        out = subprocess.run([sys.executable, SERVER], input=inp, capture_output=True, text=True, env={**self.env, **env}, timeout=30).stdout
        return [json.loads(l) for l in out.splitlines()]

    def calls(self): return open(self.log).read() if os.path.exists(self.log) else ""

    def test_handshake_and_tool_list(self):
        init, lst = self.rpc({"id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                             {"method": "notifications/initialized"}, {"id": 2, "method": "tools/list"})
        self.assertEqual(init["result"]["serverInfo"]["name"], "mira-computer")
        names = {t["name"] for t in lst["result"]["tools"]}
        self.assertTrue({"screen_look", "mouse_click", "type_text", "press_key", "scroll", "open_url"} <= names)

    def test_look_gives_picture_and_words_then_click_lands_on_the_real_pixel(self):
        look, click = self.rpc({"id": 1, "method": "tools/call", "params": {"name": "screen_look", "arguments": {}}},
                               {"id": 2, "method": "tools/call", "params": {"name": "mouse_click", "arguments": {"x": 145, "y": 210}}})
        parts = look["result"]["content"]
        self.assertEqual(parts[1]["type"], "image"); self.assertIn("Save File", parts[0]["text"]); self.assertIn("(145,210)", parts[0]["text"])
        self.assertFalse(click["result"].get("isError"))
        self.assertIn("mousemove 290 420 click 1", self.calls())          # 2560 px screen shown at 1280: x2

    def test_keys_and_typing(self):
        self.rpc({"id": 1, "method": "tools/call", "params": {"name": "press_key", "arguments": {"keys": "ctrl+shift+t"}}},
                 {"id": 2, "method": "tools/call", "params": {"name": "type_text", "arguments": {"text": "ls -la"}}})
        log = self.calls(); self.assertIn("key -- ctrl+shift+t", log); self.assertIn("type --delay 8 -- ls -la", log)

    def test_mouse_in_top_left_corner_stops_everything(self):
        r, = self.rpc({"id": 1, "method": "tools/call", "params": {"name": "mouse_click", "arguments": {"x": 10, "y": 10}}}, MOUSE_X="0", MOUSE_Y="2")
        self.assertTrue(r["result"]["isError"]); self.assertIn("emergency stop", r["result"]["content"][0]["text"])
        self.assertNotIn("click", self.calls().replace("getmouselocation", ""))

    def test_only_web_links_open(self):
        r, = self.rpc({"id": 1, "method": "tools/call", "params": {"name": "open_url", "arguments": {"url": "file:///etc/passwd"}}})
        self.assertTrue(r["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
