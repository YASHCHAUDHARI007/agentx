// What the page shows, as one reducer: every API reply is folded in here.
import type { FinishResult, Filters, Product, Step, Update } from "./api";

export interface View {
  steps: Step[];
  commitAt: number | null; // word number of the early commit
  card: Product | null;
  when: string; // "3 of 10 words before you finished"
  final: string; // note under the card
  finalWarn: boolean;
  searches: number;
  candidates: number | null;
  prevFilters: Filters; // filters before the latest update, to highlight what changed
  ms: number[]; // agent time per word
  pending: string | null; // interim speech word, not read yet
  hint: string;
  hintError: boolean;
}

export const emptyView: View = {
  steps: [],
  commitAt: null,
  card: null,
  when: "",
  final: "",
  finalWarn: false,
  searches: 0,
  candidates: null,
  prevFilters: {},
  ms: [],
  pending: null,
  hint: "",
  hintError: false,
};

export type Action =
  | { type: "reset" }
  | { type: "update"; out: Update; pending?: string | null }
  | { type: "finish"; out: FinishResult }
  | { type: "hint"; text: string; error?: boolean };

export function reduce(v: View, a: Action): View {
  switch (a.type) {
    case "reset":
      return { ...emptyView, hint: v.hint, hintError: v.hintError };

    case "hint":
      return { ...v, hint: a.text, hintError: !!a.error };

    case "update": {
      const prevFilters = v.steps.at(-1)?.filters ?? {};
      let steps = a.out.revised ? [] : v.steps;
      let { commitAt, card, candidates } = v;
      if (a.out.revised) commitAt = null;
      steps = [...steps];
      const ms = [...v.ms];
      for (const st of a.out.steps) {
        steps.push(st);
        ms.push(st.ms);
        if (st.commit) {
          card = st.commit;
          commitAt = st.n;
        }
      }
      const s = a.out.state;
      if (s.committed && commitAt === null) {
        card = s.committed; // a product already shown is never withdrawn silently
        commitAt = s.committed_at;
      }
      const last = steps.at(-1);
      if (last && last.candidates !== null && last.candidates !== undefined) candidates = last.candidates;
      else if (commitAt === null) candidates = null;
      return {
        ...v,
        steps,
        ms,
        commitAt,
        card,
        candidates,
        prevFilters,
        searches: s.searches,
        pending: a.pending ?? null,
      };
    }

    case "finish": {
      const out = a.out;
      const total = out.words;
      let { card, commitAt, when } = v;
      let final: string;
      let finalWarn = false;
      if (out.committed && out.final && out.committed.id === out.final.id) {
        const early = total - (out.committed_at ?? total);
        when = early > 0 ? `${early} of ${total} words before you finished` : "on your last word";
        final = `Final answer confirmed: same product. ${out.searches} search${out.searches === 1 ? "" : "es"}.`;
      } else if (out.final) {
        if (!out.committed) {
          card = out.final;
          commitAt = total;
        }
        when = "after the request ended";
        final = out.committed
          ? "The final answer differs from the early one (a correction came late)."
          : "The agent waited to the end: something could still have changed it.";
        finalWarn = !!out.committed;
      } else {
        final = "No product matches that request.";
      }
      if (out.rezolve?.length) {
        const r = out.rezolve[0];
        final +=
          ` Rezolve Labs semantic search was asked (${r.reason})` +
          (r.answer ? " and its answer was used." : ", but returned nothing.");
      }
      return { ...v, card, commitAt, when, final, finalWarn, searches: out.searches, pending: null };
    }
  }
}

export const rupees = (n: number | string) => "₹" + Number(n).toLocaleString("en-IN");

export function meanMs(ms: number[]): string {
  return ms.length ? (ms.reduce((a, b) => a + b, 0) / ms.length).toFixed(2) : "–";
}
