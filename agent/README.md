# ShelfSense agent (Challenge 1: Anticipatory Commerce)

Standard library only. From the kit folder:

```bash
cd starter_kit/ps1-anticipatory-commerce
python3 evaluate.py --agent ../../agent/agent.py
```

| File | Role |
|---|---|
| `lexicon.py` | Vocabularies: catalogue values plus hand-written synonyms, Hinglish words, number words, cue words |
| `parser.py` | Re-reads the words so far into filters; last mention wins (handles corrections); flags a prefix that ends mid-thought |
| `policy.py` | Commit-or-wait rule |
| `agent.py` | The `Agent` class `evaluate.py` loads |
| `rezolve.py` | Rezolve Labs semantic-search client (fallback only; off when no key is set) |
| `rezolve_mock.py` | Local stand-in for Rezolve, used only to test the wiring (`REZOLVE_MOCK=1`) |

How a request flows:
1. Every word, the whole prefix is parsed again into category, colour, brand, size and budget.
2. Once category and colour are known, one counted search fetches every product of that category and colour. Brand, size and budget then narrow that list locally, so most requests need exactly one search.
3. When one product alone fits what has been said, a later *new* constraint cannot change it; only a correction can.
4. Commit rule: if the shopper has already corrected something, commit at once (requests correct themselves at most once in dev). Otherwise wait for one plain filler word ("for my brother", "thanks", "please") after the match became unique, and never while a correction word is still waiting for its new value.

Knobs (environment variables): `AGENT_WAIT_WORDS` (default 1) and `AGENT_MAX_SEARCHES` (default 3, the per-request search cap).

## Results

| Test set | Requests | Score | Accuracy | Wrong commits | Earliness | Searches |
|---|---|---|---|---|---|---|
| Kit baseline on dev | 300 | 20.0 | 0.527 | 0 | 0% | 1.53 |
| **dev.jsonl** (kit) | 300 | **43.1** | 1.000 | 0 | 5.4% (best possible 16.3%) | 1.04 |
| Stress set (our generator, used for tuning) | 600 | 42.1 | 1.000 | 0 | 3.7% | 1.03 |
| **Holdout** (fresh phrasings and seed) | 600 | **41.4** | 0.997 | 1 | 3.0% | 1.03 |
| Stress set *before* the robustness fixes | 600 | 36.4 | 0.867 | 0 | 2.9% | 1.02 |

The two test sets come from `tests/stress/make_stress.py`: catalogue-based requests in the dev format with wording the parser was not written for (typos like "nevy", "-ish" colours, "UK9", "W32", "smol", "do hazaar", "tee shirt", new openers, closers and correction phrases). The holdout set uses a different seed and a separate bank of phrasings; it was used once to find the two commit-safety fixes (words opening a new clause, and words like "brand" that hang off a value, no longer count as the request winding down), so treat its numbers as slightly optimistic too.

```bash
python3 tests/stress/make_stress.py              # stress.jsonl
python3 tests/stress/make_stress.py --holdout    # holdout.jsonl
cd starter_kit/ps1-anticipatory-commerce
python3 evaluate.py --agent ../../agent/agent.py --data ../../tests/stress/holdout.jsonl
```

What stays hard: product words the lexicon has never heard of ("racing flats", "sneaks"). The parser then has no category and the final answer can be wrong. Rezolve Labs semantic search covers this case (next section).

## Rezolve Labs fallback

Rezolve Labs semantic search is used only when the parser's reading does not pin down one product: the final read leaves no unique match, or the colour was never understood. In those cases `finish()` sends the whole request to Rezolve with only the filters we are sure of (a guessed category is left out), and prefers a Rezolve result that also fits the local reading. Each call is counted with `tools.record_search()`.

Rules:
- It never causes an early commit. It only affects the final answer.
- Clean requests never call it. With the local stand-in, it ran on 2 of 600 holdout requests and 0 of the 300 dev requests, so it costs very few credits.
- With no `REZOLVE_API_KEY`, or on any network or API error, the agent behaves exactly as it does offline.

Setup, once you have a key (from your Rezolve Labs account):

```bash
echo 'REZOLVE_API_KEY=your-key' >> .env          # repository root; .env is git-ignored
python3 tools/rezolve_setup.py                    # uploads catalogue.csv, saves REZOLVE_KB_ID to .env
python3 tools/rezolve_setup.py --check "navy kicks size 7"   # one test search
```

Testing the wiring without a key: `REZOLVE_MOCK=1 python3 evaluate.py --agent ../../agent/agent.py --data ../../tests/stress/holdout.jsonl`. The stand-in matches by character trigrams, so it shows the plumbing works; it says nothing about how well the real Rezolve search performs.

| Holdout (600) | Score | Accuracy | Wrong commits | Searches |
|---|---|---|---|---|
| Offline | 41.4 | 0.997 | 1 | 1.033 |
| Stand-in fallback | 41.5 | 1.000 | 1 | 1.037 |

Dev and stress scores are unchanged (43.1 and 42.1): no request there triggers the fallback.

Safety design: any word the parser does not know, or only guessed at (a repaired typo, an "-ish" colour, a generic word like "shoes"), rules out an early commit for that request; the final answer still uses the guess.
