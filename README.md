![img.png](img.png)

# fixos v2.1 🔧🤖

**AI diagnostyka i naprawa wszystkich systemów** – Linux, Windows, macOS
z anonimizacją danych, trybem HITL/Autonomous i zewnętrznymi źródłami wiedzy.


---

## 🌍 Cross-Platform Support

| System | Package Manager | Audio | Hardware | System |
|:--|:--|:--:|:--:|:--:|
| **Linux** (Fedora, Ubuntu, Arch) | dnf/apt/pacman | ✅ ALSA/PipeWire | ✅ DMI/sensors | ✅ systemd/journal |
| **Windows** 10/11 | winget/choco | ✅ WMI Audio | ✅ WMI Hardware | ✅ Event Log |
| **macOS** | brew | ✅ CoreAudio | ✅ system_profiler | ✅ launchd |

---

## Szybki start (3 kroki)

```bash
# 1. Instalacja
pip install -e ".[dev]"

# 2. Token Google Gemini (domyślny, darmowy)
fixos token set AIzaSy...          # lub --provider openai/xai

# 3. Uruchom diagnostykę
fixos fix
```

---

## Komendy CLI

```
fixos scan              – tylko diagnostyka (bez LLM)
fixos fix               – diagnoza + sesja naprawcza (HITL lub autonomous)
fixos token set KEY     – zapisz token API
fixos token show        – pokaż aktualny token (zamaskowany)
fixos token clear       – usuń token
fixos config show       – pokaż konfigurację
fixos config init       – utwórz .env z szablonu
fixos config set K V    – ustaw wartość w .env
fixos providers         – lista providerów LLM
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

# Bez pokazywania danych użytkownikowi przed wysłaniem
fixos fix --no-show-data

# Z xAI Grok
fixos fix --provider xai --token xai-...

# Timeout 30 minut
fixos fix --timeout 1800

# Test połączenia z Gemini
fixos test-llm
```

---

## Tryby agenta

### 👤 Human-in-the-Loop (HITL) – domyślny

```
LLM sugeruje → Ty decydujesz → Skrypt wykonuje

fixos [00:58:42] ❯ 1           ← napraw problem nr 1
fixos [00:58:30] ❯ !dnf list   ← wykonaj komendę bezpośrednio
fixos [00:58:10] ❯ search sof  ← szukaj w zewnętrznych źródłach
fixos [00:57:55] ❯ D           ← opisz własny problem
fixos [00:57:40] ❯ q           ← zakończ
```

**Nowość v2.1**: Opcja `[D]` – opisz własny problem, a LLM zaproponuje rozwiązania.

### 🤖 Autonomous – agent działa samodzielnie

```bash
fixos fix --mode autonomous
```
- Agent analizuje → wykonuje → weryfikuje → kontynuuje
- Protokół JSON: `{ "action": "EXEC", "command": "...", "reason": "..." }`
- **Zabezpieczenia**: lista zabronionych komend (rm -rf /, mkfs, fdisk...)
- Każde `EXEC` jest logowane z wynikiem
- Limit: `--max-fixes 10` (domyślnie)
- Wymaga jawnego `yes` na starcie

---

## Anonimizacja danych

**Zawsze pokazywana użytkownikowi** przed wysłaniem do LLM (`SHOW_ANONYMIZED_DATA=true`):

```
═══════════════════════════════════════════════════════════════
  📋 DANE DIAGNOSTYCZNE (zanonimizowane) – wysyłane do LLM
═══════════════════════════════════════════════════════════════
  ... [zanonimizowane dane] ...

  🔒 Anonimizacja – co zostało ukryte:
  ✓ Hostname: 1 wystąpień
  ✓ Username: 3 wystąpień
  ✓ Adresy IPv4: 2 wystąpień
  ✓ UUID (serial/hardware): 4 wystąpień
═══════════════════════════════════════════════════════════════
```

Maskowane dane: IPv4, MAC, hostname, username, `/home/<user>`, tokeny API, UUID, numery seryjne.

---

## Moduły diagnostyki

| Moduł | Linux | Windows | macOS | Co sprawdza |
|:--|:--:|:--:|:--:|:--|
| `system` | ✅ | ✅ | ✅ | CPU, RAM, dyski, usługi, aktualizacje, firewall |
| `audio` | ✅ | ✅ | ✅ | ALSA/PipeWire (Linux), WMI Audio (Win), CoreAudio (Mac) |
| `thumbnails` | ✅ | ➖ | ➖ | ffmpegthumbnailer, cache, GNOME ustawienia |
| `hardware` | ✅ | ✅ | ✅ | DMI/WMI/system_profiler, BIOS, GPU, czujniki |

---

## Zewnętrzne źródła wiedzy (fallback)

Gdy LLM nie zna rozwiązania, fixos szuka automatycznie w:

- **Fedora Bugzilla** – baza zgłoszonych błędów
- **ask.fedoraproject.org** – forum społeczności
- **Arch Wiki** – doskonałe źródło dla ogólnych problemów Linux
- **GitHub Issues** – PipeWire, ALSA, linux-hardware repos
- **DuckDuckGo** – ogólne wyszukiwanie (bez klucza API)
- **Google via SerpAPI** – najlepsze wyniki (opcjonalny klucz `SERPAPI_KEY`)

```bash
# Ręczne wyszukiwanie w sesji HITL
fixos [00:58:00] ❯ search sof-firmware lenovo yoga no sound
```

---

## Konfiguracja (.env)

```bash
# Stwórz plik konfiguracyjny
fixos config init

# Lub ręcznie:
cp .env.example .env
chmod 600 .env
```

Kluczowe ustawienia:

```env
LLM_PROVIDER=gemini           # gemini|openai|xai|openrouter|ollama
GEMINI_API_KEY=AIzaSy...      # Klucz Gemini (darmowy)
AGENT_MODE=hitl               # hitl|autonomous
SHOW_ANONYMIZED_DATA=true     # Pokaż dane przed wysłaniem
ENABLE_WEB_SEARCH=true        # Fallback do zewnętrznych źródeł
SESSION_TIMEOUT=3600          # Timeout sesji (1h)
```

---

## Testy i Docker

### Uruchomienie testów

```bash
# Unit testy (bez API)
pytest tests/unit/ -v

# E2E testy z mock LLM
pytest tests/e2e/ -v

# E2E testy z prawdziwym API (wymaga tokena w .env)
pytest tests/e2e/ -v -k "real_llm"

# Pokrycie kodu
pytest --cov=fixos --cov-report=html
```

### Docker – symulowane środowiska

```bash
# Zbuduj wszystkie obrazy
docker compose -f docker/docker-compose.yml build

# Testuj scenariusz broken-audio
docker compose -f docker/docker-compose.yml run broken-audio

# Testuj scenariusz broken-thumbnails
docker compose -f docker/docker-compose.yml run broken-thumbnails

# Pełny scenariusz (wszystkie problemy)
docker compose -f docker/docker-compose.yml run broken-full

# Uruchom testy e2e w Dockerze
docker compose -f docker/docker-compose.yml run e2e-tests
```

### Środowiska Docker

| Obraz | Scenariusz |
|:--|:--|
| `fixos-broken-audio` | Brak sof-firmware, PipeWire failed, no ALSA cards |
| `fixos-broken-thumbnails` | Brak thumbnailerów, pusty cache, brak GStreamer |
| `fixos-broken-full` | Wszystkie problemy naraz + pending updates + failed services |

---

## Struktura projektu

```
fixos/
├── fixos/
│   ├── __init__.py
│   ├── cli.py                  # Komendy CLI (Click)
│   ├── config.py               # Zarządzanie konfiguracją (.env)
│   ├── platform_utils.py       # Cross-platform utilities (Linux/Win/Mac)
│   ├── agent/
│   │   ├── hitl.py             # Human-in-the-Loop z menu akcji
│   │   └── autonomous.py       # Tryb autonomiczny z JSON protokołem
│   ├── diagnostics/
│   │   └── system_checks.py    # Moduły: system, audio, thumbnails, hardware
│   ├── providers/
│   │   └── llm.py              # Multi-provider LLM (Gemini/OpenAI/xAI/Ollama)
│   └── utils/
│       ├── anonymizer.py       # Anonimizacja z raportem
│       └── web_search.py       # Bugzilla/AskFedora/ArchWiki/GitHub/DDG
├── tests/
│   ├── conftest.py             # Fixtures + mock diagnostics
│   ├── e2e/
│   │   ├── test_audio_broken.py
│   │   └── test_thumbnails_broken.py
│   └── unit/
│       └── test_core.py
├── docker/
│   ├── base/Dockerfile
│   ├── broken-audio/Dockerfile
│   ├── broken-thumbnails/Dockerfile
│   ├── broken-full/Dockerfile
│   └── docker-compose.yml
├── .env.example
├── pytest.ini
└── setup.py
```

---

## Licencja

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
