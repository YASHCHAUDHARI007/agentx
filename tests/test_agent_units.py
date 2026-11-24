"""Unit tests for the parser and the commit policy: python3 -m unittest discover tests

Each case pins one behaviour the score depends on, so a change that breaks it fails here with a
readable name, not only as a lower number in the full evaluation.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "starter_kit" / "ps1-anticipatory-commerce"))

from parser import Parse, parse  # noqa: E402
from policy import CommitPolicy  # noqa: E402


def read(text, final=True):
    return parse(text.split(), final=final)


class Parser(unittest.TestCase):
    def test_plain_request(self):
        self.assertEqual(read("red kurta under 2.5k").known(),
                         {"category": "kurtas", "colour": "red", "max_price": 2500})

    def test_correction_last_mention_wins(self):
        p = read("show me black running shoes size 8, I mean size 7")
        self.assertEqual(p.known()["size"], "7")
        self.assertEqual(p.changes, {"size": 1})

    def test_correction_without_repeating_the_slot(self):
        self.assertEqual(read("black running shoes size 8 no wait 9").known()["size"], "9")

    def test_hinglish_budget(self):
        self.assertEqual(read("navy blue sneakers do hazaar se kam").known()["max_price"], 2000)

    def test_spoken_numbers(self):
        self.assertEqual(read("Loomsy navy blue casual sneakers within forty five hundred").known(),
                         {"brand": "Loomsy", "category": "sneakers", "colour": "navy", "max_price": 4500})
        self.assertEqual(read("white tshirt size M under fifteen hundred").known()["max_price"], 1500)

    def test_typos_and_glued_sizes_are_repaired_and_flagged(self):
        p = read("blak sneekers UK9")
        self.assertEqual(p.known(), {"category": "sneakers", "colour": "black", "size": "9"})
        self.assertIn("black", p.guessed)        # a repaired word is never trusted blindly

    def test_open_budget_cue_is_pending(self):
        p = read("sneakers under", final=False)
        self.assertTrue(p.pending)
        self.assertNotIn("max_price", p.known())

    def test_spoken_number_may_still_grow(self):
        """'fifteen hundred' can become 'fifteen hundred fifty': not settled yet."""
        self.assertTrue(read("white tshirt size M under fifteen hundred", final=False).pending)

    def test_spoken_amount_closed_by_punctuation(self):
        """"one" starts the phrase "one piece", but "one thousand," is a finished budget."""
        p = read("floaters in olive, budget one thousand,", final=False)
        self.assertEqual(p.known().get("max_price"), 1000)

    def test_dangling_correction_word_is_open(self):
        p = read("sneakers in size 8, actually", final=False)
        self.assertTrue(p.open_correction)


class Policy(unittest.TestCase):
    def policy(self, mode):
        pol = CommitPolicy()
        pol.mode, pol.wait_words, pol.immediate = mode, 1, True
        return pol

    @staticmethod
    def state(last_slot="max_price", value=3000, **kw):
        p = Parse(filters={"category": "sneakers", last_slot: value}, set_at={"category": 0, last_slot: 3},
                  last_kind="value", n=4)
        for k, v in kw.items():
            setattr(p, k, v)
        return p

    def test_never_commits_mid_thought(self):
        for mode in ("auto", "next", "speech", "safe", "instant"):
            self.assertEqual(self.policy(mode).confidence(self.state(pending=True), held=5), 0.0, mode)
            self.assertEqual(self.policy(mode).confidence(self.state(open_correction=True), held=5), 0.0, mode)

    def test_seen_correction_commits_at_once(self):
        self.assertEqual(self.policy("speech").confidence(self.state(changes={"size": 1}), held=0), 1.0)

    def test_one_settled_word_is_enough(self):
        self.assertEqual(self.policy("speech").confidence(self.state(), held=1), 1.0)

    def test_budget_number_mid_sentence_commits_in_next_mode(self):
        self.assertEqual(self.policy("next").confidence(self.state(), held=0), 1.0)

    def test_spoken_budget_commits_when_it_lands(self):
        """'under two thousand five hundred | for': the amount completes one word late."""
        pol = self.policy("next")
        self.assertEqual(pol.confidence(self.state(), held=0, budget_landed=True), 1.0)
        self.assertEqual(self.policy("speech").confidence(self.state(), held=0, budget_landed=True), 0.0)
        self.assertEqual(pol.confidence(self.state("size", "8"), held=0, budget_landed=True), 0.0)

    def test_budget_number_at_clause_end_waits(self):
        self.assertEqual(self.policy("next").confidence(self.state(), held=0, clause_end=True), 0.0)

    def test_speech_mode_never_commits_instantly(self):
        self.assertEqual(self.policy("speech").confidence(self.state(), held=0), 0.0)

    def test_auto_is_speech_until_punctuation(self):
        pol = self.policy("auto")
        self.assertEqual(pol.confidence(self.state(), held=0, punctuated=False), 0.0)
        self.assertEqual(pol.confidence(self.state(), held=0, punctuated=True), 1.0)

    def test_sizes_wait_even_in_instant_mode(self):
        """'size 8, | I mean 7' is the commonest late correction."""
        pol = self.policy("instant")
        self.assertEqual(pol.confidence(self.state("size", "8"), held=0), 0.0)
        self.assertEqual(pol.confidence(self.state("colour", "black"), held=0), 1.0)


class FinalChoice(unittest.TestCase):
    """When several products fit at the end, the request's own words and the budget decide."""

    @classmethod
    def setUpClass(cls):
        import evaluate                           # the kit's counted search
        from agent import Agent
        cls.tools = evaluate.Tools()
        cls.agent = Agent(cls.tools, rezolve=None)

    def answer(self, text):
        self.agent.start("t")
        for w in text.split():
            self.agent.observe(w)
        return self.agent.finish()

    def test_unknown_word_matches_product_text(self):
        """'sneaks' is not in the lexicon; it still points at sneakers, not running shoes."""
        self.assertEqual(self.answer("can I get sneaks size 7 UK by Kudova navy blue color cheaper than 4000"), "P0104")

    def test_budget_prefers_price_near_it(self):
        """'racing flats' is unknown; at 'upto 8000' the shopper means the 7,599 shoe, not 1,349 sandals."""
        self.assertEqual(self.answer("help me find in navy blue coloured Strydo size 7 UK upto 8000 racing flats"), "P0005")


if __name__ == "__main__":
    unittest.main()
