"use client";
// The live demo: type, replay a sample, or speak a request, and watch the agent commit to a
// product before the request ends. Every word goes to the ShelfSense API as it arrives.
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { api, type Mode, type ShopInfo } from "@/lib/api";
import { emptyView, reduce } from "@/lib/view";
import { useSpeech } from "@/hooks/useSpeech";
import { FilterChips, ProductCard, Stats, WordStream } from "./Panels";
import s from "./demo.module.css";

const WORD_GAP_MS = 320; // roughly the pace of speech
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

const PLACEHOLDER: Record<string, string> = {
  electronics: "Type a request, e.g. Nexo blue mobile with 256 gigs under 50k",
};
const DEFAULT_PLACEHOLDER = "Type a request, e.g. show me navy Loomsy sneakers size 7 under 5000";

const MODES: { value: Mode; label: string }[] = [
  { value: "auto", label: "auto (safe for speech)" },
  { value: "next", label: "next (punctuated text)" },
  { value: "speech", label: "speech (strictest)" },
];

export default function Demo() {
  const [view, dispatch] = useReducer(reduce, emptyView);
  const [shops, setShops] = useState<ShopInfo[]>([]);
  const [shop, setShop] = useState("");
  const [mode, setMode] = useState<Mode>("auto");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const session = useRef<string | null>(null);
  const busyRef = useRef(false);
  const speech = useSpeech();

  const hint = useCallback((t: string, error = false) => dispatch({ type: "hint", text: t, error }), []);

  useEffect(() => {
    api
      .shops()
      .then((list) => {
        setShops(list);
        setShop((cur) => cur || list[0]?.name || "");
      })
      .catch((e) => hint(`Cannot reach the ShelfSense API: ${message(e)}`, true));
    return () => {
      if (session.current) api.drop(session.current).catch(() => {});
    };
  }, [hint]);

  const claim = () => {
    if (busyRef.current) return false;
    busyRef.current = true;
    setBusy(true);
    return true;
  };
  const release = () => {
    busyRef.current = false;
    setBusy(false);
  };

  const newSession = async () => {
    if (session.current) api.drop(session.current).catch(() => {});
    session.current = null;
    dispatch({ type: "reset" });
    session.current = (await api.start(shop, mode)).session;
    return session.current;
  };

  const finish = async (id: string) => {
    const out = await api.finish(id);
    session.current = null;
    dispatch({ type: "finish", out });
  };

  const stream = async (request: string) => {
    if (!request.trim() || !claim()) return;
    try {
      const id = await newSession();
      hint("Streaming one word at a time, as if spoken.");
      for (const word of request.trim().split(/\s+/)) {
        dispatch({ type: "update", out: await api.words(id, [word]) });
        await sleep(WORD_GAP_MS);
      }
      await finish(id);
      hint("");
    } catch (e) {
      hint(`Error: ${message(e)}`, true);
    } finally {
      release();
    }
  };

  const sample = async () => {
    if (busyRef.current || !shop) return;
    try {
      const [first] = await api.samples(shop, 1);
      if (first) {
        setText(first);
        await stream(first);
      }
    } catch (e) {
      hint(`Error: ${message(e)}`, true);
    }
  };

  const toggleMic = async () => {
    if (speech.listening) {
      speech.stop();
      return;
    }
    if (!claim()) return;
    let id: string;
    try {
      id = await newSession();
    } catch (e) {
      hint(`Error: ${message(e)}`, true);
      release();
      return;
    }
    hint("Listening… speak a shopping request, then pause or tap the mic.");
    let sending: Promise<void> = Promise.resolve();
    speech.start({
      onTranscript: (said, final) => {
        const words = said.split(/\s+/);
        sending = sending
          .then(async () => {
            const out = await api.transcript(id, said, false);
            dispatch({ type: "update", out, pending: final ? null : words[words.length - 1] });
          })
          .catch((e) => hint(`Error: ${message(e)}`, true));
      },
      onError: (m) => hint(m, true),
      onEnd: async (said) => {
        await sending;
        try {
          if (said) {
            dispatch({ type: "update", out: await api.transcript(id, said, true) });
            await finish(id);
          }
          hint("");
        } catch (e) {
          hint(`Error: ${message(e)}`, true);
        } finally {
          release();
        }
      },
    });
  };

  const lastFilters = view.steps.at(-1)?.filters;

  return (
    <div className={s.wrap}>
      <header className={s.header}>
        <h1 className={s.title}>
          Shelf<span>Sense</span>
        </h1>
        <div className={s.tag}>finds the product before you finish the sentence</div>
        <div className={s.controls}>
          <select
            className={s.select}
            aria-label="Shop"
            value={shop}
            onChange={(e) => {
              setShop(e.target.value);
              dispatch({ type: "reset" });
            }}
          >
            {shops.map((sh) => (
              <option key={sh.name} value={sh.name}>
                {sh.name} · {sh.products} products
              </option>
            ))}
          </select>
          <select className={s.select} aria-label="Commit mode" value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
            {MODES.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
      </header>

      <section className={s.panel}>
        <div className={s.inputRow}>
          <button
            className={speech.listening ? s.micOn : s.mic}
            onClick={toggleMic}
            disabled={!speech.supported || (busy && !speech.listening)}
            title={speech.supported ? "Speak a request" : "Speech input needs Chrome or Edge"}
            aria-label={speech.listening ? "Stop listening" : "Speak a request"}
            aria-pressed={speech.listening}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <rect x="9" y="2" width="6" height="12" rx="3" />
              <path d="M5 10a7 7 0 0 0 14 0M12 17v5" />
            </svg>
          </button>
          <input
            className={s.text}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") stream(text);
            }}
            placeholder={PLACEHOLDER[shop] ?? DEFAULT_PLACEHOLDER}
            aria-label="Shopping request"
            autoComplete="off"
          />
          <button className={s.btnPrimary} onClick={() => stream(text)} disabled={busy}>
            Stream it
          </button>
          <button className={s.btn} onClick={sample} disabled={busy || !shop}>
            Try a sample
          </button>
        </div>
        <div className={view.hintError ? s.hintError : s.hint} role="status">
          {view.hint}
        </div>
      </section>

      <div className={s.grid}>
        <section className={s.panel}>
          <p className={s.label}>What the agent hears</p>
          <WordStream steps={view.steps} commitAt={view.commitAt} pending={view.pending} />
          <p className={s.labelSpaced}>What it understood</p>
          <FilterChips filters={lastFilters} previous={view.prevFilters} />
          <Stats candidates={view.candidates} ms={view.ms} searches={view.searches} />
        </section>
        <section className={s.panel}>
          <p className={s.label}>Product</p>
          <ProductCard card={view.card} commitAt={view.commitAt} when={view.when} />
          <div className={view.finalWarn ? s.finalWarn : s.final}>{view.final}</div>
        </section>
      </div>

      <footer className={s.footer}>
        Every word goes to the ShelfSense API (<code>POST /v1/sessions/{"{id}"}/words</code> or <code>/transcript</code> for
        speech). The agent commits only when no later word can change the answer except a correction, and waits while one
        could still come.
      </footer>
    </div>
  );
}
