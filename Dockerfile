FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_ROOT_USER_ACTION=ignore
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/

# ---- test stage: lint + tests; the build stops here if anything fails ----
FROM base AS test
RUN pip install ".[dev]"
COPY tests/ tests/
RUN ruff check src tests && pytest -q

# ---- runtime: only the server dependencies, non-root ----
FROM base AS runtime
RUN pip install ".[server]" \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /data/artifacts && chown -R appuser /data
USER appuser
ENV STORAGE_DIR=/data/artifacts
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"
CMD ["uvicorn", "releasehub.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
