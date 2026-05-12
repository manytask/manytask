# Checker targets

# testcontainers may fail on some macOS Docker setups due to Ryuk connectivity issues.
# Allow overriding: `make test TESTCONTAINERS_RYUK_DISABLED=false`
TESTCONTAINERS_RYUK_DISABLED ?= true
export TESTCONTAINERS_RYUK_DISABLED

.PHONY: install-deps test test-colima lint format

CHECKER_PKG := checker
TESTS_DIR := tests

install-deps:
	uv sync --extra dev

test: install-deps
	TESTCONTAINERS_RYUK_DISABLED=$(TESTCONTAINERS_RYUK_DISABLED) PYTHONPATH=. uv run pytest -c /dev/null --rootdir=. --import-mode=importlib -n 4 --skip-firejail tests

test-colima: install-deps
	DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock" \
	uv run python -m pytest --cov-report term-missing --cov=checker --skip-firejail tests/

lint:
	@command -v uv >/dev/null 2>&1 || { echo "\033[0;31mError: uv is not installed.\033[0m"; exit 1; }
	uv run ruff format --check $(CHECKER_PKG) $(TESTS_DIR)
	uv run ruff check $(CHECKER_PKG) $(TESTS_DIR)/
	uv run mypy $(CHECKER_PKG)

format:
	@command -v uv >/dev/null 2>&1 || { echo "\033[0;31mError: uv is not installed.\033[0m"; exit 1; }
	uv run ruff format $(CHECKER_PKG) $(TESTS_DIR)
	uv run ruff check $(CHECKER_PKG) $(TESTS_DIR)/ --fix
