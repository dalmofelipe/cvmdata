.PHONY: install pipeline all \
	test lint fmt ci

# ── Ambiente ────────────────────────────────────────────────────────────────
install:
	uv sync --all-extras --all-groups


# ── Pipeline (full por padrão) ───────────────────────────────────────────────
pipeline:
	uv run cvmdata pipeline run

all: pipeline


# ── Qualidade ────────────────────────────────────────────────────────────────
test:
	uv run --extra dev --group dev pytest -v

lint:
	uv run --extra dev ruff check src/ tests/

fmt:
	uv run --extra dev ruff format src/ tests/


# ── Atalho "tudo + qualidade" ────────────────────────────────────────────────
ci: lint test
