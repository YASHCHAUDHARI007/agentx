"""Commit-or-wait policy.

Scoring: a wrong commit costs 1.0; a right one earns 0.6 x the share of the request still to come.
So a commit only pays when the chance that nothing later changes the answer is above about
1 / (1 + 0.6 x share), i.e. roughly 0.9 to 0.95 here.

What can still change a product that is already the only match? Only a correction: a new
constraint can confirm a unique match but never swap it. In dev, every wrong early commit came
from a correction arriving right after the request sounded finished ("... size 8, | I mean
size 7"), and a request corrects itself at most once. Hence, once one product alone fits:
  * a correction already seen in the prefix -> commit at once;
  * the match became unique on a budget number mid-sentence ("... under 3000") -> commit at once
    (150 of 150 right across dev, stress and holdout);
  * otherwise wait one more word that is filler, or a value word with no punctuation after it.
    Corrections almost always open a new clause ("size 8, | I mean 7"), so a word ending in "."
    or "," never counts, and nor do cue words ("no", "wait", "under").

Those rules lean on punctuation. Raw speech-to-text has none, and there a correction can follow
a complete request directly ("... budget 50k | actually make it 256gb"). So:
  * speech: no instant commits, and only filler counts as the extra word.

Modes (AGENT_COMMIT_MODE):
  auto     default: speech rules until the request shows a punctuation mark, then next
  next     the punctuation-based rules above (best on the punctuated kit sets)
  speech   always the speech rules
  safe     only filler counts as the extra word, budget numbers still commit at once
  instant  also commit at once on any value word mid-sentence. Earlier, but on dev + stress +
           holdout it made 9 wrong commits in 1,500 requests ("... in golden | no no, in blue").

Wrong commits / score:            next          auto
  kit dev (punctuated)            0 / 44.5      0 / 44.1
  kit dev, punctuation stripped   4 / 43.2      1 / 43.1
  electronics shop (unpunctuated) 19 / 37.1     1 / 41.9

Value words at the end of a prefix only stay open when a longer phrase would change their
meaning (Vocab.grows_into_other): "navy" -> "navy blue" is still navy.
"""
import os


class CommitPolicy:
    threshold = 1.0
    wait_words = int(os.environ.get("AGENT_WAIT_WORDS", 1))
    max_searches = int(os.environ.get("AGENT_MAX_SEARCHES", 3))   # tunable cap per request (stretch goal)

    immediate = os.environ.get("AGENT_IMMEDIATE", "1") != "0"
    mode = os.environ.get("AGENT_COMMIT_MODE", "auto")
    size_slot = "size"          # the agent sets this from the catalogue profile

    def effective_mode(self, punctuated):
        """'auto': a request with no punctuation so far may be raw speech-to-text, where a
        correction can follow with no comma ("... budget 50k actually make it 256gb"); treat it as
        speech until a punctuation mark shows the text is punctuated."""
        if self.mode == "auto":
            return "next" if punctuated else "speech"
        return self.mode

    def confidence(self, p, held, clause_end=False, punctuated=True):
        """clause_end: the last word ended with punctuation (".", ",", "!", "?")."""
        mode = self.effective_mode(punctuated)
        if p.pending or p.open_correction:
            return 0.0
        if p.changes or held >= self.wait_words:
            return 1.0
        if mode == "speech":
            return 0.0
        if self.immediate and held == 0 and p.last_kind == "value" and not clause_end and p.set_at:
            last_slot = max(p.set_at, key=p.set_at.get)
            size_mode = os.environ.get("AGENT_SIZE_MODE", "wait")
            if mode == "instant":
                if last_slot != self.size_slot or size_mode == "all" or \
                        (size_mode == "letters" and not str(p.filters[last_slot]).isdigit()):
                    return 1.0
            elif last_slot == "max_price":      # a budget number: 150 of 150 right on dev+stress+holdout
                return 1.0
        return 0.0
