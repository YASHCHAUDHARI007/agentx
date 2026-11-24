// The read-outs: words heard, filters understood, counters, and the product card.
import type { Filters, Product, Step } from "@/lib/api";
import { meanMs, rupees } from "@/lib/view";
import s from "./demo.module.css";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

/** For each word: did it set or change a filter? */
function valueWords(steps: Step[]): boolean[] {
  const seen: Filters = {};
  const out: boolean[] = [];
  for (const st of steps) {
    out.push(Object.keys(st.filters).some((k) => seen[k] !== st.filters[k]));
    Object.assign(seen, st.filters);
  }
  return out;
}

export function WordStream({ steps, commitAt, pending }: { steps: Step[]; commitAt: number | null; pending: string | null }) {
  const changed = valueWords(steps);
  return (
    <div className={s.words} aria-live="polite">
      {steps.map((st, i) => {
        return (
          <span
            key={st.n}
            className={cx(
              s.w,
              changed[i] && s.wValue,
              st.n === commitAt && s.wCommit,
              commitAt !== null && st.n > commitAt && s.wAfter,
            )}
          >
            {st.word}
          </span>
        );
      })}
      {pending && <span className={cx(s.w, s.wPending)}>{pending}…</span>}
    </div>
  );
}

export function FilterChips({ filters, previous }: { filters: Filters | undefined; previous: Filters }) {
  if (!filters) return <div className={s.filters} />;
  const entries = Object.entries(filters);
  return (
    <div className={s.filters}>
      {entries.length === 0 && <span className={s.tag}>nothing yet</span>}
      {entries.map(([k, v]) => (
        <span key={k} className={cx(s.f, previous[k] !== v && s.fChanged)}>
          <small>{k === "max_price" ? "budget" : k}</small>
          <b>{k === "max_price" ? `under ${rupees(v)}` : v}</b>
        </span>
      ))}
    </div>
  );
}

export function Stats({ candidates, ms, searches }: { candidates: number | null; ms: number[]; searches: number }) {
  const items: [string, string | number][] = [
    ["products still fit", candidates ?? "–"],
    ["ms per word (agent)", meanMs(ms)],
    ["searches", searches],
  ];
  return (
    <div className={s.stats}>
      {items.map(([k, v]) => (
        <div key={k} className={s.stat}>
          <div className={s.statValue}>{v}</div>
          <div className={s.statKey}>{k}</div>
        </div>
      ))}
    </div>
  );
}

export function ProductCard({ card, commitAt, when }: { card: Product | null; commitAt: number | null; when: string }) {
  if (!card) {
    return (
      <div className={s.card}>
        <div className={s.empty}>The product appears here as soon as the agent is sure.</div>
      </div>
    );
  }
  return (
    <div className={s.cardFound} key={card.id}>
      <span className={s.badge}>Found at word {commitAt}</span>
      <h3 className={s.cardTitle}>{card.title}</h3>
      <div className={s.price}>{rupees(card.price)}</div>
      <div className={s.attrs}>
        {Object.entries(card.attributes).map(([k, v]) => (
          <span key={k}>
            {k}: {v}
          </span>
        ))}
      </div>
      <div className={s.when}>{when}</div>
    </div>
  );
}
