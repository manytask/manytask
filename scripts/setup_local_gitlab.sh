#!/usr/bin/env bash
set -euo pipefail

# This script bootstraps a local GitLab for manytask:
# 1) Waits for GitLab HTTP to be ready
# 2) Creates/reads an admin PAT
# 3) Creates/reads an OAuth app for manytask and grabs client_id/secret
# 4) Reads the runners registration token
# 5) Registers the gitlab-runner container
# 6) Appends all secrets into .env (non-destructive)

GITLAB_CONTAINER="${GITLAB_CONTAINER:-manytask_gitlab}"
RUNNER_CONTAINER="${RUNNER_CONTAINER:-manytask_gitlab_runner}"
MANYTASK_ENV="${MANYTASK_ENV:-.env}"

# Host URL for readiness check (external); internal URL for env variables
HOST_GITLAB_URL="${HOST_GITLAB_URL:-http://localhost:8929}"
# Internal URL for API calls between containers
GITLAB_URL="${GITLAB_URL:-http://gitlab:8929}"
# OAuth URL accessible from browser (external)
GITLAB_OAUTH_URL="${GITLAB_OAUTH_URL:-http://localhost:8929}"
REDIRECT_URI="${REDIRECT_URI:-http://localhost:8081/login_finish}"

RUNNER_EXECUTOR="${RUNNER_EXECUTOR:-docker}"
RUNNER_IMAGE="${RUNNER_IMAGE:-alpine:latest}"

log() { echo "[setup] $*"; }
err() { echo "[setup][error] $*" >&2; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || { err "Command '$1' not found"; exit 1; }
}

wait_for_gitlab() {
    log "Waiting for GitLab at ${HOST_GITLAB_URL}..."
    for i in {1..60}; do
        if curl -fsS "${HOST_GITLAB_URL}/users/sign_in" >/dev/null 2>&1; then
            log "GitLab is responding."
            return
        fi
        sleep 5
    done
    err "GitLab did not become ready in time."
    exit 1
}

rails_runner() {
    docker exec -i "${GITLAB_CONTAINER}" sh -lc "gitlab-rails runner \"$1\""
}

ensure_env_line() {
    local key="$1" value="$2"
    if ! grep -q "^${key}=" "${MANYTASK_ENV}" 2>/dev/null; then
        printf "%s=%s\n" "${key}" "${value}" >> "${MANYTASK_ENV}"
    else
        log "Key ${key} already present in ${MANYTASK_ENV}, leaving as is."
    fi
}

main() {
    require_cmd docker
    require_cmd curl

    wait_for_gitlab

    log "Creating/retrieving admin PAT..."
    ADMIN_PAT=$(rails_runner "
        user = User.find_by_username('root')
        pat  = user.personal_access_tokens.find_by(name: 'manytask-admin')
        unless pat
          pat = user.personal_access_tokens.create!(
            name: 'manytask-admin',
            scopes: [:api, :read_user, :read_api, :write_repository, :sudo],
            expires_at: 1.year.from_now.to_date
          )
          pat.set_token(SecureRandom.hex(32))
          pat.save!
        end
        puts pat.token
    ")
    log "Admin PAT acquired."

    log "Creating/retrieving OAuth app..."
    OAUTH_DATA=$(rails_runner "
        app = Doorkeeper::Application.find_by(name: 'manytask-local')
        if app
          # Update existing app with correct scopes
          app.update!(
            redirect_uri: '${REDIRECT_URI}',
            scopes: 'openid email profile read_user api'
          )
        else
          # Create new app with all required scopes
          app = Doorkeeper::Application.create!(
            name: 'manytask-local',
            redirect_uri: '${REDIRECT_URI}',
            scopes: 'openid email profile read_user api',
            confidential: true
          )
        end
        puts [app.uid, app.secret].join(':')
    ")
    GITLAB_CLIENT_ID="${OAUTH_DATA%%:*}"
    GITLAB_CLIENT_SECRET="${OAUTH_DATA#*:}"
    log "OAuth app ready. Client ID: ${GITLAB_CLIENT_ID}"

    log "Fetching runners registration token..."
    RUNNERS_TOKEN=$(rails_runner "puts Gitlab::CurrentSettings.current_application_settings.runners_registration_token")

    log "Registering runner container..."
    docker exec -i "${RUNNER_CONTAINER}" gitlab-runner register \
        --non-interactive \
        --url "${GITLAB_URL}" \
        --registration-token "${RUNNERS_TOKEN}" \
        --executor "${RUNNER_EXECUTOR}" \
        --docker-image "${RUNNER_IMAGE}" \
        --description "manytask-local-runner" \
        --locked="false" \
        --run-untagged="true" || log "Runner registration may have failed; check runner logs."

    log "Appending secrets to ${MANYTASK_ENV} (no overwrite)..."
    touch "${MANYTASK_ENV}"
    ensure_env_line "GITLAB_URL" "${GITLAB_URL}"
    ensure_env_line "GITLAB_OAUTH_URL" "${GITLAB_OAUTH_URL}"
    ensure_env_line "GITLAB_ADMIN_TOKEN" "${ADMIN_PAT}"
    ensure_env_line "GITLAB_CLIENT_ID" "${GITLAB_CLIENT_ID}"
    ensure_env_line "GITLAB_CLIENT_SECRET" "${GITLAB_CLIENT_SECRET}"

    log "Done. Verify runner status in GitLab UI and values in ${MANYTASK_ENV}."
}

main "$@"
