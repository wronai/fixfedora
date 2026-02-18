# Instalacja fixfedora

## Wymagania systemowe

- Fedora Linux 38+ (lub RHEL/CentOS Stream 9+)
- Python 3.10+
- Dostęp do internetu (do API LLM)
- Klucz API jednego z providerów (patrz niżej)

---

## 1. Zależności systemowe (Fedora)

```bash
sudo dnf install python3-pip python3-psutil python3-pyyaml
```

---

## 2. Instalacja paczki

### Ze źródeł (zalecane podczas development)

```bash
git clone https://github.com/yourusername/fixfedora.git
cd fixfedora
pip install -e ".[dev]"    # z zależnościami testowymi
# lub
pip install -e .           # tylko runtime
```

### Z archiwum ZIP

```bash
unzip fixfedora-2.0.0.zip
cd fixfedora-2.0.0
pip install -e ".[dev]"
```

### Z PyPI (po publikacji)

```bash
pip install fixfedora
```

---

## 3. Konfiguracja tokena API

### Google Gemini (domyślny, darmowy tier)

1. Wejdź na https://aistudio.google.com/apikey
2. Kliknij "Create API Key"
3. Skopiuj klucz (`AIzaSy...`)

```bash
fixfedora token set AIzaSyTWOJKLUCZGEMINI
```

### OpenAI

```bash
fixfedora token set sk-TWOJKLUCZ --provider openai
```

### xAI (Grok)

```bash
fixfedora token set xai-TWOJKLUCZ --provider xai
```

### Ollama (lokalny, bez klucza)

```bash
# Zainstaluj Ollama: https://ollama.ai
ollama pull llama3.2
fixfedora config set LLM_PROVIDER ollama
```

---

## 4. Inicjalizacja pliku konfiguracyjnego

```bash
fixfedora config init      # tworzy .env z szablonu
nano .env                  # opcjonalne dostosowanie
```

Lub ręcznie:

```bash
cp .env.example .env
chmod 600 .env             # ogranicz dostęp!
# Edytuj .env i wstaw klucz API
```

---

## 5. Weryfikacja

```bash
fixfedora test-llm         # test połączenia z LLM
fixfedora config show      # pokaż konfigurację
fixfedora scan             # testowa diagnostyka (bez LLM)
```

---

## 6. Pierwsze uruchomienie

```bash
fixfedora fix              # pełna diagnostyka + sesja naprawcza
```

---

## Rozwiązywanie problemów instalacji

**`ModuleNotFoundError: No module named 'openai'`**
```bash
pip install openai>=1.35.0
```

**`ModuleNotFoundError: No module named 'psutil'`**
```bash
sudo dnf install python3-psutil
# lub
pip install psutil
```

**`fixfedora: command not found`**
```bash
# Dodaj ~/.local/bin do PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**`Permission denied` przy wykonaniu komend systemowych**
```bash
# fixfedora automatycznie dodaje sudo dla komend systemowych
# upewnij się że masz sudo skonfigurowane
sudo -v
```
