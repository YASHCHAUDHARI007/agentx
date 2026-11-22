"""Incremental request parser: words so far -> filters, plus signals about what may still change.

The whole prefix is re-parsed on every word (requests are short, so this costs microseconds).
Rules:
  * Phrases are matched longest-first ("running sneakers" -> running shoes, "navy blue" -> navy).
  * The last mention of a slot wins. That one rule handles corrections ("black, no wait, white",
    "size M, oops, XS", "Horavo, matlab Tikkra") and late constraints.
  * Numbers of 100 or more are budgets; small numbers that are real sizes are sizes.
  * `pending` is True when the prefix ends mid-thought ("under", "size", "one thousand", "extra",
    "sorry,"), so a commit right now would be premature.
"""
import csv
import re
from dataclasses import dataclass, field

from lexicon import (BUDGET_CUES, CATALOGUE, CATEGORY_SYNONYMS, COLOUR_MODIFIERS, COLOUR_SYNONYMS,
                     CORRECTION_CUES, CURRENCY, FILLER, GENERIC_HEADS, HALF_MORE, HINDI_FRACTIONS, HINDI_UNITS,
                     MULTIPLIERS, SIZE_CUES, SIZE_POST_CUES, SIZE_WORDS, UNITS)

SLOTS = ("category", "colour", "brand", "size", "max_price")


def _load_catalogue_vocab():
    with open(CATALOGUE, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    brands = sorted({r["brand"] for r in rows})
    sizes_by_cat = {}
    for r in rows:
        sizes_by_cat.setdefault(r["category"], set()).add(r["size"])
    sized = {c for c, s in sizes_by_cat.items() if s != {""}}
    number_sizes = {s for r in rows for s in [r["size"]] if s.isdigit()}
    categories = {r["category"] for r in rows}
    colours = {r["colour"] for r in rows}
    return brands, sized, number_sizes, categories, colours


BRANDS, SIZED_CATEGORIES, NUMBER_SIZES, CATEGORIES, COLOURS = _load_catalogue_vocab()


def _phrase_table():
    table = {}

    def add(phrase, slot, value):
        table[tuple(phrase.lower().split())] = (slot, value)

    for cat, phrases in CATEGORY_SYNONYMS.items():
        assert cat in CATEGORIES, cat
        for ph in phrases + [cat]:
            add(ph, "category", cat)
    for col, phrases in COLOUR_SYNONYMS.items():
        assert col in COLOURS, col
        for ph in phrases + [col]:
            add(ph, "colour", col)
    for b in BRANDS:
        add(b, "brand", b)
    for size, phrases in SIZE_WORDS.items():
        for ph in phrases:
            add(ph, "size", size)
    return table


PHRASES = _phrase_table()
MAX_PHRASE = max(len(k) for k in PHRASES)

# phrases that a longer phrase with a different meaning starts with ("light" -> "light blue");
# only these stay open at the end of a prefix ("navy" -> "navy blue" means the same thing)
GROWS_INTO_OTHER = {k[:j] for k, v in PHRASES.items() for j in range(1, len(k))
                    if k[:j] in PHRASES and PHRASES[k[:j]] != v}

# Words after which the next word is likely to change or complete a slot.
PREFIX_WORDS = {"running", "jogging", "casual", "track", "bag", "wrist", "hooded", "pair", "t", "flip", "baseball",
                "laptop", "school", "light", "dark", "sky", "royal", "off", "baby", "jet", "bottle", "extra", "double",
                "x", "xx", "kesar", "navy", "olive", "trail", "sports", "denim", "polo", "round", "over", "on",
                "midnight", "wine", "khaki", "card", "college", "formal", "button"} | COLOUR_MODIFIERS
LEAD_CUES = {"under", "below", "than", "within", "max", "maximum", "to", "upto", "budget", "around", "about",
             "most", "not", "more", "less", "size", "uk", "waist", "rs", "rs.", "₹", "inr", "no", "wait", "sorry",
             "oops", "actually", "mean", "meant", "rather", "change", "make", "that", "nahi", "nahin", "matlab",
             "instead", "only", "from", "by", "in", "and", "also", "plus", "with", "for", "of", "or", "but",
             "aur", "haan", "baat", "like", "uh", "um", "hmm", "er", "it's", "sure", "be",
             # hesitations that often open a correction ("I mean", "oh, and", "hold on")
             "i", "oh", "ok", "okay", "hold", "hang", "nope", "nah", "arre", "arey", "ya", "or", "plus", "make",
             "rather", "galti", "hmmm", "well", "so"}

# Words that hang off a value ("Pacevo brand", "M size", "black coloured", "Loomsy ka"): saying one
# is still part of stating the value, not a sign that the request is winding down.
VALUE_TAILS = {"brand", "size", "colour", "color", "coloured", "colored", "shade", "tone", "wala", "wali", "wale",
               "ka", "ki", "ke", "number", "waist", "uk", "rang", "rupees", "rs", "only"}

_PUNCT = re.compile(r"^[\"'(\[]+|[\"')\].,!?;:…]+$")
_DIGITS = re.compile(r"^(?:₹|rs\.?)?(\d[\d,]*(?:\.\d+)?)(k)?$")


@dataclass
class Token:
    raw: str        # the word as typed, punctuation stripped
    low: str        # lowercase (after repair, if the word was repaired)
    stop: bool      # the word ended with a clause break (",", ".", "?")
    guessed: bool = False   # the word was repaired (typo, "-ish", glued size) rather than read as typed


@dataclass
class Parse:
    filters: dict = field(default_factory=lambda: {s: None for s in SLOTS})
    set_at: dict = field(default_factory=dict)       # slot -> index of the token that last set it
    changes: dict = field(default_factory=dict)      # slot -> how many times it was set to a new value
    pending: bool = False                            # the prefix ends mid-thought
    unknown: list = field(default_factory=list)      # content words the parser did not understand
    open_correction: bool = False                    # a correction word came after the last value
    guessed: list = field(default_factory=list)      # words read only after repairing them
    last_kind: str = ""                              # "value", "cue" or "filler": what the last word was
    n: int = 0

    def known(self):
        return {k: v for k, v in self.filters.items() if v is not None}

    def key(self):
        return tuple(sorted(self.known().items()))


def tokenize(words):
    out = []
    for w in words:
        for part in w.replace("/", " ").split():
            stop = bool(re.search(r"[,.!?;:…]$", part)) and not re.fullmatch(r"rs\.", part.lower())
            raw = _PUNCT.sub("", part) if not re.fullmatch(r"rs\.", part.lower()) else part
            if raw and not re.search(r"[\w₹]", raw):      # a bare dash or ellipsis: a clause break
                raw, stop = "", True
            if raw:
                out.append(Token(raw, raw.lower(), stop))
            elif out:
                out[-1].stop = True
    return out


# ---------------------------------------------------------------- repairing unknown words

def _vocab():
    single = {k[0]: v for k, v in PHRASES.items() if len(k) == 1}
    words = set(single) | {w for k in PHRASES for w in k}
    known = (words | FILLER | BUDGET_CUES | CORRECTION_CUES | CURRENCY | SIZE_CUES | LEAD_CUES | PREFIX_WORDS
             | set(UNITS) | set(HINDI_UNITS) | set(HINDI_FRACTIONS) | HALF_MORE | set(MULTIPLIERS) | set(GENERIC_HEADS))
    return single, known


_SINGLE, _KNOWN = _vocab()
# typo targets: slot words of 4+ letters (short ones like "tan", "red" invite false repairs)
_TYPO_TARGETS = [w for w in _SINGLE if len(w) >= 4 and w.isalpha()]
_GLUED_SIZE = re.compile(r"^(uk|size|w|eu|us)(\d{1,2})$")


def _edits(a, b, limit):
    """Damerau-Levenshtein distance, giving up once it exceeds limit."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev2, prev = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            if prev2 is not None and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > limit:
            return limit + 1
        prev2, prev = prev, cur
    return prev[-1]


def repair(tok):
    """Read an unknown word as the slot word it most likely is. Returns the replacement tokens."""
    low = tok.low
    m = _GLUED_SIZE.match(low)                       # "UK9", "W32"
    if m:
        cue = "waist" if m.group(1) == "w" else "size"
        return [Token(cue, cue, False, True), Token(m.group(2), m.group(2), tok.stop, True)]
    if low.endswith("ish") and len(low) > 5:         # "bluish", "reddish", "greyish"
        stem = low[:-3]
        for cand in (stem, stem + "e", stem[:-1]):
            if cand in _SINGLE and _SINGLE[cand][0] == "colour":
                return [Token(cand, cand, tok.stop, True)]
    if len(low) >= 4 and low.isalpha():              # typos: "nevy", "whte", "biege", "headfones"
        limit = 1 if len(low) < 7 else 2
        best = sorted((_edits(low, w, limit), w) for w in _TYPO_TARGETS if w[0] == low[0])
        top = [w for d, w in best if d == best[0][0]] if best and best[0][0] <= limit else []
        if top and len({_SINGLE[w] for w in top}) == 1:   # one reading, even if several spellings fit
            w = top[0]
            return [Token(w, w, tok.stop, True)]
    return [tok]


def normalise(toks):
    out = []
    for i, t in enumerate(toks):
        nxt = toks[i + 1].low if i + 1 < len(toks) else ""
        if t.low in ("do", "ek") and nxt in MULTIPLIERS:          # "do hazaar" = 2,000, "ek hazaar" = 1,000
            v = "two" if t.low == "do" else "one"
            out.append(Token(v, v, t.stop))
        elif t.low in _KNOWN or _digit_value(t.low) is not None or t.raw in ("S", "M", "L"):
            out.append(t)
        else:
            out.extend(repair(t))
    return out


def _digit_value(low):
    m = _DIGITS.match(low)
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    return v * 1000 if m.group(2) else v


def parse_number(toks, i):
    """Read a number starting at toks[i]. Returns (value, tokens used, had_money_words) or None."""
    total, cur, half, used, money, any_num = 0.0, 0.0, False, 0, False, False
    j = i
    while j < len(toks):
        t = toks[j].low
        if t in CURRENCY:
            money = True
        elif (dv := _digit_value(t)) is not None:
            if any_num:
                break
            cur, any_num = dv, True
            money = money or "k" in t or t.startswith(("₹", "rs"))
        elif t in UNITS or t in HINDI_UNITS:
            u = UNITS.get(t, HINDI_UNITS.get(t))
            if not any_num:
                cur = u + (0.5 if half else 0)
            elif cur and cur % 100 and cur >= 20 and cur % 10 == 0 and u < 10:
                cur += u                                   # "twenty five"
            elif cur == 0 and total:
                cur = u + (0.5 if half else 0)             # "one thousand five ..."
            else:
                break
            any_num = True
        elif t in HINDI_FRACTIONS:
            if any_num and cur:
                break
            cur, any_num = HINDI_FRACTIONS[t], True
        elif t in HALF_MORE:
            if any_num and cur:
                break
            half = True
        elif t in MULTIPLIERS and any_num:
            m = MULTIPLIERS[t]
            money = True
            if m == 100:
                cur = (cur or 1) * 100
            else:
                total += (cur or 1) * m
                cur = 0
        elif t == "and" and any_num and j + 1 < len(toks) and (toks[j + 1].low in UNITS or toks[j + 1].low in HINDI_UNITS):
            pass
        else:
            break
        used = j - i + 1
        j += 1
        if toks[j - 1].stop:
            break
    if not any_num:
        return None
    return total + cur, used, money


def parse(words, final=False):
    """final=True: the request is complete, so nothing at the end is still growing."""
    toks = normalise(tokenize(words))
    p = Parse(n=len(toks))
    p.guessed = [t.low for t in toks if t.guessed]

    def put(slot, value, idx):
        if p.filters[slot] != value:
            if p.filters[slot] is not None:
                p.changes[slot] = p.changes.get(slot, 0) + 1
            p.filters[slot] = value
        p.set_at[slot] = idx

    i = 0
    last_end_open = False          # the last thing read could still grow with the next word
    kinds = []                     # per token: "value", "cue" or "filler"
    generic = []                   # generic product words seen
    last_value_at = -1
    while i < len(toks):
        tok = toks[i]
        # 1. phrases, longest first
        hit = None
        for n in range(min(MAX_PHRASE, len(toks) - i), 0, -1):
            key = tuple(t.low for t in toks[i:i + n])
            if key in PHRASES and not any(t.stop for t in toks[i:i + n - 1]):
                hit = (n, PHRASES[key])
                break
        if hit:
            n, (slot, value) = hit
            put(slot, value, i + n - 1)
            last_end_open = (i + n == len(toks)) and key in GROWS_INTO_OTHER
            kinds += ["value"] * n
            last_value_at = i + n - 1
            i += n
            continue
        # 2. single uppercase letter sizes: "S", "M", "L"
        if tok.raw in ("S", "M", "L"):
            put("size", tok.raw, i)
            kinds.append("value")
            last_value_at = i
            i += 1
            continue
        # 3. numbers: budgets and number sizes
        num = parse_number(toks, i)
        if num:
            value, used, money = num
            end = i + used
            prev = toks[i - 1].low if i else ""
            nxt = toks[end].low if end < len(toks) else ""
            size_cued = prev in SIZE_CUES or nxt in SIZE_POST_CUES
            sv = str(int(value)) if value == int(value) else None
            # word numbers can keep growing ("one thousand" ... "five hundred"); digits cannot.
            # A number that may still grow is not used yet: "below one thousand" is not a budget
            # of 1,000 if "five hundred" follows.
            last_end_open = not final and end == len(toks) and _digit_value(toks[end - 1].low) is None \
                and not toks[end - 1].stop
            if last_end_open and prev in SIZE_CUES and sv in NUMBER_SIZES:
                last_end_open = False      # "size eight" does not grow into "size eight hundred"
            if not last_end_open:
                if (value >= 100 or money) and not size_cued:
                    put("max_price", int(round(value)), end - 1)
                elif sv in NUMBER_SIZES:
                    put("size", sv, end - 1)
                elif value >= 100:
                    put("max_price", int(round(value)), end - 1)
                last_value_at = end - 1
            kinds += ["value"] * used
            i = end
            continue
        # 4. generic product words ("shoes", "pants"): used only if nothing more specific comes
        if tok.low in GENERIC_HEADS:
            generic.append(GENERIC_HEADS[tok.low])
            kinds.append("value")
            last_end_open = False
            i += 1
            continue
        # 5. everything else: cue words, filler, or unknown
        if not (tok.low in FILLER or tok.low in BUDGET_CUES or tok.low in CORRECTION_CUES or tok.low in CURRENCY
                or tok.low in SIZE_CUES or tok.low in LEAD_CUES or tok.low in PREFIX_WORDS
                or tok.low.isdigit()):
            p.unknown.append(tok.low)
            kinds.append("unknown")
        elif tok.low in CORRECTION_CUES or tok.low in LEAD_CUES or tok.low in CURRENCY or tok.low in SIZE_CUES \
                or tok.low in PREFIX_WORDS or tok.low in BUDGET_CUES:
            kinds.append("cue")
        elif tok.low in VALUE_TAILS or (i and toks[i - 1].stop):
            kinds.append("tail")       # "Pacevo brand", "black coloured", or the first word of a new clause
        else:
            kinds.append("filler")
        last_end_open = False
        i += 1

    if generic and not p.filters["category"]:
        ctx = {t.low for t in toks}
        sporty = {"running", "run", "jogging", "jog", "sports", "sport", "gym", "marathon", "trail", "training",
                  "track", "sweat", "workout"}
        if generic[-1] == "footwear":
            guess = "running shoes" if ctx & sporty else "sneakers"
        else:
            guess = "jeans" if ctx & {"denim", "jean"} else "track pants"
        p.filters["category"] = guess
        p.guessed.append(guess)

    if toks:
        last = toks[-1]
        p.pending = (last_end_open and not last.stop) or (last.low in PREFIX_WORDS and not last.stop) \
            or last.low in LEAD_CUES or last.low in CURRENCY or last.low in CORRECTION_CUES
        p.open_correction = any(t.low in CORRECTION_CUES for t in toks[last_value_at + 1:])
        p.last_kind = kinds[-1] if kinds else ""
    return p


def needed_slots(category):
    """Slots a request needs before one product can be pinned down."""
    need = ["category", "colour"]
    if category in SIZED_CATEGORIES:
        need.append("size")
    return need
