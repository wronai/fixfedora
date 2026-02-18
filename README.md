<img width="1368" height="1216" alt="obraz" src="https://github.com/user-attachments/assets/cf038295-d5e8-4e79-8ac3-db697d57b2d3" />

# fixfedora v2.0 🔧🤖

**AI diagnostyka i naprawa Fedora Linux** – audio, thumbnails, sprzęt Lenovo Yoga
z anonimizacją danych, trybem HITL/Autonomous i zewnętrznymi źródłami wiedzy.

```
  __  _      ___        __       _
 / _|(_)_ __/ __| ___  / _| ___ | |_  ___  _ _ __ _
|  _|| | \ \ (__/ -_) |  _|/ -_)|  _|/ _ \| '_/ _` |
|_|  |_|_/_/\_,_\___| |_|  \___| \__|\/\__/|_| \__,_|
  Fedora AI Diagnostics  •  v2.0.0
```

---

## Szybki start (3 kroki)

```bash
# 1. Instalacja
pip install -e ".[dev]"

# 2. Token Google Gemini (domyślny, darmowy)
fixfedora token set AIzaSy...          # lub --provider openai/xai

# 3. Uruchom diagnostykę
fixfedora fix
```

---

## Komendy CLI

```
fixfedora scan              – tylko diagnostyka (bez LLM)
fixfedora fix               – diagnoza + sesja naprawcza (HITL lub autonomous)
fixfedora token set KEY     – zapisz token API
fixfedora token show        – pokaż aktualny token (zamaskowany)
fixfedora token clear       – usuń token
fixfedora config show       – pokaż konfigurację
fixfedora config init       – utwórz .env z szablonu
fixfedora config set K V    – ustaw wartość w .env
fixfedora providers         – lista providerów LLM
fixfedora test-llm          – testuj połączenie z LLM
```

### Przykłady użycia

```bash
# Tylko diagnostyka audio + zapis do pliku
fixfedora scan --audio --output /tmp/audio-report.json

# Napraw audio i thumbnails (HITL – pyta o potwierdzenie)
fixfedora fix --modules audio,thumbnails

# Tryb autonomiczny (agent sam naprawia, max 5 akcji)
fixfedora fix --mode autonomous --max-fixes 5

# Bez pokazywania danych użytkownikowi przed wysłaniem
fixfedora fix --no-show-data

# Z xAI Grok
fixfedora fix --provider xai --token xai-...

# Timeout 30 minut
fixfedora fix --timeout 1800

# Test połączenia z Gemini
fixfedora test-llm
```

---

## Tryby agenta

### 👤 Human-in-the-Loop (HITL) – domyślny

```
LLM sugeruje → Ty decydujesz → Skrypt wykonuje

fixfedora [00:58:42] ❯ 1           ← napraw problem nr 1
fixfedora [00:58:30] ❯ !dnf list   ← wykonaj komendę bezpośrednio
fixfedora [00:58:10] ❯ search sof  ← szukaj w zewnętrznych źródłach
fixfedora [00:57:55] ❯ all         ← napraw wszystko
fixfedora [00:57:40] ❯ q           ← zakończ
```

### 🤖 Autonomous – agent działa samodzielnie

```bash
fixfedora fix --mode autonomous
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

| Moduł | Co sprawdza |
|:--|:--|
| `system` | CPU, RAM, dyski, `systemctl --failed`, `dnf check-update`, `journalctl` |
| `audio` | ALSA karty, PipeWire/WirePlumber status, SOF firmware, mikrofon Lenovo |
| `thumbnails` | ffmpegthumbnailer, totem-nautilus, cache ~/.cache/thumbnails, GNOME ustawienia |
| `hardware` | DMI (Lenovo Yoga), BIOS, GPU, touchpad, kamera, ACPI, czujniki |

---

## Znane problemy Lenovo Yoga (Fedora)

### 🔊 Brak dźwięku po aktualizacji

**Przyczyna**: Brak lub niekompatybilna wersja `sof-firmware` (Sound Open Firmware)

```bash
# Diagnoza
fixfedora scan --audio

# Naprawa
sudo dnf install sof-firmware
systemctl --user restart pipewire wireplumber
```

### 🖼️ Brak podglądów plików

**Przyczyna**: Brak thumbnailerów usuniętych przez aktualizację Fedora

```bash
# Naprawa
sudo dnf install ffmpegthumbnailer totem-nautilus gstreamer1-plugins-good
nautilus -q
rm -rf ~/.cache/thumbnails/fail/*
```

---

## Zewnętrzne źródła wiedzy (fallback)

Gdy LLM nie zna rozwiązania, fixfedora szuka automatycznie w:

- **Fedora Bugzilla** – baza zgłoszonych błędów
- **ask.fedoraproject.org** – forum społeczności
- **Arch Wiki** – doskonałe źródło dla ogólnych problemów Linux
- **GitHub Issues** – PipeWire, ALSA, linux-hardware repos
- **DuckDuckGo** – ogólne wyszukiwanie (bez klucza API)
- **Google via SerpAPI** – najlepsze wyniki (opcjonalny klucz `SERPAPI_KEY`)

```bash
# Ręczne wyszukiwanie w sesji HITL
fixfedora [00:58:00] ❯ search sof-firmware lenovo yoga no sound
```

---

## Konfiguracja (.env)

```bash
# Stwórz plik konfiguracyjny
fixfedora config init

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
pytest --cov=fixfedora --cov-report=html
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
| `fixfedora-broken-audio` | Brak sof-firmware, PipeWire failed, no ALSA cards |
| `fixfedora-broken-thumbnails` | Brak thumbnailerów, pusty cache, brak GStreamer |
| `fixfedora-broken-full` | Wszystkie problemy naraz + pending updates + failed services |

---

## Struktura projektu

```
fixfedora/
├── fixfedora/
│   ├── __init__.py
│   ├── cli.py                  # Komendy CLI (Click)
│   ├── config.py               # Zarządzanie konfiguracją (.env)
│   ├── agent/
│   │   ├── hitl.py             # Human-in-the-Loop
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

MIT License

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
