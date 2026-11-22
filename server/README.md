# ShelfSense service

The agent behind a streaming HTTP API, with a live demo page. Python standard library only.

```bash
python3 server/app.py                 # http://localhost:8080 — fashion (kit) and electronics shops
python3 server/app.py --shop mystore=shop/catalogue.csv:shop/config.json:shop/samples.jsonl --log events.jsonl
docker build -t shelfsense . && docker run -p 8080:8080 shelfsense
```

Open http://localhost:8080 for the demo:
- **Speak** a request (Chrome or Edge; uses the browser's speech recognition, `en-IN`).
- **Type** one and press *Stream it* to send it a word at a time.
- **Try a sample** to replay a request from the shop's test set.

As words arrive you see what the agent understood, how many products still fit, and the product card the moment it commits, with how many words early that was.

## API

| Call | Body | Returns |
|---|---|---|
| `POST /v1/sessions` | `{"shop": "fashion", "mode": "auto"}` | `{"session": id, ...}` |
| `POST /v1/sessions/{id}/words` | `{"words": ["show", "me"]}` | one step per word, plus session state |
| `POST /v1/sessions/{id}/transcript` | `{"text": "show me navy", "final": false}` | steps for newly settled words; `revised: true` if an earlier word changed |
| `POST /v1/sessions/{id}/finish` | | final product, when it was committed, searches used |
| `GET /v1/sessions/{id}` · `DELETE /v1/sessions/{id}` | | state · delete |
| `GET /v1/shops` · `GET /v1/shops/{shop}/samples?n=8` | | detected profiles · example requests |
| `GET /health` · `GET /metrics` | | liveness · counts and per-word latency p50/p95/p99 |

A step looks like:

```json
{"word": "if", "n": 15, "ms": 0.19, "filters": {"brand": "Loomsy", "category": "sneakers", "colour": "navy", "size": "7", "max_price": 4500},
 "candidates": 1, "leading": "P0086", "confidence": 1.0,
 "commit": {"id": "P0086", "title": "Loomsy Suede 4 Sneakers, Navy", "price": 4449, "attributes": {...}}}
```

## Speech input

Speech-to-text keeps revising its latest words ("four" becomes "fourteen hundred"). `/transcript` takes the whole running transcript each time:
- The last word of an interim transcript is not read until it settles (or `final: true`).
- If an earlier word changed, the session re-reads the request from the start. That costs microseconds, and searches are cached per session, so it doesn't search again.
- A product already shown is not silently withdrawn.

Speech has no punctuation, so sessions default to the `auto` commit mode, which uses the stricter speech rules until punctuation appears (see [agent/README.md](../agent/README.md)).

## Operations

- **Sessions** live in memory and expire after 15 idle minutes; a finished session is removed. One process serves every loaded shop; each shop's catalogue is parsed once at start-up.
- **`--log`** appends one JSON line per finished request: words, committed product and word number, final product, searches, revisions. That is the data for checking wrong commits in production.
- **Errors** return JSON with a message; tracebacks never reach the client, and are logged.
- **Rezolve Labs** is used only for the kit shop, whose catalogue is in the knowledge base, and only when `REZOLVE_API_KEY` is set.
- **Measured** on a laptop: about 0.06 ms per word in the agent (p95 0.24 ms). Each request uses about 1 search.
- **Not yet built**: authentication and rate limiting (put it behind a gateway), shared session storage for running several instances, and HTTPS (terminate at the proxy).
