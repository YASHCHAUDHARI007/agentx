# ShelfSense agent (Challenge 1: Anticipatory Commerce)

Standard library only. From the kit folder:

```bash
cd starter_kit/ps1-anticipatory-commerce
python3 evaluate.py --agent ../../agent/agent.py
```

| File | Role |
|---|---|
| `catalogue.py` | Reads any shop's catalogue CSV (plus an optional config) into a profile: columns, filters, values and the phrases that name them; also a local search over it |
| `lexicon.py` | General shopping language: English and Hinglish synonym packs, number words, cue words |
| `parser.py` | Re-reads the words so far into filters using the shop's `Vocab`; last mention wins (handles corrections); flags a prefix that ends mid-thought |
| `policy.py` | Commit-or-wait rule |
| `agent.py` | The `Agent` class `evaluate.py` loads |
| `rezolve.py` | Rezolve Labs semantic-search client (fallback only; off when no key is set) |
| `rezolve_mock.py` | Local stand-in for Rezolve, used only to test the wiring (`REZOLVE_MOCK=1`) |

How a request flows:
1. Every word, the whole prefix is parsed again into category, colour, brand, size and budget.
2. Once category and colour are known, one counted search fetches every product of that category and colour. Brand, size and budget then narrow that list locally, so most requests need exactly one search.
3. When one product alone fits what has been said, a later *new* constraint cannot change it; only a correction can.
4. Commit rule (`policy.py`): if the shopper has already corrected something, commit at once (requests correct themselves at most once in dev). If a budget number made the match unique mid-sentence, commit at once. Otherwise wait one more word: filler ("for my brother", "thanks") or a value with no punctuation after it. A word ending in "." or "," never counts, because corrections almost always open a new clause ("size 8, | I mean size 7"). Never commit while a correction word is still waiting for its new value.

Knobs (environment variables): `AGENT_COMMIT_MODE` (`auto` (default), `next`, `speech`, `safe` or `instant`, see below), `SHELFSENSE_CATALOGUE` / `SHELFSENSE_CONFIG` (which shop), `AGENT_WAIT_WORDS` (default 1) and `AGENT_MAX_SEARCHES` (default 3, the per-request search cap).

## Results

| Test set | Requests | Score | Accuracy | Wrong commits | Earliness | Searches |
|---|---|---|---|---|---|---|
| Kit baseline on dev | 300 | 20.0 | 0.527 | 0 | 0% | 1.53 |
| **dev.jsonl** (kit) | 300 | **44.3** | 1.000 | 0 | 7.4% (best possible 16.3%) | 1.04 |
| Stress set (our generator, used for tuning) | 600 | 42.6 | 1.000 | 0 | 4.5% | 1.03 |
| **Holdout** (fresh phrasings and seed) | 600 | **42.0** | 1.000 | 1 | 3.7% | 1.03 |
| **Electronics shop** (second catalogue, unpunctuated) | 300 | **42.0** | 1.000 | 1 | 4.1% (best possible 19.1%) | 1.06 |
| **Unseen product words** (dev with slang the lexicon lacks: "low tops", "parka") | 300 | 34.0 | 0.837 | 0 | | 1.04 |
| Stress set *before* the robustness fixes | 600 | 36.4 | 0.867 | 0 | 2.9% | 1.02 |

Commit modes compared (score, wrong commits in brackets). "No punctuation" is the same request with every comma and full stop removed, as raw speech-to-text would give it:

| `AGENT_COMMIT_MODE` | dev | stress | holdout | dev, no punctuation | electronics shop |
|---|---|---|---|---|---|
| `safe` (one filler word; the first policy) | 44.5 (0) | 43.0 (0) | 42.3 (1) | 43.5 (3) | 37.7 (17) |
| `next` (punctuation-based rules) | 44.8 (0) | 43.2 (0) | 42.7 (1) | 43.5 (4) | 37.2 (19) |
| **`auto` (default)** | 44.3 (0) | 42.6 (0) | 42.0 (1) | 43.5 (0) | 42.0 (1) |
| `instant` (commit at once on any value mid-sentence) | 45.2 (3) | 44.5 (2) | 43.5 (4) | 44.1 (7) | 31.2 (56) |

`next` relies on corrections starting a new clause after a comma or full stop. Raw speech has no punctuation, and a correction can follow a complete request directly ("... budget 50k | actually make it 256gb"); on the electronics shop that cost 19 wrong commits. `auto` uses the stricter speech rules until a request shows punctuation, so it gives up 0.5 to 0.7 points on the punctuated kit sets for far fewer wrong commits elsewhere. For a pure kit-benchmark run, `AGENT_COMMIT_MODE=next`. Per-word latency is about 0.03 ms.

What was tried and rejected (measured on all five sets): committing as soon as a budget phrase opens after a unique match ("..., below") scored higher on dev but made 31 wrong commits, because corrections usually follow the budget ("within 1500, no, change that to Urbanyx"); counting value tails ("M | size", "6 | UK") as the settling word made 10. Both stay out. Kept: a spoken amount ("two thousand five hundred") now commits on the word that completes it, like a typed one, and "for" after a stated budget opens a purpose ("for office"), not a value.

The two test sets come from `tests/stress/make_stress.py`: catalogue-based requests in the dev format with wording the parser was not written for (typos like "nevy", "-ish" colours, "UK9", "W32", "smol", "do hazaar", "tee shirt", new openers, closers and correction phrases). The holdout set uses a different seed and a separate bank of phrasings; it was used once to find the two commit-safety fixes (words opening a new clause, and words like "brand" that hang off a value, no longer count as the request winding down), so treat its numbers as slightly optimistic too.

```bash
python3 tests/stress/make_stress.py              # stress.jsonl
python3 tests/stress/make_stress.py --holdout    # holdout.jsonl
cd starter_kit/ps1-anticipatory-commerce
python3 evaluate.py --agent ../../agent/agent.py --data ../../tests/stress/holdout.jsonl
```

Product words the lexicon has never heard of ("racing flats", "sneaks", "low tops") leave the parser without a category, or with only a guess from a generic word ("shoes", "tops"). The final choice then does not trust the guess as a filter: among the products that fit everything else, it picks the one whose own text (title, category, description) best matches the request's words, fuzzily by character trigrams, and then the one priced nearest 0.87 x the budget (the median target price / budget over 1,143 requests). On the unseen-product-word set this took accuracy from 0.707 to 0.837 with no wrong commits; on holdout from 0.997 to 1.000. Rezolve Labs semantic search covers the rest (next section).

## Any catalogue

Nothing in the agent is tied to the starter kit's catalogue. `catalogue.py` reads a shop's CSV and works out:
- the id, price and title columns, and which columns are filters (short text values, not free text or numbers like ratings);
- which column plays which part: category, colour, size, brand (by name, or set in the config);
- which slots the first search fetches (category + colour by default) and the order filters are relaxed in;
- every phrase that names every value: built-in English/Hinglish packs where they apply, automatic variants ("t-shirt" / "tshirt", "128GB" / "128 gigs", "grey" / "gray", plurals), and the shop's own words from an optional config.

Onboarding a new shop:

```bash
python3 tools/build_profile.py shop/catalogue.csv --out shop/config.json   # detect, list values needing synonyms
python3 tools/evaluate_catalogue.py shop/catalogue.csv --config shop/config.json --data shop/requests.jsonl
SHELFSENSE_CATALOGUE=shop/catalogue.csv SHELFSENSE_CONFIG=shop/config.json  # agent default for that shop
```

Proof on a second, unrelated shop (`tests/catalogues/electronics/`, made by its `make.py`): 158 phones, laptops, tablets, earbuds and smartwatches, with different column names (`sku`, `name`, `type`, `color`, `storage`, `price_inr`), unit values ("128GB", "1TB") and a `rating` column that must not become a filter. Its 300 requests mirror the dev mix (corrections, late constraints, budgets in words) but are unpunctuated, like speech.

| Electronics shop | Accuracy | Wrong commits | Score | Type read correctly |
|---|---|---|---|---|
| Automatic profile only | 0.997 | 0 | 40.6 | 38% |
| With the shop's 5-line synonym config | 1.000 | 1 | 42.0 | 100% |

The only shop-specific input was `config.json`: the words customers use that the catalogue doesn't ("mobile" for smartphones, "tab" for tablets). In production these can be generated offline by an LLM or Rezolve Labs, then reviewed.

The parser keeps no global state: each shop gets its own `Vocab`, so one process can serve several shops (`Agent(tools, profile=Profile.load(...))`).

Tests: `python3 -m unittest discover tests` checks profile detection on both catalogues, unit-value parsing, parser and policy cases, and score floors on kit dev, stress, holdout, the unseen-product-word set and the electronics shop.

## Rezolve Labs fallback

Rezolve Labs semantic search is used only when the parser's reading does not pin down one product: the final read leaves no unique match, or the colour was never understood. In those cases `finish()` sends the whole request to Rezolve with only the filters we are sure of (a guessed category is left out), and prefers a Rezolve result that also fits the local reading. Each call is counted with `tools.record_search()`.

Rules:
- It never causes an early commit. It only affects the final answer.
- Clean requests never call it. With the local stand-in it ran on 0 of 300 dev, 0 of 600 stress and 8 of 600 holdout requests (85 of 300 on the unseen-product-word set, which is built to need it), so it costs very few credits.
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
| Offline | 42.0 | 1.000 | 1 | 1.03 |
| Stand-in fallback | 41.9 | 0.998 | 1 | 1.05 |

| Unseen product words (300) | Score | Accuracy | Wrong commits | Searches |
|---|---|---|---|---|
| Offline | 34.0 | 0.837 | 0 | 1.04 |
| Stand-in fallback | 35.7 | 0.897 | 0 | 1.36 |

Dev and stress scores are unchanged by the fallback: no request there triggers it. On holdout the stand-in, which only compares spellings, reads "casual trainers" as running shoes and overrules a right local answer once; a real semantic search is expected to do better, but that needs the key to measure.

Safety design: any word the parser does not know, or only guessed at (a repaired typo, an "-ish" colour, a generic word like "shoes"), rules out an early commit for that request; the final answer still uses the guess.
