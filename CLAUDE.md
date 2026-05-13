# STM32 Embedded Development Skill

## Code Analysis — Graphify (Automatic)

**Kural: Proje dizini verildiğinde — kaç dosya olursa olsun, 1 bile olsa — graphify MUTLAKA çalıştırılır.**

Skill invoke edilince Claude şunu yapar:
1. `graphify-out/GRAPH_REPORT.md` var mı kontrol et
2. Yoksa → `Skill(skill="graphify", args="<proje-dizini>")` ile otomatik build et
3. Varsa → oku ve analize başla

```bash
# Sorgu (graph hazır olduktan sonra)
graphify query "who uses DMA buffer"
graphify path "FuncA" "FuncB"
```

Graph çıktısı: `graphify-out/GRAPH_REPORT.md` — God nodes, call chains, paylaşılan değişkenler.

### Post-Graph Follow-Up (zorunlu adım)

Graph raporu sunulduktan sonra:

1. **En ilginç soruyu seç** — Suggested Questions listesinden en fazla community sınırını geçen veya en sürpriz köprü node'u içeren soruyu belirle.

2. **Soruyu kullanıcıya sun ve onay iste:**
   > "En ilginç soru: **[soru]**. Takip etmemi ister misin?"

3. **Kullanıcı onay verirse — graphify query ile izle:**
   ```bash
   graphify query "[soru metni]"
   ```
   - BFS sonucundaki node'ları ve edge'leri kaynak kodla karşılaştır (Read tool ile doğrula)
   - Call chain'i adım adım açıkla: hangi node'dan hangi node'a, hangi dosyada, hangi satırda
   - Kritik bulguları önceki manuel analizle birleştir
   - Her yanıt sonunda doğal bir devam öner: "Bu X'e bağlanıyor — daha derine inmek ister misin?"

4. **Kullanıcı "hayır" derse** — graph'ı kapat, normal analize geç.

**Amaç:** Graph bir harita, Claude bir rehber. Analiz tek seferlik rapor değil, interaktif keşif seansı olmalı.

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
| `ref-armlink-scatter.md` | **armlink scatter file complete syntax**: load/exec region BNF, all attributes, input section selectors (+RO/+RW/+ZI/+XO/+FIRST/+LAST), .ANY, InRoot$$Sections, EMPTY stack/heap, ZEROPAD, XO regions, linker symbols, STM32H7/F4/G4/H730 scatter templates, common pitfalls |
| `ref-compiler-hardening.md` | volatile, barriers, DMA cache, ISR reorder |
| `ref-fault-handlers.md` | HardFault decode, BusFault, reset cause |
| `ref-memory-optimization.md` | Compiler flags, memory pools, linker script |
| `ref-j1939.md` | SAE J1939: AC state machine, CMDT TP, DM1/DM11, FDCAN bit timing |
| `ref-uds-iso14229.md` | ISO 14229 UDS: P2/P2*/S3 timing, Security Access, dual-bank OTA |
| `ref-obd2.md` | OBD-II (SAE J1979): all Modes 0x01-0x0A, Permanent DTC, readiness monitors, ECU template |
| `ref-wwh-obd.md` | WWH-OBD (ISO 27145): Euro VI, J1939 29-bit IDs, 0xF6xx DIDs, IUMPR, lamp severity |
| `ref-diagnostic-stack.md` | Multi-protocol DEM: unified DTC, CAN dispatch, NVM, freeze frame, OBD+J1939+UDS+WWH |
| `ref-dtc-mapping.md` | J1939 SPN/FMI ↔ OBD-II P-code ↔ WWH wire format, conversion functions, FMI table |
| `ref-ble-bluenrg355.md` | **BlueNRG-355 BLE**: PHY 1M/2M/Coded, MTU handshake iOS/Android, Extended Advertising, max throughput, connection drop recovery, DMA, flash optimizasyonu, Security/Bonding, OTA, RF coex |
| `ref-c-code-style.md` | **C kod stili**: BARR-C:2018, QuantumLeaps, ESCR, OpenTitan, NASA SEL-94-003, MaJerle — solid index, kaynak uzlaştırma tablosu, dinamik bellek politikası |
| `ref-trustzone.md` | **TrustZone-M (STM32H5/U5/L5)**: SAU, GTZC1/2, MPCBB, CMSE veneer, NSC API, NS pointer validation, MPU Cortex-M4/M7/M33, stack guard, non-cacheable DMA |
| `ref-power-optimization.md` | **Güç yönetimi**: Sleep/Stop/Standby/Shutdown, RTC/LPTIM wakeup, voltage scaling, domain power (H7), peripheral clock gating, run-mode tuning, güç ölçüm |
| `ref-secure-boot.md` | RDP seviyeleri, option byte programlama, PCROP, ECDSA firmware imzalama, PKA doğrulama, OTFDEC, anti-rollback OTP, üretim programlama akışı |
| `ref-adc-timer.md` | ADC: kalibrasyon, DMA circular, oversampling, injected channel, multi-ADC sync, sıcaklık sensörü. Timer: PWM, complementary+dead-time, encoder, input capture, HRTIM |
| `ref-boot-clock.md` | PLL hesabı (F4/H7/H5), flash wait state, CSS (HSE fail→HSI), backup domain (LSE/RTC), H7 dual-PLL, H5/U5 clock tree, frekans doğrulama |
| `ref-fdcan-multi.md` | FDCAN çoklu instance, 8Mbps bit timing, filter konfigürasyonu, bus-off recovery, Tx/Rx FIFO, timestamp |
| `ref-arm-asm.md` | ARM Cortex-M assembly: AAPCS calling convention, intrinsics, DSP/SIMD, Thumb-2, naked ISR, DWT cycle counter |
| `ref-modbus-rtu.md` | Modbus RTU slave/master, CRC-16, framing, exception codes, HAL UART entegrasyonu |
| `ref-usb-device.md` | USB device stack: CDC-ACM, HID, MSC, descriptor tanımı, endpoint konfigürasyonu |
| `ref-usb-host-filesystem.md` | USB host stack, FatFS entegrasyonu, MSC class, USBH state machine |
| `ref-ethernet-lwip.md` | STM32H5/H7 Ethernet, LwIP raw/netconn/socket API, DHCP, TCP server pattern |
| `ref-external-memory-fmc.md` | FMC: SDRAM, NOR flash, SRAM — init sequence, timing, address mapping |
| `ref-linker-script.md` | GCC linker script (.ld): MEMORY, SECTIONS, .data/.bss/.noinit, custom sections |
| `ref-iap-ota.md` | IAP bootloader, uygulama atlama, dual-bank swap, CRC doğrulama, DFU modu |

**DoIP Referansları (gelecekte kullanmak için):**
- Keil MDK Network middleware: `https://www.keil.com/pack/doc/mw/Network/html/index.html`
- STM32H5 LwIP örnekleri (NUCLEO-H563ZI): `https://github.com/STMicroelectronics/stm32h5-classic-coremw-apps/tree/main/Projects/NUCLEO-H563ZI/Applications/LwIP`

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
