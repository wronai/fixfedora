import re

with open("README.md", "r", encoding="utf-8") as f:
    readme = f.read()

readme = readme.replace(
    "fixos scan --audio --output /tmp/audio-report.json",
    "fixos scan --audio --output /tmp/audio-report.json\n\n# Analiza i interaktywne czyszczenie zajętości dysku\nfixos fix --disc"
)

with open("README.md", "w", encoding="utf-8") as f:
    f.write(readme)

with open("CHANGELOG.md", "r", encoding="utf-8") as f:
    changelog = f.read()

new_changelog = """## [Unreleased]

### Added

- **feat(disk):** Nowa funkcja `--disc` (`--disk`) dla poleceń `fix` i `scan` do analizy zajętości dysku.
- **feat(interactive):** Kreator czyszczenia dysku (CleanupPlanner) z priorytetami (🔴/🟡/🟢).
- **feat(llm):** Fallback LLM dla błędów podczas czyszczenia dysku.
- **fix(cli):** Naprawa parsera grupowego (NaturalLanguageGroup) w celu poprawnego działania komend.

"""

changelog = changelog.replace("## [2.1.16]", new_changelog + "## [2.1.16]")

with open("CHANGELOG.md", "w", encoding="utf-8") as f:
    f.write(changelog)
