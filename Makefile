.PHONY: install lint fmt typecheck test check verify rail agent db-check demo fleet capabilities-demo capabilities-fleet kitchen-sink apps-list app-run contracts-vendor

# Adopted Circle apps (apps/) + Foundry projects (contracts/vendor/). See apps/README.md.
ARC_APPS := arc-commerce arc-escrow arc-fintech arc-multichain-wallet arc-nanopayments arc-p2p-payments arc-stablecoin-fx
VENDOR_CONTRACTS := recibo refund-protocol
OZ_VERSION := v5.1.0

install:
	pip install -e ".[dev]"
	pip install -e apps/circle-ooak   # Circle OOAK, used directly by /workflow/*

lint:
	ruff check .

fmt:
	ruff format .

typecheck:
	mypy shared rail agent registry

test:
	pytest

check: lint typecheck test

# Full verification: static gates (lint + types + tests) then the end-to-end primitive sweep.
verify: check kitchen-sink

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

# --- Adopted standalone apps + contracts (apps/, contracts/vendor/) ---

apps-list:
	@echo "Adopted Circle apps (apps/):"
	@echo "  circle-ooak              Python — used directly by /workflow/* (installed by 'make install')"
	@for a in $(ARC_APPS) agent-stack-starter-kits; do echo "  $$a"; done
	@echo "Adopted Foundry contracts (contracts/vendor/): $(VENDOR_CONTRACTS)"
	@echo "Run a Next.js app:  make app-run APP=arc-nanopayments   (or: cd apps/<app> && npm install && npm run dev)"

# Run an adopted Next.js app's dev server: make app-run APP=arc-nanopayments
app-run:
	@test -n "$(APP)" || (echo "usage: make app-run APP=<arc-app>"; exit 1)
	@test -d "apps/$(APP)" || (echo "no such app: apps/$(APP)"; exit 1)
	cd apps/$(APP) && (npm install) && npm run dev

# Bootstrap each adopted Foundry project's libs (forge-std + OpenZeppelin) and build it.
# Their lib/ are upstream git submodules dropped on vendoring, so we populate them here.
contracts-vendor:
	@for c in $(VENDOR_CONTRACTS); do \
		echo "== contracts/vendor/$$c =="; \
		test -d contracts/vendor/$$c/lib/forge-std || \
			git clone --depth 1 https://github.com/foundry-rs/forge-std contracts/vendor/$$c/lib/forge-std; \
		test -d contracts/vendor/$$c/lib/openzeppelin-contracts || \
			git clone --depth 1 --branch $(OZ_VERSION) https://github.com/OpenZeppelin/openzeppelin-contracts contracts/vendor/$$c/lib/openzeppelin-contracts; \
		( cd contracts/vendor/$$c && forge build ) || exit 1; \
	done
