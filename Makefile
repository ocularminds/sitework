.PHONY: setup check test test-ui demo

setup:
	uv sync --frozen

check:
	uv run --frozen python scripts/check.py

test:
	uv run --frozen pytest

test-ui:
	node --test tests/ui.test.mjs

demo:
	uv run --frozen uvicorn sitework.app:create_app --factory --host 127.0.0.1 --port 8000
