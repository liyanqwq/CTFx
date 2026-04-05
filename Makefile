.PHONY: install dev test build clean lint frontend

PYTHON ?= python
PYTEST_FLAGS ?= -v
PROTOBUF_ENV = PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

# ── Install ──────────────────────────────────────────────────────────────────

install:
	$(PYTHON) -m pip install -e .

install-llm:
	$(PYTHON) -m pip install -e ".[llm]"

dev:
	$(PYTHON) -m pip install -e ".[llm]"
	$(PYTHON) -m pip install pytest pytest-asyncio httpx ruff

# ── Tests ─────────────────────────────────────────────────────────────────────

test:
	$(PROTOBUF_ENV) $(PYTHON) -m pytest $(PYTEST_FLAGS) tests/

test-quick:
	$(PROTOBUF_ENV) $(PYTHON) -m pytest -x -q tests/

test-cov:
	$(PROTOBUF_ENV) $(PYTHON) -m pytest $(PYTEST_FLAGS) --tb=short tests/

# ── Lint ──────────────────────────────────────────────────────────────────────

lint:
	$(PYTHON) -m ruff check ctfx/ tests/

lint-fix:
	$(PYTHON) -m ruff check --fix ctfx/ tests/

# ── Frontend ──────────────────────────────────────────────────────────────────

frontend:
	cd frontend && npm install && npm run build

frontend-dev:
	cd frontend && npm run dev

# ── Clean ─────────────────────────────────────────────────────────────────────

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache __pycache__
	find ctfx -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find tests -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

# ── Build wheel ───────────────────────────────────────────────────────────────

build: frontend
	$(PYTHON) -m pip install --upgrade build
	$(PYTHON) -m build

# ── Quick dev loop ────────────────────────────────────────────────────────────

run-server:
	ctfx serve

webui:
	ctfx webui
