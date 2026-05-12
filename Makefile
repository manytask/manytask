# Run from repository root (parent of manytask/).
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
