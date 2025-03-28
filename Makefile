ROOT_DIR := manytask
DOCKER_COMPOSE_DEV := docker-compose.development.yml
TESTS_DIR := tests
ALEMBIC_CONFIG_PATH := manytask/alembic.ini

.PHONY: dev test reset-dev clean-db lint lint-fix setup install-deps check format install-hooks run-hooks makemigrations migrate downgrade history

check: format lint test

install-deps:
	curl -sSL https://install.python-poetry.org | python3 -
	poetry install

install-hooks:
	poetry install
	poetry run pre-commit install --install-hooks

run-hooks:
	poetry run pre-commit run --all-files

dev:
	docker-compose -f $(DOCKER_COMPOSE_DEV) up --build

clean-db:
	docker-compose -f $(DOCKER_COMPOSE_DEV) down -v
	docker volume prune -f

reset-dev: clean-db
	docker-compose -f $(DOCKER_COMPOSE_DEV) up --build

test: install-deps
	poetry run pytest --cov-report term-missing --cov=$(ROOT_DIR) $(TESTS_DIR)/

test-colima: install-deps
	DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock" \
	python -m pytest --cov-report term-missing --cov=$(ROOT_DIR) $(TESTS_DIR)/

lint:
	@command -v poetry >/dev/null 2>&1 || { echo "\033[0;31mError: poetry is not installed.\033[0m"; exit 1; }
	poetry run ruff format --check $(ROOT_DIR) $(TESTS_DIR)
	poetry run ruff check $(ROOT_DIR) $(TESTS_DIR)
	poetry run mypy $(ROOT_DIR)

format:
	@command -v poetry >/dev/null 2>&1 || { echo "\033[0;31mError: poetry is not installed.\033[0m"; exit 1; }
	poetry run ruff format $(ROOT_DIR) $(TESTS_DIR)
	poetry run ruff check $(ROOT_DIR) $(TESTS_DIR) --fix

setup: install-deps install-hooks
	poetry run mypy --install-types --non-interactive $(ROOT_DIR) $(TESTS_DIR)

makemigrations:
	@command -v poetry >/dev/null 2>&1 || { echo "\033[0;31mError: poetry is not installed.\033[0m"; exit 1; }
	@ if [ -z "$(msg)" ]; then \
		echo "\033[0;31mError: Environment variable msg not set\033[0m"; \
		echo "\033[0;31mRun command like this 'make makemigrations msg=\"Add some value to some model\"'\033[0m"; \
		exit 1; \
	fi
	poetry run alembic -c $(ALEMBIC_CONFIG_PATH) revision -m "$(msg)" --autogenerate || { echo "\033[33mWarning: Make sure that the database is running.\033[0m"; exit 1; }

migrate:
	@command -v poetry >/dev/null 2>&1 || { echo "\033[0;31mError: poetry is not installed.\033[0m"; exit 1; }
	@ if [ -z "$(rev)" ]; then \
		echo "\033[0;31mError: Environment variable rev not set\033[0m"; \
		echo "\033[0;31mRun command like this 'make migrate rev=head'\033[0m"; \
		exit 1; \
	fi
	poetry run alembic -c $(ALEMBIC_CONFIG_PATH) upgrade "$(rev)" || { echo "\033[33mWarning: Make sure that the database is running.\033[0m"; exit 1; }

downgrade:
	@command -v poetry >/dev/null 2>&1 || { echo "\033[0;31mError: poetry is not installed.\033[0m"; exit 1; }
	@ if [ -z "$(rev)" ]; then \
		echo "\033[0;31mError: Environment variable rev not set\033[0m"; \
		echo "\033[0;31mRun command like this 'make downgrade rev=-1'\033[0m"; \
		exit 1; \
	fi
	poetry run alembic -c $(ALEMBIC_CONFIG_PATH) downgrade "$(rev)" || { echo "\033[33mWarning: Make sure that the database is running.\033[0m"; exit 1; }

history:
	@command -v poetry >/dev/null 2>&1 || { echo "\033[0;31mError: poetry is not installed.\033[0m"; exit 1; }
	poetry run alembic -c $(ALEMBIC_CONFIG_PATH) history
	@echo ""
	poetry run alembic -c $(ALEMBIC_CONFIG_PATH) current || { echo "\033[33mWarning: Make sure that the database is running.\033[0m"; exit 1; }
