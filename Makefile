.PHONY: install pipeline test lint lint-fix fmt ci clean destroy


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

fmt:
	ruff format src/ tests/

fix: lint-fix fmt


# ── CI ──────────────────────────────────────────────────────────────────────
ci: lint test
