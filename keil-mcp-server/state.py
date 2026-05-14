"""
Global mutable state for the MCP debug session.
Single debug session at a time; tools read/write these fields.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import subprocess
    from pygdbmi.gdbcontroller import GdbController

# ── GDB / GDB server state ───────────────────────────────────────────────────
gdb: "GdbController | None" = None
gdbserver_proc: "subprocess.Popen | None" = None

connected: bool = False
halted: bool = False

elf_path: str | None = None
gdb_port: int = 61234

# ── SVD peripheral data (loaded on debug_connect) ───────────────────────────
svd_data: dict = {}   # {PERIPHERAL_NAME: {registers: {REG_NAME: {base_address, fields}}}}

# ── Build state ──────────────────────────────────────────────────────────────
last_build_result: dict = {}
last_flash_result: dict = {}
