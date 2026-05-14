# Keil MCP Server

Claude Code CLI'yi gerçek bir STM32 embedded geliştirme mühendisine dönüştürür.

```
IOC modifiye → CubeMX generate → UV4 build → UV4 flash → ST-Link GDB debug
     ↑                                                           │
     └───────── fix → loop ←─── memory/register/peripheral ─────┘
```

## Gereksinimler (Windows)

- Keil MDK 5 (UV4.exe)
- STM32CubeMX 6.x
- STM32CubeIDE veya STM32CubeProgrammer (ST-LINK GDB server + arm-none-eabi-gdb için)
- Python 3.11+
- Claude Code CLI

## Kurulum — Tek Komut

```cmd
git clone https://github.com/xentron-bit/stm32-embedded-skill
cd stm32-embedded-skill\keil-mcp-server
python install.py
```

`install.py` şunları yapar:
1. `pip install -r requirements.txt` (mcp, pygdbmi, pydantic)
2. Tüm araç yollarını otomatik tespit eder (Keil registry + glob)
3. Claude Code CLI ve Claude Desktop config dosyalarına `keil-mcp` girişini ekler

Claude'u yeniden başlat, hazır.

## 26 Araç

| Kategori | Araçlar |
|----------|---------|
| **Config** | `config_detect`, `config_list_probes` |
| **IOC/CubeMX** | `ioc_read`, `ioc_set_param`, `ioc_list_peripherals`, `ioc_get_mcu`, `cubemx_generate` |
| **Build/Flash** | `build_get_elf_path`, `build_project`, `flash_target` |
| **Debug** | `debug_connect`, `debug_disconnect`, `debug_control`, `debug_breakpoint_toggle`, `debug_breakpoint_list`, `debug_breakpoint_clear_all`, `debug_register_rw`, `debug_memory_rw`, `debug_evaluate`, `debug_backtrace`, `debug_locals`, `debug_watch_add`, `peripheral_read` |
| **SVD** | `svd_load` |
| **JTAG** | `jtag_get_chain`, `jtag_idcode`, `jtag_bsdl_find`, `jtag_boundary_scan` |

## Örnek — Tam Otomasyon

```
"USART2 çalışmıyor, baud rate'i kontrol et ve düzelt"

→ ioc_read(project.ioc)           # USART2.BaudRate=115200
→ ioc_set_param(...)               # BaudRate=921600
→ cubemx_generate(project.ioc)    # kod üret
→ build_project(project.uvprojx)  # derle
→ flash_target(project.uvprojx)   # flash
→ debug_connect(project.elf)       # bağlan
→ peripheral_read("USART2","BRR") # BRR register = 921600 doğrulandı
→ debug_disconnect()               # serbest bırak
```

## Dosya Yapısı

```
keil-mcp-server/
├── install.py        ← Tek komut kurulum
├── server.py         ← MCP giriş noktası (26 araç)
├── config.py         ← Araç yolu tespiti + persist
├── state.py          ← Global debug session state
├── setup.py          ← Manuel MCP kayıt
├── requirements.txt
└── tools/
    ├── cubemx.py     ← IOC read/modify + headless generate
    ├── build.py      ← UV4 build/flash + ELF discovery
    ├── debug.py      ← GDB server + tüm debug araçları
    ├── svd.py        ← Keil DFP SVD → bit field decode
    └── jtag.py       ← JTAG chain + boundary scan
```

## Notlar

- ST-Link aynı anda yalnızca bir uygulama tarafından kullanılabilir. Keil debug oturumu açıkken `debug_connect` başarısız olur — önce Keil debug'ı kapat.
- CubeMX headless generate için firmware paketi önceden indirilmiş olmalı (CubeMX GUI'den bir kez aç, paketi indir).
- `peripheral_read` için `debug_connect`'e `mcu_name` parametresi geç veya ayrıca `svd_load` çağır.
