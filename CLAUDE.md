# STM32 Embedded Development Skill

## Code Analysis — Graphify (Automatic)

**Graph yoksa SKILL otomatik çalıştırır — manuel `/graphify .` gerekmez.**

Skill invoke edilince Claude şunu yapar:
1. `graphify-out/GRAPH_REPORT.md` var mı kontrol et
2. Yoksa → `Skill(skill="graphify", args="<proje-dizini>")` ile otomatik build et
3. Varsa → oku ve analize başla

```bash
# Sorgu (graph hazır olduktan sonra)
graphify query "who uses DMA buffer" --graph graphify-out/graph.json
graphify path "FuncA" "FuncB" --graph graphify-out/graph.json
```

Graph çıktısı: `graphify-out/GRAPH_REPORT.md` — God nodes, call chains, paylaşılan değişkenler.

## Skill Activation

```
/stm32-embedded-dev
```

Activates the 5-phase workflow: Analyze Constraints → Design Architecture → Implement Drivers → Optimize Resources → Test & Verify.

## Reference Files

| File | Topic |
|------|-------|
| `ref-stm32-errata.md` | **Real-world errata, HAL bugs, GPIO speed limits, USB 48MHz, DMA DTCM, I2C hang** |
| `ref-qspi-octospi-highspeed.md` | QSPI/OCTOSPI high-speed issues, sample shift, DLYB, dummy cycles |
| `ref-communication-protocols.md` | I2C, SPI DMA, UART ring buffer, FDCAN |
| `ref-rtos-patterns.md` | FreeRTOS & RTX5 task, ISR, mutex, event patterns |
| `ref-keil-armclang.md` | Keil MDK / AC6: LTO traps, scatter, RTX5 pitfalls |
| `ref-compiler-hardening.md` | volatile, barriers, DMA cache, ISR reorder |
| `ref-fault-handlers.md` | HardFault decode, BusFault, reset cause |
| `ref-memory-optimization.md` | Compiler flags, memory pools, linker script |
| `ref-mpu-trustzone.md` | MPU stack guard, non-cacheable DMA, TrustZone |
| `ref-j1939.md` | SAE J1939: AC state machine, CMDT TP, DM1/DM11, FDCAN bit timing |
| `ref-uds-iso14229.md` | ISO 14229 UDS: P2/P2*/S3 timing, Security Access, dual-bank OTA |
| `ref-obd2.md` | OBD-II (SAE J1979): all Modes 0x01-0x0A, Permanent DTC, readiness monitors, ECU template |
| `ref-wwh-obd.md` | WWH-OBD (ISO 27145): Euro VI, J1939 29-bit IDs, 0xF6xx DIDs, IUMPR, lamp severity |
| `ref-diagnostic-stack.md` | Multi-protocol DEM: unified DTC, CAN dispatch, NVM, freeze frame, OBD+J1939+UDS+WWH |
| `ref-dtc-mapping.md` | J1939 SPN/FMI ↔ OBD-II P-code ↔ WWH wire format, conversion functions, FMI table |

## Errata Kontrol — Proje Analizi Workflow'u

**Kural: İşlemci tespit edilince, kod incelemesinden ÖNCE errata kontrol et.**

```
1. stm32-families.md → MCU ailesini belirle
2. ST errata sheet numarasını bul:
     STM32H730/H750 → ES0480
     STM32H7B0/H7A3 → ES0392
     STM32F7        → ES0334
     STM32F4        → ES0182
     STM32G4        → ES0430
     STM32L4        → ES0392
3. ref-stm32-errata.md ile bilinen sorunları cross-check et
4. Kritik errata varsa code review'e dahil et
5. Şüpheli davranış varsa ST errata PDF'ini web'den getir ve doğrula
```

Kod yanlış görünse bile errata düzeyinde bir hardware/driver sorunu olabilir.
Her review'da sadece kodun mantığı değil, donanım kısıtlamalarını da değerlendir.
