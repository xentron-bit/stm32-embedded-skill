"""
Keil MDK + STM32 Full-Loop MCP Server.

Tools exposed to Claude:
  — config_detect        Re-detect tool paths
  — config_list_probes   List connected ST-LINK probes

  — ioc_read             Read IOC file as key-value dict
  — ioc_set_param        Set a parameter in IOC file
  — ioc_list_peripherals List active peripherals in IOC
  — ioc_get_mcu          Get MCU name from IOC
  — cubemx_generate      Generate project from IOC (headless CubeMX)

  — build_get_elf_path   Parse .uvprojx to find ELF/AXF path
  — build_project        Build with UV4.exe
  — flash_target         Flash with UV4.exe

  — list_probes          List connected ST-LINK probes (via CubeProgrammer)
  — debug_connect        Start GDB server + GDB, load ELF, halt target
  — debug_disconnect     Clean disconnect, release ST-Link
  — debug_control        run / halt / step / step_over / step_out / reset_halt
  — debug_breakpoint_toggle     Smart BP toggle (add/enable/disable)
  — debug_breakpoint_list       List all breakpoints
  — debug_breakpoint_clear_all  Remove all breakpoints
  — debug_register_rw    Read or write CPU core register
  — debug_memory_rw      Read or write memory (hex/dec/binary, 1/2/4/8 bytes)
  — debug_evaluate       Evaluate C expression
  — debug_backtrace      Print call stack
  — debug_locals         List local variables in current frame
  — debug_watch_add      Add hardware watchpoint (read/write/access)
  — peripheral_read      Read peripheral registers decoded via SVD

  — svd_load             Load SVD file for MCU (enables peripheral_read decode)
  — jtag_get_chain       Scan JTAG chain
  — jtag_idcode          Read JTAG IDCODE
  — jtag_bsdl_find       Locate BSDL file for MCU
  — jtag_boundary_scan   Run IDCODE or SVF boundary scan
"""
import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

import config
from tools import build, cubemx, debug, jtag, svd

# ── Initialize tool paths at startup ─────────────────────────────────────────
config.init()

# ── MCP Server ────────────────────────────────────────────────────────────────
app = Server("keil-mcp")


# ── Tool definitions ──────────────────────────────────────────────────────────

def _str(name: str, desc: str, required: bool = True) -> dict:
    return {"type": "object", "properties": {name: {"type": "string", "description": desc}},
            "required": [name] if required else []}


TOOLS: list[Tool] = [

    # ── Config ────────────────────────────────────────────────────────────────
    Tool(
        name="config_detect",
        description="Force re-detection of Keil, CubeMX, ST-LINK GDB server and arm-gdb paths. "
                    "Use when tools were installed after the server started.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="config_list_probes",
        description="List connected ST-LINK probes via STM32CubeProgrammer CLI.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),

    # ── IOC / CubeMX ──────────────────────────────────────────────────────────
    Tool(
        name="ioc_read",
        description="Read a .ioc file and return all parameters as a JSON object.",
        inputSchema={"type": "object",
                     "properties": {"ioc_path": {"type": "string", "description": "Absolute path to .ioc file"}},
                     "required": ["ioc_path"]},
    ),
    Tool(
        name="ioc_set_param",
        description="Set a key=value parameter in a .ioc file. Adds key if not present.",
        inputSchema={"type": "object",
                     "properties": {
                         "ioc_path": {"type": "string"},
                         "key":      {"type": "string", "description": "Parameter name, e.g. 'USART2.BaudRate'"},
                         "value":    {"type": "string", "description": "New value"},
                     },
                     "required": ["ioc_path", "key", "value"]},
    ),
    Tool(
        name="ioc_list_peripherals",
        description="List all active peripheral names found in a .ioc file.",
        inputSchema={"type": "object",
                     "properties": {"ioc_path": {"type": "string"}},
                     "required": ["ioc_path"]},
    ),
    Tool(
        name="ioc_get_mcu",
        description="Return the MCU part name (e.g. STM32H730VBTx) from a .ioc file.",
        inputSchema={"type": "object",
                     "properties": {"ioc_path": {"type": "string"}},
                     "required": ["ioc_path"]},
    ),
    Tool(
        name="cubemx_generate",
        description="Generate Keil MDK project code from .ioc file using STM32CubeMX in headless mode.",
        inputSchema={"type": "object",
                     "properties": {"ioc_path": {"type": "string"}},
                     "required": ["ioc_path"]},
    ),

    # ── Build / Flash ─────────────────────────────────────────────────────────
    Tool(
        name="build_get_elf_path",
        description="Parse a .uvprojx file to find the expected ELF/AXF output path.",
        inputSchema={"type": "object",
                     "properties": {
                         "uvprojx": {"type": "string", "description": "Path to .uvprojx file"},
                         "target":  {"type": "string", "description": "Optional target name"},
                     },
                     "required": ["uvprojx"]},
    ),
    Tool(
        name="build_project",
        description="Build a Keil MDK project with UV4.exe. Returns exit code, errors, and ELF path.",
        inputSchema={"type": "object",
                     "properties": {
                         "uvprojx": {"type": "string"},
                         "target":  {"type": "string"},
                         "clean":   {"type": "boolean", "description": "Rebuild from scratch if true"},
                     },
                     "required": ["uvprojx"]},
    ),
    Tool(
        name="flash_target",
        description="Flash firmware to target using UV4.exe -flash. ST-Link is released after completion.",
        inputSchema={"type": "object",
                     "properties": {
                         "uvprojx": {"type": "string"},
                         "target":  {"type": "string"},
                     },
                     "required": ["uvprojx"]},
    ),

    # ── Debug ─────────────────────────────────────────────────────────────────
    Tool(
        name="list_probes",
        description="List connected ST-LINK probe serials (same as config_list_probes).",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="debug_connect",
        description="Start ST-LINK GDB server, connect GDB, load ELF, and halt target. "
                    "Optionally loads SVD for peripheral register decode.",
        inputSchema={"type": "object",
                     "properties": {
                         "elf_path":         {"type": "string"},
                         "port":             {"type": "integer", "default": 61234},
                         "swd":              {"type": "boolean",  "default": True,
                                              "description": "Use SWD (true) or JTAG (false)"},
                         "probe_serial":     {"type": "string",  "description": "ST-LINK serial (multi-probe)"},
                         "reset_on_connect": {"type": "boolean", "default": True},
                         "mcu_name":         {"type": "string",
                                              "description": "MCU name for SVD load, e.g. STM32H730"},
                     },
                     "required": ["elf_path"]},
    ),
    Tool(
        name="debug_disconnect",
        description="Disconnect GDB and stop GDB server. Releases ST-Link for Keil or other tools.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="debug_control",
        description="Control target execution.",
        inputSchema={"type": "object",
                     "properties": {
                         "action": {"type": "string",
                                    "enum": ["run", "halt", "step", "step_over", "step_out", "reset_halt"],
                                    "description": "run=continue, halt=break, step=step-in, "
                                                   "step_over=next, step_out=finish, reset_halt=reset+halt"},
                     },
                     "required": ["action"]},
    ),
    Tool(
        name="debug_breakpoint_toggle",
        description="Toggle breakpoint at location. Creates if absent, enables/disables if present.",
        inputSchema={"type": "object",
                     "properties": {
                         "location":  {"type": "string", "description": "file.c:line or function name"},
                         "condition": {"type": "string", "description": "Optional conditional expression"},
                     },
                     "required": ["location"]},
    ),
    Tool(
        name="debug_breakpoint_list",
        description="List all breakpoints and watchpoints.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="debug_breakpoint_clear_all",
        description="Remove all breakpoints and watchpoints.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="debug_register_rw",
        description="Read or write a CPU core register (r0-r15, pc, sp, lr, xpsr, etc.).",
        inputSchema={"type": "object",
                     "properties": {
                         "register": {"type": "string"},
                         "value":    {"type": "string", "description": "If omitted, reads the register"},
                     },
                     "required": ["register"]},
    ),
    Tool(
        name="debug_memory_rw",
        description="Read or write target memory.",
        inputSchema={"type": "object",
                     "properties": {
                         "address": {"type": "string", "description": "Hex address, e.g. 0x20000000"},
                         "length":  {"type": "integer", "default": 16,
                                     "description": "Number of units to read (ignored on write)"},
                         "value":   {"type": "string", "description": "If omitted, reads memory"},
                         "fmt":     {"type": "string", "enum": ["x","d","u","t","f","a","c","s"],
                                     "default": "x"},
                         "unit":    {"type": "string", "enum": ["b","h","w","g"],
                                     "default": "w",
                                     "description": "b=1B h=2B w=4B g=8B"},
                     },
                     "required": ["address"]},
    ),
    Tool(
        name="debug_evaluate",
        description="Evaluate a C expression in the current debug scope.",
        inputSchema={"type": "object",
                     "properties": {"expr": {"type": "string"}},
                     "required": ["expr"]},
    ),
    Tool(
        name="debug_backtrace",
        description="Print call stack.",
        inputSchema={"type": "object",
                     "properties": {"frames": {"type": "integer", "default": 20,
                                               "description": "Max frames (0=all)"}},
                     "required": []},
    ),
    Tool(
        name="debug_locals",
        description="List local variables and their values in the current stack frame.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="debug_watch_add",
        description="Add a hardware watchpoint. Target halts when expression is accessed.",
        inputSchema={"type": "object",
                     "properties": {
                         "expr":       {"type": "string"},
                         "watch_type": {"type": "string", "enum": ["read","write","access"],
                                        "default": "write"},
                     },
                     "required": ["expr"]},
    ),
    Tool(
        name="peripheral_read",
        description="Read peripheral registers decoded with SVD bit field definitions. "
                    "Requires SVD to be loaded (mcu_name in debug_connect or svd_load).",
        inputSchema={"type": "object",
                     "properties": {
                         "peripheral": {"type": "string", "description": "e.g. USART2, RCC, GPIOA"},
                         "register":   {"type": "string", "description": "Specific register; omit for all"},
                     },
                     "required": ["peripheral"]},
    ),

    # ── SVD ───────────────────────────────────────────────────────────────────
    Tool(
        name="svd_load",
        description="Load SVD file for an MCU to enable peripheral register decode.",
        inputSchema={"type": "object",
                     "properties": {"mcu_name": {"type": "string",
                                                  "description": "MCU name, e.g. STM32H730"}},
                     "required": ["mcu_name"]},
    ),

    # ── JTAG ──────────────────────────────────────────────────────────────────
    Tool(
        name="jtag_get_chain",
        description="Scan JTAG chain and return device list (requires connected debug session).",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="jtag_idcode",
        description="Read JTAG IDCODE register (32-bit device identification).",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="jtag_bsdl_find",
        description="Find BSDL file for an MCU in Keil DFP packs or local cache.",
        inputSchema={"type": "object",
                     "properties": {"mcu_name": {"type": "string"}},
                     "required": ["mcu_name"]},
    ),
    Tool(
        name="jtag_boundary_scan",
        description="Perform boundary scan: read IDCODE or play back an SVF test file.",
        inputSchema={"type": "object",
                     "properties": {
                         "action":    {"type": "string", "enum": ["idcode", "run_svf"]},
                         "svf_path":  {"type": "string", "description": "Path to .svf file (run_svf only)"},
                         "bsdl_path": {"type": "string", "description": "Informational only"},
                     },
                     "required": ["action"]},
    ),
]


# ── Handler ───────────────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    def _j(obj) -> list[TextContent]:
        return [TextContent(type="text", text=json.dumps(obj, indent=2))]

    # Config
    if name == "config_detect":
        cfg = config.reset_and_detect()
        return _j(cfg)
    if name in ("config_list_probes", "list_probes"):
        return await debug.list_probes()

    # IOC / CubeMX
    if name == "ioc_read":
        return _j(cubemx.ioc_read(arguments["ioc_path"]))
    if name == "ioc_set_param":
        return [TextContent(type="text",
                            text=cubemx.ioc_set_param(
                                arguments["ioc_path"],
                                arguments["key"],
                                arguments["value"],
                            ))]
    if name == "ioc_list_peripherals":
        return _j(cubemx.ioc_list_peripherals(arguments["ioc_path"]))
    if name == "ioc_get_mcu":
        return [TextContent(type="text", text=cubemx.ioc_get_mcu(arguments["ioc_path"]))]
    if name == "cubemx_generate":
        return _j(cubemx.cubemx_generate(arguments["ioc_path"]))

    # Build / Flash
    if name == "build_get_elf_path":
        path = build.get_elf_path(arguments["uvprojx"], arguments.get("target"))
        return [TextContent(type="text", text=path)]
    if name == "build_project":
        return _j(build.build_project(
            arguments["uvprojx"],
            arguments.get("target"),
            arguments.get("clean", False),
        ))
    if name == "flash_target":
        return _j(build.flash_target(arguments["uvprojx"], arguments.get("target")))

    # Debug
    if name == "debug_connect":
        return await debug.debug_connect(
            arguments["elf_path"],
            port=arguments.get("port", 61234),
            swd=arguments.get("swd", True),
            probe_serial=arguments.get("probe_serial"),
            reset_on_connect=arguments.get("reset_on_connect", True),
            mcu_name=arguments.get("mcu_name"),
        )
    if name == "debug_disconnect":
        return await debug.debug_disconnect()
    if name == "debug_control":
        return await debug.debug_control(arguments["action"])
    if name == "debug_breakpoint_toggle":
        return await debug.debug_breakpoint_toggle(
            arguments["location"], arguments.get("condition")
        )
    if name == "debug_breakpoint_list":
        return await debug.debug_breakpoint_list()
    if name == "debug_breakpoint_clear_all":
        return await debug.debug_breakpoint_clear_all()
    if name == "debug_register_rw":
        return await debug.debug_register_rw(arguments["register"], arguments.get("value"))
    if name == "debug_memory_rw":
        return await debug.debug_memory_rw(
            arguments["address"],
            length=arguments.get("length", 16),
            value=arguments.get("value"),
            fmt=arguments.get("fmt", "x"),
            unit=arguments.get("unit", "w"),
        )
    if name == "debug_evaluate":
        return await debug.debug_evaluate(arguments["expr"])
    if name == "debug_backtrace":
        return await debug.debug_backtrace(arguments.get("frames", 20))
    if name == "debug_locals":
        return await debug.debug_locals()
    if name == "debug_watch_add":
        return await debug.debug_watch_add(
            arguments["expr"], arguments.get("watch_type", "write")
        )
    if name == "peripheral_read":
        return await debug.peripheral_read(
            arguments["peripheral"], arguments.get("register")
        )

    # SVD
    if name == "svd_load":
        return [TextContent(type="text",
                            text=json.dumps(svd.svd_load(arguments["mcu_name"]), indent=2))]

    # JTAG
    if name == "jtag_get_chain":
        return await jtag.jtag_get_chain()
    if name == "jtag_idcode":
        return await jtag.jtag_idcode()
    if name == "jtag_bsdl_find":
        return await jtag.jtag_bsdl_find(arguments["mcu_name"])
    if name == "jtag_boundary_scan":
        return await jtag.jtag_boundary_scan(
            arguments["action"],
            svf_path=arguments.get("svf_path"),
            bsdl_path=arguments.get("bsdl_path"),
        )

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
