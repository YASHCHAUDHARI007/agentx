"""Commit-or-wait policy.

Scoring: a wrong commit costs 1.0; a right one earns 0.6 x the share of the request still to come.
So a commit only pays when the chance that nothing later changes the answer is above about
1 / (1 + 0.6 x share), i.e. roughly 0.9 to 0.95 here.

What can still change a product that is already the only match? Only a correction: a new
constraint can confirm a unique match but never swap it. In dev, every wrong early commit came
from a correction arriving right after the request sounded finished ("... size 8, | I mean
size 7"), and a request corrects itself at most once. Hence:
  * a correction already seen in the prefix  -> commit as soon as the match is unique;
  * otherwise -> wait until the unique match has held for `wait_words` more words, none of them
    a correction or hesitation word (the parser marks those as `pending`, and they do not count).
"""
import os


class CommitPolicy:
    threshold = 1.0
    wait_words = int(os.environ.get("AGENT_WAIT_WORDS", 1))
    max_searches = int(os.environ.get("AGENT_MAX_SEARCHES", 3))   # tunable cap per request (stretch goal)

    def confidence(self, p, held):
        if p.pending or p.open_correction:
            return 0.0
        need = 0 if p.changes else self.wait_words
        return 1.0 if held >= need else 0.0
