.PHONY: install dev demo test lint

PYTHON ?= python3

install:
	$(PYTHON) -m pip install -e ".[dev]"

dev:
	uvicorn app.main:app --reload

demo:
	$(PYTHON) scripts/demo_request.py

test:
	pytest

lint:
	ruff check .
