"""Rezolve Labs client: semantic product search over our catalogue knowledge base.

Standard library only. Configuration comes from environment variables, or from a `.env` file at
the repository root (git-ignored, never committed):

    REZOLVE_API_KEY=...        # from your Rezolve Labs account
    REZOLVE_KB_ID=...          # printed by tools/rezolve_setup.py after the catalogue upload
    REZOLVE_BASE_URL=...       # optional, defaults to https://api.rezolvelabs.com/api/v1

API shape (from the organisers' starter-kit README, 2026-11-10):
    POST {base}/product-discovery/search   header X-API-KEY
         {"knowledgeBaseId", "query", "filters": {"colour": "black", "price_lte": 4000, ...}, "limit"}
    Each result's `id` is the catalogue product_id. One credit per search.
The response is read defensively, since the full schema lives in the account's API reference.

Resilience (search only; setup calls are not retried, since they create things):
  * retries: a timeout, network error, HTTP 429 or 5xx is retried twice with jittered backoff,
    honouring Retry-After up to 2 s. Other errors (bad key, bad request) fail at once.
  * circuit breaker: after 3 failed searches in a row, Rezolve is not called for 30 s, so an
    outage costs the shopper nothing; the agent keeps its local answer. One trial call then
    decides whether to resume.
"""
import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = "https://api.rezolvelabs.com/api/v1"


def load_env(path=ROOT / ".env"):
    """Read KEY=VALUE lines from .env into os.environ (existing variables win)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class RezolveError(RuntimeError):
    def __init__(self, message, status=None, retry_after=None):
        super().__init__(message)
        self.status, self.retry_after = status, retry_after

    @property
    def transient(self):
        """Worth retrying: no answer at all, rate limited, or a server-side failure."""
        return self.status is None or self.status == 429 or self.status >= 500


class CircuitBreaker:
    def __init__(self, threshold=3, cooldown=30.0, clock=time.monotonic):
        self.threshold, self.cooldown, self.clock = threshold, cooldown, clock
        self.failures, self.opened_at, self.lock = 0, None, threading.Lock()

    @property
    def open(self):
        with self.lock:
            return self.opened_at is not None and self.clock() - self.opened_at < self.cooldown

    def allow(self):
        """Closed: yes. Open: no, until the cooldown ends; then one trial call goes through."""
        with self.lock:
            if self.opened_at is None:
                return True
            if self.clock() - self.opened_at >= self.cooldown:
                self.opened_at = self.clock()     # half-open: this call is the trial, others wait
                return True
            return False

    def success(self):
        with self.lock:
            self.failures, self.opened_at = 0, None

    def failure(self):
        with self.lock:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = self.clock()


class RezolveClient:
    def __init__(self, api_key, kb_id=None, base_url=DEFAULT_BASE, timeout=4.0, retries=2, backoff=0.25,
                 breaker=None, sleep=time.sleep):
        self.api_key, self.kb_id, self.base, self.timeout = api_key, kb_id, base_url.rstrip("/"), timeout
        self.retries, self.backoff, self.sleep = retries, backoff, sleep
        self.breaker = breaker or CircuitBreaker()
        self.calls = 0          # HTTP attempts at search (each may cost a credit)
        self.failures = 0       # searches that failed after all retries
        self.skipped = 0        # searches not attempted because the circuit was open
        self.lock = threading.Lock()

    def stats(self):
        return {"calls": self.calls, "failures": self.failures, "skipped": self.skipped,
                "circuit_open": self.breaker.open}

    @classmethod
    def from_env(cls):
        """A configured client, or None when no key is set (the agent then runs fully offline)."""
        load_env()
        key = os.environ.get("REZOLVE_API_KEY")
        if not key:
            return None
        return cls(key, os.environ.get("REZOLVE_KB_ID"), os.environ.get("REZOLVE_BASE_URL", DEFAULT_BASE))

    # ------------------------------------------------------------ http

    def _request(self, method, path, body=None, files=None):
        url = f"{self.base}{path}"
        headers = {"X-API-KEY": self.api_key, "Accept": "application/json"}
        data = None
        if files:
            boundary = "----shelfsense-boundary"
            parts = []
            for name, (filename, content, ctype) in files.items():
                parts += [f"--{boundary}".encode(),
                          f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode(),
                          f"Content-Type: {ctype}".encode(), b"", content]
            parts += [f"--{boundary}--".encode(), b""]
            data = b"\r\n".join(parts)
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            retry_after = None
            try:
                retry_after = float(e.headers.get("Retry-After"))
            except (TypeError, ValueError):
                pass
            raise RezolveError(f"{method} {path} -> HTTP {e.code}: {e.read()[:300]!r}", e.code, retry_after) from None
        except json.JSONDecodeError as e:
            raise RezolveError(f"{method} {path}: response is not JSON: {e}", 502) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise RezolveError(f"{method} {path} failed: {e}") from None

    def _resilient(self, method, path, body):
        """_request with retries for transient failures, behind the circuit breaker."""
        if not self.breaker.allow():
            with self.lock:
                self.skipped += 1
            raise RezolveError("Rezolve Labs paused after repeated failures (circuit open)", 503)
        for attempt in range(self.retries + 1):
            with self.lock:
                self.calls += 1
            try:
                out = self._request(method, path, body)
            except RezolveError as e:
                if not e.transient:
                    self.breaker.success()       # the service answered; the request was wrong
                    raise
                if attempt == self.retries:
                    with self.lock:
                        self.failures += 1
                    self.breaker.failure()
                    raise
                wait = self.backoff * (2 ** attempt) * (0.5 + random.random())
                if e.retry_after is not None:
                    wait = max(wait, min(e.retry_after, 2.0))
                self.sleep(wait)
            else:
                self.breaker.success()
                return out

    # ------------------------------------------------------------ knowledge base (setup)

    def create_knowledge_base(self, name):
        return _dig(self._request("POST", "/developer-platform/knowledge-bases", {"name": name}), "data", "id")

    def upload_document(self, kb_id, path):
        path = Path(path)
        out = self._request("POST", f"/developer-platform/knowledge-bases/{kb_id}/documents",
                            files={"file": (path.name, path.read_bytes(), "text/csv")})
        return _dig(out, "data", "id")

    def document_status(self, kb_id, doc_id):
        return self._request("GET", f"/developer-platform/knowledge-bases/{kb_id}/documents/{doc_id}")

    # ------------------------------------------------------------ search

    def search(self, query, filters=None, limit=5):
        """Semantic search. filters use our names (category, colour, size, brand, max_price).
        Returns product ids, best first."""
        if not self.kb_id:
            raise RezolveError("REZOLVE_KB_ID is not set: run tools/rezolve_setup.py first")
        f = {}
        for k, v in (filters or {}).items():
            if v is None:
                continue
            f["price_lte" if k == "max_price" else k] = v
        body = {"knowledgeBaseId": self.kb_id, "query": query, "limit": limit}
        if f:
            body["filters"] = f
        out = self._resilient("POST", "/product-discovery/search", body)
        return [pid for pid in (_result_id(r) for r in _results(out)) if pid]


def _dig(obj, *keys):
    for k in keys:
        if not isinstance(obj, dict) or k not in obj:
            raise RezolveError(f"unexpected response, missing {'.'.join(keys)}: {str(obj)[:300]}")
        obj = obj[k]
    return obj


def _results(out):
    """Find the list of hits wherever the response keeps it."""
    for path in (("data", "results"), ("data", "products"), ("data", "hits"), ("results",), ("products",),
                 ("hits",), ("data",)):
        obj = out
        for k in path:
            obj = obj.get(k) if isinstance(obj, dict) else None
        if isinstance(obj, list):
            return obj
    return []


def _result_id(r):
    if not isinstance(r, dict):
        return None
    for k in ("id", "product_id", "productId"):
        if r.get(k):
            return str(r[k])
    meta = r.get("metadata") or r.get("document") or {}
    return str(meta.get("product_id") or meta.get("id") or "") or None
