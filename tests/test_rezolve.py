"""Rezolve Labs client resilience, against a local stand-in server: python3 -m unittest discover tests

No real key or network is used. The stand-in answers each search with the next scripted reply.
"""
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

from rezolve import CircuitBreaker, RezolveClient, RezolveError  # noqa: E402

HIT = {"data": {"results": [{"id": "P0086"}, {"metadata": {"product_id": "P0001"}}]}}


class Stub(BaseHTTPRequestHandler):
    script, seen = [], []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Stub.seen.append((self.path, self.headers.get("X-API-KEY"), body))
        status, reply = Stub.script.pop(0) if Stub.script else (200, HIT)
        data = json.dumps(reply).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        if status == 429:
            self.send_header("Retry-After", "0")
        self.end_headers()
        self.wfile.write(data)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Resilience(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        Stub.script, Stub.seen = [], []
        self.clock, self.slept = Clock(), []
        self.client = RezolveClient("test-key", "kb1", self.base, timeout=2, sleep=self.slept.append,
                                    breaker=CircuitBreaker(threshold=3, cooldown=30, clock=self.clock))

    def test_search_request_and_result_parsing(self):
        ids = self.client.search("navy sneakers", {"colour": "navy", "max_price": 4500, "size": None}, limit=3)
        self.assertEqual(ids, ["P0086", "P0001"])
        path, key, body = Stub.seen[0]
        self.assertEqual(path, "/product-discovery/search")
        self.assertEqual(key, "test-key")
        self.assertEqual(body["filters"], {"colour": "navy", "price_lte": 4500})   # our names -> Rezolve's

    def test_transient_errors_are_retried(self):
        Stub.script = [(503, {}), (429, {})]
        self.assertEqual(self.client.search("x"), ["P0086", "P0001"])
        self.assertEqual(self.client.calls, 3)
        self.assertEqual(len(self.slept), 2)
        self.assertLess(self.slept[0], self.slept[1] * 2)     # backoff grows

    def test_client_errors_fail_at_once(self):
        Stub.script = [(401, {"error": "bad key"})]
        with self.assertRaises(RezolveError) as e:
            self.client.search("x")
        self.assertEqual(e.exception.status, 401)
        self.assertEqual(self.client.calls, 1)
        self.assertFalse(self.client.breaker.open)          # the service is up; the key is wrong

    def test_circuit_opens_after_repeated_failures_and_recovers(self):
        Stub.script = [(500, {})] * 9
        for _ in range(3):
            with self.assertRaises(RezolveError):
                self.client.search("x")
        self.assertTrue(self.client.breaker.open)
        calls = self.client.calls
        with self.assertRaises(RezolveError):
            self.client.search("x")                          # skipped: no call, no credit
        self.assertEqual(self.client.calls, calls)
        self.assertEqual(self.client.stats()["skipped"], 1)

        Stub.script = []                                      # the service is back
        self.clock.t = 31                                     # cooldown over: one trial call
        self.assertEqual(self.client.search("x"), ["P0086", "P0001"])
        self.assertFalse(self.client.breaker.open)

    def test_agent_counts_every_attempt_and_survives_outage(self):
        """The agent records each HTTP attempt as a search, and an outage only loses the fallback."""
        from agent import Agent

        class Tools:
            searches = 0

            def search(self, query="", filters=None, k=10):
                return []

            def record_search(self, n=1):
                Tools.searches += n

        Stub.script = [(503, {})] * 3 + [(503, {})] * 3       # first search and its meaning-only retry
        agent = Agent(Tools(), rezolve=self.client)
        agent.start("r1")
        for w in "help me find racing flats".split():
            agent.observe(w)
        agent.finish()
        self.assertEqual(Tools.searches, self.client.calls)
        self.assertEqual(agent.fallback_log[0][2], None)


if __name__ == "__main__":
    unittest.main()
