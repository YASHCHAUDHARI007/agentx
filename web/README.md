# ShelfSense web

The live demo, in Next.js 16 (App Router), React 19 and TypeScript. Speak, type or replay a request and watch the agent commit to a product before the request ends.

It is a static export: `npm run build` writes plain HTML, JS and CSS to `out/`, and the Python service (`server/app.py`) serves those files next to its API. One process and one port in production, with no Node.js at run time. The Docker image builds it in a first stage.

```bash
npm ci
npm run build          # -> out/, picked up by `python3 server/app.py` on the next start
```

Development with hot reload (from the repository root):

```bash
make web-dev           # API on :8080 with CORS for :3000, Next.js dev server on :3000
```

or by hand:

```bash
SHELFSENSE_CORS_ORIGINS=http://localhost:3000 python3 server/app.py
NEXT_PUBLIC_API_BASE=http://localhost:8080 npm run dev
```

## Layout

| Path | What it is |
|---|---|
| `app/layout.tsx`, `app/page.tsx` | the single page |
| `components/Demo.tsx` | the demo: input, streaming, microphone, session lifecycle |
| `components/Panels.tsx` | read-outs: words heard, filters, counters, product card |
| `components/demo.module.css`, `app/globals.css` | styles; colour tokens with light and dark themes |
| `lib/api.ts` | typed client for the ShelfSense API (contract: `server/openapi.json`), API-key handling |
| `lib/view.ts` | one reducer that folds every API reply into what the page shows |
| `hooks/useSpeech.ts` | browser speech-to-text (Web Speech API), reporting the running transcript |

When the service requires API keys, open the page once as `/?key=<key>`; the key is kept in that browser only, and the page asks for one on a 401.

Speech input needs Chrome or Edge. The microphone button is disabled in other browsers; typing and samples work everywhere.
