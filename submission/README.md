# Round 1 submission package

Everything for the Google Drive folder (deadline 30 Nov 2026, 11:59 PM IST; only the team leader submits).

| Deliverable | File | Status |
|---|---|---|
| Abstract (≤500 words: impact, cost, innovation, build) | [abstract.pdf](abstract.pdf) · source [abstract.md](abstract.md) (474 words) | ready |
| 1-page architecture note, with the Rezolve Labs capabilities used | [architecture_note.pdf](architecture_note.pdf) · source [architecture_note.html](architecture_note.html) | ready |
| Outputs on the public dev set | [dev_outputs.jsonl](dev_outputs.jsonl) (one line per request: commits, final answer, filters, searches, score) and [dev_results.txt](dev_results.txt) (the evaluator's summary) | ready |
| Code repository link | https://github.com/YASHCHAUDHARI007/shelfsense (public) | ready |
| 3-minute demo video | script: [video_script.md](video_script.md) | **to record** |

Before submitting:
- [ ] Register the team on the Techfest portal (closes with Round 1).
- [ ] Get the team's Rezolve Labs API key (coupon), run `python3 tools/rezolve_setup.py`, and record the Rezolve shot of the video. If there's no key in time, record without that shot. The architecture note already says the integration is awaiting the key.
- [ ] Record the video from the script and upload it to the Drive folder.
- [ ] Add the PDFs, the dev outputs and the repo link to the Drive folder; check the folder is shared for viewing.

Regenerate the dev outputs and PDFs after any change to the agent:

```bash
python3 starter_kit/ps1-anticipatory-commerce/evaluate.py --agent agent/agent.py --log submission/dev_outputs.jsonl > submission/dev_results.txt
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless=new --no-pdf-header-footer --print-to-pdf=submission/architecture_note.pdf "file://$PWD/submission/architecture_note.html"
```

The dev run uses the default commit mode `auto` (safe for speech). On punctuated text like the dev set, `AGENT_COMMIT_MODE=next` scores 0.4 higher (44.5) with no wrong commits on dev, but makes more wrong commits on unpunctuated input.
