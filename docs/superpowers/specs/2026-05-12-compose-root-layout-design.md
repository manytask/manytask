# Design: Compose files under repository root (`compose/`)

**Date:** 2026-05-12  
**Status:** Accepted (awaiting reader review before implementation planning)

## Summary

All Docker Compose definitions that currently live in `manytask/` are moved into a dedicated directory **`compose/`** at the repository root. Operators and developers run `docker compose` with **current working directory = repository root**, using `-f compose/<file>`.

This is a **breaking change**: paths such as `manytask/docker-compose.development.yml` cease to exist.

## Goals

- Single canonical location for Compose files under root (`compose/`).
- Predictable invocation: commands issued from repo root (`docker compose -f compose/…`).
- Correct resolution of build contexts, bind mounts, and `env_file` entries after the move.
- Updated automation and documentation (`Makefile`, GitHub Actions, `docs/`).

## Non-goals

- Changing application code, Dockerfile semantics, or image tags beyond what Compose paths require.
- Relocating the Python project tree (`manytask/` application package) out of its current layout.
- Modifying `.env.example` semantics except where documentation must reflect new `env_file` paths.

## Layout

```
<repo-root>/
  compose/
    docker-compose.production.yml
    docker-compose.development.yml
    docker-compose.sourcecraft.production.yml
    docker-compose.sourcecraft.development.yml
    docker-compose.sourcecraft.devstand.yaml
  manytask/
    Dockerfile
    …
  docs/
    …
  Makefile                     # new: thin wrapper for compose-centric targets (optional scope in plan)
```

## Path resolution rule

Compose resolves relative paths in `build`, `volumes`, and `env_file` relative to the **directory that contains each Compose file** (here: `compose/`). All updated paths assume the Compose file resides in **`compose/`**.

### Translation table (typical migrations)

Values below refer to YAML as used when the Compose file sits in **`compose/`**, preserving the same filesystem behavior as when the Compose file lived in **`manytask/`**.

| Concern | Old (`manytask/<compose>`) | New (`compose/<compose>`) |
|--------|----------------------------|---------------------------|
| Docs image build context | `context: ../docs` | `context: ../docs` (unchanged) |
| Application image build | `context: ..`, `dockerfile: manytask/Dockerfile`, `target: app` | Same triple (parent of `compose/` is repo root) |
| Bind mount for app package | `./manytask/:/app/manytask` | `../manytask/manytask:/app/manytask` |
| Dev cache bind mount | `.tmp/cache/:/cache` | `../manytask/.tmp/cache/:/cache` |
| Postgres init script | `./init-db.sh:/docker-entrypoint-initdb.d/init-db.sh` | `../manytask/init-db.sh:…` |
| Default app env file | `env_file: .env` | `env_file: ../manytask/.env` |
| Sourcecraft env file | `env_file: .env.sourcecraft` | `env_file: ../manytask/.env.sourcecraft` |

### `docker-compose.sourcecraft.devstand.yaml`

Today this file uses `build.context: .` without an explicit Dockerfile and binds `./manytask/`. After the move:

- Set `context: ..` and `dockerfile: manytask/Dockerfile` (and `target: app` aligned with sibling files) so the build matches other stacks.
- Set bind mounts using `../manytask/manytask` and cache path `../manytask/.tmp/cache` per the table above.

## Environment files

Development and Sourcecraft workflows keep **env files logically under `manytask/`** (e.g. `manytask/.env`, `manytask/.env.sourcecraft`). Compose must reference them explicitly via `env_file` paths from the table so behavior does not implicitly depend on a `.env` next to the Compose file.

Production deployments may use the same convention or symlink/copy env files server-side; the spec only requires Compose to reference **one explicit relative path per service** documented here.

## Root `Makefile`

Add a **thin** Makefile at repo root containing targets such as `dev`, `clean-db`, and optionally `reset-dev` that delegate to:

`docker compose -f compose/docker-compose.development.yml …`

Retain `manytask/Makefile` for Python workflows (`test`, `lint`, `migrate`, Alembic, etc.) unchanged except if a redundant `dev`/compose target remains there—in that case remove or deprecate duplicated compose targets in favor of the root Makefile to avoid divergence.

Exact target list is left to the implementation plan.

## CI

Update `.github/workflows/deploy.yaml`: replace

`manytask/docker-compose.development.yml`

with

`compose/docker-compose.development.yml`

(assuming the deployed tree layout matches repo root paths under `/srv/manytask/app_deploy`). If production uses a different file in the future, that is outside this spec unless explicitly changed.

## Documentation

Synchronize mentions of Compose paths and working directory in:

- `docs/local_development.md`
- `docs/deploy_guide.md`
- `docs/production.md` (ensure links—if any—to raw GitHub URLs and tree diagrams match `compose/` and root `-f compose/…`)
- `docs/dev.md`

## Backward compatibility

- Remove Compose files from `manytask/` after adding `compose/` copies (single source of truth).
- No symlink layer in `manytask/` unless a follow-up explicitly requires compat for external automation.

## Verification

Before treating the migration as complete:

1. Run `docker compose … config` (or equivalent) **from repo root** for each file under `compose/` and confirm no unresolved paths.
2. Smoke-test development stack (`development` compose) locally: docs, app, postgres, GitLab stacks as previously used.
3. Confirm CI deploy references the new path once server layout is updated accordingly.

## Open items for implementation plan only

- Whether root `Makefile` covers only `development` compose or additional profiles.
- Naming consistency (`docker compose` vs `docker-compose`) in docs to match documented Docker major version on target hosts.
