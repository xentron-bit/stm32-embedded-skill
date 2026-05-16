"""
Keil UV4.exe build and flash tools.
Parses .uvprojx XML to discover ELF/AXF output paths.
"""
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import config


# ── ELF path discovery ───────────────────────────────────────────────────────

def get_elf_path(uvprojx: str, target: str | None = None) -> str:
    """
    Parse the .uvprojx XML to find the expected ELF/AXF output path.
    Returns the path string regardless of whether the file currently exists.
    """
    tree = ET.parse(uvprojx)
    root = tree.getroot()
    proj_dir = Path(uvprojx).parent

    targets = root.findall(".//Target")
    if not targets:
        return str(proj_dir / "Objects" / "project.axf")

    tgt = targets[0]
    if target:
        tgt = next(
            (t for t in targets if t.findtext("TargetName") == target),
            targets[0],
        )

    out_dir  = tgt.findtext(".//OutputDirectory") or "./Objects/"
    out_name = tgt.findtext(".//OutputName") or "project"

    out_dir = out_dir.replace("\\", "/").rstrip("/")
    elf = proj_dir / out_dir / f"{out_name}.elf"
    axf = proj_dir / out_dir / f"{out_name}.axf"
    # Prefer .axf (Keil default), fall back to .elf
    return str(axf if axf.exists() or not elf.exists() else elf)


# ── Build log parsing ────────────────────────────────────────────────────────

# ANSI escape stripper — newer armclang emits coloured output even when
# redirected via UV4 -o log, breaking line-pattern matching.
_ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

# Keil AC5/AC6 compiler error/warning format:
#   path\file.c(42): error: #123: message
#   path\file.c(42): warning: #456: message
# Capture the error/warning code so callers can classify (was previously dropped).
_LOG_PATTERN = re.compile(
    r"^(.+?)\((\d+)\):\s*(error|warning)\s*(?:#(\d+)\s*)?:\s*(.+)$",
    re.IGNORECASE,
)

# armlink error format (no source line number):
#   Error: L6218E: Undefined symbol foo (referred from bar.o)
#   Warning: L6915W: Library member ... not loaded
# armlink codes are L\d{4}[EWI]; allow generic [A-Z]\d{4}[A-Z] only.
_LINKER_PATTERN = re.compile(
    r"^(Error|Warning):\s+([A-Z]\d{3,5}[A-Z]):\s+(.+)$",
    re.IGNORECASE,
)


def parse_build_log(log_path: str) -> list[dict]:
    """Parse Keil build log into structured error/warning list."""
    errors: list[dict] = []
    try:
        text = Path(log_path).read_text(errors="ignore", encoding="utf-8")
    except FileNotFoundError:
        return errors

    for line in text.splitlines():
        line = _ANSI_RE.sub("", line.strip())
        m = _LOG_PATTERN.match(line)
        if m:
            entry = {
                "file":    m.group(1).strip(),
                "line":    int(m.group(2)),
                "type":    m.group(3).lower(),
                "message": m.group(5).strip(),
            }
            if m.group(4):
                entry["code"] = f"#{m.group(4)}"
            errors.append(entry)
            continue
        m = _LINKER_PATTERN.match(line)
        if m:
            errors.append({
                "file":    "linker",
                "line":    0,
                "type":    m.group(1).lower(),
                "code":    m.group(2),
                "message": m.group(3).strip(),
            })
    return errors


# ── Build ────────────────────────────────────────────────────────────────────

def build_project(
    uvprojx: str,
    target: str | None = None,
    clean: bool = False,
) -> dict:
    """
    Build a Keil project with UV4.exe.

    UV4 exit codes:
        0 = success
        1 = warnings only
        2 = errors
        3 = fatal error
    """
    if not config.UV4_PATH or not Path(config.UV4_PATH).exists():
        return {"success": False, "exit_code": -1,
                "errors": [{"type": "error", "message": "UV4.exe not found"}],
                "elf_path": None}

    log_file = Path(uvprojx).parent / "build.log"
    flag = "-rebuild" if clean else "-build"
    cmd = [
        config.UV4_PATH,
        flag,
        str(Path(uvprojx).resolve()),
        "-o", str(log_file),
        "-j0",   # use all CPU cores
    ]
    if target:
        cmd += ["-t", target]

    kwargs: dict = {"capture_output": True, "text": True, "timeout": 300}
    if sys.platform == "win32":
        import subprocess as sp
        kwargs["creationflags"] = sp.CREATE_NO_WINDOW

    try:
        result = subprocess.run(cmd, **kwargs)
    except subprocess.TimeoutExpired:
        return {"success": False, "exit_code": -1,
                "errors": [{"type": "error", "message": "Build timed out after 300 s"}],
                "elf_path": None}
    except Exception as e:
        return {"success": False, "exit_code": -1,
                "errors": [{"type": "error", "message": str(e)}],
                "elf_path": None}

    code = result.returncode
    success = code <= 1  # 0=OK, 1=warnings
    errs = parse_build_log(str(log_file))

    return {
        "exit_code": code,
        "success":   success,
        "errors":    errs,
        "elf_path":  get_elf_path(uvprojx, target) if success else None,
    }


# ── Flash ────────────────────────────────────────────────────────────────────

def flash_target(uvprojx: str, target: str | None = None) -> dict:
    """
    Flash the target using UV4.exe -flash.
    UV4 releases ST-Link after flash completes; GDB server can then connect.
    """
    if not config.UV4_PATH or not Path(config.UV4_PATH).exists():
        return {"success": False, "log": "", "error": "UV4.exe not found"}

    log_file = Path(uvprojx).parent / "flash.log"
    cmd = [
        config.UV4_PATH,
        "-flash",
        str(Path(uvprojx).resolve()),
        "-o", str(log_file),
    ]
    if target:
        cmd += ["-t", target]

    kwargs: dict = {"capture_output": True, "text": True, "timeout": 120}
    if sys.platform == "win32":
        import subprocess as sp
        kwargs["creationflags"] = sp.CREATE_NO_WINDOW

    try:
        result = subprocess.run(cmd, **kwargs)
    except subprocess.TimeoutExpired:
        return {"success": False, "log": "", "error": "Flash timed out after 120 s"}
    except Exception as e:
        return {"success": False, "log": "", "error": str(e)}

    log = ""
    if log_file.exists():
        log = log_file.read_text(errors="ignore")

    return {
        "success": result.returncode == 0,
        "log":     log,
        "note":    "ST-Link released — GDB server can now connect",
    }
