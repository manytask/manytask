# Development guide

This guide explains how to set up a local development environment for Manytask, with both Manytask and a local GitLab instance running in Docker containers. It also covers how OAuth authentication works in this setup, how to add a course, run tests, and an overview of the project layout.

## Prerequisites

Before starting development, ensure you have:

- **Docker** and **Docker Compose** installed.
- **Colima** installed (macOS).
- A checkout of the repository. All Docker commands assume **`manytask/`** as the working directory unless stated otherwise.

### Minimum Colima configuration for local GitLab

A local GitLab instance needs enough resources. Start Colima with at least:

```bash
colima start --memory 4 --cpu 2 --disk 100
```

You can verify current resources with:

```bash
colima list
```

## Quick start (recommended)

The fastest way to get a fully working stack — Manytask + local GitLab in Docker — is the bundled startup script:

```bash
cd manytask
./scripts/start_local_dev.sh
```

If `.env` is missing, the script creates it from `.env.example`.

The script does the following:

1. Starts the Docker containers (Manytask, Postgres, local GitLab).
2. Waits for GitLab to become ready.
3. Runs `scripts/setup_local_gitlab.sh`, which:
   - creates or reuses an admin Personal Access Token (`manytask-admin`),
   - creates or reuses the OAuth application (`manytask-local`),
   - reads the runner registration token and tries to register a local runner.
4. Appends the following keys to `.env` (without overwriting existing values):
   - `GITLAB_URL`
   - `GITLAB_OAUTH_URL`
   - `GITLAB_ADMIN_TOKEN`
   - `GITLAB_CLIENT_ID`
   - `GITLAB_CLIENT_SECRET`
5. Restarts Manytask to pick up the updated environment variables.

After the script finishes, Manytask is available at [http://localhost:8081/](http://localhost:8081/) and the local GitLab at [http://localhost:8929/](http://localhost:8929/).

Continue with [Adding a course](#adding-a-course) below.

## Manual setup (using an existing GitLab)

Use this path if you want to develop against an existing GitLab server (for example [https://gitlab.manytask2.org/](https://gitlab.manytask2.org/)) instead of the bundled local GitLab. You will need **Admin access** to that GitLab; access to `gitlab.manytask2.org` can be requested from **[@artemzhmurov](https://t.me/artemzhmurov)**.

### Step 1 — Create a Personal Access Token in GitLab

1. In the GitLab web interface, click your user icon, go to **Preferences → Access Tokens**.
2. Create an admin token with the following scopes: `api`, `read_api`, `read_user`, `read_repository`, `write_repository`, `read_registry`, `write_registry`, `sudo`, `admin_mode`.
3. Copy the token — you'll put it into `GITLAB_ADMIN_TOKEN` in `.env`.

### Step 2 — Register the application in GitLab

1. In the GitLab web interface, go to **Admin Area → Applications**.
2. Create an application:
   - **Permissions / scopes**: `api`, `read_user`, `sudo`, `openid`, `profile`, `email`.
   - Mark as **Trusted**.
   - **Callback URL**: `http://localhost:8081/login_finish`.
3. Copy the **Application ID** and **Secret** into `GITLAB_CLIENT_ID` and `GITLAB_CLIENT_SECRET` in `.env`.

### Step 3 — Prepare the `.env` file

Copy [`manytask/.env.example`](manytask/.env.example) to `manytask/.env` and fill in the values. The relevant variables are:

| Variable                 | Description                                                                                                       |
|--------------------------|-------------------------------------------------------------------------------------------------------------------|
| `FLASK_SECRET_KEY`       | Random string                                                                                                     |
| `GITLAB_URL`             | Internal API URL used by the Manytask container (e.g. `http://gitlab:8929` for the local stack, or the public URL of an external GitLab) |
| `GITLAB_OAUTH_URL`       | Browser-facing GitLab URL used for OAuth redirects (e.g. `http://localhost:8929`)                                  |
| `GITLAB_ADMIN_TOKEN`     | Personal Access Token from Step 1                                                                                 |
| `GITLAB_CLIENT_ID`       | Application ID from Step 2                                                                                        |
| `GITLAB_CLIENT_SECRET`   | Application Secret from Step 2                                                                                    |
| `APPLY_MIGRATIONS`       | Apply DB migrations on startup (`true` by default)                                                                |
| `INITIAL_INSTANCE_ADMIN` | Your GitLab username — granted instance-admin rights on first start                                                |
| `POSTGRES_USER`          | Postgres username (e.g. `manytaskadmin`)                                                                          |
| `POSTGRES_PASSWORD`      | Postgres password (e.g. `localdevdbpass`)                                                                         |
| `POSTGRES_DB`            | Postgres database name (e.g. `manytask`)                                                                          |
| `DATABASE_URL`           | Connection string used inside containers (default: `postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}`) |
| `DATABASE_URL_EXTERNAL`  | Connection string used from the host (for Alembic etc.) (default: `postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}`) |
| `DOCS_HOST`              | Host name for docs (not used in development, can be left blank)                                                    |
| `APP_HOST`               | Host name for the Manytask app (not used in development, can be left blank)                                        |

### Step 4 — Start the application

From the **repository root** (the directory that contains both `manytask/` and `compose/`), run:

```bash
docker compose -f compose/docker-compose.development.yml up --build -d
```

Manytask becomes available on [http://localhost:8081/](http://localhost:8081/).

As a shortcut, you can also run **`make dev` from `manytask/`** — it is equivalent to passing `-f ../compose/docker-compose.development.yml` from there.

## Adding a course

### Step 1 — Create the course in the admin panel

1. Go to `admin/panel` → **create_course**.
2. Fill in all fields and remember (copy) the course token.
3. Create the course.

### Step 2 — Create GitLab groups and projects

1. Go to the GitLab web interface.
2. Create an empty **public** group with the course name.
3. Create a **private** subgroup (for student repositories).
4. Create a **public** or **internal** project inside the group — this will be the shared assignment repository.

### Step 3 — Send the course config to Manytask

From the repository root (so `@common.example.yml` resolves):

```bash
export TESTER_TOKEN=<course_token>
```

```bash
curl -X POST \
  -H "Authorization: Bearer $TESTER_TOKEN" \
  -H "Content-type: application/x-yaml" \
  --data-binary "@common.example.yml" \
  "http://localhost:8081/api/<course_name>/update_config"
```

Replace `<course_name>` with your actual course name. Once done, your first course will be available in Manytask.

## OAuth in local development

Manytask uses **two** GitLab URLs in local development:

- `GITLAB_OAUTH_URL` — browser-facing URL used for redirects, typically `http://localhost:8929`.
- `GITLAB_URL` — internal URL used by the Manytask container for token exchange and userinfo calls, typically `http://gitlab:8929`.

Typical values:

```bash
GITLAB_OAUTH_URL=http://localhost:8929
GITLAB_URL=http://gitlab:8929
```

### Why two URLs are required

OAuth in Docker has two traffic paths:

1. **Browser → GitLab** (`GITLAB_OAUTH_URL`):
   - user-facing redirects,
   - must be reachable from the host browser.
2. **Manytask container → GitLab** (`GITLAB_URL`):
   - token exchange, userinfo, API calls,
   - must be reachable from inside the Manytask container.

Using a single URL for both paths usually fails in local Docker setups.

### OAuth flow, step by step

1. **User starts sign-in.** Browser opens Manytask and the user clicks "Sign in with GitLab":
   - Browser requests `http://localhost:8081/login`.
   - Manytask returns a redirect to the GitLab authorization endpoint.
2. **Authorization redirect (browser).** Manytask builds the URL using `GITLAB_OAUTH_URL`:
   ```http
   GET http://localhost:8929/oauth/authorize?...&redirect_uri=http://localhost:8081/login_finish
   ```
   This must be browser-accessible.
3. **GitLab authenticates the user** and redirects back to Manytask with `code` and `state`:
   ```http
   GET http://localhost:8081/login_finish?code=...&state=...
   ```
4. **Token exchange (container-to-container).** Manytask exchanges `code` for `access_token` using `GITLAB_URL`:
   ```http
   POST <GITLAB_URL>/oauth/token
   ```
   This request is sent from the Manytask container, not from the browser.
5. **Userinfo fetch (container-to-container).** Manytask fetches the user profile:
   ```http
   GET <GITLAB_URL>/oauth/userinfo
   Authorization: Bearer <access_token>
   ```
6. **Session is created.** Manytask stores OAuth data in the Flask session and redirects the user to the signup / login finish routes.

### Code reference

OAuth registration is configured in [`manytask/main.py`](manytask/manytask/main.py):

```python
def _authenticate(oauth: OAuth, internal_url: str, external_url: str, client_id: str, client_secret: str) -> OAuth:
    oauth.register(
        name="gitlab",
        client_id=client_id,
        client_secret=client_secret,
        authorize_url=f"{external_url}/oauth/authorize",
        access_token_url=f"{internal_url}/oauth/token",
        userinfo_endpoint=f"{internal_url}/oauth/userinfo",
        jwks_uri=f"{internal_url}/oauth/discovery/keys",
        client_kwargs={
            "scope": "openid email profile read_user",
            "code_challenge_method": "S256",
        },
    )
    return oauth
```

The corresponding config fields are defined in [`manytask/local_config.py`](manytask/manytask/local_config.py):

- `gitlab_url`
- `gitlab_oauth_url`
- `gitlab_client_id`
- `gitlab_client_secret`

## Running tests

For convenience, the code ships with a `Makefile` containing shortcuts to run the linter, type checker, formatter, and tests. See [`manytask/Makefile`](manytask/Makefile) for details. To run all checks:

```bash
make check
```

Or, if you are using Colima:

```bash
make check-colima
```

## Useful commands

Start the full local stack:

```bash
./scripts/start_local_dev.sh
```

Check containers:

```bash
docker compose -f compose/docker-compose.development.yml ps
```

Manytask logs:

```bash
docker logs -f test-manytask
```

GitLab logs:

```bash
docker logs -f manytask_gitlab
```

Rebuild and restart only Manytask:

```bash
docker compose -f compose/docker-compose.development.yml up --build --no-deps -d manytask
```

Stop the stack:

```bash
docker compose -f compose/docker-compose.development.yml down
```

## Troubleshooting

### GitLab does not become ready

**Symptoms**: the startup script times out waiting for `/users/sign_in`.

**Actions**:

1. Check Colima resources (`colima list`).
2. Restart Colima with the minimum configuration:
   ```bash
   colima start --memory 4 --cpu 2 --disk 100
   ```
3. Check logs:
   ```bash
   docker logs -f manytask_gitlab
   ```

### Token exchange fails with connection errors

**Symptoms**: errors on `/oauth/token`, browser is stuck in a login loop, `Connection refused` in Manytask logs.

**Actions**: check that the Manytask container can reach `GITLAB_URL`:

```bash
docker exec test-manytask sh -lc 'curl -fsS $GITLAB_URL/users/sign_in >/dev/null && echo OK'
```

### OAuth scope errors

**Symptoms**: GitLab returns "invalid scope" or "malformed scope".

**Cause**: the OAuth application was created with incomplete scopes.

**Fix**: rerun the setup script — it updates the app scopes to `openid email profile read_user`:

```bash
./scripts/setup_local_gitlab.sh
```

### Runner registration returns 502

This does not block the Manytask OAuth login flow. You can continue local app testing and debug the runner separately.

## Project structure overview

A brief description of the main files in the project:

- [`abstract.py`](manytask/manytask/abstract.py) – abstract implementations of core objects.
- [`api.py`](manytask/manytask/api.py) – API endpoints.
- [`auth.py`](manytask/manytask/auth.py) – authentication on the website and in GitLab.
- [`course.py`](manytask/manytask/course.py) – business logic for the `Course` class.
- [`database.py`](manytask/manytask/database.py) – database interaction.
- [`glab.py`](manytask/manytask/glab.py) – interaction with GitLab.
- [`main.py`](manytask/manytask/main.py) – application entry point.
- [`models.py`](manytask/manytask/models.py) – database model definitions.
- [`web.py`](manytask/manytask/web.py) – web endpoint definitions.

## References

- OAuth 2.0: https://datatracker.ietf.org/doc/html/rfc6749
- PKCE: https://datatracker.ietf.org/doc/html/rfc7636
- OpenID Connect: https://openid.net/specs/openid-connect-core-1_0.html
- GitLab OAuth docs: https://docs.gitlab.com/ee/api/oauth2.html
- Authlib Flask client: https://docs.authlib.org/en/latest/client/flask.html
