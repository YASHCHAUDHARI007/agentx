# ShelfSense: common tasks. Standard library only; nothing to install.
PY ?= python3

.PHONY: test score gate serve web web-dev docker help

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

test:            ## unit, service and regression tests (score floors included)
	$(PY) -m unittest discover tests

score:           ## official evaluator on the 300-request dev set
	$(PY) starter_kit/ps1-anticipatory-commerce/evaluate.py --agent agent/agent.py

gate:            ## fail if the dev score drops below 44.0 or any wrong commit appears
	$(PY) starter_kit/ps1-anticipatory-commerce/evaluate.py --agent agent/agent.py \
	  | $(PY) tools/quality_gate.py - --min-score 44.0 --max-wrong 0 --min-accuracy 0.99

serve:           ## demo page and API on http://localhost:8080 (serves web/out once built)
	$(PY) server/app.py

web:             ## build the Next.js front end into web/out
	cd web && npm ci --no-audit --no-fund && npm run build

web-dev:         ## API on :8080 plus Next.js dev server with hot reload on :3000
	SHELFSENSE_CORS_ORIGINS=http://localhost:3000 $(PY) server/app.py & \
	cd web && NEXT_PUBLIC_API_BASE=http://localhost:8080 npm run dev; kill %1

docker:          ## build and run the image
	docker build -t shelfsense . && docker run --rm -p 8080:8080 shelfsense
