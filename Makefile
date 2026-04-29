.PHONY: install download load normalize classify indicators all \
        test lint fmt ci

# ── Ambiente ────────────────────────────────────────────────────────────────
install:
	uv sync --all-extras


# ── Pipeline demonstrativos (todos os anos padrão) ───────────────────────────
download:
	uv run cvmdata download
	uv run cvmdata download-info-cad

load:
	uv run cvmdata load
	uv run cvmdata load-info-cad

normalize:
	uv run cvmdata normalize

classify:
	uv run cvmdata classify-info-cad

indicators:
	uv run cvmdata indicators

all: download load normalize classify indicators


# ── Qualidade ────────────────────────────────────────────────────────────────
test:
	uv run pytest -v

lint:
	uv run ruff check src/ tests/

fmt:
	uv run ruff format src/ tests/


# ── Atalho "tudo + qualidade" ────────────────────────────────────────────────
ci: lint test
