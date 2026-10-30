.PHONY: setup check test test-ui demo

# Local only by default. HOST=0.0.0.0 lets a phone on the same network open /light,
# but the API has no login: anyone who can reach it can record a human release.
HOST ?= 127.0.0.1
PORT ?= 8000

setup:
	uv sync --frozen

check:
	uv run --frozen python scripts/check.py

test:
	uv run --frozen pytest

test-ui:
	node --test tests/ui.test.mjs

demo:
	uv run --frozen uvicorn sitework.app:create_app --factory --host $(HOST) --port $(PORT)
