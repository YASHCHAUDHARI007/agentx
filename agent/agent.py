"""Anticipatory shopping agent for AgentX Challenge 1.

    python ../starter_kit/ps1-anticipatory-commerce/evaluate.py --agent agent.py

How it works, per word:
  1. Re-parse the prefix into filters (parser.py).
  2. As soon as category and colour are known, run ONE counted search for them and keep the
     returned products as candidates. Later words (brand, size, budget) narrow the candidates
     locally, so no further searches are needed unless a correction changes category or colour.
  3. When exactly one candidate fits everything said so far, it is the target unless the shopper
     later corrects something: a new constraint can only confirm a unique match, never change it.
  4. Commit when the commit policy (policy.py) judges a later correction unlikely.
finish() re-reads the whole request and answers from the same candidates.

Rezolve Labs semantic search (rezolve.py) is the fallback for requests the parser could not read
cleanly: the category or colour was not understood or only guessed, or the local filters do not
leave exactly one product. Clean requests never call it, and it never triggers an early commit.
With no REZOLVE_API_KEY configured the agent runs fully offline.
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from parser import parse  # noqa: E402
from policy import CommitPolicy  # noqa: E402
from rezolve import RezolveClient, RezolveError  # noqa: E402

SEARCH_K = 200          # enough to return every product of one category and colour
RELAX_ORDER = ("max_price", "size", "brand", "colour", "category")


def _fits(product, filters):
    for k, v in filters.items():
        if k == "max_price":
            if product["price"] > v:
                return False
        elif str(product[k]).lower() != str(v).lower():
            return False
    return True


class Agent:
    def __init__(self, tools, policy=None, max_searches=None, rezolve="env"):
        self.tools = tools
        self.policy = policy or CommitPolicy()
        self.max_searches = max_searches if max_searches is not None else self.policy.max_searches
        if rezolve == "env":
            if os.environ.get("REZOLVE_MOCK"):          # local stand-in, for testing the wiring only
                from rezolve_mock import MockRezolve
                rezolve = MockRezolve()
            else:
                rezolve = RezolveClient.from_env()
        self.rezolve = rezolve
        self.fallback_log = []                          # (request id, reason, answer) per Rezolve call

    def start(self, request_id):
        self.request_id = request_id
        self.words = []
        self.pools = {}           # (category, colour) -> products returned by the search
        self.searches = 0
        self.committed = None
        self.unique = None        # product id that alone fits the current reading
        self.held = 0             # words that unique product has held since it appeared
        self.prev_filters = {}

    # ------------------------------------------------------------ searching

    def _pool(self, category, colour, query, allow_search=True):
        key = (category, colour)
        if key not in self.pools:
            if not allow_search or self.searches >= self.max_searches:
                return None
            self.searches += 1
            filters = {k: v for k, v in (("category", category), ("colour", colour)) if v}
            self.pools[key] = self.tools.search(query, filters, k=SEARCH_K)
        return self.pools[key]

    def _candidates(self, p, allow_search=True):
        f = p.known()
        if not (f.get("category") and f.get("colour")):
            return None
        pool = self._pool(f["category"], f["colour"], " ".join(self.words), allow_search)
        if pool is None:
            return None
        return [x for x in pool if _fits(x, f)]

    # ------------------------------------------------------------ protocol

    def observe(self, word):
        self.words.append(word)
        p = parse(self.words)
        out = {"filters": p.known(), "confidence": 0.0}
        if self.committed:
            return out

        # a slot changing value (a correction) resets everything we believed
        changed = any(self.prev_filters.get(k) not in (None, v) for k, v in p.known().items())
        self.prev_filters = p.known()

        # words the parser did not understand, or only guessed at, rule out an early commit
        cands = self._candidates(p) if not (p.unknown or p.guessed) else None
        if cands is not None and len(cands) == 1 and not changed:
            pid = cands[0]["product_id"]
            if pid == self.unique:
                # only plain filler ("for my brother", "thanks", "please") counts as the request
                # winding down; new values and cue words do not
                if not p.pending and not p.open_correction and p.last_kind == "filler":
                    self.held += 1
            else:
                self.unique, self.held = pid, 0
        else:
            self.unique, self.held = None, 0

        if self.unique:
            conf = self.policy.confidence(p, self.held)
            out["confidence"] = conf
            if conf >= self.policy.threshold:
                self.committed = self.unique
                out["commit"] = self.unique
        return out

    def finish(self):
        p = parse(self.words, final=True)
        filters = p.known()
        local, hits, clean = self._local_answer(p, filters)
        if clean or self.rezolve is None:
            return local
        return self._rezolve_answer(p, filters, {x["product_id"] for x in hits}) or local

    def _local_answer(self, p, filters):
        """Answer from the counted catalogue search, plus the products that fit. clean=True when
        everything understood (colour at least) leaves exactly one product, with nothing relaxed."""
        pool = None
        if filters.get("category") and filters.get("colour"):
            pool = self._pool(filters["category"], filters["colour"], " ".join(self.words))
        if pool is None:        # category or colour never understood: one broad search
            self.searches += 1
            pool = self.tools.search(" ".join(self.words), {k: v for k, v in filters.items()
                                                            if k in ("category", "colour")}, k=SEARCH_K)
        for n, drop in enumerate((None,) + RELAX_ORDER):
            f = {k: v for k, v in filters.items() if k != drop}
            hits = [x for x in pool if _fits(x, f)]
            if hits:
                clean = n == 0 and len(hits) == 1 and bool(filters.get("colour"))
                return self._best(hits)["product_id"], hits, clean
            filters = f
        return self.committed, [], False

    def _rezolve_answer(self, p, filters, local_ids):
        """Ask Rezolve Labs semantic search, with only the filters we are sure of. A result that also
        fits the local reading wins over Rezolve's own top pick."""
        sure = {k: v for k, v in filters.items() if not (k == "category" and v in p.guessed)}
        reason = "no category" if not filters.get("category") else \
            "guessed category" if "category" not in sure else "no unique local match"
        try:
            self.tools.record_search(1)                  # every external search counts
            ids = self.rezolve.search(" ".join(self.words), sure, limit=3)
            if not ids and sure:                         # filters too tight: ask by meaning alone
                self.tools.record_search(1)
                ids = self.rezolve.search(" ".join(self.words), {k: v for k, v in sure.items()
                                                                if k in ("colour", "size")}, limit=3)
        except RezolveError:
            ids = []
        agree = [i for i in ids if i in local_ids]
        answer = agree[0] if agree else ids[0] if ids else None
        self.fallback_log.append((self.request_id, reason, answer))
        return answer

    def _best(self, hits):
        words = set(re.findall(r"[a-z0-9]+", " ".join(self.words).lower()))
        return max(hits, key=lambda x: (len(words & set(re.findall(r"[a-z0-9]+", x["title"].lower()))), -x["price"]))
