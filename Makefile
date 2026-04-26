.PHONY: install lintfix lint test build

IMAGE ?= steam-library-monitor:local

.venv/bin/python:
	python3 -m venv .venv

install: .venv/bin/python
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -r requirements.txt

lintfix: install
	.venv/bin/ruff check --fix src tests
	.venv/bin/ruff format src tests

lint: install
	.venv/bin/ruff check src tests
	.venv/bin/ruff format --check src tests
	.venv/bin/mypy src tests
	.venv/bin/pylint src tests
	@if command -v hadolint >/dev/null 2>&1; then \
		hadolint Dockerfile; \
	else \
		docker run --rm -i hadolint/hadolint < Dockerfile; \
	fi

test: install
	.venv/bin/pytest

build: lint
	docker build -t $(IMAGE) .
