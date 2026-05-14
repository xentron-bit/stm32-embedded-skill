"""
Keil MCP Server — Otomatik Kurulum
===================================
Tek komutla çalıştır (Windows CMD / PowerShell):

    python install.py

Yaptıkları:
  1. pip install -r requirements.txt
  2. Araç yollarını tespit et (Keil, CubeMX, ST-LINK GDB server, arm-gdb)
  3. Claude Code CLI ~/.claude/settings.json içine mcpServers kaydını ekle
  4. Claude Desktop claude_desktop_config.json içine aynı kaydı ekle (varsa)
  5. Kurulum sonuç özetini yazdır
"""
import json
import os
import subprocess
import sys
from pathlib import Path


REPO = "https://github.com/xentron-bit/stm32-embedded-skill"
SERVER_SCRIPT = Path(__file__).parent.resolve() / "server.py"
PYTHON = sys.executable


# ── 1. Bağımlılıklar ─────────────────────────────────────────────────────────

def install_deps():
    req = Path(__file__).parent / "requirements.txt"
    print("\n[1/4] Bağımlılıklar kuruluyor...")
    result = subprocess.run(
        [PYTHON, "-m", "pip", "install", "-r", str(req), "--quiet"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  HATA: {result.stderr.strip()}")
        sys.exit(1)
    print("  OK — mcp, pygdbmi, pydantic kuruldu")


# ── 2. Araç tespiti ───────────────────────────────────────────────────────────

def detect_tools():
    print("\n[2/4] Araç yolları tespit ediliyor...")
    # config modülünü doğrudan import et (aynı dizinde)
    sys.path.insert(0, str(Path(__file__).parent))
    import config as cfg
    paths = cfg.reset_and_detect()
    found = {k: v for k, v in paths.items() if v}
    missing = [k for k, v in paths.items() if not v and k not in ("openocd", "cubeprog")]
    if missing:
        print(f"  UYARI: Şu araçlar bulunamadı: {missing}")
        print(f"  Keil veya STM32 araçlarını kurduktan sonra tekrar çalıştır: python install.py")
    return found


# ── 3. MCP kaydı ─────────────────────────────────────────────────────────────

MCP_ENTRY = {
    "command": PYTHON,
    "args": [str(SERVER_SCRIPT)],
    "env": {}
}


def _write_config(cfg_path: Path):
    if not cfg_path.exists():
        return False
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    data.setdefault("mcpServers", {})["keil-mcp"] = MCP_ENTRY
    cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return True


def register_mcp():
    print("\n[3/4] Claude'a MCP sunucusu kaydediliyor...")
    targets = [Path.home() / ".claude" / "settings.json"]  # Claude Code CLI
    if appdata := os.environ.get("APPDATA"):
        targets.append(Path(appdata) / "Claude" / "claude_desktop_config.json")

    registered = 0
    for t in targets:
        if _write_config(t):
            print(f"  OK  → {t}")
            registered += 1
        else:
            print(f"  skip (yok) → {t}")

    if registered == 0:
        print("  UYARI: Hiçbir Claude config dosyası bulunamadı.")
        print("  Claude Code CLI kuruluysa ~/.claude/settings.json oluşturulmalı.")


# ── 4. Özet ───────────────────────────────────────────────────────────────────

def print_summary(found: dict):
    print("\n[4/4] Kurulum tamamlandı")
    print("─" * 50)
    print(f"  Python   : {PYTHON}")
    print(f"  Sunucu   : {SERVER_SCRIPT}")
    print(f"  UV4      : {found.get('uv4', '(bulunamadı)')}")
    print(f"  CubeMX   : {found.get('cubemx', '(bulunamadı)')}")
    print(f"  ST-LINK  : {found.get('stlink_gdb', '(bulunamadı)')}")
    print(f"  arm-gdb  : {found.get('gdb', '(bulunamadı)')}")
    print("─" * 50)
    print("\nSonraki adım: Claude'u yeniden başlat.")
    print("Claude'da test: 'list_probes' komutu ile bağlı ST-Link'leri listele.")
    print(f"\nRepo: {REPO}")


# ── Ana ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  Keil MCP Server — Kurulum")
    print("=" * 50)
    install_deps()
    found = detect_tools()
    register_mcp()
    print_summary(found)
