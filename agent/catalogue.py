"""Catalogue profiles: everything ShelfSense needs to know about one shop's catalogue.

A profile is read from the shop's catalogue CSV plus an optional JSON config the shop can edit.
Anything the config leaves out is detected from the data:

    {
      "id": "sku", "price": "price_inr", "title": "name",       # column names
      "roles": {"category": "type", "colour": "color"},          # which column plays which part
      "slots": ["type", "brand", "color", "storage"],            # columns shoppers filter on
      "search_slots": ["type", "color"],                         # the first search fetches these
      "synonyms": {"type": {"smartphones": ["phone", "mobile"]}} # shop words -> catalogue values
    }

Where the phrases for each value come from, in order (a later source wins on a clash):
  1. Built-in language packs (lexicon.py) for the roles they cover: category, colour, size.
     A pack entry is used only for values this catalogue actually has.
  2. Automatic variants of every value: plural and singular, "t-shirt" / "t shirt" / "tshirt",
     "128GB" / "128 gb" / "128 gigs", "grey" / "gray".
  3. The shop's own synonyms from the config (they can also be generated offline, see
     tools/build_profile.py).

    SHELFSENSE_CATALOGUE=path/to/catalogue.csv SHELFSENSE_CONFIG=path/to/config.json
selects the catalogue the agent loads by default; without them it is the starter-kit catalogue.
"""
import csv
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import lexicon

KIT_CATALOGUE = lexicon.CATALOGUE

ROLE_NAMES = {
    "category": ("category", "type", "product_type", "product type", "department", "subcategory"),
    "colour": ("colour", "color", "shade"),
    "size": ("size",),
    "brand": ("brand", "make", "manufacturer"),
}
ID_NAMES = ("product_id", "id", "sku", "item_id", "productid", "product id")
PRICE_NAMES = ("price", "selling_price", "sale_price", "price_inr", "mrp", "amount")
TITLE_NAMES = ("title", "name", "product_name", "product name")
MAX_SLOT_VALUES = 200          # more distinct values than this (and long ones) is free text, not a filter
UNIT_WORDS = {"gb": ["gb", "gigs", "gig"], "tb": ["tb", "terabyte"], "mb": ["mb"], "ml": ["ml"], "l": ["litre", "liter"],
              "kg": ["kg", "kilo", "kilos"], "g": ["g", "gram", "grams"], "mah": ["mah"], "inch": ["inch", "inches"],
              "w": ["w", "watt", "watts"], "hz": ["hz"]}
_UNIT_VALUE = re.compile(r"^(\d+(?:\.\d+)?)\s*([a-z]+)$")


def _norm(s):
    return " ".join(s.lower().replace("_", " ").split())


@dataclass
class Profile:
    path: Path
    rows: list
    id: str
    price: str
    title: str
    slots: list
    roles: dict
    search_slots: list
    relax_order: list
    values: dict = field(default_factory=dict)       # slot -> set of values
    synonyms: dict = field(default_factory=dict)     # slot -> value -> phrases (from the config)

    # ------------------------------------------------------------ loading

    @classmethod
    def load(cls, path, config=None):
        path = Path(path)
        cfg = {}
        if config:
            cfg = json.loads(Path(config).read_text(encoding="utf-8")) if not isinstance(config, dict) else config
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            raise ValueError(f"{path}: no rows")
        header = list(rows[0])
        by_name = {_norm(h): h for h in header}

        def pick(key, names, fallback=None):
            if cfg.get(key):
                return cfg[key]
            return next((by_name[n] for n in names if n in by_name), fallback)

        def numeric(col):
            return all(re.fullmatch(r"\d+(\.\d+)?", r[col].replace(",", "")) for r in rows if r[col])

        pid = pick("id", ID_NAMES) or next(h for h in header if len({r[h] for r in rows}) == len(rows))
        price = pick("price", PRICE_NAMES) or next(h for h in header if h != pid and numeric(h))
        title = pick("title", TITLE_NAMES)

        roles = {role: next((by_name[n] for n in names if n in by_name), None) for role, names in ROLE_NAMES.items()}
        roles.update(cfg.get("roles", {}))
        roles = {k: v for k, v in roles.items() if v}

        if cfg.get("slots"):
            slots = list(cfg["slots"])
        else:
            slots = []
            for h in header:
                if h in (pid, price, title):
                    continue
                if h not in roles.values() and numeric(h):
                    continue          # ratings, stock counts, weights: numbers, not shopper filters
                vals = {r[h] for r in rows if r[h]}
                long_text = vals and sum(map(len, vals)) / len(vals) > 30
                if 1 < len(vals) <= max(MAX_SLOT_VALUES, len(rows) // 20) and not long_text:
                    slots.append(h)
        roles = {k: v for k, v in roles.items() if v in slots}

        if cfg.get("search_slots"):
            search_slots = list(cfg["search_slots"])
        else:
            search_slots = [roles[r] for r in ("category", "colour") if r in roles] or slots[:1]
        rest = [s for s in slots if s not in search_slots]
        size, brand = roles.get("size"), roles.get("brand")
        relax = ["max_price"] + [s for s in rest if s == size] + [s for s in rest if s not in (size, brand)] \
            + [s for s in rest if s == brand] + search_slots[::-1]

        for r in rows:
            r[price] = float(r[price].replace(",", "")) if r[price] else 0.0
            if r[price].is_integer():
                r[price] = int(r[price])
        values = {s: {r[s] for r in rows if r[s]} for s in slots}
        return cls(path, rows, pid, price, title or pid, slots, roles, search_slots, relax, values,
                   cfg.get("synonyms", {}))

    @classmethod
    def default(cls):
        cat = os.environ.get("SHELFSENSE_CATALOGUE")
        return cls.load(cat or KIT_CATALOGUE, os.environ.get("SHELFSENSE_CONFIG") or None)

    # ------------------------------------------------------------ phrases

    def phrase_table(self):
        """(words...) -> (slot, value) for every way of naming every value."""
        table = {}

        def add(phrase, slot, value):
            key = tuple(phrase.lower().split())
            if key:
                table[key] = (slot, value)

        packs = {"category": lexicon.CATEGORY_SYNONYMS, "colour": lexicon.COLOUR_SYNONYMS}
        role_of = {slot: role for role, slot in self.roles.items()}
        for slot in self.slots:
            role = role_of.get(slot)
            for value in sorted(self.values[slot]):
                if role == "size":
                    for ph in lexicon.SIZE_WORDS.get(value, []):
                        add(ph, slot, value)
                    if not value.isdigit() and len(value) > 2 and value not in lexicon.SIZE_WORDS:
                        for ph in _variants(value, "other"):
                            add(ph, slot, value)
                    continue
                pack = packs.get(role, {})
                if value in pack:
                    for ph in pack[value] + [value]:
                        add(ph, slot, value)
                else:
                    for ph in _variants(value, role or "other"):
                        add(ph, slot, value)
        for slot, entries in self.synonyms.items():
            for value, phrases in entries.items():
                if value not in self.values.get(slot, ()):
                    raise ValueError(f"config synonym for unknown value {slot}={value!r}")
                for ph in phrases:
                    add(ph, slot, value)
        return table

    def describe(self):
        lines = [f"catalogue   {self.path} ({len(self.rows)} products)",
                 f"columns     id={self.id} price={self.price} title={self.title}",
                 f"roles       " + ", ".join(f"{k}={v}" for k, v in self.roles.items()),
                 f"slots       " + ", ".join(f"{s} ({len(self.values[s])})" for s in self.slots),
                 f"search      first search by {' + '.join(self.search_slots)}",
                 f"relax       {' > '.join(self.relax_order)}"]
        return "\n".join(lines)


def _variants(value, role):
    """Ways a shopper may write a catalogue value."""
    v = value.lower().strip()
    out = {v}
    m = _UNIT_VALUE.match(v.replace(" ", ""))
    if m:                                              # "128GB" -> "128gb", "128 gb", "128 gigs"
        num, unit = m.groups()
        for u in UNIT_WORDS.get(unit, [unit]):
            out |= {f"{num}{u}", f"{num} {u}"}
        return out
    if role == "brand":
        if " " in v:
            out.add(v.replace(" ", ""))
        return out
    forms = {v}
    if "-" in v:
        forms |= {v.replace("-", " "), v.replace("-", "")}
    if " " in v:
        forms.add(v.replace(" ", ""))
    for f in list(forms):                              # plural <-> singular on the last word
        words = f.split()
        last = words[-1]
        if role != "colour":
            if last.endswith("ies") and len(last) > 4:
                alt = last[:-3] + "y"
            elif last.endswith(("ches", "shes", "sses", "xes")):
                alt = last[:-2]
            elif last.endswith("s") and not last.endswith("ss") and len(last) > 3:
                alt = last[:-1]
            elif last.endswith("y") and len(last) > 3 and last[-2] not in "aeiou":
                alt = last[:-1] + "ies"
            elif last.endswith(("ch", "sh", "ss", "x")):
                alt = last + "es"
            else:
                alt = last + "s"
            forms.add(" ".join(words[:-1] + [alt]))
    out |= forms
    out |= {f.replace("grey", "gray") for f in out} | {f.replace("gray", "grey") for f in out}
    return out


class CatalogueSearch:
    """Local search over any profile, with the starter kit's semantics: filters are exact and
    case-insensitive on slot columns, max_price/min_price on the price column; what passes is ranked
    by query-word overlap, ties to the cheaper product."""

    def __init__(self, profile):
        self.profile = profile
        text_cols = [h for h in profile.rows[0] if h != profile.price]
        self.index = [(r, set(re.findall(r"[a-z0-9]+", " ".join(str(r[c]) for c in text_cols).lower())))
                      for r in profile.rows]

    def search(self, query="", filters=None, k=10):
        pr = self.profile
        filters = {key: v for key, v in (filters or {}).items() if v is not None}
        unknown = set(filters) - set(pr.slots) - {"max_price", "min_price"}
        if unknown:
            raise ValueError(f"unknown filters: {sorted(unknown)}")
        want = {key: str(v).lower() for key, v in filters.items() if key in pr.slots}
        q = set(re.findall(r"[a-z0-9]+", query.lower()))
        hits = []
        for r, words in self.index:
            if any(str(r[key]).lower() != v for key, v in want.items()):
                continue
            if "max_price" in filters and r[pr.price] > filters["max_price"]:
                continue
            if "min_price" in filters and r[pr.price] < filters["min_price"]:
                continue
            hits.append((-len(q & words), r[pr.price], r))
        hits.sort(key=lambda h: h[:2])
        return [dict(r, score=-s) for s, _, r in hits[:k]]
