import re

with open("fixos/cli.py", "r", encoding="utf-8") as f:
    text = f.read()

group_class = """
class NaturalLanguageGroup(click.Group):
    def resolve_command(self, ctx, args):
        cmd_name = args[0] if args else None
        cmd = self.get_command(ctx, cmd_name) if cmd_name else None
        if cmd is None and args and not args[0].startswith("-"):
            return super().resolve_command(ctx, ["ask"] + args)
        return super().resolve_command(ctx, args)

@click.group(cls=NaturalLanguageGroup, invoke_without_command=True)
@click.pass_context
"""

# Replace the group decorator and cli definition
text = re.sub(
    r'@click\.group\(invoke_without_command=True\)\n@click\.pass_context\n@click\.argument\("prompt", required=False\)',
    group_class.strip(),
    text
)

text = text.replace("def cli(ctx, prompt, dry_run):", "def cli(ctx, dry_run):")

# Remove prompt handling from cli body
cli_body_old = """    # Obsluga polecenia w jezyku naturalnym - tylko gdy nie ma podkomendy
    if prompt and ctx.invoked_subcommand is None:
        _handle_natural_command(prompt, dry_run)
    elif ctx.invoked_subcommand is None:
        _print_welcome()"""

cli_body_new = """    if ctx.invoked_subcommand is None:
        _print_welcome()"""

text = text.replace(cli_body_old, cli_body_new)

with open("fixos/cli.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Parser patched successfully")
