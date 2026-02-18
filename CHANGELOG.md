## [2.1.4] - 2026-02-18

### Summary

fix(goal): CLI interface improvements

### Other

- update fixos/cli.py
- update fixos/llm_shell.py


## [2.1.3] - 2026-02-18

### Summary

refactor(docs): CLI interface improvements

### Docs

- docs: update CONTRIBUTING.md
- docs: update INSTALL.md
- docs: update README

### Other

- update LICENSE
- update fixos/agent/autonomous.py
- update fixos/cli.py
- update fixos/diagnostics/system_checks.py
- update fixos/llm_shell.py
- update fixos/system_checks.py
- update fixos/utils/web_search.py


## [2.1.1] - 2026-02-18

### Breaking Changes

- **Package renamed**: `fixfedora` → `fixos`
- **Cross-platform support**: Linux, Windows, macOS

### Added

- **Cross-platform diagnostics** for Linux/Windows/macOS
- **platform_utils.py** module with OS detection, elevation commands, package manager detection
- **Interactive action menu** in HITL mode: `[D]` describe problem, `[1-N]` select fix, `[A]` all, `[S]` skip, `[!cmd]` run command
- **Markdown-formatted output** for command results (stdout/stderr in code blocks)
- **OS-specific diagnostics**: WMI (Windows), system_profiler (macOS), systemd/journal (Linux)

### Changed

- Class `FixFedoraConfig` → `FixOsConfig`
- CLI command `fixfedora` → `fixos`
- All imports updated from `fixfedora` to `fixos`
- Documentation updated for cross-platform support
- LLM exception handling now mock-safe (type-name matching instead of hardcoded classes)

### Removed

- Duplicate `fixfedora/` package directory
- Duplicate `fixfedora.egg-info/`
- Old `.venv/` (keeping `venv/`)

---

# Changelog

Wszystkie istentne zmiany projektu fixos.
Format oparty na [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.0.0] – 2025-06

### Dodane
- Moduł diagnostyki **audio** (ALSA, PipeWire, SOF firmware, mikrofon)
- Moduł diagnostyki **thumbnails** (ffmpegthumbnailer, totem-nautilus, cache ~/.cache/thumbnails)
- Moduł diagnostyki **hardware** (DMI, BIOS, GPU, touchpad, ACPI, czujniki)
- Tryb agenta **Human-in-the-Loop** (HITL) – użytkownik zatwierdza każdą akcję
- Tryb agenta **Autonomous** – protokół JSON (`EXEC`/`SEARCH`/`SKIP`/`DONE`), lista zabronionych komend
- Obsługa wielu **providerów LLM**: Google Gemini (domyślny), OpenAI, xAI, OpenRouter, Ollama
- Domyślny model: **gemini-2.5-flash-preview-04-17**
- **Zewnętrzne źródła wiedzy** jako fallback: Bugzilla, fora, Arch Wiki, GitHub Issues, DuckDuckGo, SerpAPI
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
- Timeout sesji przez `signal.SIGALRM` z graceful shutdown (Linux/macOS)

### Usunięte
- Monolityczny `diagnose.py` i `llm_shell.py` z v1.0
- Zależność od `tabulate` (zbędna)

---

## [1.0.0] – 2025-05

### Dodane
- Podstawowa diagnostyka systemu (CPU, RAM, dyski, usługi)
- Anonimizacja IP, hostname, ścieżek
- Interaktywny shell LLM z timeoutem 1h
- CLI: `fixos --token sk-...`
- Obsługa OpenAI API
- `setup.py`, `requirements.txt`
