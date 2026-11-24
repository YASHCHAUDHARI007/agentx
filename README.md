# ShelfSense

[![CI](https://github.com/YASHCHAUDHARI007/shelfsense/actions/workflows/ci.yml/badge.svg)](https://github.com/YASHCHAUDHARI007/shelfsense/actions/workflows/ci.yml)

A shopping agent that finds the right product before the shopper finishes the sentence.

Our entry for **AgentX: The Agentic Commerce Challenge** (Techfest 2026-27, IIT Bombay, with Rezolve Ai), Challenge 1: Anticipatory Commerce. Requests arrive one word at a time; ShelfSense reads the shopper's filters as they speak, searches early, and commits to a product only when it is safe to.

| | Kit baseline | ShelfSense |
|---|---|---|
| Score on `dev.jsonl` | 20.0 | **44.3** |
| Accuracy | 0.527 | **1.000** |
| Wrong commits | 0 | **0** |
| Earliness (best possible 16.3%) | 0% | 7.4% |
| Searches per request | 1.53 | 1.04 |

```bash
cd starter_kit/ps1-anticipatory-commerce
python3 evaluate.py --agent ../../agent/agent.py
```

Live demo and API (speak or type a request, watch the product appear before you finish):

```bash
make web                     # once: build the Next.js front end (needs Node.js 20+)
python3 server/app.py        # then open http://localhost:8080
```

Without Node.js, `python3 server/app.py` serves a single-file version of the same page.

- [`agent/`](agent/README.md): the agent (parser, commit policy, search, and the Rezolve Labs fallback)
- [`server/`](server/README.md): streaming HTTP API with speech support
- [`web/`](web/README.md): the live demo, Next.js (React, TypeScript), served by the Python service as static files
- `tools/build_profile.py`, `tools/evaluate_catalogue.py`: onboard and score any shop's catalogue
- `tests/`: 49 tests (parser, commit policy, final choice, Rezolve resilience, API, score floors), stress, holdout and unseen-product-word sets, and a second (electronics) catalogue
- `tools/rezolve_setup.py`: uploads the catalogue to Rezolve Labs once you have an API key
- [`submission/`](submission/README.md): Round 1 package (abstract, architecture note, dev outputs, video script)
- [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md): research, challenge comparison and plan
- `starter_kit/`: the organisers' starter kits for both challenges

Works on any shop's catalogue: columns, filters and vocabulary are detected from the CSV, plus an optional short synonym config. On a second, unrelated electronics catalogue it reaches accuracy 1.000 with 1 wrong commit in 300 requests ([details](agent/README.md#any-catalogue)). It is also safe on unpunctuated, speech-style input.

Rezolve Labs semantic search is the fallback for requests the parser can't pin down. It is off until `REZOLVE_API_KEY` is set in `.env` (see [agent/README.md](agent/README.md#rezolve-labs-fallback)).

## Production readiness

- **CI** on every push ([workflow](.github/workflows/ci.yml)): tests on Python 3.10, 3.12 and 3.13; the front end linted, type-checked and built; the official evaluator on dev with a **score gate** (fails below 44.2 or on any wrong commit); and the Docker image built, started and checked end to end.
- **Service**: API keys, per-client rate limits, a cap on open sessions, request ids, security headers, graceful shutdown, Prometheus metrics and an [OpenAPI 3.1 contract](server/openapi.json). All off-by-default settings are environment variables ([server/README.md](server/README.md#production-settings)).
- **Rezolve Labs** calls retry transient failures and stop for 30 s after repeated ones (circuit breaker), so an outage never slows the shopper; every attempt is counted as a search.

```bash
make test     # all tests
make gate     # official evaluator + score gate
make serve    # demo on http://localhost:8080
```

Agent and service: Python 3.10+, standard library only. Front end: Next.js 16, React 19, TypeScript. MIT licence.
