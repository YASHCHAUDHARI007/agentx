"""Generate a stress set of shopping requests in the same format as dev.jsonl.

    python3 tests/stress/make_stress.py            # writes tests/stress/stress.jsonl (used for tuning)
    python3 tests/stress/make_stress.py --holdout  # writes tests/stress/holdout.jsonl (never tuned on)

Why: the hidden test set uses "some wording you will not find in dev.jsonl", and our lexicon was
written while looking at dev. This set mixes dev-style wording with phrasings the parser was NOT
built for (marked * in the banks below), so we can see how the agent behaves on new wording.
The key question is not only accuracy but safety: on words it does not understand, the agent
should wait, not commit to a wrong product.

Each request targets one catalogue product and states enough filters to pin it down uniquely,
like the kit's requests. Tags: correction, late_constraint, code_mixed (as in dev) plus `novel`
when any phrase came from the unseen banks.
"""
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = ROOT / "starter_kit" / "ps1-anticipatory-commerce" / "catalogue.csv"
OUT = Path(__file__).with_name("stress.jsonl")

# (seen phrases, unseen phrases). Unseen = wording the parser was not written for.
CATEGORY = {
    "running shoes": (["running shoes", "runners", "jogging shoes", "running sneakers"],
                      ["running trainers", "road running shoes", "shoes for running", "trail runners"]),
    "sneakers": (["sneakers", "casual shoes", "casual sneakers"],
                 ["everyday sneakers", "lifestyle sneakers", "white-sole sneakers", "low top sneakers"]),
    "sandals": (["sandals", "slides", "floaters", "flip flops"],
                ["sliders", "slip-on sandals", "beach sandals", "strappy sandals"]),
    "t-shirts": (["t-shirt", "tee", "tshirt", "t shirt"],
                 ["tee shirt", "crew neck tee", "graphic tee", "half sleeve tshirt"]),
    "shirts": (["shirt", "casual shirt"],
               ["button-up shirt", "full sleeve shirt", "linen shirt", "check shirt"]),
    "jeans": (["jeans", "denims", "pair of jeans"],
              ["denim pants", "slim fit jeans", "straight jeans", "jeans pant"]),
    "dresses": (["dress"], ["midi dress", "maxi dress", "sundress", "party dress"]),
    "kurtas": (["kurta"], ["ethnic kurta", "cotton kurta", "straight kurta", "kurta top"]),
    "hoodies": (["hoodie", "hooded sweatshirt"], ["pullover hoodie", "zip hoodie", "hoody", "zip-up hoodie"]),
    "jackets": (["jacket"], ["rain jacket", "winter jacket", "light jacket", "outer jacket"]),
    "track pants": (["track pants", "trackpants", "joggers"],
                    ["jogger pants", "track bottoms", "trackies", "sweat pants"]),
    "backpacks": (["backpack", "bag pack", "rucksack"],
                  ["travel backpack", "laptop backpack", "back pack", "college backpack"]),
    "caps": (["cap"], ["snapback", "sports cap", "baseball hat", "peak cap"]),
    "headphones": (["headphones", "headset"],
                   ["wireless headphones", "over-ear headphones", "bluetooth headphones", "headfones"]),
    "watches": (["watch", "wrist watch"], ["analog wrist watch", "chronograph watch", "watch for men", "dial watch"]),
    "wallets": (["wallet"], ["leather wallet", "bifold wallet", "money wallet", "mens wallet"]),
}
COLOUR = {
    "black": (["black"], ["jet black", "pitch black", "blk", "all black"]),
    "blue": (["blue"], ["sky blue", "royal blue", "blue colour", "bluish"]),
    "navy": (["navy", "navy blue"], ["dark navy", "nevy blue", "deep navy", "navy coloured"]),
    "grey": (["grey", "gray"], ["ash grey", "heather grey", "greyish", "grey colour"]),
    "white": (["white"], ["snow white", "pure white", "white colour", "whte"]),
    "olive": (["olive", "olive green"], ["army green", "olive colour", "military green", "olive shade"]),
    "red": (["red"], ["bright red", "cherry red", "red colour", "reddish"]),
    "maroon": (["maroon"], ["deep maroon", "maroon colour", "burgundy red", "marron"]),
    "green": (["green"], ["emerald green", "forest green", "green colour", "grean"]),
    "beige": (["beige"], ["beige colour", "biege", "light beige", "beige shade"]),
    "brown": (["brown"], ["chocolate brown", "dark brown", "brown colour", "brwn"]),
    "yellow": (["yellow"], ["lemon yellow", "bright yellow", "yellow colour", "yelow"]),
    "pink": (["pink"], ["hot pink", "light pink", "pink colour", "pinkish"]),
    "tan": (["tan"], ["tan colour", "tan brown", "tan shade", "light tan"]),
    "gold": (["gold", "golden"], ["gold tone", "gold colour", "gold-plated", "goldish"]),
    "silver": (["silver"], ["silver tone", "silver colour", "steel silver", "silvr"]),
}
HINDI_COLOUR = {"black": ["kaala", "kaale rang ka*"], "white": ["safed", "safed rang ka*"], "red": ["laal"],
                "blue": ["neela", "neele rang ka*"], "green": ["hara*"], "pink": ["gulabi"], "brown": ["bhura"],
                "yellow": ["peela*"], "grey": ["grey"], "navy": ["navy"], "maroon": ["maroon"],
                "olive": ["olive"], "beige": ["beige"], "tan": ["tan"], "gold": ["sunehra*"], "silver": ["silver"]}
WORD_SIZE = {"XS": (["XS", "extra small"], ["x-small*", "size xs"]), "S": (["S", "small"], ["size S", "smol*"]),
             "M": (["M", "medium"], ["size M", "med*"]), "L": (["L", "large"], ["size L", "lrg*"]),
             "XL": (["XL", "extra large"], ["size XL", "x-large*"]),
             "XXL": (["XXL", "2XL", "double XL"], ["size XXL", "xx-large*"])}
NUMS = {6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven"}
HINDI_NUMS = {6: "chhe", 7: "saat", 8: "aath", 9: "nau", 10: "das", 11: "gyarah"}

OPENERS = (["I need", "show me", "looking for", "can you find me", "get me", "hey, do you have any",
            "hi, I want", "I'd like", "I'm looking for"],
           ["any chance you have", "help me find", "searching for", "do you guys stock", "please suggest",
            "need to buy", "can I get"])
CLOSERS = (["for my brother", "as a gift", "thanks", "please", "need it this week", "for office",
            "nothing too flashy", "if you have it", "for the gym", "for my dad", "thank you"],
           ["for a trip", "asap", "for college", "for my wife's birthday", "cheers", "if possible",
            "for daily use", "ty"])
HI_OPENERS = ["mujhe", "mere liye", "kya aapke paas", "bhaiya, dikhao", "ek"]
HI_CLOSERS = ["chahiye", "milega?", "dikhao na", "chahiye please", "hai kya?"]


def words_for(n):
    """A budget written in words, the way people say it."""
    ones = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
            "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

    def two(x):
        return ones[x] if x < 20 else (tens[x // 10] + (" " + ones[x % 10] if x % 10 else ""))
    if n % 100:
        return None
    h = n // 100
    if n < 1000 or (n < 10000 and n % 1000 and h < 100 and random.random() < 0.5):
        return two(h) + " hundred"
    th, rest = divmod(n, 1000)
    return two(th) + " thousand" + (" " + two(rest // 100) + " hundred" if rest else "")


def budget_phrase(v, rng, novel):
    seen = [f"under {v}", f"below {v}", f"less than {v}", f"max {v}", f"within {v} rupees", f"up to {v:,}",
            f"budget {v}", f"not more than {v}", f"for under ₹{v}"]
    if v % 100 == 0 and v >= 1000:
        seen.append(f"under {v / 1000:g}k")
    w = words_for(v)
    if w:
        seen += [f"under {w}", f"budget {w}", f"not more than {w}"]
    unseen = [f"₹{v} max", f"{v} or less", f"no more than {v}", f"cheaper than {v}", f"INR {v}",
              f"under rs{v}", f"max budget of {v}", f"under {v}/-"]
    if v % 1000 == 0:
        unseen.append(f"under {v // 1000} thousand")
    return (rng.choice(unseen), True) if novel else (rng.choice(seen), False)


def hindi_budget(v, rng):
    n = {1000: "ek hazaar*", 1500: "pandrah sau", 2000: "do hazaar*", 2500: "dhai hazaar", 3000: "teen hazaar",
         3500: "saadhe teen hazaar", 5000: "paanch hazaar", 1700: "satrah sau"}.get(v)
    amount = n if n and rng.random() < 0.6 else str(v)
    return f"{amount} {rng.choice(['tak', 'se kam', 'ke andar', 'ke neeche*'])}"


def pick(bank, rng, p_novel):
    seen, unseen = bank
    if unseen and rng.random() < p_novel:
        return rng.choice(unseen), True
    return rng.choice(seen), False


def size_phrase(size, category, rng, p_novel):
    if size.isdigit():
        n = int(size)
        if category == "jeans":
            seen = [f"{n} waist", f"waist {n}", f"size {n}"]
            unseen = [f"W{n}", f"{n} inch waist", f"waist size {n}"]
        else:
            seen = [f"size {n}", f"UK {n}", f"size {NUMS[n]}", f"{n} UK", f"size {n} UK"]
            unseen = [f"UK{n}", f"size: {n}", f"{NUMS[n]} UK", f"uk size {n}", f"shoe size {n}"]
        return (rng.choice(unseen), True) if rng.random() < p_novel else (rng.choice(seen), False)
    seen, unseen = WORD_SIZE[size]
    if rng.random() < p_novel:
        ph = rng.choice(unseen)
        return ph.rstrip("*"), True
    ph = rng.choice(seen)
    return (f"{ph} size" if rng.random() < 0.3 else ph), False


# A holdout bank: fresh phrasings written after the parser fixes, never used to tune the agent.
HOLDOUT = {
    "category": {
        "running shoes": ["marathon running shoes", "jogging trainers", "running footwear", "racing flats"],
        "sneakers": ["sneaks", "kicks for daily wear", "street sneakers", "casual trainers"],
        "sandals": ["open sandals", "sandles", "rubber slides", "pool slides"],
        "t-shirts": ["tees", "polo t-shirt", "v neck tee", "printed tshirt"],
        "shirts": ["oxford shirt", "dress shirt", "office shirt", "shrit"],
        "jeans": ["skinny jeans", "jeanz", "blue denim jeans", "regular fit jeans"],
        "dresses": ["bodycon dress", "a-line dress", "dres", "floral dress"],
        "kurtas": ["kurtha", "festive kurta", "long kurta", "printed kurta"],
        "hoodies": ["fleece hoodie", "hoodi", "oversized hoodie", "hoodie sweatshirt"],
        "jackets": ["puffer jacket", "jackt", "leather jacket", "denim jacket"],
        "track pants": ["track pant", "joggers pants", "trackpant bottoms", "gym joggers"],
        "backpacks": ["back-pack", "bagpack for office", "hiking backpack", "backpak"],
        "caps": ["baseball cap hat", "trucker cap", "cap hat", "sun cap"],
        "headphones": ["noise cancelling headphones", "head phones", "studio headphones", "headphnes"],
        "watches": ["smart looking watch", "wrist-watch", "watche", "dress watch"],
        "wallets": ["slim wallet", "walet", "card wallet", "leather purse"],
    },
    "colour_suffix": ["coloured", "color", "shade", "tone"],
    "openers": ["could you show me", "pls find", "want to order", "would love a", "got any", "do u have"],
    "closers": ["for my nephew", "urgent", "for the weekend", "if in stock", "gracias", "much appreciated"],
    "budget": ["under {v} bucks", "less than ₹{v}", "{v} rupees max", "my budget is {v}", "upto {v}",
               "not over {v}", "{v} at most"],
}


def main(n=600, seed=7, holdout=False):
    rng = random.Random(seed)
    rows = list(csv.DictReader(open(CATALOGUE, encoding="utf-8")))
    for r in rows:
        r["price"] = int(r["price"])
    brands_by_cat = {}
    for r in rows:
        brands_by_cat.setdefault(r["category"], set()).add(r["brand"])
    out = []
    k = 0
    while len(out) < n:
        k += 1
        t = rng.choice(rows)
        p_novel = rng.choice([0.0, 0.35, 0.7])
        code_mixed = rng.random() < 0.15
        f = {"category": t["category"], "colour": t["colour"], "size": t["size"] or None,
             "brand": t["brand"] if rng.random() < 0.85 else None, "max_price": None}

        def matches(ff):
            return [r for r in rows if all(r[s] == ff[s] for s in ("category", "colour", "size", "brand")
                                           if ff[s]) and (ff["max_price"] is None or r["price"] <= ff["max_price"])]
        cands = matches(f)
        if len(cands) > 1 or rng.random() < 0.6:
            dearer = sorted({r["price"] for r in cands if r["price"] > t["price"]})
            cap = (dearer[0] - 1) if dearer else t["price"] * 2
            nice = [v for step in (1000, 500, 100, 50) for v in range(-(-t["price"] // step) * step, cap + 1, step)]
            f["max_price"] = nice[0] if nice else t["price"]
            cands = matches(f)
        if len(cands) != 1 or cands[0]["product_id"] != t["product_id"]:
            continue

        novel = False
        parts = []                       # (slot, phrase)
        if holdout and rng.random() < p_novel:
            cat_ph, nv = rng.choice(HOLDOUT["category"][t["category"]]), True
        else:
            cat_ph, nv = pick(CATEGORY[t["category"]], rng, p_novel)
        novel |= nv
        parts.append(("category", cat_ph))
        if code_mixed:
            colour_word = HINDI_COLOUR.get(t["colour"], [t["colour"]])
            c = rng.choice(colour_word)
            novel |= c.endswith("*")
            parts.append(("colour", c.rstrip("*")))
        else:
            c, nv = pick(COLOUR[t["colour"]], rng, 0 if holdout else p_novel)
            if holdout and rng.random() < p_novel:
                c, nv = f"{rng.choice(COLOUR[t['colour']][0])} {rng.choice(HOLDOUT['colour_suffix'])}", True
            novel |= nv
            parts.append(("colour", rng.choice([c, f"in {c}"])))
        if f["size"]:
            if code_mixed and f["size"].isdigit() and t["category"] != "jeans" and rng.random() < 0.5:
                parts.append(("size", f"{rng.choice([str(f['size']), HINDI_NUMS[int(f['size'])]])} number"))
            else:
                s, nv = size_phrase(f["size"], t["category"], rng, p_novel)
                novel |= nv
                parts.append(("size", s))
        if f["brand"]:
            b = rng.choice([f["brand"], f"by {f['brand']}", f"from {f['brand']}", f"only {f['brand']}",
                            f"{f['brand']} brand"] + ([f"{f['brand']} ka"] if code_mixed else []))
            parts.append(("brand", b))
        if f["max_price"]:
            if code_mixed and rng.random() < 0.6:
                b = hindi_budget(f["max_price"], rng)
                novel |= "*" in b
                parts.append(("max_price", b.replace("*", "")))
            else:
                if holdout and rng.random() < p_novel:
                    b, nv = rng.choice(HOLDOUT["budget"]).format(v=f["max_price"]), True
                else:
                    b, nv = budget_phrase(f["max_price"], rng, rng.random() < p_novel)
                novel |= nv
                parts.append(("max_price", b))
        rng.shuffle(parts)
        parts.sort(key=lambda x: x[0] != "colour" if rng.random() < 0.3 else 0)

        tags = []
        # a late constraint: move one non-category slot to after the request sounds finished
        late = None
        if len(parts) > 2 and rng.random() < 0.2:
            late = next(p for p in reversed(parts) if p[0] != "category")
            parts.remove(late)
            tags.append("late_constraint")
        # a correction: say a wrong value for one slot first, then fix it
        corr = None
        if rng.random() < 0.2:
            slot_i = rng.randrange(len(parts))
            slot, phrase = parts[slot_i]
            wrong = None
            if slot == "colour":
                wrong = rng.choice([c for c in COLOUR if c != t["colour"]])
            elif slot == "brand":
                wrong = rng.choice(sorted(brands_by_cat[t["category"]] - {t["brand"]}) or ["Zentrail"])
            elif slot == "size" and not f["size"].isdigit():
                wrong = rng.choice([s for s in WORD_SIZE if s != f["size"]])
            elif slot == "size":
                wrong = f"size {int(f['size']) + rng.choice([-1, 1]) if f['size'] not in ('6', '28') else int(f['size']) + 1}"
            if wrong:
                corr = (slot_i, wrong)
                tags.append("correction")

        def say(ph):
            return ph
        body = []
        end_fix = None
        for i, (slot, ph) in enumerate(parts):
            if corr and corr[0] == i:
                cue_mid = ["no wait,", "sorry,", "oops,", "I mean", "actually", "make that", "no no,"]
                cue_mid_new = ["scratch that,", "on second thought", "hmm, rather", "correction,"]
                if rng.random() < 0.5:
                    cue = rng.choice(cue_mid_new if rng.random() < p_novel else cue_mid)
                    novel |= cue in cue_mid_new
                    body.append(f"{corr[1]}, {cue} {ph}")
                else:
                    body.append(corr[1])
                    end_fix = ph
            else:
                body.append(say(ph))
        opener = rng.choice(HI_OPENERS) if code_mixed else (
            rng.choice(HOLDOUT["openers"]) if holdout and rng.random() < p_novel else pick(OPENERS, rng, p_novel)[0])
        text = f"{opener} " + " ".join(body)
        if end_fix:
            cues = ["sorry, I meant", "no, change that to", "actually, make it", "wait, I meant"]
            cues_new = ["hmm, let me change that to", "my bad, I meant", "correction:", "on second thought,"]
            c = rng.choice(cues_new) if rng.random() < p_novel else rng.choice(cues)
            novel |= c in cues_new
            text += f". {c} {end_fix}"
        if late:
            cues = ["oh, and", "also,", "and make sure it's", "one more thing,"]
            cues_new = ["btw,", "P.S.", "forgot to say,", "and it should be"]
            c = rng.choice(cues_new) if rng.random() < p_novel else rng.choice(cues)
            novel |= c in cues_new
            text += f". {c} {late[1]}"
        if rng.random() < 0.6:
            closer = rng.choice(HI_CLOSERS) if code_mixed else (
                rng.choice(HOLDOUT["closers"]) if holdout and rng.random() < p_novel else pick(CLOSERS, rng, p_novel)[0])
            text += f" {closer}"
        if code_mixed:
            tags.append("code_mixed")
        if novel:
            tags.append("novel")
        words = text.split()
        out.append({"id": f"{'holdout' if holdout else 'stress'}-{len(out) + 1:04d}", "text": text, "words": words,
                    "filters": {"category": f["category"], "colour": f["colour"], "size": f["size"],
                                "brand": f["brand"], "max_price": f["max_price"]},
                    "target": t["product_id"], "tags": tags})
    path = OUT.with_name("holdout.jsonl") if holdout else OUT
    with open(path, "w", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(out)} requests to {path}")


if __name__ == "__main__":
    import sys
    if "--holdout" in sys.argv:
        main(seed=2026, holdout=True)        # fresh phrasings, never used for tuning
    else:
        main()
