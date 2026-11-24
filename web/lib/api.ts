// Typed client for the ShelfSense API (contract: server/openapi.json).

export type Filters = Record<string, string | number>;

export interface Product {
  id: string;
  title: string;
  price: number;
  attributes: Record<string, string>;
}

export interface Step {
  word: string;
  n: number;
  ms: number;
  filters: Filters;
  candidates: number | null;
  leading: string | null;
  confidence: number;
  commit?: Product;
}

export interface SessionState {
  session: string;
  shop: string;
  mode: string;
  words: number;
  committed: Product | null;
  committed_at: number | null;
  searches: number;
  revisions: number;
  truncated: boolean;
}

export interface Update {
  steps: Step[];
  state: SessionState;
  revised?: boolean;
}

export interface FinishResult extends SessionState {
  final: Product | null;
  early_share: number;
  changed_after_commit: boolean;
  rezolve: { reason: string; answer: string | null }[];
}

export interface ShopInfo {
  name: string;
  products: number;
  slots: string[];
  roles: Record<string, string>;
}

export type Mode = "auto" | "next" | "speech";

// Same origin by default (the Python service serves this page). For `npm run dev`, point it at
// the API: NEXT_PUBLIC_API_BASE=http://localhost:8080 (and start the API with
// SHELFSENSE_CORS_ORIGINS=http://localhost:3000).
const BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");

// When the service requires API keys (SHELFSENSE_API_KEYS), open the page once as /?key=...;
// the key is kept in this browser only.
const KEY_STORE = "shelfsense_api_key";

function readKey(): string {
  if (typeof window === "undefined") return "";
  const fromUrl = new URLSearchParams(window.location.search).get("key");
  try {
    if (fromUrl) {
      window.localStorage.setItem(KEY_STORE, fromUrl);
      window.history.replaceState(null, "", window.location.pathname);
    }
    return fromUrl || window.localStorage.getItem(KEY_STORE) || "";
  } catch {
    return fromUrl || "";
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly requestId?: string,
  ) {
    super(message);
  }
}

async function call<T>(method: string, path: string, body?: unknown, retried = false): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const key = readKey();
  if (key) headers["X-API-Key"] = key;
  const r = await fetch(BASE + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (r.status === 401 && !retried && typeof window !== "undefined") {
    const k = window.prompt("This ShelfSense service needs an API key:");
    if (k) {
      try {
        window.localStorage.setItem(KEY_STORE, k.trim());
      } catch {
        /* storage blocked: the key is used for this call only */
      }
      return call<T>(method, path, body, true);
    }
  }
  if (!r.ok) throw new ApiError(data.error || r.statusText, r.status, data.request_id);
  return data as T;
}

export const api = {
  shops: () => call<{ shops: ShopInfo[] }>("GET", "/v1/shops").then((d) => d.shops),
  samples: (shop: string, n = 1) =>
    call<{ samples: string[] }>("GET", `/v1/shops/${encodeURIComponent(shop)}/samples?n=${n}`).then((d) => d.samples),
  start: (shop: string, mode: Mode) => call<SessionState>("POST", "/v1/sessions", { shop, mode }),
  words: (id: string, words: string[]) => call<Update>("POST", `/v1/sessions/${id}/words`, { words }),
  transcript: (id: string, text: string, final: boolean) =>
    call<Update>("POST", `/v1/sessions/${id}/transcript`, { text, final }),
  finish: (id: string) => call<FinishResult>("POST", `/v1/sessions/${id}/finish`),
  drop: (id: string) => call<{ deleted: string }>("DELETE", `/v1/sessions/${id}`),
};
