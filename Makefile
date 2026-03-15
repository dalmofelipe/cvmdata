.PHONY: install download load normalize indicators all \
        download-cad load-cad classify-cad \
        test lint fmt ci

# ── Ambiente ────────────────────────────────────────────────────────────────
install:
	uv sync --all-extras

# ── Pipeline demonstrativos (todos os anos padrão) ───────────────────────────
download:
	uv run cvmdata download

load:
	uv run cvmdata load

normalize:
	uv run cvmdata normalize

indicators:
	uv run cvmdata indicators

all: download load normalize indicators

# ── Ano específico: make download YEAR=2024 ──────────────────────────────────
ifdef YEAR
download:
	uv run cvmdata download --year $(YEAR)

load:
	uv run cvmdata load --year $(YEAR)
endif

# ── Pipeline cadastral ───────────────────────────────────────────────────────
download-cad:
	uv run cvmdata download-cad

load-cad:
	uv run cvmdata load-cad

classify-cad:
	uv run cvmdata classify-cad

cadastro: download-cad load-cad classify-cad

# ── Qualidade ────────────────────────────────────────────────────────────────
test:
	uv run pytest -v

lint:
	uv run ruff check src/ tests/

fmt:
	uv run ruff format src/ tests/

# ── Atalho "tudo + qualidade" ────────────────────────────────────────────────
ci: lint test
