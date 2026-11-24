"""ShelfSense streaming service: the agent behind an HTTP API, plus the live demo page.

    python3 server/app.py                         # http://localhost:8080, both demo shops
    python3 server/app.py --port 9000 --shop mystore=path/catalogue.csv:path/config.json

Standard library only. One process serves several shops; each shopper gets a session.

API (JSON in, JSON out):
  GET  /health                            liveness, loaded shops
  GET  /metrics                           request counts, commit rate, latency percentiles
  GET  /v1/shops                          shops and their detected profiles
  GET  /v1/shops/{shop}/samples?n=8       example requests to replay
  POST /v1/sessions                       {"shop": "fashion", "mode": "auto"} -> {"session": id}
  POST /v1/sessions/{id}/words            {"words": ["show", "me"]}       append words
  POST /v1/sessions/{id}/transcript       {"text": "show me navy", "final": false}
         the whole running speech-to-text transcript; words that changed are re-read
  POST /v1/sessions/{id}/finish           -> the final product
  DELETE /v1/sessions/{id}

Every word update returns the current reading: filters, how many products still fit, the
product card once the agent commits, and the time the agent took.
"""
import argparse
import json
import os
import random
import re
import secrets
import statistics
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

from agent import Agent  # noqa: E402
from catalogue import KIT_CATALOGUE, CatalogueSearch, Profile  # noqa: E402
from parser import Vocab  # noqa: E402
from policy import CommitPolicy  # noqa: E402
from rezolve import RezolveClient  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
DEFAULT_SHOPS = {
    "fashion": (ROOT / "starter_kit/ps1-anticipatory-commerce/catalogue.csv", None,
                ROOT / "starter_kit/ps1-anticipatory-commerce/dev.jsonl"),
    "electronics": (ROOT / "tests/catalogues/electronics/catalogue.csv",
                    ROOT / "tests/catalogues/electronics/config.json",
                    ROOT / "tests/catalogues/electronics/requests.jsonl"),
}
SESSION_TTL = 15 * 60
MODES = ("auto", "next", "speech", "safe", "instant")
MAX_WORDS = 200


# ---------------------------------------------------------------- shops

class Shop:
    def __init__(self, name, catalogue, config=None, samples=None):
        self.name = name
        self.profile = Profile.load(catalogue, config)
        self.vocab = Vocab(self.profile)
        self.search = CatalogueSearch(self.profile)
        self.by_id = {r[self.profile.id]: r for r in self.profile.rows}
        self.samples = []
        if samples and Path(samples).exists():
            self.samples = [json.loads(line)["text"] for line in open(samples, encoding="utf-8") if line.strip()]

    def card(self, pid):
        r = self.by_id.get(pid)
        if r is None:
            return None
        pr = self.profile
        return {"id": pid, "title": r[pr.title], "price": r[pr.price],
                "attributes": {s: r[s] for s in pr.slots if r.get(s)}}

    def info(self):
        pr = self.profile
        return {"name": self.name, "products": len(pr.rows), "slots": pr.slots, "roles": pr.roles,
                "search_slots": pr.search_slots,
                "values": {s: sorted(pr.values[s])[:40] for s in pr.slots}}


class CountingTools:
    """The agent's tools for one session: counted searches, cached per filter set, so re-reading
    a revised transcript does not search again."""

    def __init__(self, shop):
        self.shop, self.searches, self.cache = shop, 0, {}

    def search(self, query="", filters=None, k=10):
        key = (tuple(sorted((filters or {}).items())), k)
        if key not in self.cache:
            self.searches += 1
            self.cache[key] = self.shop.search.search(query, filters, k)
        return self.cache[key]

    def record_search(self, n=1):
        self.searches += n


# ---------------------------------------------------------------- sessions

class Session:
    def __init__(self, shop, mode, rezolve):
        self.id = secrets.token_urlsafe(9)
        self.shop, self.mode, self.rezolve = shop, mode, rezolve
        self.tools = CountingTools(shop)
        self.started = self.touched = time.time()
        self.words = []                 # words the agent has read
        self.committed = None           # (product id, word number)
        self.revisions = 0
        self.lock = threading.Lock()
        self._new_agent()

    def _new_agent(self):
        policy = CommitPolicy()
        policy.mode = self.mode
        self.agent = Agent(self.tools, policy=policy, vocab=self.shop.vocab, rezolve=self.rezolve)
        self.agent.start(self.id)

    def _observe(self, word):
        t0 = time.perf_counter()
        out = self.agent.observe(word) or {}
        ms = (time.perf_counter() - t0) * 1000
        self.words.append(word)
        step = {"word": word, "n": len(self.words), "ms": round(ms, 3),
                "filters": out.get("filters", {}), "candidates": out.get("candidates"),
                "leading": out.get("leading"), "confidence": out.get("confidence", 0.0)}
        if out.get("commit") and not self.committed:
            self.committed = (out["commit"], len(self.words))
            step["commit"] = self.shop.card(out["commit"])
        METRICS.word(ms)
        return step

    def add_words(self, words):
        steps = []
        for w in words:
            if len(self.words) >= MAX_WORDS:
                break
            steps.append(self._observe(w))
        return steps

    def transcript(self, text, final):
        """A running speech-to-text transcript. The last word of an interim transcript may still
        change ("four" -> "fourteen"), so only the words before it are read until final."""
        words = text.split()
        stable = words if final else words[:-1]
        if stable[:len(self.words)] == self.words:
            return self.add_words(stable[len(self.words):]), False
        # an earlier word was revised: re-read from the start (cheap; searches are cached)
        self.revisions += 1
        before = self.committed
        self.words, self.committed = [], None
        self._new_agent()
        steps = self.add_words(stable)
        if before and not self.committed:
            self.committed = before      # a shown product is not withdrawn silently
        return steps, True

    def state(self):
        pid = self.committed[0] if self.committed else None
        return {"session": self.id, "shop": self.shop.name, "mode": self.mode, "words": len(self.words),
                "committed": self.shop.card(pid) if pid else None,
                "committed_at": self.committed[1] if self.committed else None,
                "searches": self.tools.searches, "revisions": self.revisions}

    def finish(self):
        pid = self.agent.finish() or (self.committed[0] if self.committed else None)
        st = self.state()
        st["final"] = self.shop.card(pid) if pid else None
        st["early_share"] = round((len(self.words) - self.committed[1]) / len(self.words), 3) \
            if self.committed and self.words and pid == self.committed[0] else 0.0
        st["changed_after_commit"] = bool(self.committed and pid != self.committed[0])
        st["rezolve"] = [{"reason": reason, "answer": answer} for _, reason, answer in self.agent.fallback_log]
        return st


class Registry:
    def __init__(self):
        self.sessions, self.lock = {}, threading.Lock()

    def add(self, s):
        with self.lock:
            self._sweep()
            self.sessions[s.id] = s
        return s

    def get(self, sid):
        with self.lock:
            s = self.sessions.get(sid)
        if s:
            s.touched = time.time()
        return s

    def drop(self, sid):
        with self.lock:
            return self.sessions.pop(sid, None)

    def _sweep(self):
        now = time.time()
        for sid in [k for k, s in self.sessions.items() if now - s.touched > SESSION_TTL]:
            del self.sessions[sid]


class Metrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.started = time.time()
        self.word_ms = []
        self.counts = {"sessions": 0, "finished": 0, "committed": 0, "changed_after_commit": 0, "errors": 0}

    def word(self, ms):
        with self.lock:
            self.word_ms.append(ms)
            del self.word_ms[:-10000]          # keep the last 10,000

    def inc(self, key):
        with self.lock:
            self.counts[key] += 1

    def snapshot(self):
        with self.lock:
            ms = sorted(self.word_ms)
            pct = (lambda q: round(ms[int(q * (len(ms) - 1))], 3)) if ms else (lambda q: None)
            return {"uptime_s": round(time.time() - self.started), **self.counts,
                    "active_sessions": len(REGISTRY.sessions),
                    "words": len(ms), "word_ms_mean": round(statistics.mean(ms), 3) if ms else None,
                    "word_ms_p50": pct(.5), "word_ms_p95": pct(.95), "word_ms_p99": pct(.99)}


SHOPS = {}
REGISTRY = Registry()
METRICS = Metrics()
LOG = None


def log_event(event):
    if LOG:
        LOG.write(json.dumps({"t": round(time.time(), 3), **event}, ensure_ascii=False) + "\n")
        LOG.flush()


# ---------------------------------------------------------------- http

class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class Handler(BaseHTTPRequestHandler):
    server_version = "ShelfSense/1.0"

    def log_message(self, fmt, *args):            # quiet; decisions go to the event log
        pass

    # -------------------------------------------------- plumbing

    def _send(self, status, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 64_000:
            raise ApiError(413, "request too large")
        if not n:
            return {}
        try:
            body = json.loads(self.rfile.read(n))
        except json.JSONDecodeError:
            raise ApiError(400, "body is not JSON") from None
        if not isinstance(body, dict):
            raise ApiError(400, "body must be a JSON object")
        return body

    def _session(self, sid):
        s = REGISTRY.get(sid)
        if not s:
            raise ApiError(404, "no such session (they expire after 15 minutes idle)")
        return s

    def _dispatch(self, method):
        url = urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        try:
            out = self._route(method, parts, parse_qs(url.query))
            if out is not None:
                self._send(200, out)
        except ApiError as e:
            self._send(e.status, {"error": str(e)})
        except Exception as e:                    # never leak a traceback to the client
            METRICS.inc("errors")
            log_event({"event": "error", "path": url.path, "error": repr(e)})
            self._send(500, {"error": "internal error"})

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_DELETE(self):
        self._dispatch("DELETE")

    # -------------------------------------------------- routes

    def _route(self, method, parts, query):
        if method == "GET" and not parts:
            return self._static("index.html")
        if method == "GET" and parts[0] == "static" and len(parts) == 2:
            return self._static(parts[1])
        if method == "GET" and parts == ["health"]:
            return {"ok": True, "shops": sorted(SHOPS)}
        if method == "GET" and parts == ["metrics"]:
            return METRICS.snapshot()
        if parts[:1] != ["v1"]:
            raise ApiError(404, "not found")
        parts = parts[1:]

        if method == "GET" and parts == ["shops"]:
            return {"shops": [s.info() for s in SHOPS.values()]}
        if method == "GET" and len(parts) == 3 and parts[0] == "shops" and parts[2] == "samples":
            shop = SHOPS.get(parts[1]) or self._no_shop(parts[1])
            n = min(int((query.get("n") or ["8"])[0]), 50)
            return {"samples": random.sample(shop.samples, min(n, len(shop.samples)))}

        if method == "POST" and parts == ["sessions"]:
            body = self._body()
            name = body.get("shop") or next(iter(SHOPS))
            shop = SHOPS.get(name) or self._no_shop(name)
            mode = body.get("mode", "auto")
            if mode not in MODES:
                raise ApiError(400, f"mode must be one of {MODES}")
            # the Rezolve knowledge base holds the kit catalogue only (tools/rezolve_setup.py)
            rz = REZOLVE if shop.profile.path.resolve() == KIT_CATALOGUE.resolve() else None
            s = REGISTRY.add(Session(shop, mode, rz))
            METRICS.inc("sessions")
            return s.state()

        if len(parts) >= 2 and parts[0] == "sessions":
            s = self._session(parts[1])
            action = parts[2] if len(parts) == 3 else None
            if method == "DELETE" and action is None:
                REGISTRY.drop(s.id)
                return {"deleted": s.id}
            if method == "GET" and action is None:
                return s.state()
            if method == "POST" and action == "words":
                words = self._body().get("words")
                if not isinstance(words, list) or not all(isinstance(w, str) for w in words):
                    raise ApiError(400, '"words" must be a list of strings')
                with s.lock:
                    steps = s.add_words([w for w in words if w.strip()])
                    return {"steps": steps, "state": s.state()}
            if method == "POST" and action == "transcript":
                body = self._body()
                text = body.get("text")
                if not isinstance(text, str):
                    raise ApiError(400, '"text" must be a string')
                with s.lock:
                    steps, revised = s.transcript(text, bool(body.get("final")))
                    return {"steps": steps, "revised": revised, "state": s.state()}
            if method == "POST" and action == "finish":
                with s.lock:
                    out = s.finish()
                METRICS.inc("finished")
                if out["committed"]:
                    METRICS.inc("committed")
                if out["changed_after_commit"]:
                    METRICS.inc("changed_after_commit")
                log_event({"event": "request", "shop": s.shop.name, "mode": s.mode, "words": s.words,
                           "committed": out["committed"] and out["committed"]["id"],
                           "committed_at": out["committed_at"], "final": out["final"] and out["final"]["id"],
                           "searches": out["searches"], "revisions": out["revisions"]})
                REGISTRY.drop(s.id)
                return out
        raise ApiError(404, "not found")

    def _no_shop(self, name):
        raise ApiError(404, f"unknown shop {name!r}; loaded: {sorted(SHOPS)}")

    def _static(self, name):
        if not re.fullmatch(r"[\w.-]+", name):
            raise ApiError(404, "not found")
        path = STATIC / name
        if not path.is_file():
            raise ApiError(404, "not found")
        ctype = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
                 ".svg": "image/svg+xml"}.get(path.suffix, "application/octet-stream")
        self._send(200, path.read_bytes(), ctype)


REZOLVE = None


def load_shops(specs):
    shops = {}
    if not specs:
        for name, (cat, cfg, samples) in DEFAULT_SHOPS.items():
            shops[name] = Shop(name, cat, cfg, samples)
        return shops
    for spec in specs:                      # name=catalogue.csv[:config.json[:samples.jsonl]]
        name, _, rest = spec.partition("=")
        cat, cfg, samples = (rest.split(":") + [None, None])[:3]
        shops[name] = Shop(name, cat, cfg or None, samples or None)
    return shops


def make_server(host="127.0.0.1", port=8080, shops=None, log_path=None):
    global LOG, REZOLVE
    SHOPS.clear()
    SHOPS.update(shops if shops is not None else load_shops(None))
    REZOLVE = RezolveClient.from_env()
    if REZOLVE is None and os.environ.get("REZOLVE_MOCK"):     # local stand-in, for testing the page only
        from rezolve_mock import MockRezolve
        REZOLVE = MockRezolve(Profile.load(KIT_CATALOGUE))
    LOG = open(log_path, "a", encoding="utf-8") if log_path else None
    return ThreadingHTTPServer((host, port), Handler)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--shop", action="append", help="name=catalogue.csv[:config.json[:samples.jsonl]]")
    ap.add_argument("--log", help="append one JSON line per finished request here")
    args = ap.parse_args()
    srv = make_server(args.host, args.port, load_shops(args.shop), args.log)
    for s in SHOPS.values():
        print(f"shop {s.name}: {len(s.profile.rows)} products, filters {', '.join(s.profile.slots)}")
    print(f"Rezolve Labs fallback: {'on' if REZOLVE else 'off (no REZOLVE_API_KEY)'}")
    print(f"ShelfSense listening on http://{args.host}:{args.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
