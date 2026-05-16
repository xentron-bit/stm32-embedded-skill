"""
Debug tools: ST-LINK GDB server management + async GDB/MI control.

All GDB calls run pygdbmi in a thread pool executor to avoid blocking
the asyncio event loop (pygdbmi.write() is synchronous).
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Literal

from mcp.types import TextContent
from pygdbmi.gdbcontroller import GdbController

import config
import state
from tools.svd import svd_load, decode_bitfields


# ── Helpers ───────────────────────────────────────────────────────────────────

def _no_window() -> dict:
    if sys.platform == "win32":
        import subprocess as sp
        return {"creationflags": sp.CREATE_NO_WINDOW}
    return {}


def _text(s: str) -> list[TextContent]:
    return [TextContent(type="text", text=s)]


async def _gdb_a(cmd: str, timeout: int = 5) -> list:
    """Run a GDB/MI command in a thread pool — does not block the event loop."""
    if not state.gdb:
        raise RuntimeError("GDB not initialized — call debug_connect first")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: state.gdb.write(cmd, timeout_sec=timeout)
    )


def _resp_text(resp: list) -> str:
    """Extract human-readable text from pygdbmi response list."""
    parts = []
    for r in resp:
        if isinstance(r, dict):
            payload = r.get("payload")
            if isinstance(payload, str):
                parts.append(payload.replace("\\n", "\n").replace("\\t", "\t"))
            elif isinstance(payload, dict):
                parts.append(json.dumps(payload, indent=2))
    return "\n".join(parts).strip() or str(resp)


# ── Probe listing ─────────────────────────────────────────────────────────────

async def list_probes() -> list[TextContent]:
    """List connected ST-LINK probes via STM32CubeProgrammer CLI."""
    probes = config.list_connected_probes(config.CUBEPROG_PATH)
    return _text(json.dumps(probes, indent=2))


# ── Connect ───────────────────────────────────────────────────────────────────

async def debug_connect(
    elf_path: str,
    port: int = 61234,
    swd: bool = True,
    probe_serial: str | None = None,
    reset_on_connect: bool = True,
    mcu_name: str | None = None,
) -> list[TextContent]:
    """
    Start ST-LINK GDB server and connect GDB to the target.

    1. Terminates any previous debug session.
    2. Launches ST-LINK_gdbserver.exe.
    3. Starts arm-none-eabi-gdb via pygdbmi.
    4. Loads ELF, connects to remote, resets and halts target.
    5. Optionally loads SVD for peripheral decode.
    """
    if not config.STLINK_GDB_PATH or not Path(config.STLINK_GDB_PATH).exists():
        return _text("ERROR: ST-LINK_gdbserver.exe not found")
    if not config.GDB_PATH or not Path(config.GDB_PATH).exists():
        return _text("ERROR: arm-none-eabi-gdb.exe not found")

    # 1. Tear down previous session
    await debug_disconnect()

    # 2. Start GDB server
    server_cmd = [
        config.STLINK_GDB_PATH,
        "-p", str(port),
        "--swd" if swd else "--jtag",
        "-l", "1",          # log level 1 (errors + warnings)
        "--persistent",     # don't exit when GDB disconnects
    ]
    if probe_serial:
        server_cmd += ["--serial-number", probe_serial]
    if not reset_on_connect:
        server_cmd += ["--no-reset"]

    state.gdbserver_proc = subprocess.Popen(
        server_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **_no_window(),
    )
    await asyncio.sleep(1.5)   # wait for server to bind port

    if state.gdbserver_proc.poll() is not None:
        return _text(f"ERROR: GDB server exited immediately (code {state.gdbserver_proc.returncode}). "
                     "Check if ST-Link is in use by another app (Keil debug session?).")

    # 3. Start GDB
    loop = asyncio.get_event_loop()
    state.gdb = await loop.run_in_executor(None, lambda: GdbController(
        gdb_path=config.GDB_PATH,
        time_to_check_for_additional_output_sec=0.5,
    ))

    # 4. Configure GDB
    for cmd in [
        "set print elements 0",
        "set pagination off",
        "set confirm off",
        f"file {Path(elf_path).resolve()}",
        f"target remote localhost:{port}",
        "monitor reset halt",
    ]:
        await _gdb_a(cmd)

    state.connected = True
    state.halted    = True
    state.elf_path  = elf_path
    state.gdb_port  = port

    # 5. Load SVD if MCU name provided
    svd_info = ""
    if mcu_name:
        result = svd_load(mcu_name)
        if "ok" in result:
            svd_info = f"\nSVD loaded: {len(result['peripherals'])} peripherals from {result['svd_path']}"
        else:
            svd_info = f"\nSVD: {result.get('error', 'failed to load')}"

    return _text(f"Connected — ELF: {elf_path}, Port: {port}{svd_info}")


# ── Disconnect ────────────────────────────────────────────────────────────────

async def debug_disconnect() -> list[TextContent]:
    """Cleanly disconnect GDB and stop the GDB server."""
    if state.gdb:
        try:
            await _gdb_a("detach", timeout=3)
        except Exception:
            pass
        try:
            await _gdb_a("quit", timeout=2)
        except Exception:
            pass
        try:
            state.gdb.gdb_process.terminate()
        except Exception:
            pass
        state.gdb = None

    if state.gdbserver_proc:
        try:
            state.gdbserver_proc.terminate()
            state.gdbserver_proc.wait(timeout=3)
        except Exception:
            pass
        state.gdbserver_proc = None

    state.connected = False
    state.halted    = False
    return _text("Disconnected — ST-Link released")


# ── Execution control ─────────────────────────────────────────────────────────

async def debug_control(
    action: Literal["run", "halt", "step", "step_over", "step_out", "reset_halt"],
) -> list[TextContent]:
    """Control target execution."""
    mi_map: dict[str, tuple[str, int]] = {
        "run":        ("-exec-continue",  30),
        "halt":       ("-exec-interrupt",  5),
        "step":       ("-exec-step",       5),
        "step_over":  ("-exec-next",       5),
        "step_out":   ("-exec-finish",    10),
        "reset_halt": ("monitor reset halt", 5),
    }
    if action not in mi_map:
        return _text(f"ERROR: unknown action '{action}'")

    cmd, timeout = mi_map[action]
    resp = await _gdb_a(cmd, timeout)
    halted = any(
        ("stopped" in str(r) or "halt" in str(r).lower())
        for r in resp
    )
    state.halted = halted or action in ("halt", "step", "step_over", "step_out", "reset_halt")
    return _text(json.dumps({"action": action, "halted": state.halted}, indent=2))


# ── Breakpoints ───────────────────────────────────────────────────────────────

def _extract_breakpoints(resp: list) -> list[dict]:
    """Parse -break-list MI response into [{id, location, enabled}]."""
    bps: list[dict] = []
    for r in resp:
        payload = r.get("payload") if isinstance(r, dict) else None
        if not isinstance(payload, dict):
            continue
        body = payload.get("BreakpointTable", {}).get("body", [])
        for bp in body:
            bps.append({
                "id":       bp.get("number", ""),
                "location": f"{bp.get('file', '')}:{bp.get('line', '')} {bp.get('func', '')}".strip(),
                "enabled":  bp.get("enabled") == "y",
            })
    return bps


async def debug_breakpoint_toggle(
    location: str,
    condition: str | None = None,
) -> list[TextContent]:
    """
    Smart breakpoint toggle:
    - Not present → create
    - Present & enabled → disable
    - Present & disabled → enable
    """
    info = await _gdb_a("-break-list")
    bps  = _extract_breakpoints(info)
    match = next((b for b in bps if location.lower() in b["location"].lower()), None)

    if match is None:
        cmd = f"-break-insert {location}"
        if condition:
            cmd += f' -c "{condition}"'
        await _gdb_a(cmd)
        return _text(f"Breakpoint created at {location}")

    if match["enabled"]:
        await _gdb_a(f"-break-disable {match['id']}")
        return _text(f"Breakpoint disabled at {location} (id={match['id']})")
    else:
        await _gdb_a(f"-break-enable {match['id']}")
        return _text(f"Breakpoint enabled at {location} (id={match['id']})")


async def debug_breakpoint_list() -> list[TextContent]:
    """List all breakpoints and watchpoints."""
    resp = await _gdb_a("-break-list")
    bps = _extract_breakpoints(resp)
    return _text(json.dumps(bps, indent=2))


async def debug_breakpoint_clear_all() -> list[TextContent]:
    """Remove all breakpoints."""
    await _gdb_a("-break-delete")
    return _text("All breakpoints removed")


# ── Register R/W ──────────────────────────────────────────────────────────────

async def debug_register_rw(
    register: str,
    value: str | None = None,
) -> list[TextContent]:
    """Read or write a core register (r0-r15, pc, sp, lr, xpsr, etc.)."""
    if value is None:
        resp = await _gdb_a(f"info registers {register}")
        return _text(_resp_text(resp))
    await _gdb_a(f"set ${register} = {value}")
    resp = await _gdb_a(f"info registers {register}")
    return _text(f"Set ${register} = {value}\n{_resp_text(resp)}")


# ── Memory R/W ────────────────────────────────────────────────────────────────

async def debug_memory_rw(
    address: str,
    length: int = 16,
    value: str | None = None,
    fmt: Literal["x", "d", "u", "t", "f", "a", "c", "s"] = "x",
    unit: Literal["b", "h", "w", "g"] = "w",
) -> list[TextContent]:
    """
    Read or write memory.

    fmt: x=hex d=decimal u=unsigned t=binary f=float a=address c=char s=string
    unit: b=1B h=2B w=4B g=8B
    """
    if value is None:
        resp = await _gdb_a(f"x/{length}{fmt}{unit} {address}")
        return _text(_resp_text(resp))

    size_map: dict[str, str] = {
        "b": "unsigned char",
        "h": "unsigned short",
        "w": "unsigned int",
        "g": "unsigned long long",
    }
    c_type = size_map.get(unit, "unsigned int")
    await _gdb_a(f"set {{{c_type}}}({address}) = {value}")
    resp = await _gdb_a(f"x/1{fmt}{unit} {address}")
    return _text(f"Wrote [{address}] = {value}\n{_resp_text(resp)}")


# ── Expression evaluate ───────────────────────────────────────────────────────

async def debug_evaluate(expr: str) -> list[TextContent]:
    """Evaluate a C expression in the current scope."""
    resp = await _gdb_a(f"-data-evaluate-expression {expr}", timeout=10)
    return _text(_resp_text(resp))


# ── Backtrace ─────────────────────────────────────────────────────────────────

async def debug_backtrace(frames: int = 20) -> list[TextContent]:
    """Print call stack. frames=0 means all frames."""
    cmd = f"-stack-list-frames 0 {frames - 1}" if frames > 0 else "-stack-list-frames"
    resp = await _gdb_a(cmd)
    return _text(_resp_text(resp))


# ── Local variables ───────────────────────────────────────────────────────────

async def debug_locals() -> list[TextContent]:
    """List local variables in the current stack frame with their values."""
    resp = await _gdb_a("-stack-list-locals --all-values")
    return _text(_resp_text(resp))


# ── Watchpoints ───────────────────────────────────────────────────────────────

async def debug_watch_add(
    expr: str,
    watch_type: Literal["read", "write", "access"] = "write",
) -> list[TextContent]:
    """Add a hardware watchpoint. Halts execution when expr is accessed."""
    gdb_cmd = {"read": "rwatch", "write": "watch", "access": "awatch"}[watch_type]
    resp = await _gdb_a(f"{gdb_cmd} {expr}")
    return _text(_resp_text(resp))


# ── Peripheral register read (SVD-assisted) ───────────────────────────────────

async def peripheral_read(
    peripheral: str,
    register: str | None = None,
) -> list[TextContent]:
    """
    Read peripheral registers and decode bit fields using loaded SVD data.
    If register is omitted, reads all registers of the peripheral.
    """
    svd = state.svd_data
    if not svd:
        hint = ""
        if state.elf_path:
            hint = f"\nHint: derive MCU from ELF / .ioc, then call svd_load(mcu_name='STM32xxxx')."
        return _text(
            "SVD not loaded — call debug_connect with mcu_name, "
            "or call svd_load separately." + hint
        )

    p_name = peripheral.upper()
    periph = svd.get(p_name)
    if periph is None:
        avail = ", ".join(sorted(svd.keys()))
        return _text(f"Peripheral '{p_name}' not found in SVD.\nAvailable: {avail}")

    results: dict = {}

    regs_to_read = {}
    if register:
        r_name = register.upper()
        reg_def = periph["registers"].get(r_name)
        if reg_def is None:
            avail_regs = ", ".join(sorted(periph["registers"].keys()))
            return _text(f"Register '{r_name}' not found.\nAvailable: {avail_regs}")
        regs_to_read[r_name] = reg_def
    else:
        regs_to_read = periph["registers"]

    for r_name, reg_def in regs_to_read.items():
        addr = reg_def["base_address"]
        try:
            resp = await _gdb_a(f"x/1xw {addr}", timeout=5)
            raw = _resp_text(resp)
            # Extract hex value from GDB output like "0x40001000:\t0x00001234"
            import re
            m = re.search(r"0x([0-9a-fA-F]+)\s*$", raw)
            val = int(m.group(1), 16) if m else 0
            decoded = decode_bitfields(val, reg_def.get("fields", {}))
            results[r_name] = {
                "address":    addr,
                "raw_hex":    hex(val),
                "raw_uint":   val,
                "fields":     decoded,
                "description": reg_def.get("description", ""),
            }
        except Exception as e:
            results[r_name] = {"address": addr, "error": str(e)}

    return _text(json.dumps(results, indent=2))
