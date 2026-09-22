.PHONY: install pipeline test lint lint-fix ci clean


# ── Ambiente ────────────────────────────────────────────────────────────────
install:
	uv sync --all-extras

clean:
	uv run pyclean . --debris


# ── Pipeline ────────────────────────────────────────────────────────────────
pipeline:
	uv run cvmdata


# ── Qualidade ───────────────────────────────────────────────────────────────
test:
	uv run pytest -v

lint:
	ruff check src/ tests/

lint-fix:
	ruff check src/ tests/ --fix


# ── CI ──────────────────────────────────────────────────────────────────────
ci: lint test
