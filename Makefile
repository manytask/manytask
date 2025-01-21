ROOT_DIR := manytask
DOCKER_COMPOSE_DEV := docker-compose.development.yml
TEST_REQUIREMENTS := requirements.test.txt
TESTS_DIR := tests

.PHONY: dev test reset-dev clean-db lint lint-fix setup install-deps check format install-hooks run-hooks

check: format lint test

install-deps:
	pip install -r requirements.txt -r $(TEST_REQUIREMENTS)

install-hooks:
	pip install pre-commit
	pre-commit install --install-hooks

run-hooks:
	pre-commit run --all-files

dev:
	docker-compose -f $(DOCKER_COMPOSE_DEV) up --build

clean-db:
	docker-compose -f $(DOCKER_COMPOSE_DEV) down -v
	docker volume prune -f

reset-dev: clean-db
	docker-compose -f $(DOCKER_COMPOSE_DEV) up --build

test: install-deps
	python -m pytest --cov-report term-missing --cov=$(ROOT_DIR) $(TESTS_DIR)/

lint:
	@command -v isort >/dev/null 2>&1 || { echo "\033[0;31mError: isort is not installed. Run 'make install-deps' first.\033[0m"; exit 1; }
	@command -v ruff >/dev/null 2>&1 || { echo "\033[0;31mError: ruff is not installed. Run 'make install-deps' first.\033[0m"; exit 1; }
	@command -v mypy >/dev/null 2>&1 || { echo "\033[0;31mError: mypy is not installed. Run 'make install-deps' first.\033[0m"; exit 1; }
	python -m isort $(ROOT_DIR) $(TESTS_DIR) --check
	python -m ruff check $(ROOT_DIR) $(TESTS_DIR)
	mypy $(ROOT_DIR)

format:
	@command -v isort >/dev/null 2>&1 || { echo "\033[0;31mError: isort is not installed. Run 'make install-deps' first.\033[0m"; exit 1; }
	@command -v ruff >/dev/null 2>&1 || { echo "\033[0;31mError: ruff is not installed. Run 'make install-deps' first.\033[0m"; exit 1; }
	python -m isort $(ROOT_DIR) $(TESTS_DIR)
	python -m ruff check $(ROOT_DIR) $(TESTS_DIR) --fix

setup: install-deps install-hooks
	mypy --install-types --non-interactive $(ROOT_DIR) $(TESTS_DIR)