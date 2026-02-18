"""
Główny punkt wejścia CLI dla fixfedora.
Użycie: fixfedora --token sk-...
"""

import json
import os
import sys
from pathlib import Path

try:
    import click
except ImportError:
    print("[BŁĄD] Zainstaluj: pip install click")
    sys.exit(1)

from .system_checks import get_full_diagnostics
from .anonymizer import anonymize
from .llm_shell import run_llm_shell

CONFIG_FILE = Path.home() / ".fixfedora.conf"

BANNER = r"""
  __  _      ___        __       _
 / _|(_)_ __/ __| ___  / _| ___ | |_  ___  _ _ __ _
|  _|| | \ \ (__/ -_) |  _|/ -_)|  _|/ _ \| '_/ _` |
|_|  |_|_/_/\_,_\___| |_|  \___| \__|\/\__/|_| \__,_|

  Diagnostyka i naprawa Fedora z AI  •  v1.0.0
"""


def load_token_from_config() -> str | None:
    """Wczytuje token API z pliku konfiguracyjnego ~/.fixfedora.conf"""
    if not CONFIG_FILE.exists():
        return None
    try:
        for line in CONFIG_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith('OPENAI_API_KEY=') or line.startswith('TOKEN='):
                return line.split('=', 1)[1].strip()
    except Exception:
        pass
    return None


@click.command()
@click.option(
    '--token', '-t',
    default=None,
    envvar='OPENAI_API_KEY',
    help='Klucz API OpenAI (lub kompatybilnego LLM). Alternatywnie: ~/.fixfedora.conf lub env OPENAI_API_KEY'
)
@click.option(
    '--model', '-m',
    default='gpt-4o-mini',
    show_default=True,
    help='Model LLM do użycia (np. gpt-4o-mini, gpt-4o, gpt-4-turbo)'
)
@click.option(
    '--timeout', '-T',
    default=3600,
    show_default=True,
    help='Maksymalny czas sesji w sekundach (domyślnie 3600 = 1h)'
)
@click.option(
    '--diagnose-only', '-d',
    is_flag=True,
    default=False,
    help='Tylko zbierz diagnostykę i zapisz do pliku, bez uruchamiania LLM'
)
@click.option(
    '--output', '-o',
    default=None,
    help='Plik wyjściowy dla danych diagnostycznych (JSON). Używane z --diagnose-only'
)
@click.option(
    '--base-url', '-u',
    default=None,
    help='Alternatywny URL API (np. https://api.x.ai/v1 dla xAI Grok)'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    default=False,
    help='Szczegółowy output debugowania'
)
@click.option(
    '--no-banner',
    is_flag=True,
    default=False,
    help='Ukryj banner startowy'
)
def main(token, model, timeout, diagnose_only, output, base_url, verbose, no_banner):
    """
    fixfedora – Diagnostyka i naprawa systemu Fedora z pomocą AI.
    
    Zbiera metryki systemowe, anonimizuje wrażliwe dane i uruchamia
    interaktywny shell LLM do analizy i naprawy problemów.
    
    Przykłady użycia:
    
    \b
    # Podstawowe – pełna diagnostyka z LLM
    fixfedora --token sk-XXXXXXXXXXXXXXXXXXXX
    
    \b
    # Tylko diagnostyka, zapis do pliku
    fixfedora --token sk-... --diagnose-only --output raport.json
    
    \b
    # Z alternatywnym API (xAI Grok)
    fixfedora --token xai-... --base-url https://api.x.ai/v1 --model grok-beta
    
    \b
    # Sesja z limitem 30 minut
    fixfedora --token sk-... --timeout 1800
    
    \b
    # Token z pliku konfiguracyjnego ~/.fixfedora.conf
    echo "OPENAI_API_KEY=sk-..." > ~/.fixfedora.conf
    chmod 600 ~/.fixfedora.conf
    fixfedora
    """
    if not no_banner:
        click.echo(click.style(BANNER, fg='cyan'))

    # Resolve token
    resolved_token = token or load_token_from_config() or os.environ.get('OPENAI_API_KEY')
    
    if not resolved_token and not diagnose_only:
        click.echo(click.style("❌ Brak tokena API!", fg='red'))
        click.echo("Podaj go przez:")
        click.echo("  --token sk-...                    (argument CLI)")
        click.echo("  OPENAI_API_KEY=sk-... fixfedora   (zmienna środowiskowa)")
        click.echo("  echo 'OPENAI_API_KEY=sk-...' > ~/.fixfedora.conf  (plik konfiguracyjny)")
        sys.exit(1)

    # Krok 1: Diagnostyka
    click.echo(click.style("🔍 Zbieranie diagnostyki systemu Fedora...", fg='yellow'))
    try:
        diagnostics = get_full_diagnostics()
    except Exception as e:
        click.echo(click.style(f"❌ Błąd podczas diagnostyki: {e}", fg='red'))
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    click.echo(click.style("✅ Diagnostyka zebrana i zanonimizowana.", fg='green'))

    # Krok 2: Opcjonalny zapis do pliku
    if output or diagnose_only:
        save_path = output or 'fixfedora-report.json'
        try:
            anon_data = anonymize(str(diagnostics))
            with open(save_path, 'w', encoding='utf-8') as f:
                # Próba zapisu jako JSON (dane są stringiem po anonimizacji)
                json.dump({'anonymized_report': anon_data, 'raw': diagnostics}, f, 
                         ensure_ascii=False, indent=2, default=str)
            click.echo(click.style(f"💾 Raport zapisany: {save_path}", fg='green'))
        except Exception as e:
            click.echo(click.style(f"⚠️ Błąd zapisu: {e}", fg='yellow'))

        if diagnose_only:
            click.echo("ℹ️  Tryb --diagnose-only: pomijam uruchomienie LLM shell.")
            sys.exit(0)

    # Krok 3: Uruchom LLM shell
    click.echo(click.style(f"\n⏰ Uruchamianie sesji LLM (model: {model}, timeout: {timeout}s)...", fg='cyan'))
    click.echo(click.style("  Tip: wpisz '!<komenda>' aby wykonać komendę systemową (np. !dnf check-update)", fg='blue'))
    click.echo(click.style("  Tip: wpisz 'q' aby zakończyć sesję\n", fg='blue'))

    try:
        run_llm_shell(
            diagnostics_data=diagnostics,
            token=resolved_token,
            model=model,
            timeout=timeout,
            verbose=verbose,
            base_url=base_url,
        )
    except KeyboardInterrupt:
        click.echo(click.style("\n\n⚠️  Sesja przerwana (Ctrl+C).", fg='yellow'))
    except Exception as e:
        click.echo(click.style(f"\n❌ Nieoczekiwany błąd: {e}", fg='red'))
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
