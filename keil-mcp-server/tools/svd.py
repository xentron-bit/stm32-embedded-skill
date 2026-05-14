"""
SVD (System View Description) peripheral register decode.
Loads SVD files from Keil DFP packs and decodes peripheral register bit fields.
"""
import glob
import xml.etree.ElementTree as ET
from pathlib import Path

import state


# ── SVD file discovery ────────────────────────────────────────────────────────

def find_svd(mcu_name: str) -> str | None:
    """
    Locate an SVD file for the given MCU name.
    Searches Keil DFP packs (all installed STM32 families).
    Example mcu_name: 'STM32H730VB' or 'STM32H730'
    """
    # Normalize: strip package suffix like 'Tx', 'Ix' if user passed full part number
    search_name = mcu_name.upper().rstrip("TXHIVB")

    patterns = [
        rf"C:\Keil_v5\ARM\Pack\Keil\STM32*_DFP\*\SVD\*{search_name}*.svd",
        rf"C:\Keil_v5\ARM\Pack\Keil\STM32*_DFP\*\SVD\*{mcu_name}*.svd",
    ]
    for pat in patterns:
        matches = glob.glob(pat)
        if matches:
            return matches[0]
    return None


# ── SVD parsing ───────────────────────────────────────────────────────────────

def _parse_svd(svd_path: str) -> dict:
    """
    Parse SVD XML into a nested dict:
    {
      "PERIPHERAL_NAME": {
        "base_address": "0x40000000",
        "registers": {
          "REG_NAME": {
            "base_address": "0x40000000",   # periph base + offset
            "offset": 0,
            "description": "...",
            "fields": {
              "FIELD_NAME": {"bit_offset": 0, "bit_width": 1, "description": "..."}
            }
          }
        }
      }
    }
    """
    tree = ET.parse(svd_path)
    root = tree.getroot()
    peripherals: dict = {}

    for periph in root.findall(".//peripheral"):
        name_el = periph.find("name")
        base_el = periph.find("baseAddress")
        if name_el is None or base_el is None:
            continue

        p_name = name_el.text.strip().upper()
        try:
            p_base = int(base_el.text.strip(), 0)
        except (ValueError, TypeError):
            continue

        # Handle derivedFrom — copy registers from parent
        derived = periph.get("derivedFrom")
        if derived and derived.upper() in peripherals:
            src = peripherals[derived.upper()]
            registers = {
                r_name: {**r_info, "base_address": hex(p_base + r_info["offset"])}
                for r_name, r_info in src["registers"].items()
            }
        else:
            registers: dict = {}
            for reg in periph.findall(".//register"):
                r_name_el = reg.find("name")
                r_off_el  = reg.find("addressOffset")
                if r_name_el is None or r_off_el is None:
                    continue
                r_name = r_name_el.text.strip().upper()
                try:
                    r_off = int(r_off_el.text.strip(), 0)
                except (ValueError, TypeError):
                    continue

                desc_el = reg.find("description")
                desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

                fields: dict = {}
                for field in reg.findall(".//field"):
                    f_name_el = field.find("name")
                    f_off_el  = field.find("bitOffset")
                    f_wid_el  = field.find("bitWidth")
                    # Some SVDs use bitRange [MSB:LSB] instead
                    f_rng_el  = field.find("bitRange")
                    if f_name_el is None:
                        continue
                    f_name = f_name_el.text.strip()

                    if f_off_el is not None and f_wid_el is not None:
                        try:
                            f_off = int(f_off_el.text.strip(), 0)
                            f_wid = int(f_wid_el.text.strip(), 0)
                        except (ValueError, TypeError):
                            continue
                    elif f_rng_el is not None and f_rng_el.text:
                        try:
                            rng = f_rng_el.text.strip().strip("[]")
                            msb, lsb = rng.split(":")
                            f_off = int(lsb)
                            f_wid = int(msb) - int(lsb) + 1
                        except Exception:
                            continue
                    else:
                        continue

                    f_desc_el = field.find("description")
                    f_desc = f_desc_el.text.strip() if f_desc_el is not None and f_desc_el.text else ""
                    fields[f_name] = {
                        "bit_offset":   f_off,
                        "bit_width":    f_wid,
                        "description":  f_desc,
                    }

                registers[r_name] = {
                    "base_address": hex(p_base + r_off),
                    "offset":       r_off,
                    "description":  desc,
                    "fields":       fields,
                }

        peripherals[p_name] = {
            "base_address": hex(p_base),
            "registers":    registers,
        }

    return peripherals


def svd_load(mcu_name: str) -> dict:
    """Load and parse SVD for the given MCU; store in state.svd_data."""
    path = find_svd(mcu_name)
    if not path:
        return {"error": f"SVD not found for {mcu_name}. "
                         "Ensure Keil STM32 DFP pack is installed."}
    try:
        state.svd_data = _parse_svd(path)
        return {
            "ok": True,
            "svd_path":    path,
            "peripherals": list(state.svd_data.keys()),
        }
    except Exception as e:
        return {"error": f"SVD parse failed: {e}"}


# ── Bit field decode ──────────────────────────────────────────────────────────

def decode_bitfields(value: int, fields: dict) -> dict:
    """
    Decode a 32-bit register value into named bit fields.
    Returns {field_name: {value, hex, description}}.
    """
    result: dict = {}
    for fname, finfo in fields.items():
        off = finfo["bit_offset"]
        wid = finfo["bit_width"]
        mask = (1 << wid) - 1
        fval = (value >> off) & mask
        result[fname] = {
            "value":       fval,
            "hex":         hex(fval),
            "description": finfo.get("description", ""),
        }
    return result
