"""Access control for the ShelfSense service: API keys and per-client rate limits.

Configured from the environment, so the same image runs open on a laptop and locked in production:

    SHELFSENSE_API_KEYS=key1,key2   require one of these keys on /v1/* and /metrics
                                    (header "X-API-Key: key1" or "Authorization: Bearer key1");
                                    unset = open, for local demos
    SHELFSENSE_RATE=20              requests per second per client (burst 2x); 0 = no limit
    SHELFSENSE_TRUST_PROXY=1        take the client address from X-Forwarded-For (only behind a
                                    proxy you run, since clients can set that header themselves)
"""
import hmac
import os
import threading
import time


class ApiKeys:
    def __init__(self, keys=None):
        if keys is None:
            keys = os.environ.get("SHELFSENSE_API_KEYS", "")
        if isinstance(keys, str):
            keys = keys.split(",")
        self.keys = [k.strip().encode() for k in keys if k.strip()]

    @property
    def enabled(self):
        return bool(self.keys)

    def check(self, headers):
        """The matching key (for the rate limiter to key on), True when keys are off, or None."""
        if not self.keys:
            return True
        given = headers.get("X-API-Key") or ""
        auth = headers.get("Authorization") or ""
        if not given and auth.lower().startswith("bearer "):
            given = auth[7:]
        given = given.strip().encode()
        hit = None
        for k in self.keys:                       # compare against every key: no timing hint
            if hmac.compare_digest(given, k):
                hit = k
        return hit.decode() if hit else None


class RateLimiter:
    """Token bucket per client: `rate` requests per second, bursts up to `burst`."""

    def __init__(self, rate=None, burst=None, max_clients=10_000):
        if rate is None:
            rate = float(os.environ.get("SHELFSENSE_RATE", 20))
        self.rate = rate
        self.burst = burst if burst is not None else max(1.0, 2 * rate)
        self.max_clients = max_clients
        self.buckets, self.lock = {}, threading.Lock()

    def allow(self, client):
        """(allowed, seconds to wait before retrying)."""
        if self.rate <= 0:
            return True, 0.0
        now = time.monotonic()
        with self.lock:
            tokens, last = self.buckets.get(client, (self.burst, now))
            tokens = min(self.burst, tokens + (now - last) * self.rate)
            if len(self.buckets) >= self.max_clients and client not in self.buckets:
                self._prune(now)
            if tokens >= 1:
                self.buckets[client] = (tokens - 1, now)
                return True, 0.0
            self.buckets[client] = (tokens, now)
            return False, (1 - tokens) / self.rate

    def _prune(self, now):
        """Drop clients whose bucket has refilled; they would start full anyway."""
        full = self.burst / self.rate
        for c in [c for c, (_, last) in self.buckets.items() if now - last > full]:
            del self.buckets[c]


def client_address(handler, trust_proxy=None):
    if trust_proxy is None:
        trust_proxy = os.environ.get("SHELFSENSE_TRUST_PROXY") == "1"
    if trust_proxy:
        fwd = handler.headers.get("X-Forwarded-For")
        if fwd:
            return fwd.split(",")[0].strip()
    return handler.client_address[0]
