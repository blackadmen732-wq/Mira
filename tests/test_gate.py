# The password gate in front of Mira's brain: wrong password refused, right one streams Ollama's answer through.
import json, sys, threading, time, unittest, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kaggle"))
import brain


class FakeOllama(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        self.send_response(200); self.send_header("content-type", "text/event-stream"); self.end_headers()
        for w in ("hello ", "from ", body["model"]):
            self.wfile.write(f"data: {json.dumps({'text': w})}\n\n".encode()); self.wfile.flush(); time.sleep(0.05)
    do_GET = do_POST


def serve(handler):
    s = ThreadingHTTPServer(("127.0.0.1", 0), handler); threading.Thread(target=s.serve_forever, daemon=True).start(); return s


class GateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.up = serve(FakeOllama); brain.OLLAMA = ("127.0.0.1", cls.up.server_address[1])
        brain.Gate.token = "s3cret-password-123"; cls.gate = serve(brain.Gate)
        cls.url = f"http://127.0.0.1:{cls.gate.server_address[1]}"

    def call(self, path, headers):
        req = urllib.request.Request(self.url + path, data=json.dumps({"model": "m1"}).encode(),
                                     headers={"content-type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=10) as r: return r.status, r.read().decode()
        except urllib.error.HTTPError as e: return e.code, e.read().decode()

    def test_wrong_or_missing_password_is_refused(self):
        self.assertEqual(self.call("/v1/messages", {})[0], 401)
        self.assertEqual(self.call("/v1/messages", {"x-api-key": "guess"})[0], 401)

    def test_right_password_streams_the_answer(self):
        for h in ({"x-api-key": "s3cret-password-123"}, {"authorization": "Bearer s3cret-password-123"}):
            code, text = self.call("/v1/messages", h)
            self.assertEqual(code, 200); self.assertIn("hello", text); self.assertIn("m1", text)

    def test_only_the_api_is_reachable(self):
        self.assertEqual(self.call("/api/pull", {"x-api-key": "s3cret-password-123"})[0], 404)

    def test_refused_request_does_not_spoil_the_next_one_on_the_same_connection(self):
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.gate.server_address[1], timeout=10)
        c.request("POST", "/v1/messages", body=b'{"model": "x"}', headers={"content-type": "application/json"})
        r = c.getresponse(); r.read(); self.assertEqual(r.status, 401)
        c.request("POST", "/v1/messages", body=json.dumps({"model": "m2"}).encode(),
                  headers={"content-type": "application/json", "x-api-key": "s3cret-password-123"})
        r = c.getresponse(); self.assertEqual(r.status, 200); self.assertIn("m2", r.read().decode())

    def test_requests_keep_it_awake(self):
        brain.Gate.last[0] = 0; self.call("/v1/messages", {"x-api-key": "s3cret-password-123"})
        self.assertGreater(brain.Gate.last[0], time.time() - 5)


if __name__ == "__main__":
    unittest.main()
