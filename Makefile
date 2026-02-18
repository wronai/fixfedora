# ══════════════════════════════════════════════════════════
#  fixfedora – Makefile
#  Użycie: make <cel>
# ══════════════════════════════════════════════════════════

.PHONY: help install install-dev test test-unit test-e2e test-real \
        lint format clean build docker-build docker-test \
        config-init run-scan run-fix

# ── Domyślna komenda ──────────────────────────────────────
help:
	@echo ""
	@echo "  fixfedora – dostępne komendy Makefile"
	@echo ""
	@echo "  Instalacja:"
	@echo "    make install        instaluj paczkę (runtime)"
	@echo "    make install-dev    instaluj z zależnościami dev"
	@echo ""
	@echo "  Testy:"
	@echo "    make test           wszystkie testy (unit + e2e mock)"
	@echo "    make test-unit      tylko unit testy"
	@echo "    make test-e2e       e2e testy z mock LLM"
	@echo "    make test-real      e2e testy z prawdziwym API (wymaga .env)"
	@echo "    make test-cov       testy + raport pokrycia"
	@echo ""
	@echo "  Jakość kodu:"
	@echo "    make lint           sprawdź kod (ruff)"
	@echo "    make format         sformatuj kod (black)"
	@echo ""
	@echo "  Docker:"
	@echo "    make docker-build   zbuduj wszystkie obrazy testowe"
	@echo "    make docker-audio   testuj broken-audio w Docker"
	@echo "    make docker-thumb   testuj broken-thumbnails w Docker"
	@echo "    make docker-full    testuj broken-full w Docker"
	@echo "    make docker-e2e     uruchom e2e testy w Docker"
	@echo ""
	@echo "  Uruchomienie:"
	@echo "    make config-init    utwórz plik .env"
	@echo "    make run-scan       skanuj system (wszystkie moduły)"
	@echo "    make run-fix        uruchom sesję naprawczą (HITL)"
	@echo ""
	@echo "  Paczka:"
	@echo "    make build          zbuduj dystrybucję PyPI"
	@echo "    make clean          usuń pliki tymczasowe"
	@echo ""

# ── Instalacja ────────────────────────────────────────────
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	@echo "✅ Zainstalowano z zależnościami dev"

# ── Testy ─────────────────────────────────────────────────
test: test-unit test-e2e

test-unit:
	@echo "🧪 Unit testy..."
	pytest tests/unit/ -v --tb=short

test-e2e:
	@echo "🧪 E2E testy (mock LLM)..."
	pytest tests/e2e/ -v --tb=short -k "not real_llm"

test-real:
	@echo "🧪 E2E testy (prawdziwe API – wymaga .env)..."
	pytest tests/e2e/ -v --tb=short -k "real_llm"

test-cov:
	pytest tests/ -v --cov=fixfedora --cov-report=term-missing --cov-report=html:htmlcov
	@echo "📊 Raport pokrycia: htmlcov/index.html"

# ── Jakość kodu ───────────────────────────────────────────
lint:
	ruff check fixfedora/ tests/ || true

format:
	black fixfedora/ tests/

# ── Docker ───────────────────────────────────────────────
docker-build:
	docker compose -f docker/docker-compose.yml build

docker-audio:
	docker compose -f docker/docker-compose.yml run --rm broken-audio

docker-thumb:
	docker compose -f docker/docker-compose.yml run --rm broken-thumbnails

docker-full:
	docker compose -f docker/docker-compose.yml run --rm broken-full

docker-e2e:
	docker compose -f docker/docker-compose.yml run --rm e2e-tests

# ── Uruchomienie ──────────────────────────────────────────
config-init:
	fixfedora config init

run-scan:
	fixfedora scan

run-fix:
	fixfedora fix

# ── Paczka ───────────────────────────────────────────────
build: clean
	pip install build --quiet
	python -m build
	@echo "✅ Paczka gotowa w dist/"

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .coverage htmlcov/ __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Wyczyszczono"
