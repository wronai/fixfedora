import re

with open("fixos/cli.py", "r", encoding="utf-8") as f:
    text = f.read()

# Make sure imports are there
if "from typing import Dict, Any, Optional" not in text:
    text = text.replace("from pathlib import Path\n", "from pathlib import Path\nfrom typing import Dict, Any, Optional\n")

if "from .config import (" not in text:
    pass # Should be there

# Extract enhancements
with open("/home/tom/github/maskservice/c2004/fixos_cli_enhancements.py", "r", encoding="utf-8") as f:
    enh = f.read()

# Extract shared options from enh
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
new_scan = new_scan.replace("# Add @add_shared_options decorator to the existing scan function", "")
new_scan = new_scan.replace("interactive, json, llm_fallback", "interactive, json_output, llm_fallback")
new_scan = new_scan.replace("if json:", "if json_output:")

# Replace in cli.py by section markers
# The file has:
# #  fixos scan
# # ════════════ ...
# @cli.command()
# ...
# #  fixos fix
# # ════════════ ...

scan_marker = "#  fixos scan"
fix_marker = "#  fixos fix"
token_marker = "#  fixos token"

# split by markers
parts = re.split(r'(# ══════════════════════════════════════════════════════════\n#  (?:fixos scan|fixos fix|fixos token)\n# ══════════════════════════════════════════════════════════\n)', text)

# The structure is:
# parts[0]: up to fixos scan header
# parts[1]: fixos scan header
# parts[2]: scan body
# parts[3]: fixos fix header
# parts[4]: fix body
# parts[5]: fixos token header
# parts[6]: token body + rest

if len(parts) >= 7 and "def scan" in parts[2] and "def fix" in parts[4]:
    parts[2] = "\n" + new_scan + "\n\n\n"
    parts[4] = "\n" + new_fix + "\n\n\n"
    new_text = "".join(parts)
    print("Patch OK, writing...")
    with open("fixos/cli.py", "w", encoding="utf-8") as f:
        f.write(new_text)
else:
    print("Could not match format")

