"""
Register keil-mcp in Claude Desktop and Claude Code CLI.

Run on the Windows machine where Keil MDK is installed:
    python setup.py

This writes the MCP server entry to:
  - %APPDATA%\\Claude\\claude_desktop_config.json   (Claude Desktop)
  - %USERPROFILE%\\.claude\\settings.json           (Claude Code CLI)
"""
import json
import os
import sys
from pathlib import Path


def register_mcp():
    server_path = (Path(__file__).parent / "server.py").resolve()

    # Prefer python from the current interpreter (venv-aware)
    python_exe = sys.executable

    entry = {
        "command": python_exe,
        "args":    [str(server_path)],
        "env":     {},
    }

    targets: list[Path] = []

    # Claude Desktop (Windows)
    appdata = os.environ.get("APPDATA")
    if appdata:
        targets.append(Path(appdata) / "Claude" / "claude_desktop_config.json")

    # Claude Code CLI (~/.claude/settings.json) — cross-platform
    targets.append(Path.home() / ".claude" / "settings.json")

    registered = 0
    for cfg_path in targets:
        if not cfg_path.exists():
            print(f"  skip (not found): {cfg_path}")
            continue
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}

        data.setdefault("mcpServers", {})["keil-mcp"] = entry
        cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"  registered in: {cfg_path}")
        registered += 1

    if registered == 0:
        print("WARNING: No Claude config files found. "
              "Make sure Claude Desktop or Claude Code CLI is installed.")
    else:
        print(f"\nDone. Restart Claude to load the keil-mcp server.")
        print(f"Server: {server_path}")
        print(f"Python: {python_exe}")


if __name__ == "__main__":
    print("Registering keil-mcp MCP server...")
    register_mcp()
