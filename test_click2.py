from fixos.cli import cli
scan_cmd = cli.commands['scan']
print("Scan params:", [p.name for p in scan_cmd.params])
fix_cmd = cli.commands['fix']
print("Fix params:", [p.name for p in fix_cmd.params])
