.PHONY: install download load normalize indicators all test lint fmt

# ── Ambiente ────────────────────────────────────────────────────────────────
install:
	uv sync --all-extras

# ── Pipeline (todos os anos padrão) ─────────────────────────────────────────
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

# ── Qualidade ────────────────────────────────────────────────────────────────
test:
	uv run pytest -v

lint:
	uv run ruff check src/ tests/

fmt:
	uv run ruff format src/ tests/

# ── Atalho "tudo + qualidade" ────────────────────────────────────────────────
ci: lint test
