from fixos.cli import cli
print("Commands:", cli.commands.keys())
print("Is 'fix' present?", "fix" in cli.commands)
