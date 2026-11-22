"""Score ShelfSense on any catalogue, with the starter kit's scoring.

    python3 tools/evaluate_catalogue.py tests/catalogues/electronics/catalogue.csv \\
        --config tests/catalogues/electronics/config.json \\
        --data tests/catalogues/electronics/requests.jsonl

The kit's evaluate.py is reused for running and scoring; only its search tool is swapped for
catalogue.CatalogueSearch over the given catalogue (same semantics: exact filters, keyword rank).
--profile prints what was detected from the catalogue and stops.
"""
import argparse
import functools
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "starter_kit" / "ps1-anticipatory-commerce"))

import evaluate  # noqa: E402
from agent import Agent  # noqa: E402
from catalogue import CatalogueSearch, Profile  # noqa: E402
from parser import Vocab  # noqa: E402


def score(profile, requests, rezolve=None):
    evaluate.search = CatalogueSearch(profile).search          # what Tools.search calls
    agent_cls = functools.partial(Agent, vocab=Vocab(profile), rezolve=rezolve)
    results, per_word = evaluate.run(agent_cls, requests)
    return results, per_word


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("catalogue")
    ap.add_argument("--config")
    ap.add_argument("--data")
    ap.add_argument("--log")
    ap.add_argument("--profile", action="store_true")
    args = ap.parse_args()

    profile = Profile.load(args.catalogue, args.config)
    print(profile.describe())
    if args.profile:
        return
    requests = [json.loads(line) for line in open(args.data, encoding="utf-8") if line.strip()]
    results, per_word = score(profile, requests)
    s = evaluate.summarise(results)
    oracle = f", best possible {s['oracle_share']:.1%}" if s["oracle_share"] is not None else ""
    ms = sorted(per_word)
    print(f"\nrequests            {s['requests']}   ({Path(args.data).name})")
    print(f"accuracy            {s['accuracy']:.3f}")
    print(f"wrong commits       {s['wrong_commits']} in {s['requests_with_wrong_commit']} requests")
    print(f"earliness           {s['early_share']:.1%} of the request{oracle}")
    print(f"searches/request    {s['searches']:.2f}")
    print(f"latency             {1000 * statistics.mean(ms):.2f} ms/word, p95 {1000 * ms[int(.95 * (len(ms) - 1))]:.2f} ms")
    print(f"SCORE               {s['score']:.1f}")
    tags = sorted({t for r in results for t in r["tags"]}) + ["plain"]
    print("\nby tag              n    accuracy  wrong  earliness  score")
    for tag in tags:
        rows = [r for r in results if (tag in r["tags"]) or (tag == "plain" and not r["tags"])]
        if rows:
            t = evaluate.summarise(rows)
            print(f"  {tag:17} {t['requests']:4}    {t['accuracy']:.3f}   {t['wrong_commits']:4}    "
                  f"{t['early_share']:6.1%}  {t['score']:6.1f}")
    keys = list(profile.slots) + ["max_price"]
    rows = [r for r in results if r["filters_gold"]]
    if rows:
        acc = {k: sum(r["filters_reported"].get(k) == r["filters_gold"].get(k) for r in rows) / len(rows) for k in keys}
        print("\nfilters at the last word vs gold: " + "  ".join(f"{k} {v:.2f}" for k, v in acc.items()))
    if args.log:
        with open(args.log, "w", encoding="utf-8") as fh:
            for r in results:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
