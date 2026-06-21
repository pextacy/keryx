.PHONY: install lint fmt typecheck test check rail agent db-check demo fleet capabilities-demo capabilities-fleet kitchen-sink

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

demo:
	bash scripts/demo.sh

capabilities-demo:
	bash scripts/capabilities-demo.sh

kitchen-sink:
	bash scripts/kitchen-sink.sh

fleet:
	python -m agent.fleet --n 20

capabilities-fleet:
	python -m agent.capabilities_fleet --rounds 20
