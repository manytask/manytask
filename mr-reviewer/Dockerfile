# Build context is the repository root (parent of mr-reviewer/); see the compose files.
FROM python:3.14-slim-bookworm AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

COPY mr-reviewer/pyproject.toml mr-reviewer/uv.lock mr-reviewer/README.md ./
RUN uv sync --locked --no-install-project --no-dev

COPY mr-reviewer/app ./app
RUN uv sync --locked --no-dev


FROM python:3.14-slim-bookworm AS app

# git is needed by the run: checklist step (shallow sparse clone).
# bash because the run: step pipes through `bash -c <command>`.
RUN apt-get update \
    && apt-get install --no-install-recommends -y git ca-certificates bash curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — the entire bot process plus every subprocess it spawns
# runs as this uid. Matches the trust model documented in README.
RUN useradd --create-home --uid 10001 botuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY mr-reviewer/app /app/app
RUN chown -R botuser:botuser /app

USER botuser

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
