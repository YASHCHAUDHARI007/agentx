"""One-time setup: upload catalogue.csv to a Rezolve Labs knowledge base and save its id.

    echo 'REZOLVE_API_KEY=your-key' >> .env        # repository root; .env is git-ignored
    python3 tools/rezolve_setup.py                  # creates the knowledge base, uploads, waits
    python3 tools/rezolve_setup.py --check "black running shoes size 9"   # one test search

Writes REZOLVE_KB_ID to .env when the document is ready (about 10 seconds).
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

from rezolve import RezolveClient, RezolveError  # noqa: E402

CATALOGUE = ROOT / "starter_kit" / "ps1-anticipatory-commerce" / "catalogue.csv"
ENV = ROOT / ".env"


def save_env(key, value):
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    lines = [ln for ln in lines if not ln.startswith(f"{key}=")] + [f"{key}={value}"]
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    client = RezolveClient.from_env()
    if client is None:
        sys.exit("Set REZOLVE_API_KEY in .env (repository root) first.")
    if "--check" in sys.argv:
        query = " ".join(sys.argv[sys.argv.index("--check") + 1:]) or "black running shoes"
        print(client.search(query, limit=5))
        return
    if client.kb_id:
        sys.exit(f"REZOLVE_KB_ID is already set ({client.kb_id}). Remove it from .env to upload again.")
    kb = client.create_knowledge_base("ShelfSense catalogue")
    print("knowledge base", kb)
    doc = client.upload_document(kb, CATALOGUE)
    print("document", doc, "- waiting until it is ready")
    for _ in range(60):
        status = client.document_status(kb, doc)
        state = str((status.get("data") or {}).get("status", "")).lower()
        if state == "ready":
            filters = (status.get("data") or {}).get("availableFilters")
            print("ready; filters:", filters)
            save_env("REZOLVE_KB_ID", kb)
            print("saved REZOLVE_KB_ID to .env")
            return
        if state in ("failed", "error"):
            sys.exit(f"upload failed: {status}")
        time.sleep(2)
    sys.exit("document not ready after 2 minutes; check the Rezolve Labs dashboard")


if __name__ == "__main__":
    try:
        main()
    except RezolveError as e:
        sys.exit(f"Rezolve Labs error: {e}")
