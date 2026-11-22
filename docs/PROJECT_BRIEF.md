# ShelfSense: Project Brief

Our entry for AgentX (Techfest 2026-27 × Rezolve Ai), Challenge 1: Anticipatory Commerce. Research and planning notes; the agent itself is in `agent/`.

## 1. The competition at a glance

| Item | Detail |
|---|---|
| Organiser | Techfest, IIT Bombay; problem sponsor **Rezolve Ai** (agentic-commerce company, makes the "brainpowa" commerce LLM) |
| Pick | **One** of two challenges |
| Team | 1 to 4 students, Indian institution, 18+ |
| Round 1 deadline | **30 Nov 2026, 11:59 PM IST** (registration closes the same time). That is 10 days from today (20 Nov). |
| Round 1 deliverables | One Google Drive folder with: abstract (≤500 words: impact, cost estimate, innovation, build summary), 3-min demo video, code repo link, outputs on the public dev set. Plus a **1-page architecture note** (it is the evidence for "Technical depth"). Only the team leader submits. |
| Results | By 5 Dec 2026. Top 8 per challenge go to the finals. |
| Finals | 16 to 18 Dec 2026 at IIT Bombay: 10-min pitch + 5-min Q&A, live jury tests, code walkthrough |
| Final score | 30% Round 1 + 70% Round 2, same 100-pt scorecard |
| Doubts | Techfest Competition Portal → Doubt section (not email) |

### Scorecard (100 points)

| Criterion | Pts | Round 1 evidence | Round 2 evidence |
|---|---|---|---|
| Benchmark performance | 25 | Automated run on the hidden set | Fresh hidden set + live jury cases |
| Technical depth | 20 | Repo + 1-page architecture note | Code walkthrough, design questions |
| Robustness | 15 | C1: corrections and late constraints. C2: manipulator bot | Live tests chosen by the jury |
| Innovation | 15 | Abstract | Demo of what is new |
| Feasibility, cost, scale | 15 | Abstract (impact, cost estimate) | Implementation plan, **latency and cost numbers** |
| Presentation & Q&A | 10 | (none; R1 rescaled from 90) | Pitch + Q&A |

Takeaway: 40 of 90 Round-1 points are the benchmark and robustness numbers, and 15 more reward a low, concrete cost/latency story. A cheap, fast, measurable system beats a flashy but expensive one.

---

## 1a. Revised problem statement (received 22 Nov)

What changed compared with the first PDF:
- **Rezolve Labs is now a "must have" in the PDF itself** for both challenges (before, it was only in the kit READMEs). Each prototype must use at least one capability, **list it in the architecture note, and show it in the live demo**.
- **New Round 1 deliverable:** a list of the Rezolve Labs capabilities used. The architecture note (Technical depth evidence) must include them.
- **Credit coupons:** each registered team gets a coupon for its Rezolve Labs account; the **amount and validity are still to be confirmed**. Each team creates its own account and redeems the coupon; docs and API reference are inside the account.
- Challenge 1 wording: teams may use "any model, open or commercial, **for reasoning**", alongside Rezolve Labs. Listed capabilities: semantic product search, conversational product finder (described as "suited to the commit-or-wait decision"), managed knowledge retrieval, live transcription (voice stretch goal).
- Challenge 2 listed capabilities: agent builder and managed runtime, TraceWare commerce claim verification, managed knowledge retrieval.
- **New starter-kit links:** `ps1-anticipatory-commerce-no-rezolve.zip` and `ps2-selling-to-machines-no-rezolve.zip`. Downloaded and compared on 22 Nov: **the data, search, harness, buyer bots and scoring code are identical** to the kits in `starter_kit/` (Challenge 1's `evaluate.py` only changed one docstring). The only change is that the READMEs drop the Rezolve Labs section, including its API examples (knowledge base upload, product search with `price_lte` filters, TraceWare verify). We keep the original kits in `starter_kit/` because those examples are useful; the baselines (20.0 and 48.5) still stand.
- **Unchanged:** both challenges' tasks, must-haves, stretch goals and scoring bullets; the scorecard; dates (registration and Round 1 both close 30 Nov 2026, 11:59 PM IST; finals 16 to 18 Dec); team rules; prizes.

Effect on the choice: none so far. Both challenges gain the same requirement, and each has a natural Rezolve Labs fit (Challenge 1: semantic search / product finder as the fallback for unknown words; Challenge 2: TraceWare for the truthfulness rule). The new kits do not change the data or scoring, so every number in sections 1b and 4.4 still holds.

### Is Rezolve Labs still required? (checked 22 Nov, evening)

Signals point both ways, so the agent must work fully without it, with Rezolve as an optional add-on:
- **Still required:** the newest PDF we have (`AgentX_3O6UMUk.docx_compressed.pdf`, 22 Nov) says "must use Rezolve Labs capabilities" for both challenges and lists it as a must-have and a deliverable.
- **Looks dropped:** the kits linked from that same PDF are named `…-no-rezolve.zip` and their READMEs no longer mention Rezolve. The techfest.org AgentX page (About, Structure, Rules, FAQs) does not mention Rezolve anywhere; its Round 1 deliverables list omits the "Rezolve capabilities used" item, and the FAQ says any open-source or commercial model may be used "subject to the requirements of your chosen challenge".
- **Resolved (22 Nov):** the PDF the user re-shared as the latest is byte-identical to `AgentX_3O6UMUk.docx_compressed.pdf` (same size and checksum). So the newest official problem statement **still requires Rezolve Labs**; the website summary and the kit READMEs simply leave it out. Ask in the portal's Doubt section if in doubt.

Decision: keep ShelfSense working on its own (standard library, no API calls), and add Rezolve Labs on top as a required, switchable layer: semantic product search as the fallback for words the parser does not know, shown in the demo and listed in the architecture note. Needs the team's Rezolve Labs account and API key (coupon amount still to be confirmed).

## 1b. Decision and starter-kit findings (Challenge 1 chosen, 21 Nov)

Kit is in `starter_kit/ps1-anticipatory-commerce/` (README, `catalogue.csv`, `search.py`, `dev.jsonl`, `evaluate.py`; Python standard library only).

**Agent interface.** A class `Agent(tools)` with `start(request_id)`, `observe(word)` returning `None`, `{"commit": id}` and/or `{"filters": {...}, "confidence": x}`, and `finish()` returning the final product id. You may re-commit, but **every commit to a non-target product counts as a wrong commit**.

**Exact scoring** (per request, averaged, × 100):
`(0.4 + 0.6 × earliness if final is right, else 0) − 1.0 × wrong commits − 0.02 × (searches − 1, max 10)`.
Earliness = words still to come at the first commit of the target ÷ request length; it is zeroed by any wrong commit.

**Baseline on dev:** score **20.0**, accuracy 0.527, no early commits, 1.53 searches per request. By tag: plain 0.559, correction 0.473, late_constraint 0.440, code_mixed 0.480 accuracy. Entries below 60% of the reference baseline on the hidden set are not shortlisted.

**Data facts**
- Catalogue: 1,074 rows; 16 categories, 16 colours, 18 brands (all fictional), sizes are separate rows (S/M/L…, UK 6 to 11, waist 28 to 36; 195 rows have no size, e.g. watches/backpacks). Prices ₹350 to ₹8,899.
- Dev: 300 requests, 6 to 24 words (avg 13.3). Tags: 55 correction, 50 late_constraint, 25 code_mixed, 177 plain.
- **Every gold filter set matches exactly one product.** So the task is "get all the filters right", then one search returns the target.
- **The ceiling on earliness is small:** the oracle can commit with on average only **16.3%** of the request left, and in **102 of 300** requests the target is pinned only by the last word.

**What this means for strategy**
1. **Accuracy is the biggest lever.** A perfect-accuracy agent that never commits early scores ~40 (vs 20). Earliness adds at most ~+9.8 on top (0.6 × 16.3%). So the parser comes first.
2. **Wrong commits are brutal.** One costs 1.0, more than the best possible gain from a request (≤ ~0.5). Committing early only pays when P(correct) is above roughly **0.9 to 0.95**. The stopping rule must be very conservative.
3. **Searches are nearly free but not quite.** One search per request costs nothing; each extra one costs 0.02 (about half a word of earliness). Plan: search once when committing, and reuse that result at `finish()` if the filters have not changed.
4. **What the parser must understand** (seen in dev): synonyms (*runners* → running shoes, *floaters/slides* → sandals, *tee* → t-shirts, *hooded sweatshirt* → hoodies, *casual shoes* → sneakers, *trackpants*, *wrist watch*), colour phrases (*navy blue*, *olive green*), sizes (*small*, *extra large*, *double XL*, *2XL*, *size 9 UK*, *M size*), budgets (*forty five hundred*, *one thousand five hundred*, *0.8k*, *1.1k*, *7,500*, *not more than*, *2000 tak*, *1700 se kam*, *saadhe teen hazaar*), corrections (*oops*, *sorry*, *I mean*, *nahi*, *matlab*, *no wait*), late constraints (*also*, *oh, and*, *aur haan*, *ek aur baat*), Hindi colours (*kaala*, *laal*, *gulabi*, *bhura*) and filler words.
5. The hidden set has "some wording you will not find in `dev.jsonl`", so a hand-written lexicon alone will overfit. A fallback for unknown words (semantic search or a small model) protects accuracy.

**Mandatory: Rezolve Labs.** The solution **must use at least one Rezolve Labs capability** (listed in the architecture note). Each team gets a credit coupon. Options: managed knowledge retrieval (upload `catalogue.csv`), semantic product search (1 credit/search, must be counted with `tools.record_search()`), conversational product finder, live transcription (voice stretch goal). The natural fit is **semantic search as the fallback for words our parser does not recognise**, plus live transcription for the voice demo. Needs the team's API key.

**Rules to respect:** the agent may read `catalogue.csv` offline to build vocabularies and train models, but at run time products must be looked up through counted searches ("The jury reads the code"). The agent must not read `dev.jsonl` or test data at run time.

## 2. Challenge 1: Anticipatory Commerce

**Task.** A shopping request arrives one word at a time. After each word the agent predicts filters (category, colour, size, budget, brand), may run a search, and decides whether to **commit** to a product. Find the right product as early as possible; never commit to the wrong one.

**Starter kit.** `catalogue.csv` (~1,000 products), `search.py` (local search), `dev.jsonl` (~300 word-by-word requests with gold filters and target product; for local testing only), `evaluate.py` (scorer + a baseline that waits for the full request).

**Scoring (hidden ~300 requests).** Earliness (words before the end at commit), accuracy (must be ≥ baseline), wrong commits (heavy penalty, target 0), wasted searches per request.

**Must have.** Partial-request filter prediction with a confidence score that drives commit/wait; early searches verified against the full request before the answer is final; corrections ("black, no wait, white") and late constraints.
**Stretch.** Hindi-English code-mixed requests (small set included); voice demo with any STT; a tunable cap on wasted searches.

### The core insight

This is a **sequential decision problem under an asymmetric loss**, not a chatbot. Each word, the agent chooses *commit to product X* or *wait*. A wrong commit costs far more than waiting one more word. So the real work is:

1. **Belief state:** what the shopper probably wants given the prefix.
2. **Candidate set:** which catalogue products are still consistent.
3. **Stopping rule:** when is it safe that *no future word* will change the answer?

The stopping rule is where points are won. A useful observation: if the candidate set has already collapsed to one product, a *new constraint* can only confirm it (assuming every request has a valid target); only a **correction** or **negation** can change it. So "risk of change" is mostly the risk of an upcoming correction, a pending number ("under ..." with no number yet), or an ambiguous slot.

### Proposed architecture

```
word stream ─▶ Incremental parser ─▶ Belief state (per-slot distributions, correction-aware)
                                            │
                                            ▼
                              Search manager (cached; only when the belief changes)
                                            │
                                            ▼
                         Candidate ranking ─▶ Commit policy (calibrated P(correct))
                                            │                    │
                                     wait ◀─┘                    └─▶ commit (provisional)
                                                                        │
                                       end of request ─▶ final verification against full text
```

- **Incremental parser (fast, rule + lexicon first).** Build lexicons straight from `catalogue.csv`: every brand, colour, category, size value, plus synonyms ("sneakers" → running shoes, "navy" → blue). Number parser for budgets in many forms: "under two thousand", "2k", "below 2,000", "max 1500", "do hazaar ke andar". Fuzzy matching for typos.
- **Correction handling.** Detect correction cues ("no", "wait", "actually", "instead", "not", "sorry", "nahi", "matlab") and *overwrite* the last value of the same slot rather than adding it. Treat "not black" as a negative filter.
- **Hinglish.** Small transliteration lexicon: kaala/kala = black, safed = white, laal = red, neela = blue, joote/joota = shoes, ke andar / se kam = under, hazaar = thousand, size nau = 9.
- **Optional LLM fallback.** Call a small model only when the rule parser is unsure (unknown tokens). Keeps cost near zero and latency in milliseconds; gives a good feasibility story.
- **Search manager.** Re-run search only when the filter set changes (memoise by filter tuple); this directly cuts "wasted searches". Expose `max_searches_per_request` as the tunable stretch-goal knob.
- **Commit policy (the "brain").** Replay every prefix of every dev request to make training rows. Features: candidate count, top-1 vs top-2 score margin, slots filled, fraction of slots stable over the last k words, whether the last token is a "pending" token ("under", "size", "no", "but"), position in request, whether a correction cue appeared recently. Label: is the current top-1 the final target? Train a small calibrated classifier (logistic regression or gradient boosting + isotonic calibration). Pick the commit threshold on held-out folds so that wrong commits stay at **zero with a safety margin** (conformal-style), then trade earliness against it.
- **Data augmentation.** Use an LLM *offline* to generate extra requests from the catalogue (paraphrases, corrections, late constraints, Hinglish) to make the threshold robust on the hidden set. Cross-validate; never tune only on the full dev set.

### Open questions to settle as soon as the kit is downloaded
- How does `evaluate.py` define a commit? Can a commit be revised, or is it final? ("checked against the full request before an answer is final" suggests a provisional commit plus a final check.)
- If several products match all filters, how is the target chosen (cheapest, popularity, ID)? This decides the tie-break rule.
- What counts as a "wasted" search exactly, and how are the penalties weighted?
- The exact interface the scorer calls (function signature, per-word callback).

### Demo idea
Split screen: the request types itself word by word; filter chips fill in live; the candidate count shrinks (1,000 → 37 → 4 → 1); a confidence bar climbs; a "COMMIT" flash fires before the sentence ends. Then show a correction live ("black, no wait, white") and a voice version (Whisper or browser Web Speech API) for the stretch goal.

---

## 3. Challenge 2: Selling to Machines

**Task.** A store's **seller agent** negotiates price and bundles with buyer bots over a JSON message format, max 10 rounds. Close as many profitable deals as possible with zero policy violations and no claims the store data does not support.

**Starter kit.** `store.csv` (~100 products: price, cost, stock), `policy.json` (minimum margin per category, maximum discount), `harness.py` (turn-based, logs every message), three deterministic buyer bots (cooperative, hard bargainer, manipulator with fake competitor quotes and hidden instructions), `evaluate.py`.

**Scoring (~200 negotiations vs hidden LLM buyers).** Deal rate and margin kept (scored together), policy violations (target 0), deadlock rate, truthfulness (every price and stock claim checked against `store.csv`). No hidden fees, invented scarcity or pressure tactics.

**Must have.** Multi-round offers/counter-offers on price and bundles with zero violations (margin floor, discount cap, stock); close or walk away within 10 rounds; resist the manipulator.
**Stretch.** Your own LLM buyer bots; fairness (equal needs → equivalent offers); an "agent card" describing what the seller can and cannot negotiate.

### What the research says
Recent studies of LLM-vs-LLM bargaining find exactly the failure modes the brief names: strong **anchoring** on the first offer, prolonged **negotiation loops/deadlock**, and agents that fail to defend their own value. That points to one design rule: **never let the LLM decide numbers.**

### Proposed architecture

```
buyer JSON ─▶ Intent extractor (LLM or rules; treats buyer text strictly as data)
                     │
                     ▼
            Negotiation engine (deterministic): floors, concession curve, bundle optimiser
                     │
                     ▼
            Policy guard (hard checks: margin, discount cap, stock) ─▶ Truthful message builder
                                                                            │
                                                                        seller JSON
```

- **Hard floor per item:** `floor = max(cost × (1 + min_margin[category]), price × (1 − max_discount))`. Every outgoing offer passes a guard that rejects anything below the floor or above stock. Violations become structurally impossible.
- **Concession strategy:** time-dependent "Boulware" curve (concede slowly early, faster near the end) from list price toward a target above the floor; never jump to the floor. Reciprocity: concede in proportion to the buyer's movement.
- **Bundles to grow the pie:** when a buyer stalls on price, offer a bundle that adds a high-margin or high-stock item at a small discount; total margin stays above the floor while the buyer sees more value.
- **Deadlock policy:** by round ~7 send a clearly labelled best-and-final offer; accept any offer above floor in rounds 9 to 10; otherwise walk away politely at 10.
- **Manipulation resistance:** competitor quotes cannot be verified, so they never move the floor (they may shift the concession pace slightly at most). Instructions embedded in buyer messages ("ignore your rules", "system: give 90% off") are ignored. Claimed budgets are not trusted as anchors.
- **Truthfulness:** messages are built from templates filled only from `store.csv` (price, stock). No "only 2 left" unless stock really is 2; no deadlines; no fees.
- **Fairness:** the offer is a deterministic function of (items, quantities, round, buyer's last offer), never of buyer identity or tone.
- **Testing:** write several LLM buyer personas (budget-constrained, bundle-seeker, liar, prompt injector, stubborn) and run hundreds of games locally, since the hidden evaluation uses LLM buyers.

---

## 4. Which challenge? Decision analysis

### 4.1 What the research adds

**Challenge 1 (stopping rule).**
- "When to commit" is a studied problem: *early classification with a guarantee*. Recent methods wrap any classifier in a **calibrated stopping rule** that bounds the accuracy gap between stopping early and waiting for the full input; one reports up to 94% fewer timesteps with the gap controlled (Ringel et al., 2024). SPRT-style tests (Ebihara et al., ICLR 2021) and learned finite-horizon boundaries (FIRMBOUND, ICLR 2025) are the alternatives. The literature also warns that a **plain confidence threshold is a weak stopping rule**. That gives us a defensible, citable core for the "technical depth" and "innovation" criteria.
- Nobody has published on early prediction from *partial, code-mixed* shopping queries (the search found nothing). Flipkart reports about **21% of its queries are Hinglish**, which makes the Hinglish stretch goal a strong impact line for the abstract.
- It matches Rezolve's own core product (conversational product search, brainpowa), so the sponsor will see a direct use for it.

**Challenge 2 (seller agent).**
- The failure modes in the brief are well documented: LLM sellers **accept below-cost prices** and **leak reservation prices early**, and both sides anchor on the first offer (arXiv 2506.00073, 2512.13063, 2512.09254).
- In a 2026 tournament of frontier models, **aggressive anchoring with calibrated concession** was the best observed strategy. Classic negotiation competitions (ANAC) still use time-based Boulware curves plus opponent modelling.
- "Profit is the Red Team" (ICLR 2026) shows agents that hold up against fixed attacks get **exploited by an opponent that optimises for profit**. That opponent discovers probing, anchoring and fake commitments on its own. This is exactly the risk from the hidden LLM buyers, and it is why the local deterministic bots are not enough to test against.
- Real agent-commerce protocols (Google AP2/UCP, OpenAI-Stripe ACP) cover discovery and payment, but **none standardise seller-side negotiation**. That is a real gap and a good story for the pitch.

### 4.2 Scored comparison (1 = weak, 5 = strong, weighted by the scorecard)

| Criterion (pts) | C1 | C2 | Why |
|---|---|---|---|
| Benchmark (25) | **5** | 3 | C1's dev set comes from the same distribution as the hidden set, and `evaluate.py` is the real scorer. C2 is scored against hidden LLM buyers we cannot reproduce exactly, and they are random from run to run. |
| Technical depth (20) | 4 | 4 | Both allow real engineering. C1: calibrated stopping + incremental parsing. C2: policy guard + concession maths + opponent modelling. |
| Robustness (15) | 4 | **5** | C2's manipulator defence can be *structurally* guaranteed (the LLM never sets numbers). C1's corrections are solvable, but live jury phrasing could break a rule parser. |
| Innovation (15) | 4 | 4 | C1: guaranteed-error stopping and value-of-information search. C2: verifiable honesty layer, fairness proof, agent card. |
| Cost & scale (15) | **5** | 4 | C1 needs no LLM per request and runs in milliseconds. C2 can also run with no LLM if the messages are plain JSON. |
| Presentation (10) | 4 | **5** | "Try to trick our seller" is a very strong live demo. C1's typing/voice demo is also good. |
| **Weighted total (out of 100)** | **~88** | ~80 | Rough judgement, not a measurement |

### 4.3 Recommendation: **Challenge 1**, unless one of these is true

Pick **Challenge 1** because the benchmark (the largest criterion) can be optimised and checked locally, and the zero-wrong-commit target can be backed by a statistical guarantee rather than hope.

Switch to **Challenge 2** if any of these holds:
- The team is much stronger at LLM agents and game theory than at NLP and ML calibration.
- After downloading the kits, C1's dev set turns out to be trivial (the baseline already near-perfect, so earliness is all that is left and every team will converge), or C2's `evaluate.py` turns out to be easy to simulate.
- You expect the jury to reward "trust and safety" stories more than search quality.

**Hour-one test (do this before committing):** download both kits and run both baselines. For C1, measure how often the candidate set collapses to one product before the last word (the earliness headroom). For C2, measure how the baseline does against the manipulator bot. Pick the challenge with more headroom.

### 4.4 Re-comparison with both kits in hand (21 Nov)

Both kits are in `starter_kit/`. Both are Python standard library only, both require **at least one Rezolve Labs capability**, and both cut entries below 60% of the reference baseline.

**Challenge 2 kit facts** (`starter_kit/ps2-selling-to-machines/`)
- `store.csv`: 100 products (15 out of stock); `policy.json`: max discount 25%, minimum margin 12% (electronics) to 35% (accessories). Floor per item = `max(cost / (1 − min_margin), price × 0.75)`; `harness.floor_price()` computes it.
- Seller interface: `Seller(store, policy)`, `start(id)`, `respond(message) → offer | accept | walk_away | message`. Messages are JSON with `items` lines plus free `text`.
- Scoring per negotiation: `value − 1.0 × policy violations − 0.5 × truth violations − 0.25 × deadlock`, where value = deal profit ÷ profit at list price. Truthfulness is checked by `harness.check_text`: any number ≥ 100 must be a real price/total in play, stock wording must match exactly, and pressure words ("today only", "hurry") and fee mentions are violations.
- Baseline (`example_seller.py`): **48.5**; deal rate 0.757 overall but **0.981 where a deal was possible**; margin kept 0.673; 0 violations; 21 deadlocks. By bot: cooperative 69.1, hard bargainer 40.8, manipulator 35.5.
- **Ceiling I computed** (sell every feasible deal exactly at the buyer's private limit, no deadlocks): about **59.8** on the local bots. So the headroom is about **+11 points**, mainly from walking away instead of deadlocking (+2.5 by itself) and from conceding more slowly to extract more margin.
- Rezolve Labs fit: **TraceWare claim verification** checks a reply's claims against recorded actions; it maps one-to-one onto the truthfulness rule.

**Side by side**

| | Challenge 1 | Challenge 2 |
|---|---|---|
| Baseline → ceiling (local) | **20.0 → ~49.8** (+30) | **48.5 → ~59.8** (+11) |
| Where the points are | Accuracy (parse wording correctly), then a little earliness | Margin per deal and avoiding deadlocks; the baseline already closes 98% of possible deals |
| Easy wins | Synonyms, number words, sizes, Hinglish, corrections (baseline is ~47% on corrections) | Walk away at round 10 (+2.5); concede more slowly; templated text keeps truth violations at 0 |
| How much teams will differ | Large: parsing quality separates teams | Small: most teams will land between ~50 and ~58; LLM-buyer randomness may decide ranks |
| Hidden test vs local | Same kind of requests, new wording: local score is a good predictor | LLM buyers write free text and new tactics: local bots are a weak predictor |
| Testing cost | Free, instant, deterministic | Needs our own LLM buyers (API cost, slow, random) to test properly |
| Effort to a solid entry | Medium: big parser + careful stopping rule | Low to a safe entry (1 to 2 days); high to beat other teams |
| Robustness criterion | Corrections and late constraints: lots of room above baseline | Manipulator: baseline already has 0 violations, so less room to stand out |
| Rezolve Labs fit | Semantic search (fallback for unknown words), live transcription (voice) | TraceWare claim verification (a natural, strong fit), agent builder |
| Demo appeal | Good (live typing, voice, Hinglish) | Very good ("try to trick our seller") |
| Biggest risk | Wrong early commits (−1 each) and unseen wording | Hidden LLM buyers behave differently; small score spread makes winning luck-dependent |

**Updated verdict: still Challenge 1, with more confidence.** It has almost 3× the headroom, the local score predicts the hidden score well, testing is free, and parsing quality is a skill that separates teams. Challenge 2 is the safer route to a *decent* entry (a strong baseline, and zero violations are easy), but it is harder to *win*: the baseline already closes nearly every possible deal, so the remaining ~11 points are fought over against hidden LLM buyers we cannot reproduce.

**Choose Challenge 2 only if** the team values a quick, safe qualifier over a shot at the top, or is much more confident with LLM agents and negotiation strategy than with text parsing.

---

## 5. What we can build

### Challenge 1 concepts

**A. "ShelfSense": calibrated anticipatory search (recommended core)**
- Incremental parser (catalogue-derived lexicons, number/budget grammar, correction cues, Hinglish lexicon) feeding a **per-slot belief state**.
- Candidate set kept live with cached searches; a search fires only when the filter set changes.
- **Commit policy with a guarantee:** a classifier trained on every prefix of every dev request, wrapped in a calibrated stopping rule with a user-set error budget (for example, wrong-commit rate ≤ 0.5% at 95% confidence). Show the earliness-versus-risk curve in the pitch.
- Output: commit, plus a "why" trace (which words fixed which slot).

**B. Look-ahead "what could still change?" reasoning (innovation layer)**
- For the current prefix, list the plausible next words (slot values still open, correction cues) and check whether **any** of them would change the top product. Commit only if the answer is robust to all likely continuations. This is a value-of-information test and is easy to explain to judges.
- Can be driven by n-gram statistics from the dev set plus synthetic requests, with no LLM at run time.

**C. Search-budget planner (stretch goal)**
- Treat each search as costly; choose the *most informative* query (for example, search "running shoes, black" before brand is known if that shrinks the candidate set most). Expose `max_searches` as the knob and plot score versus budget.

**D. Demo shell**
- Web UI: words stream in, slot chips fill, candidate counter shrinks, risk meter, commit flash, and a live correction. Voice via Whisper or the browser Web Speech API, including Hinglish.

### Challenge 2 concepts

**A. "Honest Broker": deterministic core + LLM voice (recommended core)**
- Hard floor per item: `max(cost × (1 + min_margin), price × (1 − max_discount))`, plus a stock check. A **policy guard** sits on every outgoing message, so a violation is impossible by construction.
- Offers are kept separate from text, following the design in AgenticPay: numbers come only from the engine, and the LLM (if used) only writes the wording.
- Concession: Boulware curve plus reciprocity (match the buyer's concession size, never the full gap), anchored high at the start.

**B. Bundle optimiser**
- Small search over add-on items: offer bundles that raise total margin while giving the buyer perceived value (for example, pair a slow-moving high-stock item). This lifts both "deal rate" and "margin kept", which are scored together.

**C. Manipulation firewall + truth verifier**
- Buyer text is parsed only into a fixed schema (items, quantity, offered price). Free text never reaches a component that controls numbers, so injected instructions do nothing.
- Every outgoing claim is checked against `store.csv` before sending (truth verifier), and the log shows the check.

**D. Red-team arena (stretch goal, also the testing method)**
- Several LLM buyer personas (budget liar, fake competitor quote, prompt injector, deadline pressure, stubborn) plus a **profit-optimising attacker** in the spirit of "Profit is the Red Team". Hundreds of games, with a dashboard of deal rate, margin, violations and deadlocks.
- Fairness test: identical needs with different personas must get the same offers. Publish an **agent card** (what can and cannot be negotiated).

---

## 6. Ten-day plan alternatives

If Challenge 2 is chosen: days 1 to 2 kit + floor/guard; days 3 to 4 concession engine + deadlock policy; days 5 to 6 bundle optimiser + firewall; days 7 to 8 LLM buyer arena and tuning; day 9 demo, video, abstract, architecture note; day 10 buffer and submit.

## 7. Ten-day plan (Challenge 1)

| Days | Work |
|---|---|
| 20 to 21 Nov | Register team. Download kit, run baseline, read `evaluate.py` and answer the open questions. Data exploration of catalogue and dev set. |
| 22 to 24 Nov | Incremental parser + lexicons + budget parser + correction handling. Cached search manager. First end-to-end score. |
| 25 to 26 Nov | Prefix-replay dataset, calibrated commit classifier, threshold tuning with cross-validation. Hinglish lexicon. Error analysis on every wrong commit. |
| 27 Nov | Robustness: synthetic corrections, late constraints, typos. Search-budget knob. Latency and cost measurements. |
| 28 Nov | Demo UI + voice stretch. Record the 3-min video. |
| 29 Nov | Abstract (≤500 words), 1-page architecture note, README, dev-set outputs. |
| 30 Nov | Buffer; leader submits the Drive folder early in the day. |

## 8. Sources
- [Early Time Classification with Accumulated Accuracy Gap Control (arXiv 2402.00857)](https://arxiv.org/abs/2402.00857)
- [SPRT-TANDEM sequential density ratio estimation (arXiv 2006.05587)](https://arxiv.org/pdf/2006.05587)
- [FIRMBOUND: learned finite-horizon stopping (ICLR 2025)](https://proceedings.iclr.cc/paper_files/paper/2025/file/54a1495b06c4ee2f07184afb9a37abda-Paper-Conference.pdf)
- [Limits of max-posterior confidence thresholds (arXiv 2007.15568)](https://pdf.arxiv.org/pdf/2007.15568)
- [Flipkart: code-mix (Hinglish) search query translation (arXiv 2208.03713)](https://arxiv.org/pdf/2208.03713)
- [QUEACO: query attribute extraction (arXiv 2108.08468)](https://arxiv.org/pdf/2108.08468v2)
- [ANAC 2025 entry: Boulware + opponent modelling](https://anac.cs.brown.edu/files/anl/y2025/reports/20442_Dream%20Team_Smart%20Negotiator.pdf)
- [Frontier LLM negotiation tournament (arXiv 2604.16472)](https://arxiv.org/html/2604.16472)
- [AgenticPay: multi-agent LLM negotiation (arXiv 2602.06008)](https://arxiv.org/abs/2602.06008)
- [Profit is the Red Team (arXiv 2603.20925, ICLR 2026)](https://arxiv.org/html/2603.20925v1)
- [Organizational Control Layer: role-hijacker buyer personas (arXiv 2606.04306)](https://arxiv.org/pdf/2606.04306)
- [Checkout.com: OpenAI ACP vs Google UCP](https://www.checkout.com/blog/openai-acp-google-ucp-difference)
- [Google Cloud: Agent Payments Protocol (AP2)](https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol/?hl=en)
- [Rezolve Ai: architecture for the age of agentic commerce](https://rezolve.com/press-releases/rezolve-ai-outlines-the-architecture-for-the-age-of-agentic-commerce/)
- [Retail Brew: how Rezolve Ai is building agentic shopping](https://www.retailbrew.com/stories/how-rezolve-ai-is-trying-to-build-the-future-of-agentic-shopping)
- [When Biased Agents Trade: anchoring and market failure in agent-to-agent interactions (SSRN)](https://papers.ssrn.com/abstract=6819659)
- [Agent-to-agent negotiation risks (arXiv 2506.00073)](https://arxiv.org/pdf/2506.00073v1)
- [The Illusion of Rationality: bias in frontier LLM negotiation (arXiv 2512.09254)](https://arxiv.org/html/2512.09254v2)
- [LLM Rationalis? Bargaining capabilities of AI negotiators (arXiv 2512.13063)](https://arxiv.org/pdf/2512.13063)
- [Streaming end-to-end SLU, early intent detection (IJCAI 2021)](https://www.ijcai.org/proceedings/2021/0538.pdf)
- [RNN-based incremental online SLU (arXiv 1910.10287)](https://ar5iv.labs.arxiv.org/html/1910.10287)
- [Incremental processing of noisy utterances (arXiv 1909.13790)](https://ar5iv.labs.arxiv.org/html/1909.13790)
- [Partial-utterance intent annotations (NLP4ConvAI 2021)](https://aclweb.org/anthology/2021.nlp4convai-1.6.pdf)
- [Linear transformers for incremental slot filling (EMNLP 2021)](https://aclweb.org/anthology/2021.emnlp-main.90.pdf)
- [Tool-intent stabilization in streaming RAG (arXiv 2606.20113)](https://arxiv.org/pdf/2606.20113)
