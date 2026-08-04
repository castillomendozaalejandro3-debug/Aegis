.PHONY: build up down logs test lint certs clean

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	pytest tests/ -v --cov=src --cov-report=html

lint:
	black src/ tests/
	isort src/ tests/
	flake8 src/ tests/
	mypy src/

certs:
	chmod +x generate-certs.sh && ./generate-certs.sh

clean:
	docker-compose down -v
	docker system prune -f

reset-db:
	docker-compose down -v
	docker volume rm aegis-peru_postgres_data aegis-peru_neo4j_data aegis-peru_qdrant_data || true
	docker-compose up -d postgres neo4j qdrant
