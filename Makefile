.PHONY: install dev test lint

PYTHON ?= python3

install:
	$(PYTHON) -m pip install -e ".[dev]"

dev:
	uvicorn app.main:app --reload

test:
	pytest

lint:
	ruff check .
