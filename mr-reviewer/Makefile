# mr-reviewer targets

MR_PKG := app
TESTS_DIR := tests

.PHONY: install-deps lint test run-mr-reviewer-tests

install-deps:
	uv sync --locked

lint:
	@command -v uv >/dev/null 2>&1 || { echo "\033[0;31mError: uv is not installed.\033[0m"; exit 1; }
	uv run ruff format $(MR_PKG) $(TESTS_DIR)
	uv run ruff check $(MR_PKG) $(TESTS_DIR) --fix
	uv run mypy $(MR_PKG) $(TESTS_DIR)

test: install-deps run-mr-reviewer-tests

run-mr-reviewer-tests:
	uv run pytest
