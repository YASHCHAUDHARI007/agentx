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
        cls.srv = app.make_server(port=0, keys="", rate=0)        # open, unlimited: the API itself
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

    def test_prometheus_metrics(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/metrics?format=prometheus") as r:
            self.assertTrue(r.headers["Content-Type"].startswith("text/plain"))
            text = r.read().decode()
        self.assertIn("# TYPE shelfsense_sessions_total counter", text)
        self.assertIn('shelfsense_http_responses_total{code="200"}', text)

    def test_openapi_lists_every_route(self):
        status, spec = self.call("GET", "/openapi.json")
        self.assertEqual(status, 200)
        self.assertEqual(spec["openapi"], "3.1.0")
        for path in ("/v1/sessions", "/v1/sessions/{id}/words", "/v1/sessions/{id}/transcript",
                     "/v1/sessions/{id}/finish", "/metrics", "/health"):
            self.assertIn(path, spec["paths"])

    def test_request_id_and_security_headers(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/health", headers={"X-Request-Id": "abc-123"})
        with urllib.request.urlopen(req) as r:
            self.assertEqual(r.headers["X-Request-Id"], "abc-123")
            self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/") as r:
            self.assertIn("frame-ancestors 'none'", r.headers["Content-Security-Policy"])

    def test_static_files_stay_inside_the_root(self):
        for path in ("/static/../app.py", "/..%2fapp.py", "/%2e%2e/server/app.py", "/.env", "/_next/%2e%2e/%2e%2e/.env"):
            with self.subTest(path):
                req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
                with self.assertRaises(urllib.error.HTTPError) as e:
                    urllib.request.urlopen(req)
                self.assertEqual(e.exception.code, 404)

    def test_front_end_assets(self):
        root = app.web_root()
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/") as r:
            self.assertIn(b"ShelfSense", r.read())
        assets = sorted((root / "_next" / "static").rglob("*.js")) if (root / "_next").is_dir() else []
        if assets:                                   # only once web/ is built
            rel = assets[0].relative_to(root).as_posix()
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/{rel}") as r:
                self.assertIn("immutable", r.headers["Cache-Control"])
                self.assertTrue(r.headers["Content-Type"].startswith("text/javascript"))

    def test_cors_only_for_listed_origins(self):
        app.CORS_ORIGINS = {"http://localhost:3000"}
        try:
            def preflight(origin):
                req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/sessions", method="OPTIONS",
                                             headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
                try:
                    with urllib.request.urlopen(req) as r:
                        return r.status, r.headers
                except urllib.error.HTTPError as e:
                    return e.code, e.headers
            status, headers = preflight("http://localhost:3000")
            self.assertEqual(status, 204)
            self.assertEqual(headers["Access-Control-Allow-Origin"], "http://localhost:3000")
            self.assertIn("X-API-Key", headers["Access-Control-Allow-Headers"])
            self.assertEqual(preflight("https://evil.example")[0], 403)
        finally:
            app.CORS_ORIGINS = set()

    def test_word_cap_is_reported(self):
        sid = self.session()
        _, out = self.call("POST", f"/v1/sessions/{sid}/words", {"words": ["la"] * (app.MAX_WORDS + 5)})
        self.assertEqual(out["state"]["words"], app.MAX_WORDS)
        self.assertTrue(out["state"]["truncated"])


class Protected(unittest.TestCase):
    """The same service with SHELFSENSE_API_KEYS and SHELFSENSE_RATE set."""

    @classmethod
    def setUpClass(cls):
        cls.srv = app.make_server(port=0, keys="k-one,k-two", rate=2)     # burst of 4
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        app.KEYS, app.LIMITER = app.ApiKeys(""), app.RateLimiter(0)

    def get(self, path, **headers):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers=headers)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.headers
        except urllib.error.HTTPError as e:
            return e.code, e.headers

    def test_keys(self):
        self.assertEqual(self.get("/health")[0], 200)               # probes need no key
        self.assertEqual(self.get("/")[0], 200)                     # nor does the page
        self.assertEqual(self.get("/v1/shops")[0], 401)
        self.assertEqual(self.get("/metrics")[0], 401)
        self.assertEqual(self.get("/v1/shops", **{"X-API-Key": "wrong"})[0], 401)
        self.assertEqual(self.get("/v1/shops", **{"X-API-Key": "k-one"})[0], 200)
        self.assertEqual(self.get("/v1/shops", Authorization="Bearer k-two")[0], 200)

    def test_rate_limit_per_key(self):
        codes = [self.get("/v1/shops", Authorization="Bearer k-two")[0] for _ in range(8)]
        self.assertIn(429, codes)
        self.assertEqual(codes[0], 200)
        status, headers = self.get("/v1/shops", Authorization="Bearer k-two")
        if status == 429:
            self.assertGreaterEqual(int(headers["Retry-After"]), 1)
        self.assertEqual(self.get("/v1/shops", **{"X-API-Key": "k-one"})[0], 200)   # other keys unaffected

    def test_session_cap(self):
        old, app.MAX_SESSIONS = app.MAX_SESSIONS, 0
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/sessions", data=b"{}", method="POST",
                                         headers={"X-API-Key": "k-one", "Content-Type": "application/json"})
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(req)
            self.assertEqual(e.exception.code, 503)
        finally:
            app.MAX_SESSIONS = old


if __name__ == "__main__":
    unittest.main()
