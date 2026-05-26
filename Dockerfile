FROM python:3.13-slim-bookworm AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev


FROM python:3.13-slim-bookworm AS runtime

# git is needed by the run: checklist step (shallow sparse clone).
# bash because the run: step pipes through `bash -c <command>`.
RUN apt-get update \
    && apt-get install --no-install-recommends -y git ca-certificates bash \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — the entire bot process plus every subprocess it spawns
# runs as this uid. Matches the trust model documented in README.
RUN useradd --create-home --uid 10001 botuser

WORKDIR /app

COPY --from=builder /app /app
RUN chown -R botuser:botuser /app

USER botuser

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
