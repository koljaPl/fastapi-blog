.PHONY: help install dev test test-cov test-fast clean lint format run migrate

help:
	@echo "Available commands:"
	@echo "  make install     - Install dependencies"
	@echo "  make dev         - Install dev dependencies"
	@echo "  make test        - Run all tests"
	@echo "  make test-cov    - Run tests with coverage report"
	@echo "  make test-fast   - Run tests in parallel"
	@echo "  make clean       - Clean up generated files"
	@echo "  make lint        - Run linters"
	@echo "  make format      - Format code"
	@echo "  make run         - Run development server"
	@echo "  make migrate     - Run database migrations"

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements.txt
	pip install -e .

test:
	TESTING=true pytest

test-cov:
	TESTING=true pytest --cov=app --cov-report=html --cov-report=term

test-fast:
	TESTING=true pytest -n auto

clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf coverage.xml
	rm -rf *.egg-info
	rm -rf dist
	rm -rf build
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -f test.db

lint:
	ruff check app tests
	mypy app

format:
	black app tests
	ruff check --fix app tests

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	alembic upgrade head

migrate-create:
	@read -p "Enter migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"