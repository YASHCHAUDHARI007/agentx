# ShelfSense service. Stage 1 builds the Next.js front end to static files; stage 2 is Python
# only (standard library), serving the API and those files. No Node.js at run time.
#   docker build -t shelfsense . && docker run -p 8080:8080 shelfsense
#   docker run -p 8080:8080 -e SHELFSENSE_API_KEYS=... -e REZOLVE_API_KEY=... -e REZOLVE_KB_ID=... shelfsense

FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY agent/ agent/
COPY server/ server/
COPY starter_kit/ps1-anticipatory-commerce/ starter_kit/ps1-anticipatory-commerce/
COPY tests/catalogues/ tests/catalogues/
COPY --from=web /web/out/ web/out/
RUN useradd --create-home shelfsense
USER shelfsense
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"
CMD ["python", "server/app.py", "--host", "0.0.0.0", "--port", "8080"]
