```
  ___  _       ___  ____
 / _(_)_  __  / _ \/ ___|
| |_| \ \/ / | | | \___ \
|  _| |>  <  | |_| |___) |
|_| |_/_/\_\  \___/|____/
  AI-powered OS Diagnostics  •  v2.2.0
```

# fixOS v2.2 🔧🤖

**AI diagnostyka i naprawa systemów** – Linux, Windows, macOS  
z anonimizacją danych, trybem HITL/Autonomous, grafem problemów i 12 providerami LLM.

---

## 🌍 Cross-Platform Support

| System | Package Manager | Audio | Hardware | System |
|:--|:--|:--:|:--:|:--:|
| **Linux** (Fedora, Ubuntu, Arch, Debian) | dnf / apt / pacman | ✅ ALSA/PipeWire/SOF | ✅ DMI/sensors | ✅ systemd/journal |
| **Windows** 10/11 | winget / choco | ✅ WMI Audio | ✅ WMI Hardware | ✅ Event Log |
| **macOS** 12+ | brew | ✅ CoreAudio | ✅ system_profiler | ✅ launchd |

---

## Szybki start (3 kroki)

```bash
# 1. Instalacja
pip install -e ".[dev]"

# 2. Wybierz provider i pobierz klucz API
fixos llm                          # lista 12 providerów z linkami

# 3. Zapisz klucz i uruchom
fixos token set AIzaSy...          # Gemini (darmowy, domyślny)
fixos fix
```

---

## Komendy CLI

```
fixos                   – ekran powitalny z listą komend i statusem
fixos fix               – diagnoza + sesja naprawcza z AI (HITL)
fixos scan              – diagnostyka systemu bez AI
fixos orchestrate       – zaawansowana orkiestracja (graf problemów DAG)
fixos llm               – lista 12 providerów LLM + linki do kluczy API
fixos token set KEY     – zapisz klucz API do .env (auto-detekcja providera)
fixos token show        – pokaż aktualny token (zamaskowany)
fixos token clear       – usuń token z .env
fixos config show       – pokaż konfigurację
fixos config init       – utwórz .env z szablonu
fixos config set K V    – ustaw wartość w .env
fixos providers         – skrócona lista providerów
fixos test-llm          – testuj połączenie z LLM
```

### Przykłady użycia

```bash
# Tylko diagnostyka audio + zapis do pliku
fixos scan --audio --output /tmp/audio-report.json

# Napraw audio i thumbnails (HITL – pyta o potwierdzenie)
fixos fix --modules audio,thumbnails

# Tryb autonomiczny (agent sam naprawia, max 5 akcji)
fixos fix --mode autonomous --max-fixes 5

# Zaawansowana orkiestracja z grafem zależności
fixos orchestrate --dry-run

# Pokaż tylko darmowe providery LLM
fixos llm --free

# Ustaw Groq jako provider (ultra-szybki, darmowy)
fixos token set gsk_... --provider groq
fixos fix --provider groq

# Timeout 30 minut
fixos fix --timeout 1800
```

---

## 🤖 Dostępni Providerzy LLM (12)

| # | Provider | Tier | Model domyślny | Klucz API |
|:--|:--|:--:|:--|:--|
| 1 | **gemini** | 🟢 FREE | gemini-2.5-flash | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| 2 | **openrouter** | 🟢 FREE | openai/gpt-4o-mini | [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys) |
| 3 | **mistral** | 🟢 FREE | mistral-small-latest | [console.mistral.ai](https://console.mistral.ai/api-keys/) |
| 4 | **groq** | 🟢 FREE | llama-3.1-8b-instant | [console.groq.com/keys](https://console.groq.com/keys) |
| 5 | **together** | 🟢 FREE | llama-3.2-11B | [api.together.ai](https://api.together.ai/settings/api-keys) |
| 6 | **cohere** | 🟢 FREE | command-r | [dashboard.cohere.com](https://dashboard.cohere.com/api-keys) |
| 7 | **cerebras** | 🟢 FREE | llama3.1-8b | [cloud.cerebras.ai](https://cloud.cerebras.ai/platform/) |
| 8 | **ollama** | 🟢 LOCAL | llama3.2 | [ollama.com/download](https://ollama.com/download) |
| 9 | **openai** | 💰 PAID | gpt-4o-mini | [platform.openai.com](https://platform.openai.com/api-keys) |
| 10 | **anthropic** | 💰 PAID | claude-3-haiku | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| 11 | **xai** | 💰 PAID | grok-beta | [console.x.ai](https://console.x.ai/) |
| 12 | **deepseek** | 💰 PAID | deepseek-chat | [platform.deepseek.com](https://platform.deepseek.com/api_keys) |

```bash
fixos llm          # pełna lista z opisami i gotowymi komendami
fixos llm --free   # tylko darmowe
```

---

## Tryby agenta

### 👤 Human-in-the-Loop (HITL) – domyślny

```
LLM sugeruje → Ty decydujesz → Skrypt wykonuje

fixos [00:58:42] ❯ 1              ← napraw problem nr 1
fixos [00:58:30] ❯ A              ← napraw wszystkie
fixos [00:58:20] ❯ !systemctl status pipewire  ← własna komenda
fixos [00:58:10] ❯ search sof-firmware lenovo  ← szukaj zewnętrznie
fixos [00:57:55] ❯ D              ← opisz własny problem
fixos [00:57:40] ❯ ?              ← zapytaj o szczegóły
fixos [00:57:30] ❯ q              ← zakończ
```

Wyjście koloryzowane: 🔴 krytyczne / 🟡 ważne / 🟢 drobne, bloki kodu z ramkami box-drawing.

### 🤖 Autonomous – agent działa samodzielnie

```bash
fixos fix --mode autonomous --max-fixes 10
```
- Protokół JSON: `{ "action": "EXEC|SEARCH|SKIP|DONE", "command": "...", "reason": "..." }`
- Zabezpieczenia: lista zabronionych komend (`rm -rf /`, `mkfs`, `fdisk`, `dd if=...`)
- Każde `EXEC` logowane z wynikiem i oceną LLM
- Wymaga jawnego `yes` na starcie

### 🎼 Orchestrate – graf problemów (DAG)

```bash
fixos orchestrate
fixos orchestrate --dry-run   # podgląd bez wykonywania
```
- Buduje graf zależności między problemami
- Po każdej naprawie re-diagnozuje i wykrywa nowe problemy
- LLM ocenia wynik każdej komendy (JSON structured output)

---

## 🔒 Anonimizacja danych

Zawsze pokazywana przed wysłaniem do LLM. Maskowane kategorie:

| Kategoria | Przykład | Zamiennik |
|:--|:--|:--|
| Hostname | `moj-laptop` | `[HOSTNAME]` |
| Username | `jan` | `[USER]` |
| Ścieżki /home | `/home/jan/.pyenv/versions/3.12/bin/python` | `/home/[USER]/...` |
| Adresy IPv4 | `192.168.1.100` | `192.168.XXX.XXX` |
| Adresy MAC | `aa:bb:cc:dd:ee:ff` | `XX:XX:XX:XX:XX:XX` |
| Tokeny API | `sk-abc123...` | `[API_TOKEN_REDACTED]` |
| UUID hardware | `a1b2c3d4-...` | `[UUID-REDACTED]` |
| Numery seryjne | `SN: PF1234567` | `Serial: [SERIAL-REDACTED]` |
| Hasła w env | `PASSWORD=secret` | `PASSWORD=[REDACTED]` |

---

## Moduły diagnostyki

| Moduł | Linux | Windows | macOS | Co sprawdza |
|:--|:--:|:--:|:--:|:--|
| `system` | ✅ | ✅ | ✅ | CPU, RAM, dyski, usługi, aktualizacje, SELinux, firewall |
| `audio` | ✅ | ✅ | ✅ | ALSA/PipeWire/SOF (Linux), WMI Audio (Win), CoreAudio (Mac) |
| `thumbnails` | ✅ | ➖ | ➖ | ffmpegthumbnailer, cache, GNOME gsettings |
| `hardware` | ✅ | ✅ | ✅ | DMI/WMI/system_profiler, BIOS, GPU, czujniki, bateria |

---

## Zewnętrzne źródła wiedzy (fallback)

Gdy LLM nie zna rozwiązania, fixos szuka automatycznie w:

- **Fedora Bugzilla** – baza zgłoszonych błędów
- **ask.fedoraproject.org** – forum społeczności
- **Arch Wiki** – doskonałe źródło dla ogólnych problemów Linux
- **GitHub Issues** – PipeWire, ALSA, linux-hardware repos
- **DuckDuckGo** – ogólne wyszukiwanie (bez klucza API)
- **Google via SerpAPI** – najlepsze wyniki (opcjonalny klucz `SERPAPI_KEY`)

---

## Konfiguracja (.env)

```bash
fixos config init    # utwórz .env z szablonu
fixos config show    # sprawdź aktualną konfigurację
```

```env
LLM_PROVIDER=gemini           # gemini|openai|openrouter|groq|mistral|...
GEMINI_API_KEY=AIzaSy...      # klucz Gemini (darmowy)
AGENT_MODE=hitl               # hitl|autonomous
SHOW_ANONYMIZED_DATA=true     # pokaż dane przed wysłaniem
ENABLE_WEB_SEARCH=true        # fallback do zewnętrznych źródeł
SESSION_TIMEOUT=3600          # timeout sesji (1h)
SERPAPI_KEY=                  # opcjonalny – lepsze wyniki wyszukiwania
```

---

## Testy i Docker

### Uruchomienie testów

```bash
# Wszystkie testy jednostkowe (bez API, szybkie)
pytest tests/unit/ -v

# Testy e2e z mock LLM
pytest tests/e2e/ -v

# Tylko testy z prawdziwym API (wymaga tokena w .env)
pytest tests/e2e/ -v -m real_api

# Pokrycie kodu
pytest --cov=fixos --cov-report=html
make test-coverage
```

### Docker – symulowane środowiska

```bash
# Zbuduj wszystkie obrazy
docker compose -f docker/docker-compose.yml build

# Scenariusze broken
docker compose -f docker/docker-compose.yml run broken-audio
docker compose -f docker/docker-compose.yml run broken-thumbnails
docker compose -f docker/docker-compose.yml run broken-network
docker compose -f docker/docker-compose.yml run broken-full

# Uruchom testy e2e w Dockerze
docker compose -f docker/docker-compose.yml run e2e-tests
```

### Środowiska Docker

| Obraz | Scenariusz |
|:--|:--|
| `fixos-broken-audio` | Brak sof-firmware, PipeWire failed, no ALSA cards |
| `fixos-broken-thumbnails` | Brak thumbnailerów, pusty cache, brak GStreamer |
| `fixos-broken-network` | NetworkManager failed, DNS broken, rfkill blocked |
| `fixos-broken-full` | Wszystkie problemy naraz + pending updates + failed services |

---

## Struktura projektu

```
fixos/
├── fixos/
│   ├── cli.py                  # Komendy CLI (Click) – fixos, fix, scan, llm, ...
│   ├── config.py               # Konfiguracja + 12 providerów LLM
│   ├── platform_utils.py       # Cross-platform (Linux/Win/Mac)
│   ├── agent/
│   │   ├── hitl.py             # HITL z koloryzowanym markdown output
│   │   └── autonomous.py       # Tryb autonomiczny z JSON protokołem
│   ├── diagnostics/
│   │   └── system_checks.py    # Moduły: system, audio, thumbnails, hardware
│   ├── fixes/
│   │   ├── knowledge_base.py   # Baza znanych bugów z heurystykami
│   │   └── heuristics.py       # Matcher diagnostics → known fixes
│   ├── orchestrator/
│   │   ├── graph.py            # Graf problemów (DAG)
│   │   ├── executor.py         # Bezpieczny executor komend
│   │   └── orchestrator.py     # Główna pętla orkiestracji
│   ├── providers/
│   │   └── llm.py              # Multi-provider LLM client
│   └── utils/
│       ├── anonymizer.py       # Anonimizacja z raportem
│       └── web_search.py       # Bugzilla/AskFedora/ArchWiki/GitHub/DDG
├── tests/
│   ├── conftest.py             # Fixtures + mock diagnostics
│   ├── e2e/
│   │   ├── test_audio_broken.py
│   │   ├── test_thumbnails_broken.py
│   │   ├── test_network_broken.py
│   │   ├── test_executor.py
│   │   └── test_cli.py
│   └── unit/
│       ├── test_core.py
│       ├── test_anonymizer.py
│       └── test_executor.py
├── docker/
│   ├── base/Dockerfile
│   ├── broken-audio/Dockerfile
│   ├── broken-thumbnails/Dockerfile
│   ├── broken-network/Dockerfile
│   └── broken-full/Dockerfile
├── .env.example
├── pytest.ini
└── pyproject.toml
```

---

## 🚀 Planowane funkcje (Roadmap)

### v2.3 – Heurystyki bez LLM
- `fixos quickfix` – natychmiastowe naprawy bez API (baza 30+ znanych bugów)
- Dopasowanie heurystyczne diagnostyki do znanych wzorców
- Działa offline, zero tokenów

### v2.4 – Raporty i historia
- `fixos report` – eksport sesji do HTML/PDF/Markdown
- `fixos history` – historia napraw z wynikami
- Porównanie stanu przed/po naprawie

### v2.5 – Integracje
- `fixos watch` – monitoring w tle, powiadomienia przy problemach
- Webhook do Slack/Discord przy wykryciu błędów krytycznych
- Integracja z Prometheus/Grafana (metryki diagnostyczne)

### v3.0 – Multi-agent
- Równoległe agenty dla różnych modułów (audio, sieć, dysk)
- Koordynator z priorytetyzacją problemów
- Uczenie się z historii napraw (fine-tuning lokalnych modeli)

---

## Licencja

Apache License 2.0 – see [LICENSE](LICENSE) for details.

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
