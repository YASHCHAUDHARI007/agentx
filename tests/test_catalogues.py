"""Regression tests: python3 -m unittest discover tests"""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "starter_kit" / "ps1-anticipatory-commerce"))
os.environ.setdefault("AGENT_COMMIT_MODE", "auto")

import evaluate  # noqa: E402
from catalogue import Profile  # noqa: E402
from evaluate_catalogue import score  # noqa: E402
from parser import Vocab, parse  # noqa: E402

KIT = ROOT / "starter_kit" / "ps1-anticipatory-commerce"
ELEC = ROOT / "tests" / "catalogues" / "electronics"


def load(path):
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


class Detection(unittest.TestCase):
    def test_kit_profile(self):
        p = Profile.load(KIT / "catalogue.csv")
        self.assertEqual((p.id, p.price, p.title), ("product_id", "price", "title"))
        self.assertEqual(p.search_slots, ["category", "colour"])
        self.assertEqual(p.relax_order, ["max_price", "size", "brand", "colour", "category"])

    def test_electronics_profile(self):
        p = Profile.load(ELEC / "catalogue.csv")
        self.assertEqual((p.id, p.price, p.title), ("sku", "price_inr", "name"))
        self.assertEqual(p.roles["category"], "type")
        self.assertNotIn("rating", p.slots)          # numeric, not a filter

    def test_unit_values(self):
        v = Vocab(Profile.load(ELEC / "catalogue.csv", ELEC / "config.json"))
        f = parse("Voltra blue mobile with 128 gigs under 30k".split(), vocab=v).known()
        self.assertEqual(f, {"brand": "Voltra", "type": "smartphones", "color": "blue",
                             "storage": "128GB", "max_price": 30000})
        self.assertTrue(parse("Voltra blue mobile 128".split(), vocab=v).pending)   # "128" may become "128 gb"


class Scores(unittest.TestCase):
    """Floors, not exact numbers: a change that drops below them needs a look."""

    def check(self, results, min_score, max_wrong):
        s = evaluate.summarise(results)
        self.assertGreaterEqual(s["score"], min_score)
        self.assertLessEqual(s["wrong_commits"], max_wrong)
        self.assertGreaterEqual(s["accuracy"], 0.99)

    def test_kit_dev(self):
        results, _ = score(Profile.load(KIT / "catalogue.csv"), load(KIT / "dev.jsonl"))
        self.check(results, 44.0, 0)

    def test_electronics(self):
        results, _ = score(Profile.load(ELEC / "catalogue.csv", ELEC / "config.json"), load(ELEC / "requests.jsonl"))
        self.check(results, 41.0, 1)


if __name__ == "__main__":
    unittest.main()
