FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir '.[api,agent,cloud]'
COPY docs ./docs
RUN addgroup --system tarcsmem && adduser --system --ingroup tarcsmem tarcsmem \
    && mkdir -p /data && chown -R tarcsmem:tarcsmem /app /data
USER tarcsmem
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
CMD ["sh", "-c", "tarcsmem seed --db ${TARCSMEM_DB_PATH:-/data/tarcsmem.db} --if-empty && tarcsmem serve --db ${TARCSMEM_DB_PATH:-/data/tarcsmem.db} --host 0.0.0.0 --port 8000"]
