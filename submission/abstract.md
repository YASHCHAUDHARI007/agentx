# ShelfSense: finds the product before the shopper finishes the sentence

**AgentX Challenge 1: Anticipatory Commerce** · code: https://github.com/YASHCHAUDHARI007/shelfsense

**Impact.** Voice and chat shoppers speak in fragments, change their minds mid-sentence ("size 8, I mean 7") and mix Hindi and English ("do hazaar se kam"). An assistant that waits for the full request feels slow; one that guesses early shows the wrong product and loses trust. ShelfSense reads each word as it arrives, searches once, and shows the product the moment only a correction could still change it.

**Results.** On the 300-request public dev set: score 44.3 against the baseline's 20.0, accuracy 1.000 (baseline 0.527), zero wrong commits, 1.04 searches per request, and every filter read correctly at the last word. On 1,200 generated requests with unseen phrasings (typos, Hinglish, "UK9", new correction phrases): accuracy 1.000, one wrong commit. On a second, unrelated electronics catalogue: accuracy 1.000 and one wrong commit in 300 requests, with no catalogue-specific code, only a five-line synonym file.

**Innovation.**
1. *Safe by construction.* Once one product alone fits what was said, a new constraint can only confirm it; only a correction can change it. So the commit decision reduces to one question, "could a correction still come?", answered from clause structure, correction and hesitation cues, and words the parser did not understand.
2. *Speech-aware commits.* Raw speech-to-text has no punctuation, so a correction can follow a complete request directly. ShelfSense switches to stricter rules until the input shows punctuation; on speech-style input this cut wrong commits from 19 to 1.
3. *Works on any catalogue.* Columns, filters and vocabulary are detected from the shop's CSV, with English and Hinglish language packs and automatic variants ("128GB" / "128 gigs").
4. *One search per request.* It fetches the products of the spoken category and colour once, then narrows locally as brand, size and budget arrive.
5. *Rezolve Labs semantic product search* over the catalogue knowledge base is the fallback for words the parser does not know. Clean requests never call it (0 of 300 dev requests), so it adds almost no cost.

**Cost estimate.** No language-model calls at run time. The agent uses 0.37 ms of CPU per request, including its local search (about 2,700 requests per second on one laptop core), and 0.03 ms per word (p95 0.15 ms), far below the ~300 ms between spoken words. At an assumed ₹4 per cloud core-hour, compute costs under ₹0.001 per 1,000 requests. Searches: 1.04 per request; Rezolve Labs credits: about 0.01 per request as a fallback, or about 1 per request if Rezolve becomes the main search for very large catalogues.

**Build.** Python standard library back end: a word-by-word parser (corrections, typo repair, Hinglish numbers), a measured commit policy, a catalogue profiler, a Rezolve Labs client, a streaming HTTP service that accepts live, revising speech transcripts (API keys, rate limits, Prometheus metrics, OpenAPI contract, Docker), a Next.js demo with microphone input, and 49 automated tests run in CI with a score gate.
