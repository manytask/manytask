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

The HTTP layer (FastAPI) exposes `/healthz` and admin endpoints under `/courses` to register or remove courses.

## Polling worker

On startup the bot launches a background worker (`app/worker/loop.py`) as an
asyncio task. Every `POLL_INTERVAL_SEC` (default 900) it:

1. Re-reads all courses from Redis (`CourseStore`) — a `DELETE /courses` mid-cycle
   is handled gracefully.
2. For each course, for each task with `manual_review: true`, lists open MRs in
   the course's `gitlab_group` labelled with the task name.
3. Runs the checklist and upserts the summary comment + labels.
4. Processes new reviewer score comments: a comment matching the course's
   `score_comment_pattern` (default `Score: {score}`) from a verified course admin
   is reported to manytask with `allow_reduction=true` and `check_deadline=false`
   (a manual override is authoritative — not capped by a prior score, not reduced
   by the deadline multiplier).

Each MR is processed under a `PER_MR_TIMEOUT_SEC` (default 120) guard so one slow
MR cannot stall the cycle. Admin verification uses manytask
`GET /api/<course>/is_admin?rms_username=<gitlab username>` (the deployed endpoint
keys on `rms_username`; the bot relies on "GitLab username == manytask username").

## Observability & reliability

### Endpoints

- `GET /healthz` — liveness. Returns `200 {"status":"ok"}` when Redis answers
  `PING` and the time since the last **completed** poll cycle (or process
  start, before any cycle finishes) is within `HEALTHZ_POLL_STALE_SEC`
  (default 1800s). `last_poll_timestamp` is seeded at boot and refreshed only
  when a poll cycle completes. Returns `503` if Redis is unreachable or that
  watermark is too old; the Docker `HEALTHCHECK` uses this to recycle a wedged
  container.

  - Before the first cycle completes, the boot-time seed is the watermark — a
    fresh bot reports healthy only while that first cycle runs **shorter** than
    `HEALTHZ_POLL_STALE_SEC`. The timestamp does not advance mid-cycle.
  - A poll cycle still in progress when `HEALTHZ_POLL_STALE_SEC` elapses since
    the last completion (or boot) makes `/healthz` return 503 even if the
    worker is actively processing MRs; with Docker `restart: always` that can
    recycle a still-healthy container.
  - **Ops:** set `HEALTHZ_POLL_STALE_SEC` comfortably above the worst-case full
    poll-cycle duration (scales with number of MRs × `PER_MR_TIMEOUT_SEC`),
    otherwise long but healthy in-progress cycles look stale and trigger
    restarts.

- `GET /metrics` — Prometheus exposition (unauthenticated; restrict network
  access to the scraper). Metrics:
  - `poll_cycles_total`, `poll_cycle_overlapping_total`, `poll_duration_seconds`
  - `mrs_processed_total{course}`
  - `checklist_failures_total{course,type}`
  - `manytask_errors_total{endpoint}`
  - `run_step_duration_seconds{course,task}`

### Logging

Logs are emitted to stdout. `LOG_JSON=true` (default) serializes each record as
JSON; set `LOG_JSON=false` for human-readable local dev. The default level is
`LOG_LEVEL` (falls back to `INFO` if set to an unknown value). Per-module
overrides use `LOG_MODULE_LEVELS`, e.g.
`app.worker=DEBUG,app.manytask=WARNING` (format `module=LEVEL,module2=LEVEL`;
malformed entries and unknown levels are ignored).

### Reliability

- Transient Manytask failures (transport errors / 5xx) and GitLab failures
  (connection/timeout / 5xx) are retried with exponential backoff
  (`MANYTASK_RETRY_*` / `GITLAB_RETRY_*`; default 3 attempts each, 1 = no
  retry).
- The GitLab adapter watches `RateLimit-Remaining`; when the remaining budget
  drops below `GITLAB_RATE_LIMIT_THRESHOLD` of `RateLimit-Limit` it sleeps until
  `RateLimit-Reset` (capped at `GITLAB_RATE_LIMIT_MAX_SLEEP_SEC`; uses
  `GITLAB_RATE_LIMIT_FALLBACK_SLEEP_SEC` when `RateLimit-Reset` is missing).
- Retrying the GitLab note-creation POST on an ambiguous 5xx/timeout can in rare
  cases create a duplicate anchored comment if GitLab persisted the first
  request — an accepted tradeoff of blanket 5xx retry on blocking GitLab calls.

### HEALTHCHECK runbook

The image declares `HEALTHCHECK` with `curl -fsS http://localhost:8000/healthz`
(`-f` fails on HTTP 503). Development compose sets `restart: always` on the
bot service.

Manual test:

1. Start the stack:

```bash
docker compose -f docker-compose.development.yml up --build -d
```

2. Confirm the container is healthy:

```bash
docker inspect --format '{{.State.Health.Status}}' mrr-bot
# healthy
```

3. Confirm `/healthz` responds OK:

```bash
curl http://localhost:8000/healthz
# {"status":"ok"}
```

4. Stop Redis:

```bash
docker stop mrr-redis
```

5. Confirm `/healthz` now returns 503:

```bash
curl -i http://localhost:8000/healthz
# HTTP/1.1 503 Service Unavailable
```

6. After ~90s, confirm the container is unhealthy; with `restart: always` the
   container is recycled:

```bash
docker inspect --format '{{.State.Health.Status}}' mrr-bot
# unhealthy
```

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
| `GET`    | `/metrics`          | none (Prometheus exposition)           |

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

The `mr_review` section in the course YAML requires `gitlab_group` (GitLab group
path scanned for student MRs) and supports optional `score_comment_pattern` and
per-task `manual_review` (defaults to `true`; set `false` to skip a task in the
polling worker). Example:

```yaml
mr_review:
  gitlab_group: python/students-2025-fall
  score_comment_pattern: "Score: {score}"
  tasks:
    - name: compgraph
      manual_review: true
      checklist:
        - type: pipeline_passed
```

## Hosting providers

The bot reads MRs through a provider-agnostic `HostingAdapter` interface
defined in `app/hosting/protocol.py`. Today only GitLab is wired up
(`app/hosting/gitlab_adapter.py`); SourceCraft will arrive as a sibling
implementation without touching the worker or the checklist runner.

All sync `python-gitlab` calls run on a dedicated `ThreadPoolExecutor`
(`BOT_HOSTING_EXECUTOR_WORKERS=32` by default) so they never block FastAPI's
default executor. Per-MR work uses `asyncio.gather` in batches of 16 to keep
the GitLab connection pool healthy on courses with thousands of open MRs.

The factory is `app.hosting.build_hosting_adapter(hosting_type, ...)`. Add a
new provider by implementing `HostingAdapter` and extending the factory.

## Checklist & `run:` trust model

The bot runs an ordered list of checks for every open MR:

- `pipeline_passed` — head pipeline must be `success`.
- `forbidden_files` — no files with blacklisted extensions.
- `folder_structure` — every change lives under a configured prefix.
- `run` — runs `<command>` in a sandboxed subprocess.

Summary is rendered to Markdown via Jinja2 and posted to the MR with an
anchor of the form `<!-- mr-reviewer:checklist:<task_name> -->`. The bot
upserts its own comment by anchor + author filter — a student cannot make
the bot edit a forged comment by faking the anchor.

### `run:` sandbox

- Working directory: shallow sparse clone of the MR's source branch, with
  sparse-checkout restricted to files changed in the MR. A 5 MiB student
  task occupies under 100 MiB on disk because the rest of the repo is
  fetched as blobless references.
- Environment: explicit whitelist of `MR_ID`, `MR_URL`, `COURSE_NAME`,
  `MANYTASK_COURSE_TOKEN`, `PATH`, `HOME`, `LANG`. **No `GITLAB_TOKEN`** —
  course scripts cannot exfiltrate the bot's GitLab credentials.
- Timeout: `BOT_RUN_STEP_TIMEOUT_SEC` (default 60s). Process is killed and
  the step reports a failure if it overruns.
- Uid: in MVP the `run:` step executes inside the same container as the
  rest of the bot, under the container's non-root `botuser` (uid 10001).
  This means **course `run:` commands are trusted code** — a malicious
  course could read other courses' configs from memory. Run only courses
  whose teaching staff you trust. A future ticket will move `run:` into
  per-MR ephemeral pods for full isolation.
- Stdout: truncated to the first 4 KiB before being placed into the
  checklist comment. Stderr: logged with the GitLab token redacted.

The bot also applies labels:

- `checklist` — always applied after a run (the bot processed the MR).
- `fix it` — applied additionally when at least one step failed; removed
  when all checks pass.

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
- `app/api/` — HTTP routes (`/healthz`, `/metrics`, `/courses`)
- `app/config.py` — settings via `pydantic-settings`
- `app/observability/` — Prometheus metrics + loguru configuration
- `app/hosting/` — provider-agnostic protocol + GitLab adapter
- `app/manytask/` — manytask HTTP client
- `app/storage/` — Redis-backed stores
- `app/checklist/` — checklist runner and built-in steps
- `app/worker/` — poll loop and score processing
- `tests/` — pytest suite
