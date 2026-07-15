.PHONY: install pipeline test lint lint-fix fmt ci clean

# ── Ambiente ────────────────────────────────────────────────────────────────
install:
	uv sync --all-extras

clean:
	rm -rf data/raw data/db
	uv run pyclean src/ tests/


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
