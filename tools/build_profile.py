"""Onboard a shop: detect its catalogue profile and write a starter config to edit.

    python3 tools/build_profile.py path/to/catalogue.csv --out path/to/config.json

The config lists what was detected (columns, roles, filters, first-search slots) and, for every
value that has no built-in synonyms, an empty list to fill with the words customers use
("smartphones": ["phone", "mobile"]). That list can be filled by hand, or offline by an LLM or
Rezolve Labs; nothing in it is needed at run time beyond the words themselves.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))

import lexicon  # noqa: E402
from catalogue import Profile  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("catalogue")
    ap.add_argument("--config", help="existing config to start from")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    p = Profile.load(args.catalogue, args.config)
    print(p.describe())
    packs = {"category": lexicon.CATEGORY_SYNONYMS, "colour": lexicon.COLOUR_SYNONYMS}
    role_of = {slot: role for role, slot in p.roles.items()}
    todo = {}
    for slot in p.slots:
        role = role_of.get(slot)
        if role in ("brand", "size"):
            continue
        for value in sorted(p.values[slot]):
            have = p.synonyms.get(slot, {}).get(value)
            if have is None and value not in packs.get(role, {}):
                todo.setdefault(slot, {})[value] = []
            elif have is not None:
                todo.setdefault(slot, {})[value] = have
    cfg = {"id": p.id, "price": p.price, "title": p.title, "roles": p.roles, "slots": p.slots,
           "search_slots": p.search_slots, "synonyms": todo}
    Path(args.out).write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    empty = sum(1 for s in todo.values() for v in s.values() if not v)
    print(f"\nwrote {args.out}: {empty} values still have no synonyms beyond automatic variants")


if __name__ == "__main__":
    main()
