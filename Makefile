.PHONY: setup check test

setup:
	uv sync --frozen

check:
	uv run --frozen python scripts/check.py

test:
	uv run --frozen pytest
