# ShelfSense: 3-minute demo video script

Record the screen at 1080p with the demo page open (`make web` once, then `python3 server/app.py` and http://localhost:8080) and a terminal beside it. Use Chrome, so the microphone works. Speak slowly. The timings add up to 3:00.

Before recording:
- Put `REZOLVE_API_KEY` and `REZOLVE_KB_ID` in `.env` (run `python3 tools/rezolve_setup.py` once) and restart the server. It should print "Rezolve Labs fallback: on". Without a key, skip the Rezolve shot and say it is wired but awaiting the key.
- Do a full rehearsal once. The microphone needs permission the first time.

| Time | Show | Say |
|---|---|---|
| 0:00–0:15 | Title: the demo page, idle | "Shoppers don't speak in clean queries. They change their minds mid-sentence and mix Hindi and English. ShelfSense finds the product while they're still talking, and when it isn't sure, it waits instead of guessing." |
| 0:15–0:45 | **Type and stream** the dev example: `hi, I want Loomsy navy blue casual sneakers within forty five hundred, size 7 if you have it` | "Each word goes to the agent as it arrives. Watch the filters fill in: brand, colour, category, budget. After one search, nine products fit, then one. It commits at word 15, three words before the shopper finished, and the final answer confirms it." |
| 0:45–1:15 | **Correction**: shop = electronics, stream `get me Nexo blue mobile with 512 gigs under 60k sorry with 256 gigs please` | "A wrong commit costs more than an early one earns, so the agent asks one question per word: could a correction still come? Here the request sounded complete after 'under 60k', but there was no punctuation, as in real speech, so it waited. The correction came, and it committed to the 256 GB phone." |
| 1:15–1:45 | **Speak** into the mic, fashion shop: "show me a black Pacevo hoodie, medium, under fifteen hundred, thanks, it's for my brother" | "This is live speech recognition. Words that are still changing show dashed, and the agent only reads a word once it settles. Same agent, same rules." |
| 1:45–2:10 | **Rezolve Labs**: stream `help me find in navy blue coloured Strydo size 7 UK upto 8000 racing flats for daily use`, then point at the line under the card | "'Racing flats' is not a word the parser knows. At the end of the request, ShelfSense asks Rezolve Labs semantic product search over our catalogue knowledge base, sending only the filters it is sure of, and gets the right shoe. Clean requests never call it, so it costs almost nothing." |
| 2:10–2:35 | **Terminal**: `python3 starter_kit/ps1-anticipatory-commerce/evaluate.py --agent agent/agent.py` (scroll to the SCORE line) | "On the 300-request dev set: score 44 against the baseline's 20, accuracy 100%, zero wrong commits, about one search per request, and 0.04 milliseconds per word." |
| 2:35–2:50 | Switch the shop dropdown to *electronics*; show `tools/evaluate_catalogue.py` output | "It isn't tied to one catalogue: it reads any shop's CSV. On a different electronics catalogue: accuracy 100%, one wrong commit in 300." |
| 2:50–3:00 | Back to the page | "ShelfSense: no language-model calls, a fraction of a millisecond per word, and zero wrong commits on the dev set. Thank you." |

Backup lines if something fails live: use *Try a sample* instead of typing, and the stream button instead of the microphone.
