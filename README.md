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

## Course onboarding API

The bot exposes per-course admin endpoints under `/courses`. Every route is
authenticated with a Bearer token and validated against manytask `/ping`.

| Method | Route               | Auth                                   |
|--------|---------------------|----------------------------------------|
| `POST`   | `/courses/<name>`   | `Authorization: Bearer <COURSE_TOKEN>` |
| `DELETE` | `/courses/<name>`   | `Authorization: Bearer <COURSE_TOKEN>` or `Bearer <BOT_ADMIN_TOKEN>` |
| `GET`    | `/courses`          | `Authorization: Bearer <BOT_ADMIN_TOKEN>` |
| `GET`    | `/healthz`          | none                                   |

The `<COURSE_TOKEN>` is the same token the course uses for manytask
(`/api/<course>/report` etc.). The bot validates it by calling
`GET <MANYTASK_BASE_URL>/api/<name>/ping` and caches successful checks in Redis
for `BOT_PING_CACHE_TTL_SEC` seconds.

Push a course config from CI/CD:

```bash
curl -fSs -X POST "http://bot.example.com/courses/python-101" \
  -H "Authorization: Bearer $COURSE_TOKEN" \
  -H "Content-Type: application/x-yaml" \
  --data-binary @manytask.yml
```

Possible responses:

- `201 Created` — config persisted, course included in the next polling tick.
- `403 Forbidden` — token rejected by manytask `/ping` (e.g. cross-course token).
- `404 Not Found` — manytask does not know the course at all.
- `422 Unprocessable Entity` — YAML parse error or `mr_review` section invalid.
- `502 Bad Gateway` — manytask is unreachable; retry later.

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
