## [2.1.2] - 2026-02-18

### Summary

refactor(goal): deep code analysis engine with 6 supporting modules

### Other

- update fixfedora/__init__.py
- update fixfedora/agent/__init__.py
- update fixfedora/agent/autonomous.py
- update fixfedora/agent/hitl.py
- update fixfedora/anonymizer.py
- update fixfedora/cli.py
- update fixfedora/config.py
- update fixfedora/diagnostics/__init__.py
- update fixfedora/diagnostics/system_checks.py
- update fixfedora/llm_shell.py
- ... and 10 more


## [2.1.1] - 2026-02-18

### Summary

chore(goal): config module improvements

### Config

- config: update goal.yaml


## [2.0.8] - 2026-02-18

### Summary

fix(tests): deep code analysis engine with 6 supporting modules

### Test

- update tests/e2e/test_anonymization_layers.py

### Other

- update fixfedora/agent/autonomous.py


## [2.0.7] - 2026-02-18

### Summary

refactor(goal): CLI interface improvements

### Test

- update tests/unit/test_orchestrator.py

### Other

- update fixfedora/cli.py


## [2.0.6] - 2026-02-18

### Summary

fix(docs): core module improvements

### Docs

- docs: update README

### Other

- update fixfedora/agent/hitl.py
- update img.png


## [2.0.5] - 2026-02-18

### Summary

refactor(config): docs module improvements

### Docs

- docs: update INSTALL.md

### Build

- update pyproject.toml
- update setup.py


## [2.0.4] - 2026-02-18

### Summary

feat(tests): new API capabilities

### Test

- update tests/e2e/test_audio_broken.py


## [2.0.3] - 2026-02-18

### Summary

fix(config): config module improvements

### Other

- update fixfedora/config.py


## [2.0.2] - 2026-02-18

### Summary

fix(config): deep code analysis engine with 2 supporting modules

### Build

- update pyproject.toml

### Other

- update fixfedora/utils/anonymizer.py


## [2.0.1] - 2026-02-18

### Summary

fix(docs): CLI interface improvements

### Docs

- docs: update CONTRIBUTING.md
- docs: update INSTALL.md
- docs: update README

### Test

- update tests/__init__.py
- update tests/conftest.py
- update tests/e2e/__init__.py
- update tests/e2e/test_audio_broken.py
- update tests/e2e/test_thumbnails_broken.py
- update tests/unit/__init__.py
- update tests/unit/test_core.py

### Build

- update pyproject.toml
- update setup.py

### Config

- config: update goal.yaml

### Other

- update .env.example
- update .gitignore
- update LICENSE
- update MANIFEST.in
- build: update Makefile
- docker: update Dockerfile
- docker: update Dockerfile
- docker: update Dockerfile
- docker: update Dockerfile
- docker: update docker-compose.yml
- ... and 16 more


# Changelog

Wszystkie istotne zmiany projektu fixfedora.
Format oparty na [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.0.0] – 2025-06

### Dodane
- Moduł diagnostyki **audio** (ALSA, PipeWire, SOF firmware, mikrofon) – specjalnie pod Lenovo Yoga
- Moduł diagnostyki **thumbnails** (ffmpegthumbnailer, totem-nautilus, cache ~/.cache/thumbnails)
- Moduł diagnostyki **hardware** (DMI, BIOS, GPU, touchpad, ACPI, czujniki)
- Tryb agenta **Human-in-the-Loop** (HITL) – użytkownik zatwierdza każdą akcję
- Tryb agenta **Autonomous** – protokół JSON (`EXEC`/`SEARCH`/`SKIP`/`DONE`), lista zabronionych komend
- Obsługa wielu **providerów LLM**: Google Gemini (domyślny), OpenAI, xAI, OpenRouter, Ollama
- Domyślny model: **gemini-2.5-flash-preview-04-17**
- **Zewnętrzne źródła wiedzy** jako fallback: Fedora Bugzilla, ask.fedoraproject.org, Arch Wiki, GitHub Issues, DuckDuckGo, SerpAPI
- Podgląd **zanonimizowanych danych** dla użytkownika przed wysłaniem do LLM + raport co zamaskowano
- Nowe komendy CLI: `token set/show/clear`, `config show/init/set`, `providers`, `test-llm`, `scan`, `fix`
- Konfiguracja przez **plik .env** (python-dotenv)
- **3 środowiska Docker** dla testów: `broken-audio`, `broken-thumbnails`, `broken-full`
- **Testy e2e i unit** z fixtures i mock LLM (pytest + pytest-mock)
- `pyproject.toml` jako standard pakietowania

### Zmienione
- Przepisana architektura na moduły: `agent/`, `diagnostics/`, `providers/`, `utils/`
- Anonimizacja teraz zwraca `tuple(anon_str, AnonymizationReport)` z kategoryzacją
- LLMClient z retry logic (3 próby), obsługą rate limit, streamingiem
- Timeout sesji przez `signal.SIGALRM` z graceful shutdown

### Usunięte
- Monolityczny `diagnose.py` i `llm_shell.py` z v1.0
- Zależność od `tabulate` (zbędna)

---

## [1.0.0] – 2025-05

### Dodane
- Podstawowa diagnostyka Fedora (CPU, RAM, dyski, dnf, journalctl)
- Anonimizacja IP, hostname, ścieżek
- Interaktywny shell LLM z timeoutem 1h
- CLI: `fixfedora --token sk-...`
- Obsługa OpenAI API
- `setup.py`, `requirements.txt`
