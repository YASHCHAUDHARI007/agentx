# ShelfSense service

The agent behind a streaming HTTP API, plus the live demo. The service is Python standard library only; the demo is the Next.js app in [`web/`](../web/README.md), which this server serves once built (`make web`). Without a build it serves the single-file page in `static/`, so the service runs with Python alone.

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
| `GET /health` · `GET /metrics` | | liveness · counts and per-word latency p50/p95/p99 (JSON, or Prometheus text with `?format=prometheus`) |
| `GET /openapi.json` | | the API contract, OpenAPI 3.1 ([openapi.json](openapi.json)) |

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

## Production settings

All set by environment variables, so the same image runs open on a laptop and locked down in production:

| Variable | Default | Effect |
|---|---|---|
| `SHELFSENSE_API_KEYS` | unset (open) | Comma-separated keys. When set, `/v1/*` and `/metrics` need `X-API-Key: <key>` or `Authorization: Bearer <key>`; otherwise 401. `/health`, the page and `/openapi.json` stay open. Keys are compared in constant time. |
| `SHELFSENSE_RATE` | `20` | Requests per second per API key (or per IP when keys are off), bursts up to 2x. Over the limit: 429 with `Retry-After`. `0` turns it off. |
| `SHELFSENSE_TRUST_PROXY` | unset | `1` reads the client IP from `X-Forwarded-For`. Only behind your own proxy. |
| `SHELFSENSE_MAX_SESSIONS` | `1000` | Open sessions per process; above it, new sessions get 503. |
| `SHELFSENSE_CORS_ORIGINS` | unset | Comma-separated origins allowed to call the API from another origin (`http://localhost:3000` for `next dev`). |
| `REZOLVE_API_KEY`, `REZOLVE_KB_ID` | unset | Turn on the Rezolve Labs fallback for the kit shop. |

With keys on, open the demo page once as `http://host:8080/?key=<key>`; the page keeps the key in that browser and asks for one on a 401.

```bash
SHELFSENSE_API_KEYS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))") python3 server/app.py
```

## Operations

- **Sessions** live in memory and expire after 15 idle minutes; a finished session is removed. One process serves every loaded shop; each shop's catalogue is parsed once at start-up.
- **`--log`** appends one JSON line per finished request: words, committed product and word number, final product, searches, revisions. That is the data for checking wrong commits in production.
- **Errors** return JSON with a message and the request id; tracebacks never reach the client, and are logged with the same id.
- **Request ids**: every response carries `X-Request-Id` (the caller's, if it sent one), so a client report can be matched to the log.
- **Headers**: `nosniff`, `no-referrer`, and on the page a Content-Security-Policy that allows only this origin and forbids framing.
- **Limits**: bodies over 64 KB get 413; a session reads at most 200 words and then reports `truncated: true`.
- **Shutdown**: on SIGTERM (`docker stop`, Kubernetes) the server stops accepting, finishes in-flight requests and exits 0.
- **Rezolve Labs outages**: searches retry twice on timeouts, 429 and 5xx (with backoff, honouring `Retry-After`); after 3 failed searches in a row the client stops calling for 30 s, so an outage costs the shopper nothing and spends no credits. `/metrics` reports calls, failures and whether the circuit is open.
- **Rezolve Labs** is used only for the kit shop, whose catalogue is in the knowledge base, and only when `REZOLVE_API_KEY` is set.
- **Measured** on a laptop: about 0.03 ms per word in the agent (p95 0.15 ms), 0.37 ms of CPU per request. Each request uses about 1 search.
- **Not yet built**: shared session storage (for example Redis) for running several instances behind a load balancer, WebSocket streaming instead of one POST per word, and HTTPS (terminate it at the proxy or load balancer).
