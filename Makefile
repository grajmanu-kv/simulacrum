.DEFAULT_GOAL := help
PY ?= python

.PHONY: help install lint format typecheck test cov check run serve build docker clean

help: ## list targets
	@grep -E '^[a-z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

install: ## editable install with dev tools
	$(PY) -m pip install -e ".[dev]"

lint: ## ruff lint + format check
	ruff check .
	ruff format --check .

format: ## apply formatter and safe lint fixes
	ruff check . --fix
	ruff format .

typecheck: ## mypy over src/
	$(PY) -m mypy

test: ## unit + integration tests
	$(PY) -m pytest

cov: ## tests with coverage gate
	$(PY) -m pytest --cov --cov-report=term-missing

check: lint typecheck cov ## everything CI runs

run: ## headless demo: 200 ticks of the forest
	$(PY) -m simulacrum run src/simulacrum/ecosystems/forest.json --ticks 200 --every 50

serve: ## web UI on http://127.0.0.1:8000
	$(PY) -m simulacrum serve

build: ## wheel + sdist into dist/
	$(PY) -m pip install -q build && $(PY) -m build

docker: ## container image
	docker build -t simulacrum:dev .

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov src/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
