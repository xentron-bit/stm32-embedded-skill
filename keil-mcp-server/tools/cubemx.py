"""
CubeMX / IOC file tools.
Reads, modifies, and generates STM32 projects from .ioc files.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import config


# ── IOC read / write ─────────────────────────────────────────────────────────

def ioc_read(ioc_path: str) -> dict:
    """Parse IOC file into key-value dict (skips comments and blank lines)."""
    text = Path(ioc_path).read_text(encoding="utf-8", errors="replace")
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result


def ioc_set_param(ioc_path: str, key: str, value: str) -> str:
    """Set a key in the IOC file. Adds the key if it does not exist."""
    path = Path(ioc_path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"OK: {key} = {value}"


def ioc_list_peripherals(ioc_path: str) -> list[str]:
    """Return list of active peripheral names found in IOC."""
    data = ioc_read(ioc_path)
    peripherals = set()
    for key in data:
        parts = key.split(".")
        if len(parts) >= 2:
            name = parts[0]
            # Skip ProjectManager, Mcu, BoardManager, etc.
            if not any(name.startswith(p) for p in
                       ("ProjectManager", "Mcu", "Board", "NVIC", "RCC.VS", "File")):
                peripherals.add(name)
    return sorted(peripherals)


def ioc_get_mcu(ioc_path: str) -> str:
    """Return the MCU part name from the IOC file."""
    data = ioc_read(ioc_path)
    return (data.get("Mcu.Name")
            or data.get("ProjectManager.LibraryCopySrc")
            or "unknown")


def ioc_get_uvprojx_path(ioc_path: str) -> str:
    """Derive the expected .uvprojx path from IOC ProjectManager fields."""
    data = ioc_read(ioc_path)
    proj_path = data.get("ProjectManager.ProjectPath", "")
    proj_name = data.get("ProjectManager.ProjectName", "")
    if not proj_path or not proj_name:
        return ""
    return str(Path(proj_path) / "MDK-ARM" / f"{proj_name}.uvprojx")


# ── CubeMX headless code generation ─────────────────────────────────────────

def cubemx_generate(ioc_path: str) -> dict:
    """
    Run CubeMX in headless mode to regenerate code from the IOC file.

    Requirements:
    - CubeMX 6.x must be installed and the firmware package already downloaded
      (CubeMX will fail silently if it needs to download during headless run).
    - The IOC ProjectManager.Toolchain/IDE must be set to 'MDK-ARM'.
    """
    if not config.CUBEMX_PATH or not Path(config.CUBEMX_PATH).exists():
        return {"success": False, "error": "STM32CubeMX not found", "output": ""}

    resolved = str(Path(ioc_path).resolve())
    script_content = f"loadproject {resolved}\ngenerate\nexit\n"

    script_file = Path(tempfile.mktemp(suffix=".script"))
    script_file.write_text(script_content, encoding="utf-8")

    cmd = [config.CUBEMX_PATH, "-s", str(script_file)]
    # --no-gui supported in CubeMX >= 6.3; safe to add for newer installs
    cmd.append("--no-gui")

    kwargs: dict = {"capture_output": True, "text": True, "timeout": 180}
    if sys.platform == "win32":
        import subprocess as sp
        kwargs["creationflags"] = sp.CREATE_NO_WINDOW

    try:
        result = subprocess.run(cmd, **kwargs)
    except subprocess.TimeoutExpired:
        script_file.unlink(missing_ok=True)
        return {"success": False, "error": "CubeMX timed out after 180 s", "output": ""}
    except Exception as e:
        script_file.unlink(missing_ok=True)
        return {"success": False, "error": str(e), "output": ""}
    finally:
        script_file.unlink(missing_ok=True)

    output = (result.stdout or "") + (result.stderr or "")
    output = output[-3000:]  # keep last 3000 chars

    success = (result.returncode == 0
               and ("Code Generation success" in output
                    or "generate done" in output.lower()))

    uvprojx = ioc_get_uvprojx_path(ioc_path) if success else None
    return {
        "success": success,
        "returncode": result.returncode,
        "output": output,
        "uvprojx": uvprojx,
    }
