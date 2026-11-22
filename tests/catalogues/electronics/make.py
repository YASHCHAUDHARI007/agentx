"""A second, unrelated catalogue to prove ShelfSense is not tied to the starter kit's.

    python3 tests/catalogues/electronics/make.py

Writes, next to this file:
  catalogue.csv   ~100 electronics products. Column names differ from the kit on purpose
                  (sku, name, type, color, storage, price_inr) and there is a numeric rating
                  column that must not be mistaken for a filter.
  requests.jsonl  300 shopper requests in the dev.jsonl format, tagged correction /
                  late_constraint like the kit's, with "earliest" (the first word after which
                  the said filters pin the target).
config.json (written by hand) holds the synonyms a shop would supply, e.g. "mobile" -> smartphones.
"""
import csv
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent

TYPES = {   # type: (brands, colours, storages, price range)
    "smartphones": (["Voltra", "Nexo", "Orbix", "Kaidan"], ["black", "white", "blue", "green", "gold"],
                    ["64GB", "128GB", "256GB", "512GB"], (8000, 90000)),
    "laptops": (["Voltra", "Lumio", "Orbix"], ["silver", "space grey", "black"], ["256GB", "512GB", "1TB"],
                (32000, 150000)),
    "tablets": (["Nexo", "Lumio", "Kaidan"], ["silver", "space grey", "pink"], ["64GB", "128GB", "256GB"],
                (12000, 80000)),
    "earbuds": (["Voltra", "Nexo", "Sonique", "Kaidan"], ["black", "white", "blue"], [""], (900, 15000)),
    "smartwatches": (["Orbix", "Lumio", "Sonique"], ["black", "silver", "pink", "green"], [""], (1800, 40000)),
}
MODEL = {"smartphones": ["Nova", "Pulse", "Edge", "Zen"], "laptops": ["Air", "Book", "Pro"],
         "tablets": ["Slate", "Tab", "Pad"], "earbuds": ["Buds", "Pods", "Beat", "Air"],
         "smartwatches": ["Fit", "Watch", "Band"]}

SAY_TYPE = {"smartphones": ["phone", "smartphone", "mobile", "mobile phone", "5g phone"],
            "laptops": ["laptop", "notebook"], "tablets": ["tablet", "tab"],
            "earbuds": ["earbuds", "wireless earbuds", "buds", "tws earbuds"],
            "smartwatches": ["smartwatch", "smart watch", "fitness watch"]}
SAY_COLOUR = {"black": ["black", "jet black"], "white": ["white"], "blue": ["blue"], "green": ["green"],
              "gold": ["gold", "golden"], "silver": ["silver"], "space grey": ["space grey", "space gray"],
              "pink": ["pink"]}
WORD_NUM = {10: "ten", 15: "fifteen", 20: "twenty", 25: "twenty five", 30: "thirty", 40: "forty", 50: "fifty",
            60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety"}
OPENERS = ["I want", "looking for", "show me", "do you have", "can you find me", "I need", "get me", "hi, I want"]
CLOSERS = ["", "", "", "please", "for my sister", "thanks", "for college", "if you have it", "for office"]


def say_storage(s, rng):
    num, unit = s[:-2], s[-2:].lower()
    return rng.choice([s, f"{num} {unit.upper()}", f"{num}gb" if unit == "gb" else f"{num}tb",
                       f"{num} gigs" if unit == "gb" else f"{num} TB"])


def say_budget(v, rng):
    k = v // 1000
    forms = [f"under {k}k", f"below {v:,}", f"within ₹{v}", f"budget {k}k", f"not more than {v:,}"]
    if k in WORD_NUM:
        forms.append(f"under {WORD_NUM[k]} thousand")
    return rng.choice(forms)


def build_catalogue(rng):
    rows = []
    for t, (brands, colours, storages, (lo, hi)) in TYPES.items():
        for bi, b in enumerate(brands):
            model = MODEL[t][bi % len(MODEL[t])]
            base = rng.randrange(lo, hi // 2, 500)
            for c in colours:
                for si, s in enumerate(storages):
                    price = base + si * rng.choice([3000, 5000, 8000]) + rng.choice([0, 500, 1000])
                    pretty = t[:-1].title() if t != "earbuds" else "Earbuds"
                    rows.append({"name": f"{b} {model} {pretty}, {c.title()}" + (f", {s}" if s else ""),
                                 "brand": b, "type": t, "color": c, "storage": s, "price_inr": price,
                                 "rating": round(rng.uniform(3.4, 4.9), 1),
                                 "description": f"{model} {t[:-1]} by {b} in {c}."
                                                + (f" {s} storage." if s else "")})
    rng.shuffle(rows)
    for i, r in enumerate(rows, 1):
        r["sku"] = f"E{i:04d}"
    return rows


def matches(rows, f):
    out = []
    for r in rows:
        if all((r["price_inr"] <= v) if k == "max_price" else r[k] == v for k, v in f.items()):
            out.append(r)
    return out


def make_request(rows, target, rng, n):
    gold = {"type": target["type"], "brand": target["brand"], "color": target["color"]}
    if target["storage"]:
        gold["storage"] = target["storage"]
    if rng.random() < 0.6:
        gold["max_price"] = (target["price_inr"] // 1000 + rng.choice([1, 2, 5])) * 1000
    tags = []
    # pieces: (slot, value, text)
    def piece(slot, value):
        if slot == "type":
            return rng.choice(SAY_TYPE[value])
        if slot == "color":
            return rng.choice(["", "in "])[:3] + rng.choice(SAY_COLOUR[value])
        if slot == "brand":
            return rng.choice([value, f"from {value}", f"{value} brand", f"by {value}"])
        if slot == "storage":
            return rng.choice(["", "with "]) + say_storage(value, rng)
        return say_budget(value, rng)

    order = [s for s in ("brand", "color", "type", "storage", "max_price") if s in gold]
    if rng.random() < 0.3:
        rng.shuffle(order)
    late = None
    if rng.random() < 0.2 and len(order) > 3:
        late = rng.choice([s for s in order if s != "type"])
        order.remove(late)
        tags.append("late_constraint")
    pieces = [(s, gold[s], piece(s, gold[s])) for s in order]
    if late:
        pieces.append((late, gold[late], rng.choice(["oh, and", "also,", "and make sure it's"]) + " " + piece(late, gold[late])))
    if rng.random() < 0.2:
        slot = rng.choice([s for s in ("color", "storage", "brand") if s in gold])
        pool = {"color": TYPES[gold["type"]][1], "storage": TYPES[gold["type"]][2],
                "brand": TYPES[gold["type"]][0]}[slot]
        wrong = rng.choice([v for v in pool if v != gold[slot]])
        i = next(i for i, p in enumerate(pieces) if p[0] == slot)
        cue = rng.choice(["no wait,", "sorry,", "actually, make it", "no, change that to"])
        pieces[i] = (slot, wrong, piece(slot, wrong))
        pieces.append((slot, gold[slot], cue + " " + piece(slot, gold[slot])))
        tags.append("correction")
    text_parts, spans = [rng.choice(OPENERS)], []
    for slot, value, txt in pieces:
        text_parts.append(txt)
        spans.append((slot, value, len(" ".join(text_parts).split())))
    closer = rng.choice(CLOSERS)
    if closer:
        text_parts.append(closer)
    words = " ".join(text_parts).split()
    earliest = None
    for t in range(1, len(words) + 1):
        said = {}
        for slot, value, end in spans:
            if end <= t:
                said[slot] = value
        if all(gold.get(k) == v for k, v in said.items()):
            hits = matches(rows, said)
            if len(hits) == 1 and hits[0]["sku"] == target["sku"]:
                earliest = t
                break
    return {"id": f"elec-{n:04d}", "text": " ".join(words), "words": words, "filters": gold,
            "target": target["sku"], "earliest": earliest or len(words), "tags": tags}


def main():
    rng = random.Random(11)
    rows = build_catalogue(rng)
    cols = ["sku", "name", "brand", "type", "color", "storage", "price_inr", "rating", "description"]
    with open(HERE / "catalogue.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    reqs = []
    while len(reqs) < 300:
        target = rng.choice(rows)
        r = make_request(rows, target, rng, len(reqs) + 1)
        f = {k: v for k, v in r["filters"].items()}
        if len(matches(rows, f)) == 1:          # the request must pin exactly one product
            reqs.append(r)
    with open(HERE / "requests.jsonl", "w", encoding="utf-8") as fh:
        for r in reqs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows)} products, {len(reqs)} requests")


if __name__ == "__main__":
    main()
