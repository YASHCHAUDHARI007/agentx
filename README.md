# ShelfSense

A shopping agent that finds the right product before the shopper finishes the sentence.

Our entry for **AgentX: The Agentic Commerce Challenge** (Techfest 2026-27, IIT Bombay, with Rezolve Ai), Challenge 1: Anticipatory Commerce. Requests arrive one word at a time; ShelfSense reads the shopper's filters as they speak, searches early, and commits to a product only when it is safe to.

| | Kit baseline | ShelfSense |
|---|---|---|
| Score on `dev.jsonl` | 20.0 | **44.1** |
| Accuracy | 0.527 | **1.000** |
| Wrong commits | 0 | **0** |
| Earliness (best possible 16.3%) | 0% | 7.0% |
| Searches per request | 1.53 | 1.04 |

```bash
cd starter_kit/ps1-anticipatory-commerce
python3 evaluate.py --agent ../../agent/agent.py
```

Live demo and API (speak or type a request, watch the product appear before you finish):

```bash
python3 server/app.py        # then open http://localhost:8080
```

- [`agent/`](agent/README.md): the agent (parser, commit policy, search, and the Rezolve Labs fallback)
- [`server/`](server/README.md): streaming HTTP API with speech support, and the live demo page
- `tools/build_profile.py`, `tools/evaluate_catalogue.py`: onboard and score any shop's catalogue
- `tests/`: regression tests, stress and holdout sets, and a second (electronics) catalogue
- `tools/rezolve_setup.py`: uploads the catalogue to Rezolve Labs once you have an API key
- [`submission/`](submission/README.md): Round 1 package (abstract, architecture note, dev outputs, video script)
- [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md): research, challenge comparison and plan
- `starter_kit/`: the organisers' starter kits for both challenges

Works on any shop's catalogue: columns, filters and vocabulary are detected from the CSV, plus an optional short synonym config. On a second, unrelated electronics catalogue it reaches accuracy 1.000 with 1 wrong commit in 300 requests ([details](agent/README.md#any-catalogue)). It is also safe on unpunctuated, speech-style input.

Rezolve Labs semantic search is the fallback for requests the parser can't pin down. It is off until `REZOLVE_API_KEY` is set in `.env` (see [agent/README.md](agent/README.md#rezolve-labs-fallback)).

Python 3.9+, standard library only. MIT licence.
