# OAuth Authentication Flow in Local Development

This document explains how OAuth authentication works in local development when Manytask and GitLab run in Docker containers.

## Purpose

Use this guide when you:

- run Manytask locally with Docker,
- use a local GitLab instance,
- want to understand why OAuth needs different internal and external URLs,
- need a stable startup sequence and troubleshooting steps.

## Prerequisites

- Docker and Docker Compose installed.
- Colima installed (macOS).
- Local project configured with `docker-compose.development.yml`.

### Minimum Colima configuration for local GitLab

GitLab needs enough RAM to become healthy. Start Colima with at least:

```bash
colima start --memory 4 --cpu 2 --disk 100
```

You can verify current resources with:

```bash
colima list
```

## URL model used by OAuth

Manytask uses two GitLab URLs in local development:

- `GITLAB_OAUTH_URL`: browser-facing URL (for redirects), usually `http://localhost:8929`
- `GITLAB_URL`: internal API URL used by Manytask container for token and userinfo calls

Typical values:

```bash
GITLAB_OAUTH_URL=http://localhost:8929
GITLAB_URL=http://gitlab:8929
```

If your container network setup does not resolve `gitlab`, use:

```bash
GITLAB_URL=http://host.docker.internal:8929
```

## Quick start

Start the environment:

```bash
./scripts/start_local_dev.sh
```

This script does the following:

1. Starts Docker containers.
2. Waits for GitLab readiness.
3. Runs `scripts/setup_local_gitlab.sh`.
4. Creates or reuses:
   - admin PAT,
   - OAuth app,
   - runner registration.
5. Appends missing GitLab keys to `.env`.
6. Restarts Manytask to pick up updated env vars.

## OAuth flow: step by step

### 1. User starts sign-in

The browser opens Manytask and user clicks "Sign in with GitLab":

- Browser requests `http://localhost:8081/login`.
- Manytask returns redirect to GitLab authorization endpoint.

### 2. Authorization redirect (browser)

Manytask builds URL using `GITLAB_OAUTH_URL`:

```http
GET http://localhost:8929/oauth/authorize?...&redirect_uri=http://localhost:8081/login_finish
```

This must be browser-accessible.

### 3. GitLab authenticates user

GitLab shows sign-in / approval page.
After approval, GitLab redirects back to Manytask with `code` and `state`:

```http
GET http://localhost:8081/login_finish?code=...&state=...
```

### 4. Token exchange (container-to-container)

Manytask backend exchanges `code` for `access_token` using `GITLAB_URL`:

```http
POST <GITLAB_URL>/oauth/token
```

This request is sent from the Manytask container, not from the browser.

### 5. Userinfo fetch (container-to-container)

Manytask fetches user profile:

```http
GET <GITLAB_URL>/oauth/userinfo
Authorization: Bearer <access_token>
```

### 6. Session is created

Manytask stores OAuth data in Flask session and redirects user to signup/login finish routes.

## Why two URLs are required

OAuth in Docker has two traffic paths:

1. Browser to GitLab (`GITLAB_OAUTH_URL`):
   - user-facing redirects,
   - must be reachable from host machine browser.
2. Manytask container to GitLab (`GITLAB_URL`):
   - token exchange,
   - userinfo and API calls,
   - must be reachable from inside the Manytask container.

Using one URL for both paths often fails in local Docker setups.

## Code reference

OAuth registration is configured in `manytask/main.py`:

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

Config fields are defined in `manytask/local_config.py`:

- `gitlab_url`
- `gitlab_oauth_url`
- `gitlab_client_id`
- `gitlab_client_secret`

## What setup script configures

`scripts/setup_local_gitlab.sh` does:

- waits for GitLab web endpoint,
- creates or reuses root PAT (`manytask-admin`),
- creates or reuses OAuth app (`manytask-local`),
- reads runner registration token,
- tries to register local runner,
- appends missing values to `.env` without overwriting existing keys.

Keys appended when missing:

- `GITLAB_URL`
- `GITLAB_OAUTH_URL`
- `GITLAB_ADMIN_TOKEN`
- `GITLAB_CLIENT_ID`
- `GITLAB_CLIENT_SECRET`

## Troubleshooting

### GitLab does not become ready

Symptoms:

- startup script times out waiting for `/users/sign_in`.

Actions:

1. Check Colima resources (`colima list`).
2. Start Colima with minimum config:

```bash
colima start --memory 4 --cpu 2 --disk 100
```

3. Check logs:

```bash
docker logs -f manytask_gitlab
```

### Token exchange fails with connection errors

Symptoms:

- errors on `/oauth/token`,
- browser returns to login loop,
- `Connection refused` in Manytask logs.

Actions:

1. Check that container can reach `GITLAB_URL`:

```bash
docker exec test-manytask sh -lc 'curl -fsS $GITLAB_URL/users/sign_in >/dev/null && echo OK'
```

2. If `gitlab` hostname is not resolvable in your setup, set:

```bash
GITLAB_URL=http://host.docker.internal:8929
```

3. Restart Manytask container.

### OAuth scope errors

Symptoms:

- GitLab returns invalid scope / malformed scope.

Cause:

- OAuth app created with incomplete scopes.

Fix:

- rerun setup script:

```bash
./scripts/setup_local_gitlab.sh
```

The script updates app scopes to:

- `openid email profile read_user api`

### Runner registration returns 502

This does not block Manytask OAuth login flow.
You can continue local app testing and debug runner separately.

## Useful commands

Start full local stack:

```bash
./scripts/start_local_dev.sh
```

Check containers:

```bash
docker-compose -f docker-compose.development.yml ps
```

Manytask logs:

```bash
docker logs -f test-manytask
```

GitLab logs:

```bash
docker logs -f manytask_gitlab
```

Stop stack:

```bash
docker-compose -f docker-compose.development.yml down
```

## References

- OAuth 2.0: https://datatracker.ietf.org/doc/html/rfc6749
- PKCE: https://datatracker.ietf.org/doc/html/rfc7636
- OpenID Connect: https://openid.net/specs/openid-connect-core-1_0.html
- GitLab OAuth docs: https://docs.gitlab.com/ee/api/oauth2.html
- Authlib Flask client: https://docs.authlib.org/en/latest/client/flask.html
