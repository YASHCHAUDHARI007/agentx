"""Fail (exit 1) when the official evaluator's output falls below the agreed floors.

    python starter_kit/ps1-anticipatory-commerce/evaluate.py --agent agent/agent.py > score.txt
    python tools/quality_gate.py score.txt --min-score 44.0 --max-wrong 0 --min-accuracy 0.99

Reads the evaluator's printed report, so the gate checks exactly what the leaderboard runs.
"""
import argparse
import re
import sys


def read_report(text):
    def num(pattern):
        m = re.search(pattern, text, re.M)
        if not m:
            sys.exit(f"quality gate: could not find {pattern!r} in the evaluator output")
        return float(m.group(1))
    return {"score": num(r"^SCORE\s+(-?[\d.]+)"), "accuracy": num(r"^accuracy\s+([\d.]+)"),
            "wrong": num(r"^wrong commits\s+(\d+)")}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("report", help="evaluate.py output ('-' for stdin)")
    ap.add_argument("--min-score", type=float, required=True)
    ap.add_argument("--max-wrong", type=int, default=0)
    ap.add_argument("--min-accuracy", type=float, default=0.0)
    a = ap.parse_args()
    text = sys.stdin.read() if a.report == "-" else open(a.report, encoding="utf-8").read()
    r = read_report(text)
    fails = []
    if r["score"] < a.min_score:
        fails.append(f"score {r['score']} < {a.min_score}")
    if r["wrong"] > a.max_wrong:
        fails.append(f"wrong commits {int(r['wrong'])} > {a.max_wrong}")
    if r["accuracy"] < a.min_accuracy:
        fails.append(f"accuracy {r['accuracy']} < {a.min_accuracy}")
    print(f"quality gate: score {r['score']}, accuracy {r['accuracy']}, wrong commits {int(r['wrong'])}: "
          f"{'FAIL - ' + '; '.join(fails) if fails else 'pass'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
