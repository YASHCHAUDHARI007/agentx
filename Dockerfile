# ShelfSense service: python only, no dependencies.
#   docker build -t shelfsense . && docker run -p 8080:8080 shelfsense
#   docker run -p 8080:8080 -e REZOLVE_API_KEY=... -e REZOLVE_KB_ID=... shelfsense
FROM python:3.12-slim
WORKDIR /app
COPY agent/ agent/
COPY server/ server/
COPY starter_kit/ps1-anticipatory-commerce/ starter_kit/ps1-anticipatory-commerce/
COPY tests/catalogues/ tests/catalogues/
RUN useradd --create-home shelfsense
USER shelfsense
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"
CMD ["python", "server/app.py", "--host", "0.0.0.0", "--port", "8080"]
