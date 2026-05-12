# Compose Root Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all Docker Compose files from `manytask/` into `compose/` at the repository root with corrected relative paths, wire CI/docs/root Makefile, and remove duplicate definitions under `manytask/`.

**Architecture:** Canonical Compose files live in `compose/`. Paths are resolved relative to `compose/` (Compose file parent directory). Operators use repository root as the working directory and pass `-f compose/<file>`. A root `Makefile` holds `dev` / `clean-db` / `reset-dev`; `manytask/Makefile` delegates to the parent so `make dev` still works from `manytask/`.

**Tech stack:** Docker Compose v2 (`docker compose`), GNU Make, YAML, GitHub Actions.

---

## File map (what changes)

| Path | Action |
|------|--------|
| `compose/docker-compose.production.yml` | Create (migrated + path fixes) |
| `compose/docker-compose.development.yml` | Create |
| `compose/docker-compose.sourcecraft.production.yml` | Create |
| `compose/docker-compose.sourcecraft.development.yml` | Create |
| `compose/docker-compose.sourcecraft.devstand.yaml` | Create |
| `Makefile` | Create at repo root |
| `manytask/Makefile` | Modify `dev` / `clean-db` / `reset-dev` to delegate to parent |
| `manytask/docker-compose*.yml` and `manytask/docker-compose*.yaml` | Delete (five files) |
| `.github/workflows/deploy.yaml` | Update `-f` path |
| `docs/local_development.md` | Update compose paths and working directory |
| `docs/dev.md` | Same |
| `docs/deploy_guide.md` | Same + tree diagram lines if present |
| `docs/production.md` | Links + curl examples + `-f compose/…` |
| `docs/system_setup.md` | Optional wording if it references compose examples |
| `docs/superpowers/specs/2026-05-12-compose-root-layout-design.md` | No logic change; optional cross-link from plan only |

**Out of scope for this plan:** `terraform/cloud-init/manytask.yaml` embeds a self-contained `/opt/manytask/docker-compose.yml` for VMs; it does not track the git repo layout. Aligning that template with `compose/` is a separate hardening task.

---

### Task 1: Add `compose/docker-compose.production.yml`

**Files:**

- Create: `compose/docker-compose.production.yml`

- [ ] **Step 1: Create the file with the content below** (only change from `manytask/docker-compose.production.yml`: `env_file` for service `manytask` → `../manytask/.env`).

```yaml
networks:
  manytask-net:
    name: nginx-manytask-net
    driver: bridge

volumes:
    cache:
    solutions:
    acme:
        name: acme
    certs:
        name: certs
    vhost:
        name: vhost
    html:
        name: html
    conf:
        name: conf

services:
    nginx-proxy:
        image: nginxproxy/nginx-proxy:1.7.0
        container_name: nginx-proxy
        restart: always
        ports:
            - "80:80"
            - "443:443"
        environment:
            DHPARAM_SKIP: "true"
        volumes:
            - certs:/etc/nginx/certs:ro
            - vhost:/etc/nginx/vhost.d
            - html:/usr/share/nginx/html
            - /var/run/docker.sock:/tmp/docker.sock:ro
            - conf:/etc/nginx/conf.d
        networks:
            - manytask-net

    acme-companion:
        image: nginxproxy/acme-companion:2.5.2
        container_name: nginx-proxy-acme
        restart: always
        environment:
            DEFAULT_EMAIL: no-reply@manytask.org
            NGINX_PROXY_CONTAINER: nginx-proxy
        volumes:
            - /var/run/docker.sock:/var/run/docker.sock:ro
            - acme:/etc/acme.sh
            - certs:/etc/nginx/certs:rw
            - vhost:/etc/nginx/vhost.d:rw
            - html:/usr/share/nginx/html:rw
        networks:
            - manytask-net
    docs:
        build:
            context: ../docs
        container_name: manytask-docs
        restart: always
        expose:
            - "80"
        environment:
            VIRTUAL_HOST: ${DOCS_HOST}
            VIRTUAL_PORT: 80
            LETSENCRYPT_HOST: ${DOCS_HOST}
        healthcheck:
            test: [ "CMD", "curl", "-f", "http://localhost:80" ]
            interval: 1m
            timeout: 15s
            retries: 3
            start_period: 30s
        networks:
            - manytask-net
    manytask:
        # image: manytask/manytask:latest  # set SPECIFIC version you'll use
        build:
            dockerfile: manytask/Dockerfile
            context: ..
            target: app
        container_name: manytask  # change this to your project name
        restart: always
        expose:
            - "5050"
        env_file: ../manytask/.env
        environment:
            VIRTUAL_HOST: ${APP_HOST}
            VIRTUAL_PORT: 5050
            LETSENCRYPT_HOST: ${APP_HOST}
            LETSENCRYPT_EMAIL: no-reply@manytask.org
        volumes:
            - cache:/cache
        networks:
            - manytask-net
```

- [ ] **Step 2: Commit**

```bash
git add compose/docker-compose.production.yml
git commit -m "chore(compose): add production stack under compose/"
```

---

### Task 2: Add `compose/docker-compose.development.yml`

**Files:**

- Create: `compose/docker-compose.development.yml`

- [ ] **Step 1: Create the file** (`docs` context unchanged; `manytask` + `postgres` `env_file` and volume paths adjusted for `compose/` base).

```yaml
networks:
    manytask-dev-net:
        name: manytask-dev-net
        driver: bridge

services:

    docs:
        build:
            context: ../docs
        container_name: test-manytask-docs
        restart: always
        environment:
            VIRTUAL_HOST: localhost
            VIRTUAL_PORT: 80
            LETSENCRYPT_HOST: localhost
        ports:
            - "8080:80"
        healthcheck:
            test: [ "CMD", "curl", "-f", "http://localhost:8080" ]
            interval: 1m
            timeout: 15s
            retries: 3
            start_period: 30s
        networks:
            - manytask-dev-net

    manytask:
        build:
            context: ..
            dockerfile: manytask/Dockerfile
            target: app
        container_name: test-manytask
        env_file: ../manytask/.env
        environment:
            VIRTUAL_HOST: localhost
            VIRTUAL_PORT: 5050
            LETSENCRYPT_HOST: localhost
        ports:
            - "8081:5050"
        volumes:
            - ../manytask/manytask:/app/manytask
            - ../manytask/.tmp/cache:/cache
        networks:
            - manytask-dev-net

    postgres:
        image: postgres:17
        container_name: manytask_postgres
        env_file: ../manytask/.env
        expose:
            - "5432"
        volumes:
            - postgres_data:/var/lib/postgresql/data
            - ../manytask/init-db.sh:/docker-entrypoint-initdb.d/init-db.sh
        healthcheck:
            test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
            interval: 5s
            timeout: 5s
            retries: 5
        networks:
            - manytask-dev-net

    gitlab:
        image: gitlab/gitlab-ce:latest
        container_name: manytask_gitlab
        restart: always
        hostname: gitlab
        environment:
            GITLAB_ROOT_PASSWORD: "changeme123!"
            GITLAB_OMNIBUS_CONFIG: |
                external_url 'http://localhost:8929'
                gitlab_rails['gitlab_shell_ssh_port'] = 8222
                prometheus_monitoring['enable'] = false
                alertmanager['enable'] = false
                node_exporter['enable'] = false
                redis_exporter['enable'] = false
                postgres_exporter['enable'] = false
                gitlab_exporter['enable'] = false
                gitlab_kas['enable'] = false
                puma['worker_processes'] = 0
                sidekiq['concurrency'] = 10
        ports:
            - "8929:8929"    # HTTP web UI
            - "8222:22"      # SSH (optional)
        shm_size: '256m'
        volumes:
            - gitlab_config:/etc/gitlab
            - gitlab_logs:/var/log/gitlab
            - gitlab_data:/var/opt/gitlab
        networks:
            - manytask-dev-net

    gitlab-runner:
        image: gitlab/gitlab-runner:alpine
        container_name: manytask_gitlab_runner
        restart: always
        volumes:
            - gitlab_runner_config:/etc/gitlab-runner
            - /var/run/docker.sock:/var/run/docker.sock
        depends_on:
            - gitlab
        networks:
            - manytask-dev-net

volumes:
    postgres_data:
        name: manytask_postgres_data
    gitlab_config:
        name: manytask_gitlab_config
    gitlab_logs:
        name: manytask_gitlab_logs
    gitlab_data:
        name: manytask_gitlab_data
    gitlab_runner_config:
        name: manytask_gitlab_runner_config
```

- [ ] **Step 2: Commit**

```bash
git add compose/docker-compose.development.yml
git commit -m "chore(compose): add development stack under compose/"
```

---

### Task 3: Add Sourcecraft Compose files

**Files:**

- Create: `compose/docker-compose.sourcecraft.production.yml`
- Create: `compose/docker-compose.sourcecraft.development.yml`
- Create: `compose/docker-compose.sourcecraft.devstand.yaml`

- [ ] **Step 1: Create `compose/docker-compose.sourcecraft.production.yml`**

```yaml
networks:
  manytask-net:
    external: true
    name: nginx-manytask-net

volumes:
    cache:

services:
    manytask-src:
        # image: manytask/manytask:latest  # set SPECIFIC version you'll use
        build:
            dockerfile: manytask/Dockerfile
            context: ..
            target: app
        container_name: manytask-src  # change this to your project name
        restart: always
        expose:
            - "5050"
        env_file: ../manytask/.env.sourcecraft
        environment:
            VIRTUAL_HOST: ${SRC_APP_HOST}
            VIRTUAL_PORT: 5050
            LETSENCRYPT_HOST: ${SRC_APP_HOST}
            LETSENCRYPT_EMAIL: no-reply@manytask.org
        volumes:
            - cache:/cache
        networks:
            - manytask-net
```

- [ ] **Step 2: Create `compose/docker-compose.sourcecraft.development.yml`**

```yaml
services:

    docs:
        build:
            context: ../docs
        container_name: test-manytask-docs
        restart: always
        network_mode: bridge
        environment:
            VIRTUAL_HOST: localhost
            VIRTUAL_PORT: 80
            LETSENCRYPT_HOST: localhost
        ports:
            - "8080:80"
        healthcheck:
            test: [ "CMD", "curl", "-f", "http://localhost:8080" ]
            interval: 1m
            timeout: 15s
            retries: 3
            start_period: 30s

    manytask:
        build:
            context: ..
            dockerfile: manytask/Dockerfile
            target: app
        container_name: test-manytask
        network_mode: bridge
        env_file: ../manytask/.env.sourcecraft
        environment:
            VIRTUAL_HOST: localhost
            VIRTUAL_PORT: 5050
            LETSENCRYPT_HOST: localhost
        ports:
            - "8081:5050"
        volumes:
            - ../manytask/manytask:/app/manytask
            - ../manytask/.tmp/cache:/cache
        links:
            - postgres:postgres

    postgres:
        image: postgres:17
        container_name: manytask_postgres
        network_mode: bridge
        env_file: ../manytask/.env.sourcecraft
        expose:
            - "5432"
        volumes:
            - postgres_data:/var/lib/postgresql/data
            - ../manytask/init-db.sh:/docker-entrypoint-initdb.d/init-db.sh
        healthcheck:
            test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
            interval: 5s
            timeout: 5s
            retries: 5


volumes:
    postgres_data:
        name: manytask_postgres_data
```

- [ ] **Step 3: Create `compose/docker-compose.sourcecraft.devstand.yaml`**

```yaml
services:
    manytask:
        build:
            context: ..
            dockerfile: manytask/Dockerfile
            target: app
        container_name: test-manytask-src
        network_mode: bridge
        env_file: ../manytask/.env.sourcecraft
        environment:
            VIRTUAL_HOST: src.manytask2.org
            VIRTUAL_PORT: 5050
            LETSENCRYPT_HOST: src.manytask2.org
        ports:
            - "8082:5050"
        volumes:
            - ../manytask/manytask:/app/manytask
            - ../manytask/.tmp/cache:/cache
        links:
            - postgres:postgres

    postgres:
        image: postgres:17
        container_name: manytask_postgres-src
        network_mode: bridge
        env_file: ../manytask/.env.sourcecraft
        expose:
            - "5432"
        volumes:
            - postgres_data:/var/lib/postgresql/data
            - ../manytask/init-db.sh:/docker-entrypoint-initdb.d/init-db.sh
        healthcheck:
            test: ["CMD-SHELL", "pg_isready -U manytask -d manytask"]
            interval: 5s
            timeout: 5s
            retries: 5


volumes:
    postgres_data:
        name: manytask_src_postgres_data
```

- [ ] **Step 4: Commit**

```bash
git add compose/docker-compose.sourcecraft.production.yml compose/docker-compose.sourcecraft.development.yml compose/docker-compose.sourcecraft.devstand.yaml
git commit -m "chore(compose): add sourcecraft compose variants under compose/"
```

---

### Task 4: Root `Makefile` and delegation from `manytask/Makefile`

**Files:**

- Create: `Makefile` (repository root)
- Modify: `manytask/Makefile` (`dev`, `clean-db`, `reset-dev`)

- [ ] **Step 1: Add root `Makefile`**

```makefile
# Run from repository root: docker compose -f compose/docker-compose.development.yml …
COMPOSE ?= docker compose
DEV_COMPOSE_FILE := compose/docker-compose.development.yml

.PHONY: dev clean-db reset-dev

dev:
	$(COMPOSE) -f $(DEV_COMPOSE_FILE) down
	$(COMPOSE) -f $(DEV_COMPOSE_FILE) up --build

clean-db:
	$(COMPOSE) -f $(DEV_COMPOSE_FILE) down -v
	docker volume prune -f

reset-dev: clean-db
	$(COMPOSE) -f $(DEV_COMPOSE_FILE) up --build
```

- [ ] **Step 2: Edit `manytask/Makefile` — remove `DOCKER_COMPOSE_DEV` if unused, replace `dev` / `clean-db` / `reset-dev` bodies with delegation:**

Add after line 13 (`export TESTCONTAINERS_RYUK_DISABLED`), or remove the old `DOCKER_COMPOSE_DEV` line and use:

Replace the block from `dev:` through `reset-dev:` (lines 26–35) with:

```makefile
dev:
	$(MAKE) -C .. dev

clean-db:
	$(MAKE) -C .. clean-db

reset-dev:
	$(MAKE) -C .. reset-dev
```

Delete the line `DOCKER_COMPOSE_DEV := docker-compose.development.yml` at line 3 (no longer needed).

- [ ] **Step 3: Verify**

Run from repository root (requires `manytask/.env` present — copy from `manytask/.env.example` if needed):

```bash
docker compose -f compose/docker-compose.development.yml config >/dev/null && echo OK
```

Expected: `OK` (no YAML/resolve errors).

- [ ] **Step 4: Commit**

```bash
git add Makefile manytask/Makefile
git commit -m "build: root Makefile for compose dev; manytask Makefile delegates"
```

---

### Task 5: GitHub Actions deploy path

**Files:**

- Modify: `.github/workflows/deploy.yaml` line 23

- [ ] **Step 1: Replace** `manytask/docker-compose.development.yml` with `compose/docker-compose.development.yml` in the `script: |` block.

Expected line:

```yaml
          sudo docker compose -f compose/docker-compose.development.yml up --build --force-recreate -d
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/deploy.yaml
git commit -m "ci: point deploy workflow at compose/docker-compose.development.yml"
```

**Note:** Confirm the server clone at `/srv/manytask/app_deploy` has the new `compose/` directory after `git pull` on `main`.

---

### Task 6: Documentation updates

**Files:**

- Modify: `docs/local_development.md`
- Modify: `docs/dev.md`
- Modify: `docs/deploy_guide.md`
- Modify: `docs/production.md`
- Modify: `docs/system_setup.md` (only if it references concrete compose filenames)

- [ ] **Step 1: `docs/local_development.md`**

  - State that Compose lives under `compose/` and commands assume **current working directory = repository root**.
  - Replace every `docker-compose -f docker-compose.development.yml` with `docker compose -f compose/docker-compose.development.yml` (or document both `docker compose` plugin vs legacy binary consistently with the rest of the file).
  - Update the bullet that says `docker-compose.development.yml` to `compose/docker-compose.development.yml`.

- [ ] **Step 2: `docs/dev.md`**

  - Same replacement pattern for the example `up --build` command.

- [ ] **Step 3: `docs/deploy_guide.md`**

  - Replace `sudo docker compose -f docker-compose.development.yml` with `sudo docker compose -f compose/docker-compose.development.yml` (add a note that these commands run from repo root).
  - Update the directory tree snippet around line 172 so `docker-compose.development.yml` appears under `compose/` (e.g. `compose/docker-compose.development.yml`).

- [ ] **Step 4: `docs/production.md`**

  - Fix internal links from `/docker-compose.production.yml` to `/compose/docker-compose.production.yml` (GitHub-style paths).
  - Update `curl` example raw URLs from `.../main/docker-compose.development.yml` to `.../main/compose/docker-compose.development.yml`.
  - Update example commands to `docker compose -f compose/docker-compose.production.yml` (and logs similarly).

- [ ] **Step 5: `docs/system_setup.md`**

  - If line 44 references a concrete compose filename, point to `compose/` or keep generic wording.

- [ ] **Step 6: Commit**

```bash
git add docs/local_development.md docs/dev.md docs/deploy_guide.md docs/production.md docs/system_setup.md
git commit -m "docs: describe compose under compose/ and repo-root workflow"
```

---

### Task 7: Remove old Compose files under `manytask/`

**Files:**

- Delete: `manytask/docker-compose.production.yml`
- Delete: `manytask/docker-compose.development.yml`
- Delete: `manytask/docker-compose.sourcecraft.production.yml`
- Delete: `manytask/docker-compose.sourcecraft.development.yml`
- Delete: `manytask/docker-compose.sourcecraft.devstand.yaml`

- [ ] **Step 1: Delete the five files** (only after Tasks 1–3 merged locally or present in branch).

- [ ] **Step 2: Commit**

```bash
git add -u manytask/
git commit -m "chore: remove compose files from manytask/ (moved to compose/)"
```

---

### Task 8: Validation checklist

- [ ] **Step 1:** From repository root, run `docker compose` **`config`** for each file:

```bash
cd /path/to/repo
for f in compose/docker-compose.production.yml compose/docker-compose.development.yml compose/docker-compose.sourcecraft.production.yml compose/docker-compose.sourcecraft.development.yml compose/docker-compose.sourcecraft.devstand.yaml; do
  docker compose -f "$f" config >/dev/null && echo "$f OK" || echo "$f FAIL"
done
```

Placeholders: `manytask/.env` and `manytask/.env.sourcecraft` must exist or Compose may report missing env file — create empty copies from `.env.example` for local validation only (do not commit secrets).

- [ ] **Step 2:** From `manytask/`, run `make dev` — should invoke parent Makefile and use `compose/docker-compose.development.yml` (abort with Ctrl+C after images start if desired).

- [ ] **Step 3:** `git grep manytask/docker-compose` from repo root — expected: **no matches** except possibly changelog or historical notes; fix stragglers.

- [ ] **Step 4:** Final commit if any grep fixes.

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Directory `compose/` with five files | Tasks 1–3 |
| Path rules / `env_file` under `manytask/` | Tasks 1–3 |
| Devstand explicit Dockerfile + context | Task 3 |
| Root Makefile | Task 4 |
| CI path | Task 5 |
| Docs | Task 6 |
| Remove old manytask compose | Task 7 |
| `docker compose config` verification | Task 8 |

## Plan complete handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-12-compose-root-layout.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach would you prefer?
