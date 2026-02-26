import re

with open("fixos/cli.py", "r", encoding="utf-8") as f:
    text = f.read()

# Make sure imports are there
if "from typing import Dict, Any, Optional" not in text:
    text = text.replace("from pathlib import Path\n", "from pathlib import Path\nfrom typing import Dict, Any, Optional\n")

# Extract enhancements
with open("/home/tom/github/maskservice/c2004/fixos_cli_enhancements.py", "r", encoding="utf-8") as f:
    enh = f.read()

shared_opts = """
def add_shared_options(func):
    \"\"\"Shared options for both scan and fix commands\"\"\"
    func = click.option("--disc", is_flag=True, default=False,
                       help="Analiza zajętości dysku + grupowanie przyczyn")(func)
    func = click.option("--disk", "disc", is_flag=True, default=False,
                       help="Analiza zajętości dysku (alias do --disc)")(func)
    func = click.option("--dry-run", is_flag=True, default=False,
                       help="Symuluj wykonanie komend bez faktycznego uruchamiania")(func)
    func = click.option("--interactive/--no-interactive", default=True,
                       help="Tryb interaktywny (pytaj przed każdą akcją)")(func)
    func = click.option("--json", "json_output", is_flag=True, default=False,
                       help="Wyjście w formacie JSON")(func)
    func = click.option("--llm-fallback/--no-llm-fallback", default=True,
                       help="Użyj LLM gdy heurystyki nie wystarczą")(func)
    return func
"""

if "def add_shared_options" not in text:
    text = text.replace("def add_common_options(fn):\n    for opt in reversed(COMMON_OPTIONS):\n        fn = opt(fn)\n    return fn", "def add_common_options(fn):\n    for opt in reversed(COMMON_OPTIONS):\n        fn = opt(fn)\n    return fn\n" + shared_opts)

# Extract new fix command
new_fix = enh.split("# Enhanced fix command - replace the existing fix function with this")[1].split("# Enhanced scan command - add these options to existing scan command")[0].strip()
new_fix = new_fix.replace("interactive, json, llm_fallback", "interactive, json_output, llm_fallback")
new_fix = new_fix.replace("if json:", "if json_output:")

# Extract new scan command
new_scan = enh.split("# Enhanced scan command - add these options to existing scan command")[1].split("# Add this helper function to fixos/cli.py")[0].strip()
new_scan = new_scan.replace("# Add @add_shared_options decorator to the existing scan function\n", "")
new_scan = new_scan.replace("interactive, json, llm_fallback", "interactive, json_output, llm_fallback")
new_scan = new_scan.replace("if json:", "if json_output:")

# Split text
scan_idx = text.find("#  fixos scan")
fix_idx = text.find("#  fixos fix")
token_idx = text.find("#  fixos token")

if scan_idx != -1 and fix_idx != -1 and token_idx != -1:
    before_scan = text[:scan_idx]
    
    # We want to replace from after the scan comment block until fix_idx
    header_end_scan = text.find("def scan", scan_idx)
    # the function scan goes up to `def _print_quick_issues` or similar. Let's precise:
    end_scan = text.find("def _print_quick_issues", scan_idx)
    
    header_end_fix = text.find("def fix", fix_idx)
    end_fix = token_idx
    
    new_text = (
        text[:scan_idx] +
        "#  fixos scan\n# ══════════════════════════════════════════════════════════\n\n" +
        new_scan + "\n\n" +
        text[end_scan:fix_idx] +
        "#  fixos fix\n# ══════════════════════════════════════════════════════════\n\n" +
        new_fix + "\n\n" +
        text[token_idx:]
    )
    
    with open("fixos/cli.py", "w", encoding="utf-8") as f:
        f.write(new_text)
    print("Patched successfully")
else:
    print("Could not find sections")
