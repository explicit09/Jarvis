.PHONY: install dev run run-standalone run-ui bench bench-report test lint format clean help

# Default Python
PYTHON := python3
UV := uv

help:
	@echo "J.A.R.V.I.S - Voice AI Assistant"
	@echo ""
	@echo "Usage:"
	@echo "  make install        Install dependencies"
	@echo "  make dev            Install with dev dependencies"
	@echo "  make run            Run in LiveKit mode"
	@echo "  make run-standalone Run in standalone mode (wake word)"
	@echo "  make run-ui         Run the local web UI"
	@echo "  make bench          Run model benchmarks"
	@echo "  make bench-report   Summarize benchmark results"
	@echo "  make test           Run tests"
	@echo "  make lint           Run linter"
	@echo "  make format         Format code"
	@echo "  make clean          Clean build artifacts"
	@echo ""
	@echo "Setup:"
	@echo "  1. Copy .env.example to .env"
	@echo "  2. Add your API keys to .env"
	@echo "  3. Run 'make install'"
	@echo "  4. Run 'make run'"

install:
	$(UV) pip install -e .

dev:
	$(UV) pip install -e ".[dev]"

run:
	$(PYTHON) -m jarvis.main

run-standalone:
	$(PYTHON) -m jarvis.standalone

run-ui:
	$(PYTHON) -m jarvis.ui.server

bench:
	$(PYTHON) -m jarvis.bench.runner $(ARGS)

bench-report:
	$(PYTHON) -m jarvis.bench.report $(ARGS)

run-debug:
	$(PYTHON) -m jarvis.main --debug

test:
	pytest tests/ -v

lint:
	ruff check jarvis/ tests/

format:
	ruff format jarvis/ tests/
	ruff check --fix jarvis/ tests/

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# Development helpers
check-env:
	@echo "Checking environment..."
	@test -f .env || (echo "ERROR: .env file not found. Copy .env.example to .env" && exit 1)
	@echo "Environment OK"

download-whisper:
	$(PYTHON) -c "from faster_whisper import WhisperModel; WhisperModel('base.en')"
	@echo "Whisper model downloaded"
