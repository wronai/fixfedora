# Wkład do projektu fixfedora

## Zgłaszanie błędów

Otwórz issue na GitHub z:
- Wersją Fedory (`cat /etc/os-release`)
- Modelem sprzętu (dla problemów audio/hardware)
- Zanonimizowanym outputem `fixfedora scan --output report.json`
- Treścią błędu

## Dodawanie modułów diagnostycznych

Nowe moduły dodaj w `fixfedora/diagnostics/system_checks.py`:

```python
def diagnose_moj_modul() -> dict:
    return {
        "sprawdzenie": _cmd("komenda"),
    }

# Zarejestruj w DIAGNOSTIC_MODULES:
DIAGNOSTIC_MODULES["moj_modul"] = ("🔧 Opis modułu", diagnose_moj_modul)
```

## Uruchamianie testów

```bash
make install-dev
make test           # unit + e2e mock
make test-real      # wymaga tokena w .env
```

## Styl kodu

- Python 3.10+, type hints gdzie możliwe
- `black` do formatowania, `ruff` do lintingu
- Docstringi po polsku (projekt skierowany do polskich użytkowników)
