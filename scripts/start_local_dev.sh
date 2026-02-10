#!/usr/bin/env bash
set -euo pipefail

# This script starts the full local development environment:
# 1. Starts all Docker containers
# 2. Waits for GitLab to be ready
# 3. Sets up GitLab OAuth and tokens
# 4. Restarts Manytask with new environment variables

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.development.yml}"
GITLAB_URL="${GITLAB_URL:-http://localhost:8929}"
SETUP_SCRIPT="${SETUP_SCRIPT:-./scripts/setup_local_gitlab.sh}"

log() { echo "🚀 [start] $*"; }
err() { echo "❌ [start][error] $*" >&2; }

check_requirements() {
    log "Checking requirements..."

    if ! command -v docker &> /dev/null; then
        err "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        err "docker-compose is not installed or not in PATH"
        exit 1
    fi

    if [ ! -f "${COMPOSE_FILE}" ]; then
        err "Docker Compose file not found: ${COMPOSE_FILE}"
        exit 1
    fi

    if [ ! -f "${SETUP_SCRIPT}" ]; then
        err "Setup script not found: ${SETUP_SCRIPT}"
        exit 1
    fi

    log "All requirements satisfied ✓"
}

start_containers() {
    log "Starting Docker containers..."
    docker-compose -f "${COMPOSE_FILE}" up -d
    log "Containers started ✓"
}

wait_for_gitlab() {
    log "Waiting for GitLab to be ready (this may take 2-3 minutes)..."

    local max_attempts=60
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -fsS "${GITLAB_URL}/users/sign_in" >/dev/null 2>&1; then
            log "GitLab is ready ✓"
            return 0
        fi

        attempt=$((attempt + 1))

        # Show progress every 5 attempts
        if [ $((attempt % 5)) -eq 0 ]; then
            log "Still waiting for GitLab... (attempt ${attempt}/${max_attempts})"
        fi

        sleep 5
    done

    err "GitLab did not become ready in time (waited $((max_attempts * 5)) seconds)"
    err "Check GitLab logs: docker logs manytask_gitlab"
    exit 1
}

setup_gitlab() {
    log "Running GitLab setup script..."

    if ! bash "${SETUP_SCRIPT}"; then
        err "GitLab setup failed"
        exit 1
    fi

    log "GitLab setup completed ✓"
}

restart_manytask() {
    log "Restarting Manytask with new environment variables..."
    docker-compose -f "${COMPOSE_FILE}" up -d manytask
    log "Manytask restarted ✓"
}

show_success_message() {
    echo ""
    echo "✅ =========================================="
    echo "✅  Local development environment is ready!"
    echo "✅ =========================================="
    echo ""
    echo "📝 Services:"
    echo "   • Manytask:    http://localhost:8081"
    echo "   • GitLab:      http://localhost:8929"
    echo "   • Docs:        http://docs.localhost"
    echo ""
    echo "🔑 GitLab credentials:"
    echo "   • Username:    root"
    echo "   • Password:    changeme123!"
    echo ""
    echo "📊 Check status:"
    echo "   docker-compose -f ${COMPOSE_FILE} ps"
    echo ""
    echo "📋 View logs:"
    echo "   docker logs -f test-manytask"
    echo "   docker logs -f manytask_gitlab"
    echo ""
    echo "🛑 Stop all services:"
    echo "   docker-compose -f ${COMPOSE_FILE} down"
    echo ""
}

main() {
    log "Starting local development environment..."
    echo ""

    check_requirements
    start_containers
    wait_for_gitlab
    setup_gitlab
    restart_manytask

    show_success_message
}

main "$@"
