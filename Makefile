.PHONY: dev test reset-dev clean-db

dev:
	docker-compose -f docker-compose.development.yml up --build 

clean-db:
	docker-compose -f docker-compose.development.yml down -v
	docker volume prune -f

reset-dev: clean-db
	docker-compose -f docker-compose.development.yml up --build

test:
	pip install -r requirements.txt -r requirements.test.txt
	python -m pytest --cov-report term-missing --cov=manytask tests/ 