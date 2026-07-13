.PHONY: install pipeline all \
	test lint fmt ci

# ── Ambiente ────────────────────────────────────────────────────────────────
install:
	uv sync --all-extras --all-groups


# ── Pipeline (full por padrão) ───────────────────────────────────────────────
pipeline:
	uv run cvmdata

all: pipeline


# ── Qualidade ────────────────────────────────────────────────────────────────
test:
	uv run --extra dev pytest -v

lint:
	uv run --extra dev ruff check src/ tests/

lint-fix:
	uv run --extra dev ruff check src/ tests/ --fix

fmt:
	uv run --extra dev ruff format src/ tests/


# ── Atalho "tudo + qualidade" ────────────────────────────────────────────────
ci: lint test
