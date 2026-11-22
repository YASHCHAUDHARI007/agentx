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
"""
import json
import os
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
    pass


class RezolveClient:
    def __init__(self, api_key, kb_id=None, base_url=DEFAULT_BASE, timeout=4.0):
        self.api_key, self.kb_id, self.base, self.timeout = api_key, kb_id, base_url.rstrip("/"), timeout
        self.calls = 0

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
            raise RezolveError(f"{method} {path} -> HTTP {e.code}: {e.read()[:300]!r}") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            raise RezolveError(f"{method} {path} failed: {e}") from None

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
        self.calls += 1
        out = self._request("POST", "/product-discovery/search", body)
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
