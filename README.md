# manytask-mr-reviewer

Universal merge-request review bot for [manytask](https://github.com/manytask) courses. Replaces the Python-specific `pythonbot-2025` with a course-agnostic skeleton.

## Architecture

```
+----------------+      poll      +-------------------+
|  Worker loop   | -------------> |  Hosting adapter  |  (GitLab today,
|  (app.worker)  |                |  (app.hosting)    |   GitHub later)
+--------+-------+                +---------+---------+
         |                                  |
         | run                              | comments
         v                                  v
+----------------+                +-------------------+
| Checklist      | <------------- |  Manytask client  |
| runner         |  task metadata |  (app.manytask)   |
+--------+-------+                +-------------------+
         |
         | dedupe / state
         v
+----------------+
|     Redis      |
| (app.storage)  |
+----------------+
```

The HTTP layer (FastAPI) exposes `/healthz` and admin endpoints under `/courses` to register or remove courses. A long-running worker reads course configs from Redis, polls each hosting provider for new MRs, runs the checklist, and posts comments back.

## Quick start

Requirements: Docker, Docker Compose, `uv` (for local development).

```bash
cp .env.example .env
docker compose -f docker-compose.development.yml up --build
```

Verify the bot is alive:

```bash
curl http://localhost:8000/healthz
# {"status":"ok"}
```

## Local development

```bash
uv sync
uv run pre-commit install
uv run pytest
```

Useful commands:

- `uv run ruff check .` — lint
- `uv run ruff format .` — format
- `uv run mypy app tests` — type check
- `uv run pre-commit run --all-files` — full quality pass

## Layout

- `app/main.py` — FastAPI factory and lifespan
- `app/api/` — HTTP routes (`/healthz`, `/courses`)
- `app/config.py` — settings via `pydantic-settings`
- `app/hosting/` — provider-agnostic protocol + GitLab adapter
- `app/manytask/` — manytask HTTP client
- `app/storage/` — Redis-backed stores
- `app/checklist/` — checklist runner and built-in steps
- `app/worker/` — background poll loop
- `tests/` — pytest suite
