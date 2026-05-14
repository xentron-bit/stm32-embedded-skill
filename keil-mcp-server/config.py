"""
Tool path auto-detection for Keil MDK + STM32 toolchain.
Searches common install locations + Windows registry.
Persists found paths to ~/.keil-mcp-config.json for fast subsequent starts.
"""
import glob
import json
import subprocess
import sys
from pathlib import Path

def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)

CONFIG_FILE = Path.home() / ".keil-mcp-config.json"

# ── Search lists ────────────────────────────────────────────────────────────

def _cubemx_candidates() -> list[str]:
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    return [
        r"C:\ST\STM32CubeMX\STM32CubeMX.exe",
        r"C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeMX\STM32CubeMX.exe",
        r"C:\Program Files (x86)\STMicroelectronics\STM32Cube\STM32CubeMX\STM32CubeMX.exe",
        *glob.glob(r"C:\ST\STM32CubeIDE_*\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.cubemx*\tools\bin\STM32CubeMX.exe"),
        *glob.glob(r"C:\ST\STM32CubeIDE*\STM32CubeMX\STM32CubeMX.exe"),
        *(glob.glob(str(Path(local) / "ST" / "STM32CubeMX" / "STM32CubeMX.exe")) if local else []),
        *(glob.glob(str(Path(local) / "ST" / "STM32CubeIDE*" / "STM32CubeIDE" / "plugins" / "com.st.stm32cube.ide.mcu.externaltools.cubemx*" / "tools" / "bin" / "STM32CubeMX.exe")) if local else []),
    ]


def _uv4_candidates() -> list[str]:
    local = str(Path.home().parent.parent / "AppData" / "Local")  # fallback
    import os
    local = os.environ.get("LOCALAPPDATA", local)
    return [
        r"C:\Keil_v5\UV4\UV4.exe",
        r"C:\Keil\UV4\UV4.exe",
        r"C:\Program Files\ARM\Keil\UV4\UV4.exe",
        r"C:\Program Files (x86)\Keil\UV4\UV4.exe",
        str(Path(local) / "Keil_v5" / "UV4" / "UV4.exe"),
        str(Path(local) / "Keil" / "UV4" / "UV4.exe"),
        *glob.glob(str(Path(local) / "Keil*" / "UV4" / "UV4.exe")),
    ]


def _stlink_gdb_candidates() -> list[str]:
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    return [
        *glob.glob(r"C:\ST\STM32CubeIDE_*\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.stlink-gdb-server*\tools\bin\ST-LINK_gdbserver.exe"),
        r"C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\ST-LINK_gdbserver.exe",
        r"C:\ST\STM32CubeProgrammer\bin\ST-LINK_gdbserver.exe",
        *glob.glob(r"C:\ST\STM32CubeProgrammer*\bin\ST-LINK_gdbserver.exe"),
        *(glob.glob(str(Path(local) / "ST" / "STM32CubeIDE*" / "STM32CubeIDE" / "plugins" / "com.st.stm32cube.ide.mcu.externaltools.stlink-gdb-server*" / "tools" / "bin" / "ST-LINK_gdbserver.exe")) if local else []),
        *(glob.glob(str(Path(local) / "ST" / "STM32CubeProgrammer*" / "bin" / "ST-LINK_gdbserver.exe")) if local else []),
    ]


def _gdb_candidates() -> list[str]:
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    return [
        *glob.glob(r"C:\ST\STM32CubeIDE_*\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32*\tools\bin\arm-none-eabi-gdb.exe"),
        r"C:\Keil_v5\ARM\ARMCLANG\bin\arm-none-eabi-gdb.exe",
        *glob.glob(r"C:\Program Files (x86)\GNU Arm Embedded Toolchain\*\bin\arm-none-eabi-gdb.exe"),
        *glob.glob(r"C:\Program Files\GNU Arm Embedded Toolchain\*\bin\arm-none-eabi-gdb.exe"),
        *(glob.glob(str(Path(local) / "Keil_v5" / "ARM" / "ARMCLANG" / "bin" / "arm-none-eabi-gdb.exe")) if local else []),
        *(glob.glob(str(Path(local) / "ST" / "STM32CubeIDE*" / "STM32CubeIDE" / "plugins" / "com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32*" / "tools" / "bin" / "arm-none-eabi-gdb.exe")) if local else []),
    ]


def _openocd_candidates() -> list[str]:
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    return [
        r"C:\OpenOCD\bin\openocd.exe",
        r"C:\Program Files\OpenOCD\bin\openocd.exe",
        *glob.glob(r"C:\ST\STM32CubeIDE_*\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.openocd*\tools\bin\openocd.exe"),
        *(glob.glob(str(Path(local) / "ST" / "STM32CubeIDE*" / "STM32CubeIDE" / "plugins" / "com.st.stm32cube.ide.mcu.externaltools.openocd*" / "tools" / "bin" / "openocd.exe")) if local else []),
    ]


def _cubeprog_candidates() -> list[str]:
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    return [
        r"C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe",
        r"C:\ST\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe",
        *glob.glob(r"C:\ST\STM32CubeProgrammer*\bin\STM32_Programmer_CLI.exe"),
        *(glob.glob(str(Path(local) / "ST" / "STM32CubeProgrammer*" / "bin" / "STM32_Programmer_CLI.exe")) if local else []),
    ]


# ── Registry fallback (Keil on Windows) ─────────────────────────────────────

def _find_keil_from_registry() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Keil\Products\MDK")
        path, _ = winreg.QueryValueEx(key, "Path")
        candidate = Path(path) / "UV4" / "UV4.exe"
        return str(candidate) if candidate.exists() else None
    except Exception:
        return None


# ── Core detection logic ─────────────────────────────────────────────────────

def _find_first(candidates: list[str]) -> str | None:
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def detect_all_tools() -> dict:
    uv4 = _find_first(_uv4_candidates()) or _find_keil_from_registry()
    cfg = {
        "cubemx":    _find_first(_cubemx_candidates()),
        "uv4":       uv4,
        "stlink_gdb": _find_first(_stlink_gdb_candidates()),
        "gdb":       _find_first(_gdb_candidates()),
        "openocd":   _find_first(_openocd_candidates()),   # optional
        "cubeprog":  _find_first(_cubeprog_candidates()),  # optional
    }

    missing = [k for k, v in cfg.items() if v is None and k not in ("openocd", "cubeprog", "gdb", "stlink_gdb")]
    if missing:
        _log(f"[keil-mcp] WARNING: tools not found: {missing}")
    for k, v in cfg.items():
        _log(f"[keil-mcp] {k}: {v or '(not found)'}")
    return cfg


def load_or_detect() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    cfg = detect_all_tools()
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def reset_and_detect() -> dict:
    """Force re-detection even if config cache exists."""
    CONFIG_FILE.unlink(missing_ok=True)
    return load_or_detect()


# ── Probe listing via STM32CubeProgrammer CLI ────────────────────────────────

def _parse_probe_list(output: str) -> list[dict]:
    """
    Parse STM32_Programmer_CLI --list output into structured probe list.
    Expected lines like:
        ST-LINK SN: 066DFF484849887867065529
        ST-LINK Firmware version: V2J37M27
        ST-LINK JTAG/SWD HW: V3
    """
    probes: list[dict] = []
    current: dict = {}
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("ST-LINK SN:"):
            if current:
                probes.append(current)
            current = {"serial": line.split(":", 1)[1].strip()}
        elif line.startswith("ST-LINK Firmware version:") and current:
            current["version"] = line.split(":", 1)[1].strip()
        elif ("JTAG" in line or "SWD" in line) and current:
            current["interface"] = "JTAG/SWD"
    if current:
        probes.append(current)
    return probes


def list_connected_probes(cubeprog_path: str | None) -> list[dict]:
    if not cubeprog_path or not Path(cubeprog_path).exists():
        return [{"error": "STM32_Programmer_CLI not found — cannot list probes"}]
    try:
        result = subprocess.run(
            [cubeprog_path, "--list"],
            capture_output=True, text=True, timeout=15,
            **(_no_window() if sys.platform == "win32" else {})
        )
        probes = _parse_probe_list(result.stdout)
        return probes if probes else [{"info": "No ST-LINK probes detected"}]
    except subprocess.TimeoutExpired:
        return [{"error": "Probe listing timed out"}]
    except Exception as e:
        return [{"error": str(e)}]


def _no_window() -> dict:
    """Windows: suppress console window for subprocesses."""
    import subprocess as sp
    return {"creationflags": sp.CREATE_NO_WINDOW}


# ── Module-level paths (populated by load_or_detect at import time) ──────────

_cfg: dict = {}

def init() -> dict:
    global _cfg, CUBEMX_PATH, UV4_PATH, STLINK_GDB_PATH, GDB_PATH, OPENOCD_PATH, CUBEPROG_PATH
    _cfg = load_or_detect()
    CUBEMX_PATH    = _cfg.get("cubemx")
    UV4_PATH       = _cfg.get("uv4")
    STLINK_GDB_PATH = _cfg.get("stlink_gdb")
    GDB_PATH       = _cfg.get("gdb")
    OPENOCD_PATH   = _cfg.get("openocd")
    CUBEPROG_PATH  = _cfg.get("cubeprog")
    return _cfg


# Populated on first import via init()
CUBEMX_PATH: str | None = None
UV4_PATH: str | None = None
STLINK_GDB_PATH: str | None = None
GDB_PATH: str | None = None
OPENOCD_PATH: str | None = None
CUBEPROG_PATH: str | None = None
