.PHONY: install lint fmt typecheck test check rail agent db-check

install:
	pip install -e ".[dev]"

lint:
	ruff check .

fmt:
	ruff format .

typecheck:
	mypy shared rail agent registry

test:
	pytest

check: lint typecheck test

rail:
	uvicorn rail.main:app --reload

agent:
	uvicorn agent.main:app --reload

db-check:
	python scripts/db_check.py
