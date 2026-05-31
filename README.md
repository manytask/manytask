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
- `app/api/` — HTTP routes (`/healthz`, `/courses`)
- `app/config.py` — settings via `pydantic-settings`
- `app/hosting/` — provider-agnostic protocol + GitLab adapter
- `app/manytask/` — manytask HTTP client
- `app/storage/` — Redis-backed stores
- `app/checklist/` — checklist runner and built-in steps
- `app/worker/` — poll loop, score processing, metrics
- `tests/` — pytest suite
