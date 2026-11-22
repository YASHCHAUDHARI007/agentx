"""Local stand-in for Rezolve Labs semantic search. TEST ONLY: it exercises the fallback wiring
(REZOLVE_MOCK=1) before we have an API key. It is not a model of how good Rezolve's search is.

Scoring: character-trigram overlap between the query and each product's title, category and
description, after applying the same exact-match filters the real API takes.
"""
import csv
import re

from lexicon import CATALOGUE


def _grams(text):
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        w = f" {w} "
        out |= {w[i:i + 3] for i in range(len(w) - 2)}
    return out


class MockRezolve:
    def __init__(self, path=CATALOGUE):
        with open(path, newline="", encoding="utf-8") as f:
            self.rows = list(csv.DictReader(f))
        for r in self.rows:
            r["_g"] = _grams(f"{r['title']} {r['category']} {r['description']}")
        self.calls = 0

    def search(self, query, filters=None, limit=5):
        self.calls += 1
        q = _grams(query)
        hits = []
        for r in self.rows:
            ok = True
            for k, v in (filters or {}).items():
                if k == "max_price":
                    ok = float(r["price"]) <= float(v)
                else:
                    ok = str(r.get(k, "")).lower() == str(v).lower()
                if not ok:
                    break
            if ok:
                hits.append((len(q & r["_g"]) / (len(r["_g"]) ** 0.5 or 1), r["product_id"]))
        hits.sort(key=lambda h: -h[0])
        return [pid for _, pid in hits[:limit]]
