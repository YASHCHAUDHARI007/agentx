"""Service tests: python3 -m unittest discover tests"""
import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

import app  # noqa: E402


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = app.make_server(port=0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def session(self, shop="fashion", mode="auto"):
        status, s = self.call("POST", "/v1/sessions", {"shop": shop, "mode": mode})
        self.assertEqual(status, 200)
        return s["session"]

    def test_health_and_shops(self):
        self.assertEqual(self.call("GET", "/health")[1]["shops"], ["electronics", "fashion"])
        shops = {s["name"]: s for s in self.call("GET", "/v1/shops")[1]["shops"]}
        self.assertEqual(shops["electronics"]["roles"]["category"], "type")

    def test_words_commit_early_and_finish(self):
        sid = self.session()
        words = "hi, I want Loomsy navy blue casual sneakers within forty five hundred, size 7 if you have it".split()
        _, out = self.call("POST", f"/v1/sessions/{sid}/words", {"words": words})
        commits = [s for s in out["steps"] if s.get("commit")]
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0]["commit"]["id"], "P0086")
        self.assertLess(commits[0]["n"], len(words))           # before the request ended
        _, fin = self.call("POST", f"/v1/sessions/{sid}/finish")
        self.assertEqual(fin["final"]["id"], "P0086")
        self.assertFalse(fin["changed_after_commit"])
        self.assertEqual(fin["searches"], 1)
        self.assertEqual(self.call("GET", f"/v1/sessions/{sid}")[0], 404)   # finished sessions are gone

    def test_transcript_interim_word_is_not_read(self):
        sid = self.session("electronics")
        _, out = self.call("POST", f"/v1/sessions/{sid}/transcript", {"text": "show me a Nexo blue four", "final": False})
        self.assertNotIn("four", [s["word"] for s in out["steps"]])

    def test_transcript_revision_rereads(self):
        sid = self.session("electronics")
        self.call("POST", f"/v1/sessions/{sid}/transcript", {"text": "Nexo green mobile with 256 gigs", "final": False})
        _, out = self.call("POST", f"/v1/sessions/{sid}/transcript",
                           {"text": "Nexo blue mobile with 256 gigs under 60k please", "final": True})
        self.assertTrue(out["revised"])
        self.assertEqual(out["steps"][-1]["filters"]["color"], "blue")
        _, fin = self.call("POST", f"/v1/sessions/{sid}/finish")
        self.assertEqual(fin["final"]["attributes"]["color"], "blue")

    def test_errors(self):
        self.assertEqual(self.call("POST", "/v1/sessions", {"shop": "nope"})[0], 404)
        self.assertEqual(self.call("POST", "/v1/sessions", {"mode": "reckless"})[0], 400)
        sid = self.session()
        self.assertEqual(self.call("POST", f"/v1/sessions/{sid}/words", {"words": "not a list"})[0], 400)
        self.assertEqual(self.call("POST", "/v1/sessions/missing/words", {"words": []})[0], 404)
        self.assertEqual(self.call("GET", "/static/../app.py")[0], 404)

    def test_metrics(self):
        m = self.call("GET", "/metrics")[1]
        self.assertIn("word_ms_p95", m)


if __name__ == "__main__":
    unittest.main()
