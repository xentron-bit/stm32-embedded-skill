"""
JTAG chain scan and IEEE 1149.1 boundary scan tools.
Uses GDB 'monitor' commands routed through the ST-LINK GDB server (OpenOCD compatible).
BSDL file discovery for STM32 boundary scan description files.
"""
import glob
from pathlib import Path
from typing import Literal

from mcp.types import TextContent

import state
from tools.debug import _gdb_a, _text


# ── BSDL discovery ────────────────────────────────────────────────────────────

_BSDL_CACHE = Path.home() / ".keil-mcp-bsdl"


def bsdl_find(mcu_name: str) -> str | None:
    """
    Find a BSDL file for the given MCU name.

    Search order:
    1. Local cache: ~/.keil-mcp-bsdl/<mcu>*.bsd
    2. Keil DFP pack directories (recursive)

    If not found, the user must manually place the file in ~/.keil-mcp-bsdl/
    (ST provides BSDL files at st.com/resource/en/boundary_scan_description_language/).
    """
    _BSDL_CACHE.mkdir(exist_ok=True)

    for f in _BSDL_CACHE.glob(f"*{mcu_name}*.bsd"):
        return str(f)
    for f in _BSDL_CACHE.glob(f"*{mcu_name}*.bsdl"):
        return str(f)

    for pattern in [
        rf"C:\Keil_v5\ARM\Pack\Keil\STM32*_DFP\*\**\*{mcu_name}*.bsd",
        rf"C:\Keil_v5\ARM\Pack\Keil\STM32*_DFP\*\**\*{mcu_name}*.bsdl",
    ]:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return matches[0]

    return None


async def jtag_bsdl_find(mcu_name: str) -> list[TextContent]:
    """Locate the BSDL file for the given MCU."""
    path = bsdl_find(mcu_name)
    if path:
        return _text(f"Found BSDL: {path}")
    cache = str(_BSDL_CACHE)
    return _text(
        f"BSDL not found for {mcu_name}.\n"
        f"Download from: https://www.st.com/resource/en/boundary_scan_description_language/\n"
        f"Place in: {cache}"
    )


# ── JTAG chain scan ───────────────────────────────────────────────────────────

async def jtag_get_chain() -> list[TextContent]:
    """
    Scan JTAG chain and return device IDCODEs.
    Requires GDB to be connected (debug_connect must be called first).
    The GDB server must support OpenOCD-compatible 'monitor' commands.
    """
    if not state.connected:
        return _text("ERROR: Not connected — call debug_connect first")

    try:
        resp  = await _gdb_a("monitor jtag init", timeout=10)
        resp2 = await _gdb_a("monitor scan_chain", timeout=10)
        from tools.debug import _resp_text
        return _text(f"JTAG chain:\n{_resp_text(resp)}\n{_resp_text(resp2)}")
    except Exception as e:
        return _text(f"JTAG chain scan failed: {e}")


# ── IDCODE read ───────────────────────────────────────────────────────────────

async def jtag_idcode() -> list[TextContent]:
    """
    Read device IDCODE via JTAG IDCODE instruction (IR=0xFF, DR=32 bits).
    The 32-bit IDCODE encodes manufacturer, part number, and version.
    """
    if not state.connected:
        return _text("ERROR: Not connected — call debug_connect first")

    try:
        from tools.debug import _resp_text
        r1 = await _gdb_a("monitor jtag init", timeout=10)
        r2 = await _gdb_a("monitor jtag arp_init-reset", timeout=10)
        r3 = await _gdb_a("monitor irscan auto 0xFF", timeout=10)   # IDCODE instruction
        r4 = await _gdb_a("monitor drscan auto 32 0x0", timeout=10)  # shift 32 bits
        output = "\n".join(_resp_text(r) for r in [r1, r2, r3, r4])
        return _text(f"IDCODE result:\n{output}")
    except Exception as e:
        return _text(f"IDCODE read failed: {e}")


# ── SVF boundary scan playback ────────────────────────────────────────────────

async def jtag_boundary_scan(
    action: Literal["idcode", "run_svf"],
    svf_path: str | None = None,
    bsdl_path: str | None = None,
) -> list[TextContent]:
    """
    Perform boundary scan operations.

    action='idcode' — read JTAG IDCODE register
    action='run_svf' — play back an SVF (Serial Vector Format) test file.
        svf_path: path to the .svf file
        bsdl_path: optional; informational only (SVF is generated from BSDL offline)

    SVF files encode boundary scan test vectors and can be generated from
    BSDL files using tools like XJTAG, OpenOCD bsdl2svf, or UrJTAG.
    """
    if not state.connected:
        return _text("ERROR: Not connected — call debug_connect first")

    if action == "idcode":
        return await jtag_idcode()

    if action == "run_svf":
        if not svf_path:
            return _text("ERROR: svf_path required for run_svf action")
        svf = Path(svf_path).resolve()
        if not svf.exists():
            return _text(f"ERROR: SVF file not found: {svf}")
        try:
            from tools.debug import _resp_text
            resp = await _gdb_a(f'monitor svf "{svf}" progress', timeout=120)
            return _text(f"SVF playback result:\n{_resp_text(resp)}")
        except Exception as e:
            return _text(f"SVF playback failed: {e}")

    return _text(f"ERROR: unknown action '{action}'")
