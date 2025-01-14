ROOT_DIR := manytask
DOCKER_COMPOSE_DEV := docker-compose.development.yml
TEST_REQUIREMENTS := requirements.test.txt

.PHONY: dev test reset-dev clean-db lint lint-fix setup install-deps check format

check: format lint test

install-deps:
	pip install -r requirements.txt -r $(TEST_REQUIREMENTS)

dev:
	docker-compose -f $(DOCKER_COMPOSE_DEV) up --build

clean-db:
	docker-compose -f $(DOCKER_COMPOSE_DEV) down -v
	docker volume prune -f

reset-dev: clean-db
	docker-compose -f $(DOCKER_COMPOSE_DEV) up --build

test: install-deps
	python -m pytest --cov-report term-missing --cov=$(ROOT_DIR) tests/

lint:
	python -m isort $(ROOT_DIR) --check
	python -m ruff check $(ROOT_DIR)
	mypy $(ROOT_DIR)

format:
	python -m isort $(ROOT_DIR)
	python -m ruff check $(ROOT_DIR) --fix

setup: install-deps
	mypy --install-types --non-interactive $(ROOT_DIR)