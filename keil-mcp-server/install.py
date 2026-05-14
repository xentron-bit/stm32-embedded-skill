"""
Keil MCP Server -- Automatic Installer
=======================================
Run from Windows CMD / PowerShell:

    python install.py

Steps:
  1. pip install -r requirements.txt
  2. Detect tool paths (Keil, CubeMX, ST-LINK GDB server, arm-gdb)
  3. Register MCP server in Claude Code CLI ~/.claude/settings.json
  4. Register in Claude Desktop claude_desktop_config.json (if found)
  5. Print summary
"""
import sys

# Force UTF-8 output on Windows cp1252 consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import os
import subprocess
from pathlib import Path


REPO = "https://github.com/xentron-bit/stm32-embedded-skill"
SERVER_SCRIPT = Path(__file__).parent.resolve() / "server.py"
PYTHON = sys.executable


# -- 1. Dependencies ----------------------------------------------------------

def install_deps():
    req = Path(__file__).parent / "requirements.txt"
    print("\n[1/4] Installing dependencies...")
    result = subprocess.run(
        [PYTHON, "-m", "pip", "install", "-r", str(req), "--quiet"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
        sys.exit(1)
    print("  OK -- mcp, pygdbmi, pydantic installed")


# -- 2. Tool detection --------------------------------------------------------

def detect_tools():
    print("\n[2/4] Detecting tool paths...")
    sys.path.insert(0, str(Path(__file__).parent))
    import config as cfg
    paths = cfg.reset_and_detect()
    found = {k: v for k, v in paths.items() if v}
    missing = [k for k, v in paths.items() if not v and k not in ("openocd", "cubeprog", "gdb", "stlink_gdb")]
    if missing:
        print(f"  WARNING: Tools not found: {missing}")
        print(f"  Install Keil / STM32 tools then re-run: python install.py")
    return found


# -- 3. MCP registration ------------------------------------------------------

MCP_ENTRY = {
    "type": "stdio",
    "command": PYTHON,
    "args": [str(SERVER_SCRIPT)],
    "env": {}
}


def _write_claude_json(cfg_path: Path):
    """Write to ~/.claude.json (Claude Code CLI user-scope MCP config)."""
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        data = {}
    data.setdefault("mcpServers", {})["keil-mcp"] = MCP_ENTRY
    cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return True


def _write_desktop_config(cfg_path: Path):
    """Write to Claude Desktop claude_desktop_config.json (no type field needed)."""
    if not cfg_path.exists():
        return False
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    entry = {k: v for k, v in MCP_ENTRY.items() if k != "type"}
    data.setdefault("mcpServers", {})["keil-mcp"] = entry
    cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return True


def register_mcp():
    print("\n[3/4] Registering MCP server with Claude...")
    registered = 0

    # Claude Code CLI: ~/.claude.json (root of home, NOT inside ~/.claude/)
    cli_json = Path.home() / ".claude.json"
    if _write_claude_json(cli_json):
        print(f"  OK  -> {cli_json}")
        registered += 1

    # Claude Desktop (optional)
    if appdata := os.environ.get("APPDATA"):
        desktop = Path(appdata) / "Claude" / "claude_desktop_config.json"
        if _write_desktop_config(desktop):
            print(f"  OK  -> {desktop}")
            registered += 1
        else:
            print(f"  skip (not found) -> {desktop}")

    if registered == 0:
        print("  WARNING: Could not register MCP server.")


# -- 4. Summary ---------------------------------------------------------------

def print_summary(found: dict):
    print("\n[4/4] Installation complete")
    print("-" * 50)
    print(f"  Python   : {PYTHON}")
    print(f"  Server   : {SERVER_SCRIPT}")
    print(f"  UV4      : {found.get('uv4', '(not found)')}")
    print(f"  CubeMX   : {found.get('cubemx', '(not found)')}")
    print(f"  ST-LINK  : {found.get('stlink_gdb', '(not found)')}")
    print(f"  arm-gdb  : {found.get('gdb', '(not found)')}")
    print("-" * 50)
    print("\nNext step: Restart Claude.")
    print("Test: type 'list_probes' in Claude to see connected ST-Link devices.")
    print(f"\nRepo: {REPO}")


# -- Main ---------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 50)
    print("  Keil MCP Server -- Installer")
    print("=" * 50)
    install_deps()
    found = detect_tools()
    register_mcp()
    print_summary(found)
