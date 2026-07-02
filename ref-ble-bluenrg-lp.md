# BLE — BlueNRG-LP / LPS / 355 SoC + Protocol Reference

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Device architecture, memory map, power modes, errata workarounds, security-advisory content, OTA architecture, radio-timer model** here is authoritative — that is why this file exists. Sourced from ST datasheets, reference manuals, errata and application notes (catalog below).
> - **Inline HAL/LL/ACI code snippets** are illustrative. Verified against the **STSW-BNRGLP-DK v1.5.0** source (BLE Stack Library v3.2a). The API can drift between stack versions; for the canonical symbol at your SDK release confirm in your local DK tree or `gh search code <SymbolName> --owner=STMicroelectronics` — see §XI and [ref-st-github-map.md](ref-st-github-map.md).
> - **API-NAMING TRAP (read §V):** two independent things, don't conflate them. **(a)** ACI generation: old **BlueNRG-1/2/MS** ACI (`aci_gatt_add_serv`, `aci_gatt_update_char_value`, `aci_gatt_init`) vs the **BlueNRG-LP** ACI (`aci_gatt_srv_*` / `aci_gatt_clt_*`) — the DK v3.x already uses the new names. **(b)** Usage model: **standalone-SoC** stack tick `BLE_STACK_Tick()` vs **network-coprocessor host** tick `BTLE_StackTick()` (SimpleBlueNRG-LP_HCI).
> - **Bu dosya artık HER İKİ katmanı kapsar** (eski `ref-ble-bluenrg355.md` 2026-06-16'da buraya birleştirildi): **Part A (§I–§XII)** = SoC/silikon katmanı (authoritative); **Part B (§XIII–§XXIV)** = BLE protokol, throughput & app katmanı (PHY, MTU, conn params, iOS/Android, recovery, security-manager, GATT, DMA, RF coex). Part B inline kodu **illüstratiftir** ve eski **BlueNRG-1/2/MS ACI** isimlerini kullanır (`aci_gatt_add_char`, `aci_gatt_update_char_value_ext`, `aci_gatt_attribute_modified_event`); BlueNRG-LP/LPS/355'te bunları **`aci_gatt_srv_*` / `aci_gatt_clt_*`** nesline eşle (§V). Throughput/PHY/MTU/zamanlama kavramları silikon-doğrudur.
> - **For generic bootloader / IAP / OTA theory** the canonical checklist is in [ref-bootloader.md](ref-bootloader.md); the BlueNRG-specific OTA flow is §VIII here.

Platform: BlueNRG-LP / BlueNRG-LPS / **BlueNRG-355** — standalone programmable BLE SoC (Arm Cortex-M0+, up to 64 MHz). BlueNRG-355/-345 = LP order-code'ları (aynı silikon, bkz. §I).
Radio: BlueNRG-LP = BLE 5.2 · BlueNRG-LPS = BLE 5.3 · +8 dBm TX · −97 dBm @1M / −104 dBm @125k · AoA/AoD
SDK: **STSW-BNRGLP-DK v1.5.0** (01-Dec-2023, son sürüm; BLE Stack Library **v3.2a**)
ACI = Application Command Interface (Bluetooth HCI + ST vendor extensions)
App-layer middleware (Part B): **x-cube-blemgr** (BLE Manager) — stack uzerinde opsiyonel katman.

## Kaynak Dokümanlar (source catalog)

| Doc | Tür | Konu |
|-----|-----|------|
| DS13282 | Datasheet | BlueNRG-LP electrical/feature spec |
| DS13819 (Rev 4) | Datasheet | BlueNRG-LPS electrical/feature spec |
| RM0491 | Reference manual | BlueNRG-LPS (Cortex-M0+ system, RCC, flash, power, peripherals) |
| RM0498 | Reference manual | BlueNRG-LPS **radio IP** (radio controller, packet RAM, timers) |
| PM0269 | Programming manual | Bluetooth LE stack v3.x programming guidelines (ACI/GAP/GATT/SM) |
| ES0576 (Rev 4) | **Errata** | BlueNRG-LPS device limitations — see §X |
| SA0041 (Rev 2) | **Security advisory** | Secure-bootloader image-verification issue — see §IX |
| AN5463 | App note | OTA (over-the-air) firmware upgrade — see §VIII |
| AN5466 | App note | Power-save modes (DeepStop/Shutdown) — see §VII |
| AN5469 | App note | Radio timer module (virtual timers, STU) — see §VI |
| AN5471 | App note | UART system bootloader protocol — see §IX |
| AN5503 | App note | Device bring-up guidelines (clock, first boot) — see §IV |
| AN5526 / AN5574 | App note | PCB design / external RF front-end |
| AN5528 / AN5569 / AN5570 / AN5572 | App note | RF range estimation; ETSI EN 300 328 / FCC part 15 / ARIB STD-T66 |
| AN6140 | App note | Secure bootloader / signed image (remediation for SA0041) |
| UM2735 / UM2058 / UM2726 | User manual | DK boards / BlueNRG GUI / 2.4 GHz proprietary radio driver |
| TN1347 | Tech note | CMSIS-DAP probe usage |

## INDEX

### Part A — SoC / Silikon Katmanı (§I–§XII, authoritative)

| Bölüm | Konu |
|-------|------|
| [I. Aile ve Part Numarası](#i-aile-ve-part-numarası) | LP vs LPS vs 355, order-code decode, silikon cut'ları |
| [II. Bellek Haritası ve Boot](#ii-bellek-haritası-ve-boot) | Flash @ 0x10040000, ROM bootloader, OTP, NVM, REMAP |
| [III. Donanım Özeti](#iii-donanım-özeti) | Çekirdek, radyo, çevre birimleri, LP vs LPS farkları |
| [IV. Saat Ağacı ve Bring-up](#iv-saat-ağacı-ve-bring-up) | HSE 32M, RC64MPLL, LSE/LSI, SystemInit, HSE trim |
| [V. BLE Stack ve ACI API](#v-ble-stack-ve-aci-api) | SoC vs coprocessor, ACI nesil farkı, BLE_STACK_Init, modüler config |
| [VI. Radio / Virtual Timer](#vi-radio--virtual-timer) | STU, kalibrasyon, VTIMER / RADIO_TIMER API |
| [VII. Güç Modları](#vii-güç-modları) | DeepStop/Shutdown, power-save seviyeleri, akımlar, RAM retention |
| [VIII. OTA Firmware Upgrade](#viii-ota-firmware-upgrade) | Servis UUID'leri, paket yapısı, reset-manager vs service-manager |
| [IX. Secure Bootloader ve Güvenlik](#ix-secure-bootloader-ve-güvenlik) | UART bootloader, SA0041, imzalı imaj |
| [X. Errata (ES0576)](#x-errata-es0576) | RTC/DEEPSTOP, GPIO-RF, CTE RX-lock + workaround'lar |
| [XI. SDK, GitHub ve Toolchain](#xi-sdk-github-ve-toolchain) | Repolar, gh reçeteleri, IDE'ler, flash araçları |
| [XII. Olmaz sa Olmaz](#xii-olmaz-sa-olmaz) | SoC bring-up + BLE + güç + OTA kontrol listesi |

### Part B — BLE Protokol, Throughput & Uygulama Katmanı (§XIII–§XXIV)

> Eski `ref-ble-bluenrg355.md` (2026-06-16'da buraya birleştirildi). Inline ACI isimleri eski nesil — §V ile `aci_gatt_srv_*`/`aci_gatt_clt_*`'ye eşle. "512KB flash" geçen yerler YANLIŞ (LP/355 = 256KB).

| Bölüm | Konu |
|-------|------|
| [XIII. PHY Seçimi](#xiii-phy-seçimi) | LE 1M / 2M / Coded PHY, ACI komutları |
| [XIV. MTU Negotiation](#xiv-mtu-negotiation) | iOS/Android max MTU, handshake, ATT payload |
| [XV. Extended Advertising](#xv-extended-advertising) | AE PDU, multi-handle, scan response |
| [XVI. Connection Parameters](#xvi-connection-parameters) | Interval, latency, timeout — throughput |
| [XVII. Max Throughput](#xvii-max-throughput) | Hız formülü, benchmark, bottleneck |
| [XVIII. Connection Drop Recovery](#xviii-connection-drop-recovery) | Supervision timeout, reconnect FSM |
| [XIX. iOS Kısıtlamaları](#xix-ios-kısıtlamaları) | Apple BLE kısıtları, Core Bluetooth |
| [XX. Android Kısıtlamaları](#xx-android-kısıtlamaları) | Android BLE farkları, MTU override |
| [XXI. Flash Optimizasyonu](#xxi-flash-optimizasyonu) | App code size (stack config: §V.2) |
| [XXII. Debug ve Ölçüm](#xxii-debug-ve-ölçüm) | Throughput ölçüm, ACI event log |
| [XXIII. DMA Kullanımı](#xxiii-dma-kullanımı) | UART/SPI DMA, IDLE+circular, stack DMA uyarıları |
| [XXIV. Olmaz sa Olmaz (Protokol/App)](#xxiv-olmaz-sa-olmaz-protokolapp) | Pairing/bonding, GATT, allowlist, güç, OTA app, stack init, ATT errors, RF coex |

---

## I. Aile ve Part Numarası

### I.1 Ailenin yeri

BlueNRG-LP ve BlueNRG-LPS, BlueNRG ailesinin **2. nesil "tek-yonga" (standalone, programlanabilir)** BLE SoC'leridir. Önceki nesil BlueNRG-1/-2 (Cortex-M0) yerine **Cortex-M0+ @ 64 MHz** kullanırlar. Bunlar bir host MCU'ya bağlanan harici BLE modülü (BlueNRG-M0/MS) değildir — uygulama kodu doğrudan SoC üzerinde çalışır.

| Cihaz | Çekirdek | BLE | Flash | RAM | Konumu |
|-------|----------|-----|-------|-----|--------|
| BlueNRG-LP  | Cortex-M0+ 64 MHz | 5.2 | 256 KB | 64 KB / 32 KB | Üst segment, zengin çevre birimi |
| BlueNRG-LPS | Cortex-M0+ 64 MHz | 5.3 | 192 KB | 24 KB (+4 KB PKA) | Küçük/ucuz, direction-finding odaklı |

> **BlueNRG-355 = BlueNRG-LP (AYNI SİLİKON).** BlueNRG-355 (ve -345), BlueNRG-LP ailesinin sipariş kodlarıdır — ayrı bir çip değil; bu dosyadaki **tüm** silikon/bellek/güç/errata/secure-boot içeriği BlueNRG-355'e birebir uygulanır. "BlueNRG-355" adı genelde *network coprocessor* (harici host'a HCI/ACI veren; DK'da `Projects/External_Micro/*_NWK`) konfigürasyonu için kullanılır. Throughput/PHY/MTU/protokol detayları için **Part B (§XIII–§XXIV)**; SoC katmanı (Part A) LP+LPS+355'i kapsar.

### I.2 Order-code çözümü — BlueNRG-LPS (DS13819 Fig.22)

Şablon: **`BlueNRG-332xy`**

| Konum | Alan | Değer → anlam |
|-------|------|---------------|
| 1. hane | seri | `3` = seri 3 |
| 2. hane | bellek | `3` = 192 KB flash / 24 KB RAM (LPS'te tek seçenek) |
| 3. hane | ürün tipi | `2` = BlueNRG-LPS |
| 4. (x) | paket | `A` = QFN32 (VFQFPN32 5×5mm) · `V` = WLCSP36 |
| 5. (y) | sıcaklık | `T` = −40…+105 °C · `C` = −40…+85 °C |

Somut parçalar: **BlueNRG-332AT / -332AC / -332VT / -332VC**. IPD eşi (harici balun matching): **MLPF-NRG-01D3**.

> **BlueNRG-LP order-code'u** "BlueNRG-3**x5**yz" şemasını izler (3. hane `5` = LP ürün tipi; ör. BlueNRG-345/-355). 256 KB flash; paketler QFN48 (32 I/O), WLCSP49 (30 I/O), QFN32 (20 I/O). Tam hane-hane çözümü için DS13282'ye bakın — SA0041 tüm LP'leri "BLUENRG-3x5yz", tüm LPS'leri "BLUENRG-332xy" diye gruplar.

### I.3 Silikon cut'ları (ES0576)

`SYSCFG` → **DIE_ID register @ 0x40000000** ile okunur:

| DIE_ID | Cut | Not |
|--------|-----|-----|
| 0x120 | 2.0 | |
| 0x121 | 2.1 | |
| 0x121 | 2.2 | 2.1 ile aynı register değeri — **paket üstü marking** ile ayrılır |

ES0576'daki **tüm limitasyonlar her üç cut'ı da etkiler** (§X).

---

## II. Bellek Haritası ve Boot

> ⚠️ STM32 ana hattından **en büyük sapma**: Flash `0x08000000`'de **değil**. Cortex-M0+ çekirdek (M3/M4/M7) ile çalışmaya alışkın iseniz, adresler farklıdır.

### II.1 Adres haritası (RM0491 / DS13819, BlueNRG-LPS)

| Bölge | Taban | Boyut / Not |
|-------|-------|-------------|
| Code (REMAP'e göre flash/SRAM0) | `0x0000 0000` | reset vektörü buradan çekilir |
| **ROM** (ST-reserved) | `0x1000 0000` | 7 KB: ilk **6 KB UART bootloader**, son 1 KB ADC trim + ST değerleri |
| **OTP** (kullanıcı) | OTP alanı; LPS lock `0x1000 1BFC` | 1 KB, **silinemez**, kilitlenebilir |
| OTP — imaj başlangıç adresi | **`0x1000 1804`** | secure bootloader bunu okur — bkz. SA0041 (§IX) |
| **Main Flash** | **`0x1000 0000` taban; uygulama `0x1004 0000`** | LPS 192 KB · LP 256 KB |
| Reset Manager / OTA taban | `0x1004 0000` | OTA reset manager bu adreste başlar (§VIII) |
| Lower application (OTA) | `0x1004 0800` | reset manager üstü |
| **NVM** (BLE stack non-volatile) | flash'ın **üst ucu**, ~4 KB | bonding/security DB; `REGION_NVM` |
| SRAM0 | `0x2000 0000` | LPS 12 KB — **DEEPSTOP'ta her zaman korunur** |
| SRAM1 | `0x2000 3000` | LPS 12 KB — retention **kullanıcı seçimli** |
| PKA RAM | ayrı 4 KB | public-key accelerator'a ayrılmış |
| APB0 / APB1 | `0x4000 0000` / `0x4100 0000` | çevre birimleri |
| AHB0 | `0x4800 0000` | |
| APB2 (RF) | `0x6000 0000` | radyo IP |
| Cortex-M0+ iç | `0xE000 0000` | NVIC/SysTick/SCB |

> Linker script ORIGIN değerleri (DK v1.5.0): GCC `BlueNRG_LP.ld` / `BlueNRG_LPS.ld`, Keil ARM `BlueNRG_LP[S].sct` scatter, IAR `BlueNRG_LP[S].icf` — her projenin `WiSE-Studio/`, `MDK-ARM/`, `EWARM/` alt-klasöründe. Parametrik `_MEMORY_FLASH_BEGIN_ = 0x10040000` ve `_MEMORY_RAM_BEGIN_` sembolleri static-stack/OTA bölünmesi için uygulamayı kaydırmaya izin verir (BLE_OTA_ResetManager `.icf` örneği: app `0x10040800`).

### II.2 Boot ve REMAP

- Reset sonrası `CLK_SYS / 4` → **16 MHz** CPU/DMA/bellek/çevre saatine kadar.
- `REMAP` biti: ana flash veya SRAM0'ı `0x0000 0000`'a haritalar.
- **UART ROM bootloader'a girme:** reset anında **PA10 yüksek** tutulur (DS13819 §2.11; otomatik baud, 1 Mbps'e kadar). NUCLEO kartlarda JP1 (pin 1-2) sökülerek de tetiklenir.
- Flash: 1 bank, sayfa 2 KB (LPS'te 96 sayfa), 32-bit oku/yaz, sayfa + mass erase, write-protect segmentleri.

---

## III. Donanım Özeti

### III.1 Çekirdek ve sistem (her iki cihaz)

- **Arm Cortex-M0+**, 32-bit, 2-stage pipeline, Von Neumann, single-cycle multiplier. **FPU yok.**
- Max 64 MHz (1–64 MHz). **MPU var** (8 bölgeye kadar). NVIC 32 vektör, 4 öncelik seviyesi, VTOR var. SysTick 24-bit.
- **DMA: 1 controller, 8 kanal**, DMAMUX ile esnek eşleme (ADC, SPI, I2C, USART, LPUART).
- 32-bit çok katmanlı AHB matrisi; 3 master: CPU, DMA1, **Radio**.
- Besleme: gömülü **SMPS step-down** (intelligent bypass) + LDO'lar (MLDO 1.2V, LPREG 1.0V always-on, ayrı RF LDO). SMPS aktif/radyo akımını düşürür; düşük VDD'de otomatik bypass.
- Reset/koruma: POR ~1.65 V, PDR (BOR gibi) ~1.58 V, programlanabilir PVD (7 eşik ~2.05–2.91 V).

### III.2 Radyo

| Özellik | BlueNRG-LP | BlueNRG-LPS |
|---------|-----------|-------------|
| BLE sürümü | 5.2 | 5.3 |
| PHY | 1M / 2M / Coded S2 (500k) / Coded S8 (125k) | aynı |
| Max TX gücü | +8 dBm (antende, programlanabilir) | +8 dBm |
| RX hassasiyeti | −97 dBm @1M · −104 dBm @125k | aynı |
| Eşzamanlı bağlantı | 128 fiziksel bağlantı | 128 |
| Roller | central/peripheral/observer/broadcaster, çoklu rol eşzamanlı | aynı |
| Direction finding (AoA/AoD, CTE) | destekli | **öne çıkan özellik** (RTLS/positioning) |
| 2.4 GHz proprietary radyo | var (UM2726 sürücüsü) | var |
| RF front-end | harici PA desteği | harici **PA + LNA** |
| Radyo akımı | TX 4.3 mA @0 dBm · RX 3.4 mA | aynı |

Radyo, DMA-tabanlı **BlueNRG core coprocessor** + **HAL Virtual/Radio Timer** ile zamanlanır (§VI). Düzenleyici uyum: ETSI EN 300 328 (AN5569), FCC part 15 (AN5570), ARIB STD-T66 (AN5572).

### III.3 Çevre birimleri (LP vs LPS)

| Birim | BlueNRG-LP | BlueNRG-LPS |
|-------|-----------|-------------|
| GPIO | ≤32 (28 wake-up, 31 5V-tolerant) | ≤20 (hepsi wake-up + 5V-tolerant) |
| ADC | 12-bit SAR, 8 ext + 3 int kanal, decimation ile 16-bit, analog watchdog | aynı IP ailesi |
| Dijital mikrofon | **1× PDM + analog mic I/F + PGA** | **yok** |
| USART | 1× (ISO7816, IrDA, SPI-master, Modbus) | 1× |
| LPUART | 1× | 1× |
| SPI | 1× SPI + 2× SPI/I2S (3 toplam) | 1× SPI/I2S |
| I²C | 2× (SMBus/PMBus) | 1× |
| Timer | 1× 16-bit 6-ch advanced + GP timer'lar + quadrature | TIM2 (4-ch) + TIM16/17 (2-ch) |
| RTC / IWDG | 1× / 1× | 1× / 1× |
| Kripto | AES-128 HW, **PKA** (ECC), **RNG/TRNG**, CRC, 64-bit UID | RNG var; AES/PKA aynı güvenlik IP'si |
| Dinamik akım | 18 µA/MHz | **14 µA/MHz** |
| Besleme / sıcaklık | 1.7–3.6 V / −40…+105 °C | aynı |

> **AEC-Q100 yok** — her iki cihaz da endüstriyel sınıf (otomotiv-qualified değil). Otomotiv hedefi varsa bu bir kısıttır.

---

## IV. Saat Ağacı ve Bring-up

### IV.1 Saat kaynakları (RM0491 §2.9)

| Kaynak | Frekans | Not |
|--------|---------|-----|
| HSE | **32 MHz** harici kristal | fail-safe, gömülü trim cap'ler; radyo için zorunlu |
| HSI | 64 MHz iç RC | |
| **RC64MPLL / PLL64M** | 64 MHz | harici 32 MHz XO'ya kilitlenir; HSI+PLL ortak blok |
| LSE | 32.768 kHz kristal veya single-ended 32.738 kHz | |
| LSI | ~32 kHz iç RC (24–49 kHz aralığı) | sıcaklığa duyarlı → kalibrasyon gerekir (§VI) |
| Alt-LS | HSI/HSE'den bölünmüş 32 kHz | **DEEPSTOP'ta yok** |

Sabit çevre saatleri: I2C/USART/flash/RNG/ADC daima 16 MHz; LPUART 16 MHz veya LSE; SPI/I2S 32 MHz'e kadar.

### IV.2 İlk boot (AN5503 / AN5469)

```c
/* Sistem saatini kur: 64 MHz CPU, 32 MHz BLE sysclk (STSW-BNRGLP-DK) */
if (SystemInit(SYSCLK_64M, BLE_SYSCLK_32M) != SUCCESS) {
    /* Saat yapılandırması başarısız — radyo çalışmaz, dur */
    while (1) { }
}
```

### IV.3 HSE kristal trim

Radyo doğruluğu HSE 32 MHz kristalin doğru "load capacitance trim"ine bağlıdır. Trim değeri `CONFIG_HW_HSE_TUNE` sembolü ile ayarlanır; doğrulama **MCO pininde** (ör. PA11) frekans ölçümü veya **2.402 GHz RF tone** ile yapılır (AN5503). Hazır araçlar: `stm32-hotspot/BlueNRG_LP_HSE_CALIB` (+ `_LPS_`, `_RTT` varyantları — buton/MCO veya J-Link RTT ile trim).

---

## V. BLE Stack ve ACI API

> 🔑 **İKİ AYRI EKSEN — KARIŞTIRMA.** Doğrulanan gerçek (STSW-BNRGLP-DK **v1.5.0**, stack v3.2a kaynağından):
> 1. **Kullanım modeli:** tüm stack çip üstünde mi (**standalone SoC**), yoksa BlueNRG-LP ağ-yardımcı işlemci olup harici MCU mu sürüyor (**network coprocessor / HCI host**)? İşlem-döngüsü fonksiyonu buna göre değişir.
> 2. **ACI nesli:** eski BlueNRG-1/2/MS sözcük dağarcığı mı, yoksa BlueNRG-LP'nin `srv`/`clt` ACI'si mi? DK v3.x **zaten yeni** olanı kullanır.

**A) Kullanım modeli — işlem-döngüsü fonksiyonu buradan gelir (her ikisi de DK içinde mevcut):**

| | Standalone SoC (tam stack çipte) | Network coprocessor (harici host) |
|---|----------------------------------|-----------------------------------|
| Header'lar | `Middlewares/ST/Bluetooth_LE/inc/`: `bluenrg_lp_stack.h`, `bluenrg_lp_api.h`, `bluenrg_lp_gatt.h`, `bluenrg_lp_events.h`, `ble_status.h`, `stack_user_cfg.h` | `Middlewares/ST/External_micro/SimpleBlueNRG-LP_HCI/includes/`: `bluenrg_lp_gap_aci.h`, `..._gatt_aci.h`, `..._hal_aci.h`, `..._l2cap_aci.h`, `bluenrg_lp_aci.h` |
| İşlem döngüsü | **`BLE_STACK_Tick()`** | **`BTLE_StackTick()`** |
| Event teslimi | uygulama adlandırılmış callback'leri implemente eder: `hci_le_connection_complete_event(...)`, `aci_gatt_srv_attribute_modified_event(...)`, `aci_hal_*_event(...)` | host HCI dispatch'i (SimpleBlueNRG-LP_HCI) |
| Stack lib | `libbluenrg_lp_stack.a` (host+controller) / `libbluenrg_lp_stack_controller_only.a` | host kütüphane + ağ-yardımcı FW imajı çipte |

**B) ACI sözcük dağarcığı — asıl "naming trap" nesil farkıdır:**

| İşlev | **Eski** BlueNRG-1/2/MS | **BlueNRG-LP** (DK v3.x'te zaten bu) |
|-------|------------------------|--------------------------------------|
| GATT sunucu | `aci_gatt_init`, `aci_gatt_add_serv`, `aci_gatt_update_char_value` | `aci_gatt_srv_init`, `aci_gatt_srv_add_service`, `aci_gatt_srv_add_char`, `aci_gatt_srv_notify`, `aci_gatt_srv_resp` (`ble_gatt_srv_def_t`/`ble_gatt_chr_def_t`) |
| GATT istemci | `aci_gatt_disc_*`, `aci_gatt_read_*` | `aci_gatt_clt_disc_*`, `aci_gatt_clt_read[_long\|_using_char_uuid]`, `aci_gatt_clt_write` |

Ortak (model/nesil fark etmez): `aci_gap_*`, `aci_hal_*`, `aci_l2cap_*`, `hci_*`/`hci_le_*`, `BLE_STACK_Init()`, `tBleStatus`.

### V.1 Stack init — kanonik: `Bluetooth_LE/inc/bluenrg_lp_stack.h`

Doğrulanmış DK v1.5.0 deseni (`BLE_Beacon_main.c`). Struct uygulamadaki **`BLE_STACK_INIT_PARAMETERS`** makrosuyla (app_conf.h) doldurulur:

```c
/* Doğrulanmış BLE_STACK_InitTypeDef alanları — bluenrg_lp_stack.h */
BLE_STACK_InitTypeDef p = BLE_STACK_INIT_PARAMETERS;   /* app_conf.h makrosu */
/* Açık kurulumda alanlar (struct'ın tamamı header'da): */
p.BLEStartRamAddress = (uint8_t*)dyn_alloc_buffer;     /* 32-bit hizalı */
p.TotalBufferSize    = BLE_STACK_TOTAL_BUFFER_SIZE(...);/* makro ile hesaplanır */
p.NumAttrRecords     = CFG_BLE_NUM_GATT_ATTRIBUTES;    /* uint16 */
p.NumOfLinks         = CFG_NUM_RADIO_TASKS;            /* eşzamanlı radyo görevi/link (≤128, RAM'e bağlı) — NumOfRadioTasks DEĞİL */
p.ATT_MTU            = CFG_BLE_ATT_MTU_MAX;            /* 23..1020 */
p.SleepClockAccuracy = CFG_BLE_SLEEP_CLOCK_ACCURACY;  /* ppm */
/* + MaxNumOfClientProcs, NumBlockCount, MaxConnEventLength, NumOfEATTChannels,
   ext-adv/periodic-adv/CTE/L2CAP-CoC ve isr0/isr1/user_fifo_size alanları */

tBleStatus ret = BLE_STACK_Init(&p);
if (ret != BLE_STATUS_SUCCESS) { /* 0x00 = BLE_STATUS_SUCCESS */ }

/* Ana döngü — DK'da ModulesTick() bunu sarar:
   void ModulesTick(void){ HAL_VTIMER_Tick(); BLE_STACK_Tick(); }            */
while (1) {
    ModulesTick();                                   /* virtual timer + stack işleme + tüm callback'ler */
    /* Power-save talebi: derinliği PWR yöneticisi BLE_STACK_SleepCheck() +
       App_PowerSaveLevel_Check() kullanıcı callback'ine danışarak belirler (§VII) */
    HAL_PWR_MNGR_Request(POWER_SAVE_LEVEL_STOP_NOTIMER, wakeupIO, &stopLevel);
}
```

> **KURAL (`bluenrg_lp_stack.h`):** `BLE_STACK_Tick()` çalışırken **hiçbir** stack fonksiyonu çağrılmamalı. Bir stack fonksiyonu bir ISR'den çağrılabiliyorsa, o IRQ `BLE_STACK_Tick()` süresince **disable** edilmeli. *(DK v1.5.0'da `BLE_STACK_ProcessRequest` / `BLE_STACK_TickNoEvents` **yok**.)*
>
> Kanonik kaynak: `Middlewares/ST/Bluetooth_LE/inc/bluenrg_lp_stack.h` (alan sırası burada).

### V.2 Modüler stack yapılandırması

Her özellik bir `*_ENABLED` makrosuyla derlenir. Kanonik dosya `Bluetooth_LE/inc/stack_user_cfg.h`; uygulamadaki `app_conf.h` `CFG_BLE_*` değerlerine bağlanır. `stack_user_cfg.h`'tan doğrulanmış makrolar: `CONNECTION_ENABLED`, `CONTROLLER_MASTER_ENABLED`, `CONTROLLER_PRIVACY_ENABLED`, `SECURE_CONNECTIONS_ENABLED`, `CONTROLLER_DATA_LENGTH_EXTENSION_ENABLED`, `CONTROLLER_2M_CODED_PHY_ENABLED`, `CONTROLLER_EXT_ADV_SCAN_ENABLED`, `CONTROLLER_PERIODIC_ADV_ENABLED`, `CONTROLLER_CTE_ENABLED`, `CONTROLLER_POWER_CONTROL_ENABLED`, `CONTROLLER_CIS_ENABLED`, `CONTROLLER_BIS_ENABLED`, `CONTROLLER_ISO_ENABLED`, `CONTROLLER_CHAN_CLASS_ENABLED`, `L2CAP_COS_ENABLED`, `EATT_ENABLED`, `CONNECTION_SUBRATING_ENABLED`.
İki link konfigürasyonu iki prebuilt lib'e eşlenir: tam = `libbluenrg_lp_stack.a`, sadece-controller = `libbluenrg_lp_stack_controller_only.a` *(DK `library/` içinde doğrulandı)*. **Flash/RAM küçültmenin ana kolu budur** — kullanmadığın profili `0` yap.

### V.3 Event modeli — DK: `bluenrg_lp_events.h`

DK'da (standalone SoC) uygulama, almak istediği her event için adlandırılmış callback'i **doğrudan implemente eder** (zayıf default'ları override eder). Doğrulanmış örnekler (`SensorDemo`): `hci_le_connection_complete_event(...)`, `hci_disconnection_complete_event(...)`, `aci_gatt_srv_attribute_modified_event(...)`, `aci_hal_end_of_radio_activity_event(...)`, `hci_hardware_error_event(...)`, `aci_hal_fw_error_event(...)`. Prototipler `bluenrg_lp_events.h`'ta.

> Bağlantı/PHY/MTU/throughput state machine'leri ve ACI komut örnekleri için **Part B §XIII–§XVIII** (örnekler eski nesil ACI isimleriyle) — LP'de GATT için `aci_gatt_srv_*` / `aci_gatt_clt_*` kullan.

---

## VI. Radio / Virtual Timer

BlueNRG-LP/LPS link controller'ı tek bir donanım **radio timer counter** sunar. Uygulama bunu kullanmaz; bunun üzerine kurulu **radio timer module** (= "virtual timer" sürücüsü) kullanılır. (AN5469)

**Sürücü dosyaları (STSW-BNRGLP-DK):** `rf_driver_hal_vtimer.c/.h`, `rf_driver_ll_timer.c/.h` (`Drivers/Peripherals_Drivers/`)

**İki katman:** High-Level (virtual timer kuyruğu, callback yönetimi, kalibrasyon ve radyo-olay zamanlama) + Low-Level (zaman birim dönüşümleri, yavaş saat ölçümü, donanım timer programlama).

### VI.1 Zaman birimleri

- **STU (System Time Unit)** = `625/256 µs` ≈ **2.4414 µs**. Donanım osilatör varyasyonundan bağımsız; kullanıcı bununla çalışır.
- **MTU (Machine Time Unit)** = donanım sayaç birimi (osilatöre bağlı).
- Zaman 64-bit STU akümülatöründe tutulur → ~1 milyon yılda taşar. Ama donanım sayacı sonlu; modül, taşmadan önce zaman tabanını yeniler — bunun için cihaz **~138 dakikada bir** otomatik uyanır.
- **1 saniye = 409600 STU.**

### VI.2 Düşük hızlı osilatör kalibrasyonu

İç RC (LSI) kullanılıyorsa frekans sıcaklıkla kayar (≈160 ppm/°C @−40…−20 °C, ≈60 ppm/°C @85…105 °C). Modül periyodik olarak RC'yi kararlı kaynağa karşı ölçüp STU↔MTU dönüşümünü günceller.
- 0.1 °C/s değişimde <500 ppm hata için **en az ~31 s'de bir** ölçüm gerekir.
- Bir kalibrasyon ~**800 µs** sürer.
- **Harici XO** kullanılıyorsa kalibrasyona gerek yok → `PeriodicCalibrationInterval = 0`.

### VI.3 API (STSW-BNRGLP-DK)

> `rf_driver_hal_vtimer.h`'tan doğrulandı (DK v1.5.0).

| İşlev | API |
|-------|-----|
| Init | `HAL_VTIMER_Init(&InitStruct)` |
| Ana döngü tick | `HAL_VTIMER_Tick()` |
| Timer IRQ handler içinden | `HAL_VTIMER_TimeoutCallback()` *(user callback DEĞİL)* |
| Sanal timer başlat (ms) | `HAL_VTIMER_StartTimerMs(&h, ms)` |
| Sanal timer başlat (mutlak STU) | `HAL_VTIMER_StartTimerSysTime(&h, t)` |
| Durdur | `HAL_VTIMER_StopTimer(&h)` |
| Şimdiki zaman (STU) | `HAL_VTIMER_GetCurrentSysTime()` |
| Radyo timer ayarla | `HAL_VTIMER_SetRadioTimerValue(t, evt, cal)` |
| Radyo timer temizle | `HAL_VTIMER_ClearRadioTimerValue()` |

```c
/* Init struct (DK) */
HAL_VTIMER_InitType v = {
    .XTAL_StartupTime           = HS_STARTUP_TIME,   /* STU cinsinden HSE oturma süresi */
    .EnableInitialCalibration   = INITIAL_CALIBRATION,
    .PeriodicCalibrationInterval= CALIBRATION_INTERVAL,  /* ms; harici XO ise 0 */
};
HAL_VTIMER_Init(&v);

/* Bir saniyelik sanal timer */
static VTIMER_HandleType h;     /* {uint64 expiryTime; callback; active; *next; *userData} */
h.callback = my_cb;
HAL_VTIMER_StartTimerMs(&h, 1000);
while (1) { HAL_VTIMER_Tick(); }   /* callback Tick içinde tetiklenir */

/* TimeoutCallback timer IRQ'sundan çağrılır — user callback değildir: */
void CPU_WKUP_IRQHandler(void) { HAL_VTIMER_TimeoutCallback(); }
```

> **Radio timer** (TX/RX tetikleme için), virtual timer'dan ayrıdır ve kuyruğa alınmaz. Önce radyo init + işlem yapılandırılmalı, sonra `SetRadioTimerValue(timeout_STU, HAL_VTIMER_TX_EVENT, HAL_VTIMER_PLL_CALIB_REQ)`. Timeout çok yakınsa API hata döner. `ClearRadioTimerValue()` dönüş kodu: `0`=temizlendi, `1`=çok geç, `2`=temizlenemedi (zaten tetiklenmiş olabilir).

### VI.4 Uyku engelleri

Timer modülü şu durumlarda cihazın uyumasını **engeller**: (1) sanal timer doldu ama callback'i henüz çalışmadı; (2) yavaş saat ölçümü sürüyor; (3) sıradaki radyo işlemi çok yakın; (4) back-to-back haberleşme. `BLE_STACK_SleepCheck()` / `HAL_VTIMER` durumu uyumadan önce mutlaka kontrol edilmeli.

---

## VII. Güç Modları

### VII.1 Donanım modları (AN5466 / RM0491)

| Mod | Açıklama | Wake-up kaynakları | RAM retention |
|-----|----------|--------------------|---------------|
| **Run** | tüm saat/çevre aktif | — | tümü |
| **DeepStop (LS clock ON)** | sistem/bus saati durur, dijital domain 1.0V, LSI/LSE çalışır, RTC/IWDG aktif | GPIO **PA0–PA15, PB0–PB11**, RTC*, IWDG, Radio (radyo wakeup bloğu + timer'ı), HAL Virtual Timers | SRAM0 daima; diğer bankalar yazılımla seçilir |
| **DeepStop (LS clock OFF)** | daha derin; LSI/LSE durur | **sadece GPIO** (PA0–PA15, PB0–PB11) | SRAM0 daima; diğerleri seçimli |
| **Shutdown** | tüm regülatör/saat/RF kapalı, en düşük güç | **sadece RSTN pini** (POR benzeri çıkış, PORRSTF flag); BOR opsiyonel | yok (tam güç kaybı) |

> *RTC, DEEPSTOP'tan **iç** alarm wake-up yapamaz — bkz. ES0576 §1.1 (§X). RTC wake-up'ı PA8'e yönlendir.

### VII.2 Yazılım power-save seviyeleri

`HAL_PWR_MNGR_Request(level)` ile (AN5466):
- `POWER_SAVE_LEVEL_RUNNING` — hiçbir şey durmaz (en yüksek tüketim).
- `POWER_SAVE_LEVEL_CPU_HALT` — sadece CPU (WFI); çevre birimleri çalışır; herhangi bir IRQ uyandırır.
- `POWER_SAVE_LEVEL_STOP_WITH_TIMER` — HW DeepStop, LS clock ON; GPIO/RTC/IWDG/Radio/VTimer uyandırır.
- `POWER_SAVE_LEVEL_STOP_NOTIMER` — HW DeepStop, LS clock OFF; **sadece GPIO** uyandırır.

> Her power-save çıkışında **bir reset oluşur**; çevre/uygulama bağlamı power-save yazılımı tarafından geri yüklenir (uygulamaya şeffaf). Bu yüzden "reset gibi görünen" davranış normal olabilir.

### VII.3 Akımlar (1.8 V)

| Durum | BlueNRG-LP | BlueNRG-LPS |
|-------|-----------|-------------|
| Shutdown | 10 nA | 8 nA |
| DeepStop + harici LSE + BLE wakeup | 0.6 µA | 0.8 µA |
| DeepStop + iç LSI + BLE wakeup | 0.9 µA | 1.0 µA |
| Radyo TX @0 dBm / RX | 4.3 mA / 3.4 mA | 4.3 / 3.4 mA |

**Ölçülmüş BLE sistem akımı** (AN5466, BlueNRG-LP, 3.3 V, 0 dBm, 64 KB tam retention):

| Senaryo | Ortalama |
|---------|----------|
| Advertising 100 ms (28-byte) | 137.9 µA |
| Advertising 1000 ms | 15.4 µA |
| Connection 100 ms (boş paket) | 69.5 µA |
| Connection 1000 ms | 8.8 µA |

> Pil ömrü için en güçlü kol **connection/advertising interval**'dir (10×–17× fark). SMPS açık + gereksiz RAM bankalarının retention'ını kapatmak ek kazanç sağlar.

---

## VIII. OTA Firmware Upgrade

(AN5463) OTA, BLE stack üzerinde çalışan bir GATT servisidir. Servis kodu **`OTA_btl.[ch]`** (`Middlewares\ST\BLE_Application\OTA`).

### VIII.1 OTA servisi (UUID'ler — 128-bit, proprietary, `OTA_btl.c`'de tanımlı)

| Karakteristik | UUID | İçerik |
|---------------|------|--------|
| OTA servisi | `OTA_SRVC_UUID` | FW upgrade servisi |
| Image | `IMAGE_CHR_UUID` | boş bellek alt/üst sınırları |
| New image | `NEW_IMAGE_CHR_UUID` | hedef imaj taban adresi + boyut + notification range |
| Image content | `IMAGE_CONTENT_CHR_UUID` | 16-byte blok + seq no (2B) + checksum (1B) |
| Expected seq | `IMAGE_SEQ_NUM_CHR_UUID` | slave'in beklediği sonraki blok no |

### VIII.2 OTA paket yapısı

```
| Checksum (8b) | Image data ((N*16)*8 b) | Needs ack (8b) | Sequence number (16b) |
N = (OTA_ATT_MTU_SIZE - 3 - 4) / 16
```
Bloklar `ACI_GATT_CLT_WRITE_WITHOUT_RESP` ile yazılır. Hız için **Data Length Extension** şart: `HCI_LE_SET_DATA_LENGTH()` (PDU 251) + `ACI_ATT_CLT_EXCHANGE_MTU()`; modüler config'te en az `BLE_STACK_SLAVE_DLE_CONF`.

### VIII.3 İki mimari

**A — Lower/Higher Application + Reset Manager** (her iki uygulama da OTA servisi içerir):
```
Flash:  [Reset Manager @0x10040000] [Lower App @0x10040800] [Higher App]
```
- Reset manager `0x10040000`'da; en son geçerli imaja atlar. Geçerlilik, her uygulamanın IVT'sindeki ayrılmış bir girişe yazılan **application validity tag** ile belirlenir (`OTA_Check_Application_Tags_Value()` — `OTA_ResetManager.c`). Başarısız OTA, geçersiz uygulamaya atlamayı önler (her zaman son geçerli imaja gider).
- Proje: `BLE_OTA_ResetManager`. Derleme: `CONFIG_OTA_LOWER` / `CONFIG_OTA_HIGHER`.

**B — OTA Service Manager** (bağımsız updater; yeni uygulama OTA servisi içermez):
```
Flash:  [OTA Service Manager + Reset Manager @0x10040000] [New App (OTA servissiz)]
```
- Servis manager sabit adreste; tüm güncelleme yükünü taşır. Yeni uygulama sabit tabanda olmalı. Geçiş: `OTA_Jump_To_Service_Manager_Application()`. Proje: `BLE_OTA_ServiceManager`. Config: `CONFIG_OTA_USE_SERVICE_MANAGER`.

### VIII.4 Uygulamaya OTA ekleme (özet, EWARM örneği)

1. `CONFIG_OTA_LOWER`/`CONFIG_OTA_HIGHER` + `CONFIG_SW_OTA_DATA_LENGTH_EXT` preprocessor; DK linker referans dosyasını kullan.
2. `OTA_btl.c`/`.h`'yi projeye ekle.
3. `OTA_Add_Btl_Service()` çağır.
4. `hci_le_set_scan_resp_data(18, BTLServiceUUID4Scan)` ile UUID'yi scan response'a ekle.
5. `aci_gatt_attribute_modified_event()` / `aci_gatt_srv_write_event()` → `OTA_Write_Request_CB()`.
6. `aci_gatt_srv_read_event()` → `OTA_Read_Char()`.
7. Ana döngüde `if (OTA_Tick() == 1) OTA_Jump_To_New_Application();`.
8. `aci_hal_end_of_radio_activity_event()` → `OTA_Radio_Activity()` (flash yazımını radyo ile senkronlar).
- İlgili kodu `#if ST_OTA_FIRMWARE_UPGRADE_SUPPORT` ile sar. PC tarafı: BlueNRG GUI (STSW-BNRGUI) "OTA bootloader" aracı veya `OTA_Central_3_x.py`. Demo: STEVAL-IDB011V1 (OTA sırasında LED DL3).

---

## IX. Secure Bootloader ve Güvenlik

### IX.1 UART system bootloader (AN5471)

ROM'daki 6 KB bootloader (`0x10000000`), reset anında **PA10 yüksek** ile girilir. UART, otomatik baud (1 Mbps'e kadar), 8N1. STM32CubeProgrammer (≥2.17) ve RF-Flasher (STSW-BNRGFLASHER) bu protokolü kullanır.

DK'daki **Secure Bootloader GUI** PC aracı (STSW-BNRGLP-DK v1.5.0): authentication key üretir, binary imajı **imzalar** ve secure bootloader'ı **OTP üzerinden aktive** eder — SA0041/AN6140 ile doğrudan ilgili (§IX.2). Init parametreleri için **BlueNRG-X Radio Init Wizard** `BLE_STACK_Init()` ayarlarını üretip `*_config.h` çıkarır.

### IX.2 ⚠️ SA0041 — Secure bootloader imaj-doğrulama açığı (Rev 2, Jul 2025)

**Etkilenen:** **BlueNRG-332xy / LPS** (bootloader v0x02), **BlueNRG-3x5yz / LP & 355** (v0x04) — bootloader silikona gömülü.

**Açık:** Aşağıdakilerden biri imza doğrulamasını bozar:
1. İmzalı uygulama imajını **flash başlangıcı `0x10040000` dışına** koymak.
2. **OTP adresi `0x10001804`**'ü imaj başlangıç adresinden farklı bir değere set etmek.

**Etki:** İmaj doğrulaması yalnızca kısmi yapılabilir veya başarısız olur (→ imzasız/değiştirilmiş imaj kabul edilebilir).

**Çözüm:** **AN6140 v3**'teki talimatları izle; imajı tam olarak `0x10040000`'a yerleştir ve OTP `0x10001804`'ü imaj başlangıç adresine eşitle. *Credit: Johannes Obermaier, Amazon · psirt@st.com.*

> Bu, BlueNRG-355/-345 (BlueNRG-3x5yz) order-code'larını **de** etkiler — secure boot kullanan her LP/LPS/355 projesinde kontrol et (Part B'deki app örnekleri de buna tabidir).

### IX.3 Genel güvenlik

- **TrustZone YOK** (Cortex-M0+). İzolasyon için MPU + flash write-protect segmentleri kullanılır.
- AES-128 HW + PKA (ECC) + RNG/TRNG → BLE LE Secure Connections ve imza/şifreleme.
- **NVM** (flash üst ucu, ~4 KB): bonding/security key veritabanı. NVM bölgesini OTA imaj alanından ayrı tut.
- OTP `0x10001BFC` lock; OTP silinemez — tek seferlik provizyon (MAC adresi, anahtarlar).

---

## X. Errata (ES0576)

BlueNRG-LPS, **cut 2.0 / 2.1 / 2.2'nin tamamını** etkileyen 4 limitasyon. (Errata cross-check kuralı için bkz. [CLAUDE.md](CLAUDE.md) — review öncesi zorunlu.)

### X.1 RTC alarmı DEEPSTOP'tan iç wake-up yapamaz
- **Açıklama:** RTC, DEEPSTOP'ta çalışır ama **iç RTC alarm wake-up event'i üretemez.**
- **Etki:** RTC alarmı DEEPSTOP'tan uyandırma kaynağı olarak kullanılamaz.
- **Workaround:** RTC alarmını **PA8'e çıkışla**, bu pini DEEPSTOP'tan wake-up pini olarak kullan.

### X.2 RUN modunda RTC interrupt tetiklenmeyebilir
- **Açıklama:** RTC saat kaynağı **LSI veya LSE** iken RUN modunda RTC interrupt'ları kaybolabilir. `CLK_16MHz/512` kaynağında sorun **yok**.
- **Etki:** RUN modunda RTC interrupt'ları gerçek-zamanlı kontrol için güvenilmez.
- **Workaround:** RUN modunda RTC interrupt kullanma → **`RTC_ISR` register'ını polle**; veya alarm/wakeup'ı PA8/PA9'a çıkarıp I/O interrupt pini olarak kullan. *Not: DEEPSTOP wake-up etkilenmez; DEEPSTOP'ta RTC interrupt daima güvenilirdir.*

### X.3 Bazı GPIO aktiviteleri RF performansını bozar
- **Açıklama:** RF sırasında: (a) QFN32'de **PB14/PB15** toggle; (b) QFN32+WLCSP36'da **OSCIN/OSCOUT** pinlerine yakın yönlendirilmiş GPIO track'lerinin toggle'ı.
- **Etki:** Yüksek paket hata oranı (PER).
- **Workaround:** QFN32'de RF sırasında PB14/15'i toggle etme (input/output fark etmez); GPIO track'lerini OSCIN/OSCOUT'a yakın yönlendirme (PCB layout — AN5526).

### X.4 Connectionless AoA/AoD CTE paketinde RX kilitlenmesi
- **Açıklama:** CTE uzantılı advertising paketi alırken, paket malform/bozuksa ve payload uzunluğu 1–2 byte anlaşılırsa, dijital radyo de-framing'i kilitlenir ve **RX state'inde takılı kalır** (LE_1M veya LE_2M).
- **Etki:** Radyo RX'te asılı kalır, tamamlanma interrupt'ı üretmez.
- **Workaround:** CTE'li extended adv almaya hazırlanırken (`TxRxPack.CTEAndSamplingEnable=1`, `TxRxPack.Advertise=1`) radyonun kilitlenebileceğini varsay; **paralel bir watchdog timer** kur (max beklenen payload+CTE süresi kadar). Interrupt gelmeden süre dolarsa mevcut alımı **abort** et.

> **BlueNRG-LP errata'sı:** Bu dosya BlueNRG-LPS (ES0576) limitasyonlarını içerir. BlueNRG-LP için ayrı errata sheet'i, review öncesi ST ürün sayfasından (Resources → Errata) doğrula.

---

## XI. SDK, GitHub ve Toolchain

### XI.1 Repolar (GitHub-first kaynak)

| Repo / Paket | İçerik |
|--------------|--------|
| **STSW-BNRGLP-DK v1.5.0** | Resmi **son** ve **kanonik** DK (01-Dec-2023, BLE stack v3.2a; st.com Inno Setup installer — ST GitHub'da YOK). macOS'ta kurmadan açma: `brew install innoextract && innoextract -s "BlueNRG-LP_LPS DK-1.5.0.0-Setup.exe"`. İçerik: stack lib + 26 BLE + 5 NWK + peripheral örnekleri (§XI.4). Bayat ayna (son çare): `svcguy/BlueNRG-LP_LPS-DK-1.2.0` |
| `STMicroelectronics/stm32-mw-wpan` | BLE stack middleware upstream aynası (`ble/stack/{include,lib}`) |
| `STMicroelectronics/fp-sns-datalog2` | BlueNRG-LP stack kopyası (`Middlewares/ST/BlueNRG-LP/...`) |
| `stm32-hotspot/BlueNRG_LP*_HSE_CALIB*` | HSE kristal trim yardımcıları (buton/MCO/RTT) |

### XI.2 `gh` reçeteleri

> **Kanonik kaynak yerel DK'dır** (`STSW-BNRGLP-DK v1.5.0`, ST GitHub'da yok). Sembolleri DK ağacında ara; `gh` reçeteleri yalnızca upstream ayna doğrulaması içindir.

```bash
# Yerel DK'da sembol doğrulama (birincil yöntem)
grep -rn 'BLE_STACK_InitTypeDef' <DK>/Middlewares/ST/Bluetooth_LE/inc/bluenrg_lp_stack.h
grep -rn 'aci_gatt_srv_add_char\|aci_gatt_clt_write' <DK>/Middlewares/ST/Bluetooth_LE/inc/bluenrg_lp_api.h

# Upstream ayna (stack include/lib) — gh ile, klonlamadan
gh search code 'BLE_STACK_InitTypeDef' --owner=STMicroelectronics --json repository,path
# → stm32-mw-wpan / fp-sns-datalog2 altında ble/stack kopyaları

# Yeni srv/clt GATT isimleri vs eski nesil
gh search code 'aci_gatt_srv_add_char'  --owner=STMicroelectronics --json repository,path  # BlueNRG-LP (yeni)
gh search code 'aci_gatt_update_char_value' --owner=STMicroelectronics --json repository,path  # eski BlueNRG-1/2/MS (LP'de YOK)
```

### XI.3 Toolchain ve flashing

| IDE | Klasör | Startup | Linker |
|-----|--------|---------|--------|
| IAR EWARM | `EWARM/` | `startup_BlueNRG_LP.c` | `BlueNRG_LP.icf` / `BlueNRG_LPS.icf` |
| Keil MDK-ARM | `MDK-ARM/` | `startup_BlueNRG_LP.c` | `BlueNRG_LP[S].sct` (scatter) |
| WiSE-Studio (GCC) | `WiSE-Studio/` | `startup_BlueNRG_LP.c` | `BlueNRG_LP[S].ld` |
| System | — | — | `system_BlueNRG_LP.c` |

| Flash aracı | Paket | Cihaz / arayüz |
|-------------|-------|----------------|
| STM32CubeProgrammer (≥2.17) | st.com | BlueNRG-LP/LPS — SWD + UART; flash/OTP/key |
| RF-Flasher Utility | STSW-BNRGFLASHER | BlueNRG-1/2/**LP/LPS** — UART bootloader + SWD (ST-LINK/J-Link/CMSIS-DAP) |
| BlueNRG GUI | STSW-BNRGUI | HCI/ACI konsolu, OTA bootloader aracı, IFR/HW param |
| UART ROM bootloader | gömülü | PA10 yüksek @reset; AN5471 |

> **Static-stack (opsiyonel):** stack'i bağımsız imaj olarak bir kez flash'la (`BLE_StaticStack.hex`), uygulamayı `sym_export.txt` → `ble_static_stack_sym.a` ile bağla. Uygulama, stack ile **aynı** özellik setini ve `CFG_NUM_RADIO_TASKS`'ı kullanmalı + RAM/flash bölme sembollerini set etmeli. Stack'i yeniden flash'lamadan uygulamayı OTA'lamayı sağlar.

---

## XII. Olmaz sa Olmaz

SoC bring-up + BLE + güç + OTA için zorunlu kontrol listesi:

**Silikon / bellek**
- [ ] Flash uygulama tabanı **`0x10040000`** (STM32 ana hattının `0x08000000`'i DEĞİL).
- [ ] Cut'ı `DIE_ID @0x40000000` ile oku; ES0576 limitasyonlarını uygula (§X).
- [ ] NVM bölgesi (flash üst ucu) uygulama/OTA imaj alanından ayrı; üzerine yazma.

**Saat / radyo**
- [ ] HSE 32 MHz kristal var ve **trim doğru** (MCO/RF tone ile doğrula) — yoksa radyo çalışmaz/sapar.
- [ ] İç LSI kullanılıyorsa `PeriodicCalibrationInterval` set edildi (≤31 s); harici XO ise 0.
- [ ] `SystemInit(SYSCLK_64M, BLE_SYSCLK_32M)` başarı döndü.

**BLE stack**
- [ ] Doğru kullanım modeli/API (§V): **standalone SoC** → `BLE_STACK_Tick()`; **network coprocessor (harici host)** → `BTLE_StackTick()`.
- [ ] GATT için BlueNRG-LP ACI'si kullanılıyor: `aci_gatt_srv_*` / `aci_gatt_clt_*` — eski BlueNRG-1/2/MS `aci_gatt_add_serv` / `aci_gatt_update_char_value` DEĞİL.
- [ ] `BLE_STACK_Init()` dönüşü `BLE_STATUS_SUCCESS (0x00)` kontrol edildi.
- [ ] `BLE_STACK_Tick()` ana döngüde; **ISR'den çağrılmıyor** (ISR'de yalnız `BLE_STACK_ProcessRequest()`).
- [ ] Kullanılmayan stack modülleri `CFG_BLE_*` ile kapatıldı (flash/RAM tasarrufu).

**Güç**
- [ ] Uyumadan önce `BLE_STACK_SleepCheck()` + VTimer durumu kontrol ediliyor.
- [ ] RTC'yi DEEPSTOP wake-up için doğrudan kullanma → PA8 workaround (ES0576 §1.1).
- [ ] RUN'da RTC interrupt yerine polling (ES0576 §1.2).
- [ ] DeepStop'ta gerekli RAM bankaları retention'da; gereksizler kapalı (akım).
- [ ] Power-save çıkışındaki **reset** davranışı uygulama tarafından bekleniyor/ele alınıyor.

**RF / layout**
- [ ] QFN32'de RF sırasında PB14/15 toggle YOK; GPIO track'leri OSCIN/OSCOUT'tan uzak (ES0576 §1.3, AN5526).
- [ ] CTE/AoA/AoD alıcısı varsa RX-lock watchdog'u kurulu (ES0576 §1.4).

**OTA / güvenlik**
- [ ] OTA mimarisi seçildi (Reset Manager vs Service Manager); reset manager `0x10040000`.
- [ ] OTA için Data Length Extension açık (`HCI_LE_SET_DATA_LENGTH` + MTU exchange).
- [ ] Secure boot kullanılıyorsa: imaj **tam `0x10040000`**'da + OTP **`0x10001804`** = imaj başlangıcı (SA0041, AN6140 v3).
- [ ] AEC-Q100 gerekiyorsa: LP/LPS endüstriyel sınıf — otomotiv qualifikasyonu yok, bunu doğrula.


---

# Part B — BLE Protokol, Throughput & Uygulama Katmanı

> **Köken:** Bu bölüm eski `ref-ble-bluenrg355.md` dosyasından **2026-06-16**'da bu dosyaya birleştirildi (tek kanonik LP referansı). Konu: BLE **protokol/throughput** + iOS/Android + connection recovery + security-manager (app) + GATT profile + DMA (app) + RF coexistence katmanı. SoC/silikon katmanı = Part A (§I–§XII).
>
> ⚠️ **ACI NESİL UYARISI (oku):** Aşağıdaki inline kod örnekleri **illüstratiftir** ve büyük ölçüde eski **BlueNRG-1/2/MS ACI** sözcük dağarcığını kullanır (`aci_gatt_add_service`, `aci_gatt_add_char`, `aci_gatt_update_char_value_ext`, `aci_gatt_attribute_modified_event`, `aci_gap_set_undirected_connectable`, `aci_gap_set_directed_connectable`). BlueNRG-LP/LPS/355 **DK v3.2a**'da karşılıkları **`aci_gatt_srv_*` / `aci_gatt_clt_*`** neslidir — bkz. **§V (API-naming trap)**. Throughput/PHY/MTU/zamanlama **kavramları** silikon-doğrudur; yalnız sembol adlarını kendi DK ağacınızda doğrulayın (`gh search code <Symbol> --owner=STMicroelectronics`).
>
> ⚠️ **FLASH BOYUTU:** Aşağıda yer yer geçen **"512 KB flash" YANLIŞTIR.** BlueNRG-LP/345/355 = **256 KB**, BlueNRG-LPS = 192 KB (doğrulanmış: §I.1, §III; DS13282/DS13819). Etkilenen yerler `[DÜZELTME]` notuyla işaretlendi. OTA bölünmesi/staging adresleri buna göre yeniden boyutlandırılmalı — kanonik ST OTA mimarisi için **§VIII** (Reset Manager / Service Manager).

---

## XIII. PHY Seçimi

### PHY Karşılaştırma

| PHY | Bit Rate | Max Throughput | Menzil | Kullanım |
|-----|----------|----------------|--------|----------|
| LE 1M | 1 Mbps | ~800 Kbps | Baseline | Legacy, iOS ≤13 uyumluluk |
| **LE 2M** | **2 Mbps** | **~1.4 Mbps** | ≈%20 kısa | **OTA, dosya aktarım** |
| LE Coded S=2 | 500 Kbps | ~250 Kbps | 4× | Uzun menzil |
| LE Coded S=8 | 125 Kbps | ~60 Kbps | 8× | Maksimum menzil |

### ACI PHY Komutları

```c
/* Bağlantı kurulduktan sonra PHY güncelle */
tBleStatus ret = aci_le_set_phy(
    connection_handle,
    0x00,        /* ALL_PHYS: 0x00 = tercih var, 0x01 = TX any, 0x02 = RX any */
    0x02,        /* TX_PHYS: BIT(0)=1M, BIT(1)=2M, BIT(2)=Coded */
    0x02,        /* RX_PHYS: BIT(1)=2M */
    0x0000       /* PHY_options: Coded PHY seçilmediyse 0 */
);
if (ret != BLE_STATUS_SUCCESS) {
    /* Peer 2M desteklemiyorsa 1M'de kalır — hata değil */
}

/* PHY Update Complete event — HCI_LE_PHY_UPDATE_COMPLETE_EVENT */
void hci_le_phy_update_complete_event(uint8_t  status,
                                       uint16_t conn_handle,
                                       uint8_t  tx_phy,
                                       uint8_t  rx_phy)
{
    /* tx_phy/rx_phy: 0x01=1M, 0x02=2M, 0x03=Coded */
    if (status != 0x00U) {
        /* PHY update reddedildi — peer desteklemiyor */
        return;
    }
    current_phy = tx_phy;
    /* 2M aktifse MTU re-negotiate fırsatı var */
}

/* PHY tercihini advertising'de de belirt */
aci_le_set_default_phy(
    0x00,   /* ALL_PHYS */
    0x02,   /* TX: 2M tercih */
    0x02    /* RX: 2M tercih */
);

/* Mevcut PHY'yi sorgula */
uint8_t tx_phy, rx_phy;
aci_le_read_phy(connection_handle, &tx_phy, &rx_phy);
```

### PHY Update State Machine

```c
typedef enum {
    PHY_STATE_1M      = 0,
    PHY_STATE_2M      = 1,
    PHY_STATE_CODED   = 2,
    PHY_STATE_PENDING = 3,
} phy_state_t;

static phy_state_t s_phy = PHY_STATE_1M;

/* Bağlantı kurulunca 2M'e geç */
void on_connection_complete(uint16_t handle) {
    s_phy = PHY_STATE_PENDING;
    aci_le_set_phy(handle, 0x00, 0x02, 0x02, 0x0000);
}

void on_phy_update_complete(uint16_t handle, uint8_t tx, uint8_t rx, uint8_t status) {
    if (status == 0x00U && tx == 0x02U) {
        s_phy = PHY_STATE_2M;
        /* Şimdi MTU negotiate et */
        aci_gatt_exchange_config(handle);
    } else {
        s_phy = PHY_STATE_1M;
    }
}
```

---

## XIV. MTU Negotiation

### MTU Teori

```
BLE paket yapısı (LE 2M PHY, 251 byte Data PDU):
  ┌────────────────────────────────────────────┐
  │ L2CAP Header: 4 bytes                      │
  │   └─ ATT Header: 3 bytes                   │
  │       └─ ATT Payload: MTU-3 bytes          │
  └────────────────────────────────────────────┘

Data PDU max = 251 bytes (DLE ile, default 27)
L2CAP SDU max = Data PDU - 4 = 247 bytes  (L2CAP header çıktı)
ATT PDU max   = L2CAP SDU = 247 bytes
MTU max       = 247 bytes
ATT payload   = MTU - 3 = 244 bytes       (ATT opcode + handle = 3 byte)

Yani: aci_gatt_update_char_value_ext() ile max 244 byte/paket
```

### MTU Exchange

```c
/* 1. Data Length Extension aktif et (DLE) — önce bu */
aci_le_set_data_length(
    connection_handle,
    251U,    /* TX Octets: max 251 */
    2120U    /* TX Time: 251 * 8 + overhead, max 17040 μs */
);

/* LE_SET_DATA_LENGTH_COMPLETE event bekle, sonra MTU exchange */

/* 2. MTU exchange başlat (client tarafından) */
tBleStatus ret = aci_gatt_exchange_config(connection_handle);

/* 3. MTU Exchange Response event */
void aci_att_exchange_mtu_resp_event(uint16_t conn_handle,
                                     uint16_t server_rx_mtu)
{
    /* Efektif MTU = min(client_mtu, server_rx_mtu) */
    /* BlueNRG-355 server MTU = 247 tipik */
    effective_mtu = MIN(247U, server_rx_mtu);
    max_payload   = effective_mtu - 3U;   /* ATT opcode+handle */
}

/* 4. Characteristic update — max payload ile */
void send_data(uint16_t handle, const uint8_t *data, uint16_t len) {
    uint16_t offset = 0;
    while (offset < len) {
        uint16_t chunk = MIN(max_payload, len - offset);
        tBleStatus ret = aci_gatt_update_char_value_ext(
            service_handle,
            char_handle,
            0x01,          /* Update_Type: 0=local, 1=notification */
            len,           /* Val_Length: total */
            offset,        /* Value_Offset */
            chunk,         /* Value_Length: this chunk */
            data + offset
        );
        if (ret == BLE_STATUS_INSUFFICIENT_RESOURCES) {
            /* TX buffer dolu — bekle ve tekrar dene */
            HAL_Delay(1U);
            continue;
        }
        offset += chunk;
    }
}
```

### iOS ve Android MTU Davranışı

| Platform | Davranış | Max MTU | ATT Payload |
|----------|----------|---------|-------------|
| iOS 11+ | Exchange'i client başlatır; 185 byte ister | **185 bytes** | **182 bytes** |
| iOS ≤10 | MTU exchange yapmaz | 23 bytes (default) | 20 bytes |
| Android 5.0+ | `requestMtu(512)` çağrısı gerekir | 512 istek → **247** gerçek | 244 bytes |
| Android (sistem default) | Exchange yapmaz, uygulamaya bırakır | 23 bytes | 20 bytes |

```c
/* iOS: 185 byte MTU gönderir — 182 byte payload */
/* Android: uygulama requestMtu() çağırmadan sadece 20 byte alır */

/* Server: maksimum MTU advertise et */
/* BlueNRG-355 stack init'te: */
BLE_STACK_Init_Params_t params = {
    .AttMtu = 247U,    /* Server desteklediği max MTU */
    /* ... */
};

/* Gelen MTU'ya göre payload boyutunu adaptif ayarla */
static uint16_t s_eff_mtu = 23U;  /* default: MTU negotiate olmadı */
static uint16_t s_payload = 20U;

void on_mtu_exchange(uint16_t conn, uint16_t peer_mtu) {
    uint16_t neg = MIN(247U, peer_mtu);
    s_eff_mtu = neg;
    s_payload = neg - 3U;
    /* iOS'ta s_payload = 182, Android'da 244 (requestMtu çağırdıysa) */
}
```

---

## XV. Extended Advertising

### Legacy vs Extended Advertising

```
Legacy Advertising (BLE 4.x):
  ADV_IND PDU: max 31 bytes payload
  SCAN_RSP PDU: max 31 bytes payload
  → Total visible data: 62 bytes

Extended Advertising (BLE 5.0+, BlueNRG-355):
  Primary channel: advertising handle + pointer
  Secondary channel (LE 2M): max 254 bytes per PDU
  Chained: multi-PDU → max 1650 bytes total data
  → Manufacturer data, complete service list, longer name
```

### ACI Extended Advertising Kurulumu

```c
/* Step 1: Extended advertising parameters */
tBleStatus ret;
uint8_t adv_handle = 0x00U;  /* Handle 0: primary set */

ret = aci_le_set_extended_advertising_parameters(
    adv_handle,
    ADV_EVT_PROP_CONNECTABLE,   /* Properties: connectable, undirected */
    160U, 160U,                  /* Primary_Interval: 100ms (160 * 0.625ms) */
    0x07U,                       /* Primary_Channel_Map: ch37+38+39 */
    PUBLIC_ADDR,                 /* Own_Address_Type */
    PUBLIC_ADDR,                 /* Peer_Address_Type (N/A for undirected) */
    NULL,                        /* Peer_Address */
    0x00U,                       /* Adv_Filter_Policy */
    0x00U,                       /* Adv_TX_Power: host-selected */
    LE_1M_PHY,                   /* Primary_Adv_PHY: MUST be 1M or Coded.
                                  * BT Core 5.4 Vol 6 Part B §2.3.1 forbids
                                  * LE_2M_PHY on primary channels; controllers
                                  * return HCI error 0x12 (Invalid HCI Params)
                                  * if 2M is requested here. */
    0x00U,                       /* Secondary_Max_Skip */
    LE_2M_PHY,                   /* Secondary_Adv_PHY: 2M is allowed here */
    0x00U,                       /* Adv_SID */
    0x00U                        /* Scan_Req_Notification_Enable */
);

/* Step 2: Extended advertising data (31+ bytes mümkün) */
uint8_t adv_data[] = {
    /* Flags */
    2U, AD_TYPE_FLAGS, FLAG_BIT_LE_GENERAL_DISCOVERABLE | FLAG_BIT_BR_EDR_NOT_SUPPORTED,
    /* Complete Local Name */
    11U, AD_TYPE_COMPLETE_LOCAL_NAME, 'B','l','u','e','N','R','G','-','3','5','5',
    /* Manufacturer Specific */
    5U, AD_TYPE_MANUFACTURER_SPECIFIC_DATA, 0x30U, 0x00U, 0x01U, 0x02U,
    /* Service UUID 128-bit */
    17U, AD_TYPE_128_BIT_SERV_UUID_CMPLT_LIST,
    0x1b,0xc5,0xd5,0xa5,0x02,0x00,0xa6,0x87,0xec,0x11,0x36,0x39,0xcb,0xcd,0x2b,0x26,
};

ret = aci_le_set_extended_advertising_data(
    adv_handle,
    SET_ADVERTISING_DATA,   /* Operation: complete data */
    0x01U,                   /* Fragment_Preference: no fragmentation */
    sizeof(adv_data),
    adv_data
);

/* Step 3: Extended scan response (opsiyonel, scan için) */
uint8_t scan_data[] = {
    /* 16-bit Service UUIDs */
    3U, AD_TYPE_16_BIT_SERV_UUID_CMPLT_LIST, 0x00U, 0xFE,
};
ret = aci_le_set_extended_scan_response_data(
    adv_handle, SET_ADVERTISING_DATA, 0x01U,
    sizeof(scan_data), scan_data
);

/* Step 4: Enable */
Advertising_Set_t adv_set = {
    .Advertising_Handle       = adv_handle,
    .Duration                 = 0x0000U,   /* süresiz */
    .Max_Extended_Advertising_Events = 0x00U,  /* sınırsız */
};
ret = aci_le_set_extended_advertising_enable(
    ENABLE,
    1U,           /* Num_Sets */
    &adv_set
);
```

### Multi-Handle Extended Advertising (Simultaneous)

```c
/* Eş zamanlı 2 advertising set: connectable + non-connectable beacon */
Advertising_Set_t sets[2] = {
    { .Advertising_Handle = 0x00U, .Duration = 0, .Max_Extended_Advertising_Events = 0 },
    { .Advertising_Handle = 0x01U, .Duration = 0, .Max_Extended_Advertising_Events = 0 },
};

/* Set 0: connectable, 2M secondary */
aci_le_set_extended_advertising_parameters(0x00U, ADV_EVT_PROP_CONNECTABLE,
    160U, 160U, 0x07U, PUBLIC_ADDR, PUBLIC_ADDR, NULL, 0, 0, LE_1M_PHY, 0, LE_2M_PHY, 0, 0);

/* Set 1: non-connectable, non-scannable beacon */
aci_le_set_extended_advertising_parameters(0x01U, ADV_EVT_PROP_NONE,
    1600U, 1600U, 0x07U, PUBLIC_ADDR, PUBLIC_ADDR, NULL, 0, -50, LE_1M_PHY, 0, LE_1M_PHY, 1, 0);

aci_le_set_extended_advertising_enable(ENABLE, 2U, sets);
```

---

## XVI. Connection Parameters

### Throughput vs Latency Trade-off

```
Connection Interval (CI):
  Min: 7.5ms (6 units × 1.25ms)
  Max: 4000ms
  Her CI'da max 1 Data PDU (LE 1M) veya 2+ PDU (LE 2M, eğer destekleniyorsa)

Slave Latency (SL):
  Peripheral SL adet CI'yı atlayabilir
  0 = her CI'da cevap (max throughput)
  SL > 0 → güç tasarrufu, throughput azalır

Supervision Timeout (ST):
  Min: max(100ms, (1+SL) × CI × 2)
  Önerilen: max(6000ms, CI × 10)
```

### Bağlantı Parametre Güncelleme (L2CAP)

```c
/* Peripheral → Central: bağlantı parametre güncelleme isteği */
/* iOS: Core Bluetooth güncellemeyi 30s'ye kadar geciktirebilir */
/* Android: genellikle anında uygular */

tBleStatus ret = aci_l2cap_connection_parameter_update_req(
    connection_handle,
    6U,       /* Interval_Min: 7.5ms (en hızlı) */
    6U,       /* Interval_Max: 7.5ms */
    0U,       /* Peripheral_Latency: 0 = max throughput */
    500U      /* Timeout_Multiplier: 6250ms (500 × 10ms) */
);

/* HIGH THROUGHPUT — yüksek hız transferi için */
#define CI_HIGH_THROUGHPUT_MIN   6U    /*  7.5ms */
#define CI_HIGH_THROUGHPUT_MAX   6U    /*  7.5ms */
#define SL_HIGH_THROUGHPUT       0U    /* latency = 0 */
#define ST_HIGH_THROUGHPUT       500U  /* 6250ms */

/* LOW POWER — pil tasarrufu için */
#define CI_LOW_POWER_MIN   800U  /* 1000ms */
#define CI_LOW_POWER_MAX   1600U /* 2000ms */
#define SL_LOW_POWER       4U    /* 4 CI atlayabilir */
#define ST_LOW_POWER       600U  /* 6000ms */

/* Event: L2CAP connection update response */
void aci_l2cap_connection_update_resp_event(uint16_t conn,
                                             uint16_t result)
{
    if (result == 0x0000U) {
        /* Kabul edildi */
    } else if (result == 0x0001U) {
        /* Reddedildi — mevcut parametrelerde devam */
    }
}
```

### Platform Spesifik Davranış

```c
/* iOS Connection Parameter politikası:
   - iOS 6ms interval'a izin verir ANCAK yalnızca:
     a) BLE Audio akışı varsa
     b) HID profili kullanılıyorsa
     c) Özel Apple entitlement varsa
   - Normal uygulama: min 15ms (12 units) önerilir
   - 7.5ms kullanmak istiyorsan, Apple MFi programı gerekli */

/* Android:
   - 7.5ms kabul edilir çoğu cihazda
   - Qualcomm yongalı cihazlar: <15ms'yi reddedebilir
   - requestConnectionPriority(CONNECTION_PRIORITY_HIGH) = ~11.25ms */

/* Güvenli evrensel değerler (iOS + Android): */
#define CI_UNIVERSAL_MIN   12U   /* 15ms */
#define CI_UNIVERSAL_MAX   12U   /* 15ms */
#define SL_UNIVERSAL       0U
#define ST_UNIVERSAL       400U  /* 4000ms */
```

---

## XVII. Max Throughput

### Hız Formülü

```
LE 2M PHY, MTU=247, DLE=251, CI=7.5ms, SL=0:

Teori:
  Data PDU = 251 bytes
  Air time per PDU (LE 2M) = (8 + 251) × 8 / 2,000,000 = ~1.036ms
  + IFS (Inter Frame Space) = 0.15ms
  + Empty ACK PDU = ~0.2ms
  Effective per PDU = ~1.4ms

  Max PDU per CI (7.5ms) = 7.5 / 1.4 ≈ 5 PDU

  Throughput = 5 × (251-4) bytes × 8 / 7.5ms
             = 5 × 247 × 8 / 0.0075
             = ~1,317 Kbps

Gerçek (protocol overhead ile):
  ATT payload per PDU = MTU - 3 = 244 bytes
  Effective ≈ 800-1,000 Kbps (iOS ~700Kbps, Android ~900Kbps)
```

### Throughput Benchmark

| Konfigürasyon | Platform | Gerçek Throughput |
|---------------|----------|-------------------|
| 2M, MTU=247, CI=7.5ms | Android (good chip) | ~900 Kbps |
| 2M, MTU=247, CI=15ms | Android | ~600 Kbps |
| 2M, MTU=185, CI=15ms | iOS (realistic) | ~500 Kbps |
| 1M, MTU=247, CI=7.5ms | Android | ~450 Kbps |
| 1M, MTU=23, CI=30ms | Default (no opt) | ~10 Kbps |

### TX Buffer Yönetimi

```c
/* BlueNRG-355: limited HCI TX buffer — overflow yönetimi şart */
#define BLE_TX_BUFFER_SIZE    3U   /* tipik stack TX buffer count */

static uint8_t s_tx_pending = 0U;

/* ACI_GATT_TX_POOL_AVAILABLE_EVENT: buffer müsait olunca gelir */
void aci_gatt_tx_pool_available_event(uint16_t conn, uint16_t available_buffers)
{
    /* Buffer açıldı — bekleyen veriyi gönder */
    if (s_tx_pending > 0U) {
        s_tx_pending = 0U;
        send_next_chunk();
    }
}

/* Gönderme fonksiyonu: buffer dolunca flag set et */
bool try_send_chunk(uint16_t svc, uint16_t chr, const uint8_t *data, uint16_t len) {
    tBleStatus ret = aci_gatt_update_char_value_ext(svc, chr, 0x01U, len, 0, len, data);
    if (ret == BLE_STATUS_INSUFFICIENT_RESOURCES) {
        s_tx_pending = 1U;
        return false;  /* retry on aci_gatt_tx_pool_available_event */
    }
    return (ret == BLE_STATUS_SUCCESS);
}
```

---

## XVIII. Connection Drop Recovery

### Supervision Timeout vs Disconnect

```
Disconnect türleri:
  1. Explicit disconnect: peer HCI_DISCONNECT komutu gönderdi
     → hci_disconnection_complete_event(reason=0x13 or 0x16)
  2. Supervision Timeout: supervision_timeout süresi içinde paket yok
     → hci_disconnection_complete_event(reason=0x08)
  3. MIC failure: AES-CCM MIC doğrulama başarısız
     → reason=0x3D — nadiren, RF interference
  4. Connection Failed to be Established: timing sorunları
     → reason=0x3E

reason=0x08 (Connection Timeout) → RF sorunları → agresif reconnect
reason=0x13 (Remote User Terminated) → karşı taraf istedi → nazik reconnect
reason=0x22 (Unacceptable Connection Parameters) → param. güncelle ve yeniden dene
```

### Reconnect State Machine

```c
typedef enum {
    CONN_STATE_DISCONNECTED = 0,
    CONN_STATE_ADVERTISING  = 1,
    CONN_STATE_CONNECTED    = 2,
    CONN_STATE_RECONNECTING = 3,
} conn_state_t;

#define RECONNECT_FAST_INTERVAL_MS  100U  /* ilk 30s: 100ms adv */
#define RECONNECT_SLOW_INTERVAL_MS  1000U /* sonra: 1s adv */
#define RECONNECT_FAST_DURATION_S   30U
#define MAX_RECONNECT_ATTEMPTS      10U

static conn_state_t s_conn_state = CONN_STATE_DISCONNECTED;
static uint8_t      s_reconnect_count = 0U;
static uint32_t     s_disconnect_tick = 0U;
static uint8_t      s_disconnect_reason = 0U;
static uint16_t     s_last_conn_handle = 0xFFFFU;

void hci_disconnection_complete_event(uint8_t  status,
                                       uint16_t conn_handle,
                                       uint8_t  reason)
{
    s_conn_state = CONN_STATE_DISCONNECTED;
    s_disconnect_reason = reason;
    s_disconnect_tick = HAL_GetTick();

    if (reason == 0x13U || reason == 0x16U) {
        /* Karşı taraf bağlantıyı kapattı — yavaş reconnect */
        start_advertising(RECONNECT_SLOW_INTERVAL_MS);
    } else {
        /* Timeout veya RF sorunu — hızlı reconnect */
        start_advertising(RECONNECT_FAST_INTERVAL_MS);
        s_reconnect_count = 0U;
        s_conn_state = CONN_STATE_RECONNECTING;
    }
}

void hci_le_connection_complete_event(uint8_t  status,
                                       uint16_t conn_handle,
                                       /* ... */)
{
    if (status != 0x00U) {
        s_reconnect_count++;
        if (s_reconnect_count >= MAX_RECONNECT_ATTEMPTS) {
            /* Yeniden deneme bitti — uyku moduna geç */
            stop_advertising();
            enter_low_power();
            return;
        }
        start_advertising(RECONNECT_FAST_INTERVAL_MS);
        return;
    }
    s_conn_state = CONN_STATE_CONNECTED;
    s_reconnect_count = 0U;
    s_last_conn_handle = conn_handle;

    /* Yeniden bağlandı — PHY ve MTU negotiate et */
    if (s_disconnect_reason == 0x08U) {
        /* Timeout sonrası: daha uzun supervision timeout iste */
        aci_l2cap_connection_parameter_update_req(conn_handle,
            CI_UNIVERSAL_MIN, CI_UNIVERSAL_MAX, SL_UNIVERSAL, 600U);
    }
    aci_le_set_phy(conn_handle, 0x00U, 0x02U, 0x02U, 0x0000U);
}

/* Fast → Slow interval geçişi (zamanlayıcı ile) */
void reconnect_timer_cb(void) {
    if (s_conn_state != CONN_STATE_RECONNECTING) { return; }
    uint32_t elapsed = HAL_GetTick() - s_disconnect_tick;
    if (elapsed > RECONNECT_FAST_DURATION_S * 1000U) {
        /* Artık yavaş advertising */
        stop_advertising();
        start_advertising(RECONNECT_SLOW_INTERVAL_MS);
        s_conn_state = CONN_STATE_ADVERTISING;
    }
}
```

### Supervision Timeout Hesabı

```c
/* SPEC: Supervision Timeout > (1 + Peripheral_Latency) × CI × 2 */
/* Güvenli formül: */
static uint16_t calc_supervision_timeout(uint16_t ci_units, uint16_t sl) {
    /* ci_units: bağlantı interval (1.25ms birimi) */
    /* return: 10ms biriminde timeout */
    uint32_t min_ms = (1U + (uint32_t)sl) * (uint32_t)ci_units * 2U * 125U / 100U;
    uint32_t timeout_ms = MAX(min_ms + 1000U, 5000U);  /* min 5s, 1s ekstra */
    return (uint16_t)(timeout_ms / 10U);  /* 10ms birimi */
}
/* Örnek: CI=7.5ms (6 units), SL=0 → min=15ms → timeout=500 (5000ms) */
```

---

## XIX. iOS Kısıtlamaları

```c
/* iOS Core Bluetooth kısıtları (test edilmiş, iOS 16-17): */

/* 1. MTU: iOS maks 185 byte MTU talep eder (182 byte payload) */
/*    Server 247 advertise etse bile iOS 185'i kabul etmez/öğrenmez */
/*    → payload hesabını 182 üzerinden yap, iOS'ta 244 gelmez */

/* 2. Connection interval: 15ms minimum önerilen */
/*    iOS 7.5ms'yi bağlantı kurulunca reddedebilir */
/*    "Preferred Connection Parameters" characteristic (GAPP §12.3): */
typedef struct __attribute__((packed)) {
    uint16_t preferred_conn_interval_min;  /* 0x000C = 15ms */
    uint16_t preferred_conn_interval_max;  /* 0x000C = 15ms */
    uint16_t preferred_peripheral_latency; /* 0x0000 */
    uint16_t preferred_supervision_timeout;/* 0x01F4 = 5000ms */
} pref_conn_params_char_t;

/* Bu characteristic'i GAP servisine ekle — iOS otomatik okur */

/* 3. Background mode: iOS arka planda advertising görmez (scan kısıtı) */
/*    Peripheral olarak çalışırken iOS foreground'da da advertise gör */

/* 4. Notification throttle: iOS 15+ saniyede maks ~1000 notification */
/*    Rate limitleme: 1ms delay between notifications değil, */
/*    aci_gatt_tx_pool_available_event bekle */

/* 5. iOS 13+ LE 2M PHY destekler (iPhone XS ve üzeri) */
/*    PHY update sonrası throughput ölçüm: ~500-700 Kbps tipik */

/* 6. RSSI tabanlı bağlantı yönetimi: */
/*    CoreBluetooth RSSI threshold yok; uygulama katmanında yönet */
int8_t rssi;
aci_hal_read_raw_rssi(&rssi);  /* dBm */
if (rssi < -90) {
    /* Zayıf sinyal — Coded PHY'ye geç veya bağlantı kalitesini izle */
}
```

---

## XX. Android Kısıtlamaları

```c
/* Android BLE kütüphane farkları: */

/* 1. MTU: Android uygulama requestMtu(247) çağırmak zorunda */
/*    Çağrılmazsa: default 23 byte MTU → 20 byte payload */
/*    Çağrılırsa: server 247 kabul eder → 244 byte payload */

/* 2. Bağlantı parametresi: requestConnectionPriority() */
/*    BALANCED = ~45ms, LOW_POWER = ~180ms, HIGH = ~11.25ms */
/*    Android 6.0+: HIGH priority 30 dakika sonra otomatik BALANCED'a döner */

/* 3. Qualcomm SoC (Snapdragon 800 serisi): 7.5ms kabul etmeyebilir */
/*    Güvenli min: 11.25ms (9 units) */

/* 4. Android fragment: WriteWithResponse vs WriteWithoutResponse */
/*    iOS her ikisini de mtu-3 ile keser */
/*    Android: WriteWithoutResponse için Android 12+: max 512 byte (internal fragmentation) */

/* 5. Notification vs Indication seç: */
/*    Indication: ACK var → throughput %30 düşük */
/*    Notification: ACK yok → max throughput, packet loss riski */
/*    OTA için: Notification + uygulama katmanında sıra numarası + NAK */

/* 6. BlueNRG-355 tarafında: karakteristik property doğru set et */
/* CHAR_PROP_NOTIFY → Notification (Android ve iOS) */
/* CHAR_PROP_INDICATE → Indication */
/* Her ikisi: subscriber CCCD yazar */

/* OTA için önerilen characteristic properties: */
#define OTA_DATA_CHAR_PROPS   (CHAR_PROP_WRITE_WITHOUT_RESP | CHAR_PROP_NOTIFY)
/* TX (device→phone): NOTIFY, max throughput */
/* RX (phone→device): WRITE_WITHOUT_RESP, max throughput */
```

---

## XXI. Flash Optimizasyonu

```c
/* BlueNRG-355 flash küçük → her byte önemli */

/* 1. BLE Manager debug string'leri kaldır */
/* ble_manager_conf.h: */
#define BLE_MANAGER_DEBUG       0    /* tüm printf devre dışı: ~2-5KB tasarruf */

/* 2. Kullanılmayan BLE Manager characteristic'leri devre dışı bırak */
/* Örnekler — gerekmeyen tümü kapat: */
/* #undef BLUE_STD_TERM_MANAGER  — terminal characteristic (~1KB) */
/* #undef BLUE_STD_ERR_MANAGER   — error characteristic (~1KB) */

/* 3. LTO (Link Time Optimization) — AC6/GCC */
/* CMakeLists.txt / Keil: */
/* AC6: -flto    GCC: -flto */
/* BlueNRG BLE stack (.a library): LTO desteklemez, sadece app kodu */

/* 4. Kullanılmayan HAL modülleri devre dışı */
/* bluenrg_lp_hal_conf.h: */
#define HAL_ADC_MODULE_DISABLED
#define HAL_I2C_MODULE_DISABLED
/* (proje gereksinimine göre) */

/* 5. String literal boyutu */
/* KÖTÜ: printf formatları */
printf("Error: connection timeout on handle 0x%04X, reason=0x%02X\r\n", h, r);
/* İYİ: tek karakter event log */
log_event(EVT_DISCONNECT, reason);   /* sadece struct yazma */

/* 6. OTA kodu: fonksiyon pointer + weak pattern */
/* Kullanılmayan OTA callback stub'ları = ~200 byte printf string */
/* BLE_MANAGER_DEBUG=0 ile elimine edilir */

/* 7. Flash section analizi */
/* AC6: .map dosyası → en büyük semboller */
/* arm-none-eabi-nm --size-sort build/app.elf | tail -30 */

/* Tipik BlueNRG-355 kod boyutları: */
/* BLE stack (binary):     ~90-110 KB */
/* BLE manager (app):      ~20-30 KB (debug açıksa) */
/* BLE manager (no debug): ~8-12 KB */
/* OTA fonksiyonelliği:    ~3-5 KB (uygulama mantığı) */
/* Toplam app hedefi:      [DÜZELTME] 256KB - 90KB = ~166KB (LP/355=256KB, 512KB DEĞİL) */
```

---

## XXII. Debug ve Ölçüm

### Throughput Ölçüm

```c
/* Byte sayacı + DWT timer */
static uint32_t s_bytes_sent = 0U;
static uint32_t s_meas_start_tick = 0U;

void throughput_start(void) {
    s_bytes_sent = 0U;
    s_meas_start_tick = HAL_GetTick();
}

void throughput_on_sent(uint16_t len) {
    s_bytes_sent += len;
}

void throughput_report(void) {
    uint32_t elapsed_ms = HAL_GetTick() - s_meas_start_tick;
    if (elapsed_ms > 0U) {
        uint32_t kbps = (s_bytes_sent * 8U * 1000U) / elapsed_ms / 1000U;
        /* kbps değerini UART veya BLE term karakteristiğine gönder */
    }
}
```

### ACI Event Logging (Flash etkin)

```c
/* Minimal event log — sadece type + timestamp */
typedef struct {
    uint32_t tick;
    uint8_t  event_type;
    uint8_t  param;
} ble_log_entry_t;

#define LOG_SIZE 32U
static ble_log_entry_t s_log[LOG_SIZE];
static uint8_t s_log_idx = 0U;

static void log_evt(uint8_t type, uint8_t param) {
    s_log[s_log_idx].tick       = HAL_GetTick();
    s_log[s_log_idx].event_type = type;
    s_log[s_log_idx].param      = param;
    s_log_idx = (s_log_idx + 1U) % LOG_SIZE;
}

/* Kullanım: */
/* log_evt(0x01, reason);   // disconnect */
/* log_evt(0x02, tx_phy);   // PHY update */
/* log_evt(0x03, s_eff_mtu); // MTU set */
```

---

## XXIII. DMA Kullanımı

> BlueNRG-355 (Cortex-M0+): M0+ çekirdeğinde D-cache yok → cache coherency sorunu yok.
> Ancak DMA konfigürasyon hataları ve BLE stack DMA çakışması kritik.

### BlueNRG-355 DMA Mimarisi

```c
/* BlueNRG-355 DMA kanalları (sınırlı):
   - DMA1: 8 kanal
   - Her kanal: REQUEST seçimi zorunlu (multiplexer ile)
   - Kanallar paylaşımlı — BLE stack bazı kanalları dahili kullanır

   ⚠ KRİTİK: BLE radio DMA kanalları — uygulama tarafından kullanılamaz
   BLE stack, DMA kanallarını otomatik tahsis eder
   Uygulama DMA kanalı seçerken stack belgelerine bak */

/* UART DMA TX — tipik konfigürasyon */
void uart_dma_init(void) {
    LL_DMA_InitTypeDef dma_cfg = {0};

    /* BlueNRG-355: USART1_TX → DMA1_Channel1, Request=5 (örnek) */
    dma_cfg.PeriphOrM2MSrcAddress  = LL_USART_DMA_GetRegAddr(USART1, LL_USART_DMA_REG_DATA_TRANSMIT);
    dma_cfg.MemoryOrM2MDstAddress  = (uint32_t)uart_tx_buf;
    dma_cfg.Direction              = LL_DMA_DIRECTION_MEMORY_TO_PERIPH;
    dma_cfg.Mode                   = LL_DMA_MODE_NORMAL;
    dma_cfg.PeriphOrM2MSrcIncMode  = LL_DMA_PERIPH_NOINCREMENT;
    dma_cfg.MemoryOrM2MDstIncMode  = LL_DMA_MEMORY_INCREMENT;
    dma_cfg.PeriphOrM2MSrcDataSize = LL_DMA_PDATAALIGN_BYTE;
    dma_cfg.MemoryOrM2MDstDataSize = LL_DMA_MDATAALIGN_BYTE;
    dma_cfg.NbData                 = 0U;
    dma_cfg.PeriphRequest          = LL_DMAMUX_REQ_USART1_TX;  /* DMAMUX request */
    dma_cfg.Priority               = LL_DMA_PRIORITY_LOW;

    LL_DMA_Init(DMA1, LL_DMA_CHANNEL_1, &dma_cfg);
    LL_DMA_EnableIT_TC(DMA1, LL_DMA_CHANNEL_1);   /* transfer complete interrupt */
    LL_DMA_EnableIT_TE(DMA1, LL_DMA_CHANNEL_1);   /* transfer error interrupt */
}

/* M0+: cache yok → SCB_CleanDCache gerekmez */
/* Ancak: compiler reorder engelle — COMPILER_BARRIER() */
void uart_dma_send(const uint8_t *data, uint16_t len) {
    /* Buffer hazır — derleyici reorder engelle */
    __DMB();  /* Memory barrier: write buffer flush */

    LL_DMA_SetDataLength(DMA1, LL_DMA_CHANNEL_1, len);
    LL_DMA_SetMemoryAddress(DMA1, LL_DMA_CHANNEL_1, (uint32_t)data);
    LL_DMA_EnableChannel(DMA1, LL_DMA_CHANNEL_1);
    LL_USART_EnableDMAReq_TX(USART1);
}

void DMA1_Channel1_IRQHandler(void) {
    if (LL_DMA_IsActiveFlag_TC1(DMA1)) {
        LL_DMA_ClearFlag_TC1(DMA1);
        LL_DMA_DisableChannel(DMA1, LL_DMA_CHANNEL_1);
        LL_USART_DisableDMAReq_TX(USART1);
        uart_tx_done_cb();
    }
    if (LL_DMA_IsActiveFlag_TE1(DMA1)) {
        LL_DMA_ClearFlag_TE1(DMA1);
        /* DMA transfer error — handle */
    }
}
```

### BLE Stack DMA Çakışması

```c
/* BLE stack (BlueNRG-355 integrated radio):
   - Radio eventi işlerken CPU/DMA meşgul olabilir
   - hci_user_evt_proc() çağrısı sırasında DMA interrupt'ı engelleme
   - ACI komut gönderimi: stack internal DMA kullanır (HCI transport) */

/* YANLIŞ: ACI komutunu DMA ISR içinden çağır */
void DMA1_Channel2_IRQHandler(void) {  /* SPI RX complete */
    LL_DMA_ClearFlag_TC2(DMA1);
    /* YANLIŞ: ACI komutunu buradan çağırma */
    aci_gatt_update_char_value_ext(...);  /* YANLIŞ — stack re-entrancy riski */
}

/* DOĞRU: Flag set et, main loop veya task'tan çağır */
static volatile bool s_spi_rx_done = false;

void DMA1_Channel2_IRQHandler(void) {
    LL_DMA_ClearFlag_TC2(DMA1);
    s_spi_rx_done = true;  /* sadece flag */
}

void main_loop(void) {
    hci_user_evt_proc();  /* BLE event processing */

    if (s_spi_rx_done) {
        s_spi_rx_done = false;
        process_spi_rx_data();
        /* Şimdi ACI komutu güvenle çağırılabilir */
        aci_gatt_update_char_value_ext(...);
    }
}
```

### DMA Buffer Gereksinimleri (BlueNRG-355)

```c
/* M0+: D-cache yok → cache coherency sorunu yok */
/* AMA: DMA buffer alignment önemli (bazı periferik kısıtları) */

/* DOĞRU: 4-byte aligned DMA buffer */
static uint8_t uart_rx_buf[256] __attribute__((aligned(4)));
static uint8_t spi_tx_buf[64]  __attribute__((aligned(4)));
static uint8_t spi_rx_buf[64]  __attribute__((aligned(4)));

/* BLE notification data: ACI stack kopyası yapar → alignment gerekmez */
/* Ancak aci_gatt_update_char_value_ext() çağrısına giren data pointer: */
/* Stack bu pointer'ı HCI packet oluşturmak için kullanır — aligned tercih */

/* SPI DMA: full-duplex TX+RX eş zamanlı */
void spi_dma_xfer(const uint8_t *tx, uint8_t *rx, uint16_t len) {
    /* TX DMA: Memory → SPI DR */
    LL_DMA_SetMemoryAddress(DMA1, LL_DMA_CHANNEL_3, (uint32_t)tx);
    LL_DMA_SetDataLength(DMA1, LL_DMA_CHANNEL_3, len);
    LL_DMA_EnableChannel(DMA1, LL_DMA_CHANNEL_3);  /* TX */

    /* RX DMA: SPI DR → Memory */
    LL_DMA_SetMemoryAddress(DMA1, LL_DMA_CHANNEL_4, (uint32_t)rx);
    LL_DMA_SetDataLength(DMA1, LL_DMA_CHANNEL_4, len);
    LL_DMA_EnableChannel(DMA1, LL_DMA_CHANNEL_4);  /* RX */

    LL_SPI_EnableDMAReq_TX(SPI1);
    LL_SPI_EnableDMAReq_RX(SPI1);
}
```

### DMA + BLE Event Priority (NVIC)

```c
/* BLE stack interrupt'ı en yüksek öncelikte — DMA'nın üstünde */
/* BlueNRG-355 tipik NVIC konfigürasyonu: */

/* BLE radio event: priority 0 (en yüksek) */
NVIC_SetPriority(BLE_IRQn, 0U);
NVIC_EnableIRQ(BLE_IRQn);

/* DMA kanalları: priority 1 veya 2 */
NVIC_SetPriority(DMA1_Channel1_IRQn, 1U);
NVIC_EnableIRQ(DMA1_Channel1_IRQn);

/* UART/SPI: priority 2 */
NVIC_SetPriority(USART1_IRQn, 2U);
NVIC_EnableIRQ(USART1_IRQn);

/* ⚠ SysTick (HAL_GetTick): priority 15 (en düşük) */
/* BLE timing: SysTick'ten bağımsız — BLE stack kendi timer'ını kullanır */
```

### DMA ile BLE Throughput Optimizasyonu

```c
/* BLE notification loop: DMA tabanlı sensor okuma + immediate notification */

/* KÖTÜ: blocking sensor okuma + notification */
void sensor_loop(void) {
    uint8_t data[20];
    HAL_SPI_Receive(&hspi, data, 20, 10);  /* blocking 10ms */
    aci_gatt_update_char_value_ext(...);    /* notification gönder */
}
/* Problem: 10ms SPI bekleme → CI=7.5ms kaçırılır → throughput düşer */

/* İYİ: DMA SPI okuma → TC interrupt → notification */
static uint8_t s_sensor_buf[20] __attribute__((aligned(4)));
static bool    s_sensor_ready = false;

void sensor_dma_start(void) {
    spi_dma_xfer(dummy_tx, s_sensor_buf, 20U);  /* non-blocking */
}

void DMA1_Channel4_IRQHandler(void) {  /* SPI RX complete */
    s_sensor_ready = true;
}

void main_loop(void) {
    hci_user_evt_proc();

    if (s_sensor_ready) {
        s_sensor_ready = false;
        /* Doğrudan gönder — kopyalamaya gerek yok */
        aci_gatt_update_char_value_ext(svc, chr, 0x01U,
            20U, 0U, 20U, s_sensor_buf);
        sensor_dma_start();  /* hemen bir sonraki okumayı başlat */
    }
}
/* DMA pipeline: sensor okuma + BLE TX üst üste çalışır → max throughput */
```

### PHY + MTU Sequence Checklist

```
Bağlantı kurulunca doğru sıra:
□ hci_le_connection_complete_event → conn_handle kaydet
□ aci_le_set_data_length(251, 2120) → DLE aktive et
□ LE_SET_DATA_LENGTH_COMPLETE event bekle
□ aci_le_set_phy(0x02, 0x02) → 2M PHY iste
□ hci_le_phy_update_complete_event → PHY konfirme
□ aci_gatt_exchange_config() → MTU negotiate et
□ aci_att_exchange_mtu_resp_event → effective MTU hesapla
□ aci_l2cap_connection_parameter_update_req → CI=7.5ms (veya 15ms iOS için)
□ Veri göndermeye başla: aci_gatt_update_char_value_ext()
□ BLE_STATUS_INSUFFICIENT_RESOURCES → aci_gatt_tx_pool_available_event bekle
```

### UART DMA — Tam Uygulama (BlueNRG-355)

```c
/* BlueNRG-355 UART DMA: tam TX + RX circular double-buffer örneği */
/* UART tipik kullanım: debug/log çıkışı VEYA host MCU haberleşmesi */

#define UART_TX_BUF_SIZE  256U
#define UART_RX_BUF_SIZE  256U

/* 4-byte aligned — M0+ DMA alignment zorunlu */
static uint8_t s_uart_tx_buf[UART_TX_BUF_SIZE] __attribute__((aligned(4)));
static uint8_t s_uart_rx_buf[UART_RX_BUF_SIZE] __attribute__((aligned(4)));

/* TX state */
static volatile bool s_uart_tx_busy = false;
static uint16_t      s_uart_tx_len  = 0U;

/* RX circular write pointer (DMA günceller, CPU okur) */
static volatile uint16_t s_uart_rx_head = 0U;  /* DMA position */
static uint16_t          s_uart_rx_tail = 0U;  /* CPU read position */

/* -------------------------------------------------------
   TX: non-blocking, DMA ile
   Kuyruk yönetimi yoksa: busy döndür, caller tekrar dener
   ------------------------------------------------------- */
bool uart_tx_send(const uint8_t *data, uint16_t len)
{
    if (s_uart_tx_busy || len == 0U || len > UART_TX_BUF_SIZE) {
        return false;  /* busy veya overflow */
    }
    memcpy(s_uart_tx_buf, data, len);
    __DMB();  /* write buffer flush — M0+ için yeterli (D-cache yok) */

    s_uart_tx_busy = true;
    s_uart_tx_len  = len;

    LL_DMA_SetDataLength(DMA1, LL_DMA_CHANNEL_1, len);
    LL_DMA_SetMemoryAddress(DMA1, LL_DMA_CHANNEL_1, (uint32_t)s_uart_tx_buf);
    LL_DMA_EnableChannel(DMA1, LL_DMA_CHANNEL_1);
    LL_USART_EnableDMAReq_TX(USART1);
    return true;
}

/* TX Transfer Complete ISR */
void DMA1_Channel1_IRQHandler(void)
{
    if (LL_DMA_IsActiveFlag_TC1(DMA1)) {
        LL_DMA_ClearFlag_TC1(DMA1);
        LL_DMA_DisableChannel(DMA1, LL_DMA_CHANNEL_1);
        LL_USART_DisableDMAReq_TX(USART1);
        s_uart_tx_busy = false;
        /* Varsa sıradaki paketi tetikle (uygulama katmanında yap) */
    }
    if (LL_DMA_IsActiveFlag_TE1(DMA1)) {
        LL_DMA_ClearFlag_TE1(DMA1);
        s_uart_tx_busy = false;  /* hata — bırak, tekrar dene */
    }
}

/* -------------------------------------------------------
   RX: circular DMA — IDLE line interrupt ile sınır tespiti
   DMA sürekli döner; IDLE interrupt CPU'ya bildir
   ------------------------------------------------------- */
void uart_rx_dma_start(void)
{
    /* Circular mode: buffer dolunca başa döner — CPU geride kalırsa overrun */
    LL_DMA_SetDataLength(DMA1, LL_DMA_CHANNEL_2, UART_RX_BUF_SIZE);
    LL_DMA_SetMemoryAddress(DMA1, LL_DMA_CHANNEL_2, (uint32_t)s_uart_rx_buf);
    LL_DMA_EnableChannel(DMA1, LL_DMA_CHANNEL_2);
    LL_USART_EnableDMAReq_RX(USART1);

    /* IDLE line interrupt: burst sonunu tespit etmek için */
    LL_USART_EnableIT_IDLE(USART1);
}

/* UART IDLE ISR — paket tamamlandı */
void USART1_IRQHandler(void)
{
    if (LL_USART_IsActiveFlag_IDLE(USART1)) {
        LL_USART_ClearFlag_IDLE(USART1);

        /* DMA kaç byte yazdı? */
        uint16_t remaining = LL_DMA_GetDataLength(DMA1, LL_DMA_CHANNEL_2);
        uint16_t new_head  = UART_RX_BUF_SIZE - remaining;
        s_uart_rx_head = new_head;  /* volatile → CPU okuyacak */
        /* main loop'u uyandır — ACI'yi buradan ÇAĞIRMA */
    }
}

/* CPU tarafı — main loop'ta çağır */
uint16_t uart_rx_read(uint8_t *out, uint16_t max_len)
{
    uint16_t head = s_uart_rx_head;  /* volatile okuma */
    uint16_t tail = s_uart_rx_tail;
    uint16_t avail;

    if (head >= tail) {
        avail = head - tail;
    } else {
        avail = UART_RX_BUF_SIZE - tail + head;  /* wrap */
    }

    uint16_t to_read = (avail < max_len) ? avail : max_len;
    for (uint16_t i = 0U; i < to_read; i++) {
        out[i] = s_uart_rx_buf[(tail + i) % UART_RX_BUF_SIZE];
    }
    s_uart_rx_tail = (tail + to_read) % UART_RX_BUF_SIZE;
    return to_read;
}
```

#### UART DMA Tuzakları — BlueNRG-355

| Tuzak | Sonuç | Çözüm |
|-------|-------|-------|
| TX DMA bitmeden ikinci send | Buffer bozulması | `s_uart_tx_busy` flag kontrol |
| IDLE interrupt yerine TC interrupt | Son byte kaçırılır | IDLE + circular DMA kombine kullan |
| DMA ISR'dan ACI çağırma | BLE stack re-entrancy crash | Flag set et, main loop'ta işle |
| Circular RX'te CPU geride kalırsa | Silent overrun | Head - tail farkı monitör et |
| USART TC flag'ı temizlenmezse | Sonraki TX başlamaz | `LL_USART_ClearFlag_TC()` veya DMA konfigür |
| 16-bit olmayan DMA data size | Yanlış byte sayısı | BYTE mode zorunlu UART DMA'da |

---

## XXIV. Olmaz sa Olmaz (Protokol/App)

> BLE ürün geliştirirken sıkça atlanan ama üretim için kritik konular.

---

### A. BLE Security Manager — Pairing ve Bonding

```c
/* BLE 5.x Security Manager (SM) — 4 pairing modu */
/*
   Just Works:       0 doğrulama, MITM yok — sadece meşruiyet düşük cihazlar
   Passkey Entry:    6 haneli pin — kullanıcı girer veya cihaz gösterir
   Numeric Comparison: BLE 5.0+ LE SC — her iki taraf 6 haneli sayıyı karşılaştırır
   OOB (Out of Band): NFC/QR ile key exchange — en güvenli
*/

/* Stack init sırasında IO capability ve auth requirement ayarla */
void ble_security_init(void)
{
    /* IO capability: cihazın ne yapabildiği */
    /* 0x03 = NoInputNoOutput (Just Works zorunlu) */
    /* 0x04 = KeyboardDisplay (Passkey gir veya göster) */
    aci_gap_set_io_capability(IO_CAP_KEYBOARD_DISPLAY);

    /* Kimlik doğrulama gereksinimleri */
    aci_gap_set_authentication_requirement(
        BONDING,                    /* bonding: 0x01 = evet */
        MITM_PROTECTION_REQUIRED,   /* MITM: 0x01 = zorunlu */
        SC_IS_SUPPORTED,            /* LE Secure Connections: 0x02 */
        KEYPRESS_IS_NOT_SUPPORTED,  /* keypress notification */
        7U,                         /* min enc key size (bytes) */
        16U,                        /* max enc key size (bytes) */
        DONOT_USE_FIXED_PIN,        /* fixed pin kullanma */
        0U,                         /* fixed pin değeri (kullanılmaz) */
        PUBLIC_ADDR                 /* address type */
    );
}

/* Pairing başlatma (Peripheral initiates) */
void ble_request_pairing(uint16_t conn_handle)
{
    tBleStatus ret = aci_gap_slave_security_req(conn_handle);
    if (ret != BLE_STATUS_SUCCESS) {
        /* Central pairing'i reddetti — bağlantıyı kapat */
    }
}

/* Pairing event'leri */
void aci_gap_pass_key_req_event(uint16_t conn_handle)
{
    /* Passkey Entry modu: kullanıcıdan al veya sabit passkey gönder */
    uint32_t passkey = 123456U;  /* gerçekte: rastgele üret veya kullanıcıdan al */
    aci_gap_pass_key_resp(conn_handle, passkey);
}

void aci_gap_numeric_comparison_value_event(uint16_t conn_handle, uint32_t numeric_value)
{
    /* LE SC: kullanıcı her iki cihazda sayıyı karşılaştırır */
    /* UI'da göster, kullanıcı onaylarsa: */
    aci_gap_numeric_comparison_value_confirm_yesno(conn_handle, 0x01U);  /* 0x01=yes */
}

void aci_gap_pairing_complete_event(uint16_t conn_handle, uint8_t status, uint8_t reason)
{
    if (status == 0x00U) {
        /* Pairing başarılı — bond bilgisi otomatik kaydedildi (stack) */
        /* LTK, IRK, CSRK, peer address → NVM'ye yaz */
        save_bonding_info_to_nvm(conn_handle);
    } else {
        /* status=0x01: pairing failed, reason codes:
           0x01: PasskeyEntryFailed
           0x02: OOB Not Available
           0x03: AuthReqs Not Met
           0x04: ConfirmValueFailed */
    }
}
```

#### Bonding Bilgisi NVM'ye Kaydetme

```c
/* BlueNRG-355: stack bonded device bilgisini RAM'de tutar */
/* Reset sonrası kaybolmaması için NVM'ye manuel yaz */

typedef struct {
    uint8_t  peer_addr[6];
    uint8_t  peer_addr_type;
    uint8_t  ltk[16];
    uint8_t  irk[16];
    uint16_t ediv;
    uint8_t  rand[8];
    uint8_t  valid;
} bond_record_t;

#define MAX_BONDED_DEVICES  4U
static bond_record_t s_bonds[MAX_BONDED_DEVICES];

void save_bonding_info_to_nvm(uint16_t conn_handle)
{
    /* Stack'ten bonding bilgisini al */
    Bonded_Device_Entry_t entries[MAX_BONDED_DEVICES];
    uint8_t count = 0U;
    aci_gap_get_bonded_devices(&count, entries);

    /* Flash'a yaz — HAL_FLASH_Program ile */
    /* Production'da: AES-128 ile şifrele, CRC ile koru */
}

void restore_bonding_from_nvm(void)
{
    /* Boot'ta: flash'tan oku → stack'e yükle */
    /* aci_gap_configure_whitelist() ile whitelist'e ekle */
}
```

---

### B. GATT Profil Mimarisi

```c
/* GATT hiyerarşi: Profile → Service → Characteristic → Descriptor */
/*
   Service:         UUID ile tanımlı logical gruplandırma
   Characteristic:  Gerçek veri konteynerı — properties belirler
   Descriptor:      Characteristic metadata (CCCD, User Desc, Format)
   CCCD (0x2902):   Notify/Indicate aktif etmek için client yazar
*/

/* Servis oluşturma */
uint16_t s_svc_handle   = 0U;
uint16_t s_char_handle  = 0U;
uint16_t s_cccd_handle  = 0U;

void ble_profile_init(void)
{
    uint8_t svc_uuid[16] = { /* 128-bit custom UUID — little-endian */ };
    uint8_t chr_uuid[16] = { /* 128-bit custom UUID */ };

    /* Service ekle */
    Service_UUID_t svc = { .Service_UUID_128 = svc_uuid };
    aci_gatt_add_service(UUID_TYPE_128, &svc,
                         PRIMARY_SERVICE,
                         9U,               /* max attribute records */
                         &s_svc_handle);

    /* Characteristic ekle — notify özelliği ile */
    Char_UUID_t chr = { .Char_UUID_128 = chr_uuid };
    aci_gatt_add_char(s_svc_handle,
                      UUID_TYPE_128, &chr,
                      244U,                          /* max value len */
                      CHAR_PROP_NOTIFY | CHAR_PROP_READ,
                      ATTR_PERMISSION_NONE,
                      GATT_NOTIFY_ATTRIBUTE_WRITE,   /* write event */
                      10U,                           /* enc key size */
                      CHAR_VALUE_LEN_VARIABLE,
                      &s_char_handle);

    /* CCCD (0x2902) otomatik ekleniyor — aci_gatt_add_char_desc gerekmez */
    /* s_cccd_handle = s_char_handle + 2 (generic offset) */
}

/* CCCD yazma event'i — client notify'ı aktif/deaktif etti */
void aci_gatt_attribute_modified_event(uint16_t conn_handle,
                                        uint16_t attr_handle,
                                        uint16_t attr_data_len,
                                        uint8_t *attr_data)
{
    if (attr_handle == s_char_handle + 2U) {  /* CCCD offset */
        uint16_t cccd_val = (uint16_t)attr_data[0] | ((uint16_t)attr_data[1] << 8);
        if (cccd_val & 0x0001U) {
            /* Notify aktif — veri göndermeye başla */
            s_notify_enabled = true;
        } else {
            s_notify_enabled = false;
        }
    }
}
```

---

### C. Advertising Filter Policy ve Allow List

```c
/* Allow list (whitelist): sadece bilinen cihazlara bağlan */
/* Bonded cihazlar reconnect ederken çok önemli */

void ble_configure_allowlist(void)
{
    /* Allow list'i temizle */
    aci_gap_clear_security_db();   /* dikkatli: bonding bilgisini de siler */

    /* Bonded peer'ı allow list'e ekle */
    /* aci_gap_configure_whitelist() BlueNRG-LP stack v3.x */
    /* Peer address ve address type gerekli */
}

/* Advertising filter policy */
void start_advertising_with_filter(void)
{
    ADV_Filter_Policy_t filter_policy;

    if (s_bonded_device_count > 0U) {
        /* Sadece allow list'teki cihazlar bağlanabilir */
        filter_policy = ADV_FILTER_WHITE_LIST_FOR_ALL;
    } else {
        /* İlk bağlantı: herkese açık */
        filter_policy = ADV_NO_WHITE_LIST_USE;
    }

    aci_gap_set_undirected_connectable(
        ADV_INTERVAL_MIN, ADV_INTERVAL_MAX,
        PUBLIC_ADDR,
        filter_policy
    );
}

/* Directed advertising: bilinen peer'a doğrudan bağlan (daha hızlı) */
void start_directed_advertising(const uint8_t *peer_addr, uint8_t peer_addr_type)
{
    /* Directed ADV: 1.28s içinde bağlantı olmazsa timeout */
    /* Avantaj: connection event <3ms — normal ADV'den çok daha hızlı */
    aci_gap_set_directed_connectable(
        PUBLIC_ADDR,
        peer_addr_type,
        peer_addr,
        LE_1M_PHY
    );
}
```

---

### D. Güç Yönetimi — BLE Olayları Arası Uyku

```c
/* BlueNRG-355: BLE connection event'leri arasında MCU uyuyabilir */
/* LE 2M + CI=7.5ms → her 7.5ms'de radio aktif, arada CPU uyur */

/* BLE stack sleep API */
extern PowerSaveLevels App_PowerSaveLevel_Check(PowerSaveLevels level);

PowerSaveLevels App_PowerSaveLevel_Check(PowerSaveLevels level)
{
    /* Uygulama kodu uyku modunu veto edebilir */
    if (s_uart_tx_busy || s_sensor_pending) {
        return POWER_SAVE_LEVEL_RUNNING;  /* uyuma */
    }
    /* Stack önerilen seviye: POWER_SAVE_LEVEL_STOP_WITH_TIMER */
    return level;
}

/* Main loop içinde — BlueNRG-LP HAL sleep hook */
void main_loop(void)
{
    for (;;) {
        hci_user_evt_proc();

        /* Uygulama işi */
        app_tick();

        /* BLE stack sleep — otomatik wakeup ile */
        /* Stack, bir sonraki BLE event'e kadar MCU'yu durdurur */
        BLEPLAT_CpuPowerSave();
        /* Bu çağrı geri döndüğünde: BLE event veya başka interrupt */
    }
}

/* ⚠ Uyku öncesi kontrol listesi: */
/* □ UART TX tamamlandı mı? (DMA TC interrupt beklendi mi?) */
/* □ SPI işlemi bitti mi? */
/* □ Pending timer callback var mı? */
/* □ Flash yazma devam ediyor mu? */
/* □ ADC conversion başlatıldı mı? */
```

#### Bağlantı Event Timing

```
CI = 7.5ms (6 units)

|<------ 7.5ms ------>|<------ 7.5ms ------>|
| Radio TX/RX (~1ms)  | CPU sleep           | Radio TX/RX (~1ms)  | ...
|                     |<--- BLEPLAT_CpuPowerSave() burada uyur -->|

Ortalama aktif süre: ~%13 → güç tasarrufu %87
LE 2M PHY: radio aktif süresi biraz daha kısa (yüksek bit hızı)
```

---

### E. OTA Firmware Update Mimarisi

```c
/* [DÜZELTME] BlueNRG-LP/355 = 256 KB flash (512KB DEĞİL). Bu custom dual-bank
   layout illüstratiftir; 256 KB'de Bank/staging adresleri yeniden boyutlandırılmalı.
   ÜRETİM: kanonik ST OTA mimarisini kullan — Reset Manager / Service Manager (§VIII, OTA_btl.c). */
/* Bank 0: 0x10040000 — aktif firmware (illüstratif) */
/* Bank 1: 0x10060000 — OTA staging (256KB'de offset yeniden hesaplanmalı) */
/* (Kanonik bellek haritası: §II; kanonik OTA: §VIII) */

#define OTA_STAGING_BASE    0x10060000UL
#define OTA_STAGING_SIZE    (192U * 1024U)  /* 192KB */
#define OTA_MAGIC           0x4F544100UL    /* "OTA\0" */
#define OTA_CRC_POLY        0x04C11DB7UL

typedef struct __attribute__((packed)) {
    uint32_t magic;        /* OTA_MAGIC */
    uint32_t fw_size;      /* bytes */
    uint32_t crc32;        /* CRC32 of firmware */
    uint32_t version;      /* anti-rollback */
    uint16_t seq_total;    /* toplam paket sayısı */
    uint16_t chunk_size;   /* paket başına byte (max 244) */
} ota_header_t;

/* OTA Karakteristikleri */
/* Control Char:  UUID=... — client write → OTA komutları */
/* Data Char:     UUID=... — client write no-response → firmware chunk */
/* Status Char:   UUID=... — server notify → ilerleme % */

typedef enum {
    OTA_CMD_START    = 0x01U,  /* header gönder */
    OTA_CMD_CHUNK    = 0x02U,  /* firmware chunk */
    OTA_CMD_COMPLETE = 0x03U,  /* transfer bitti, CRC doğrula */
    OTA_CMD_ABORT    = 0x04U,  /* iptal et */
    OTA_CMD_APPLY    = 0x05U,  /* doğrulandı, apply et (reset) */
} ota_cmd_t;

typedef enum {
    OTA_STATUS_IDLE    = 0x00U,
    OTA_STATUS_READY   = 0x01U,  /* start kabul edildi */
    OTA_STATUS_ONGOING = 0x02U,  /* chunk'lar geliyor */
    OTA_STATUS_CRC_OK  = 0x03U,  /* CRC doğrulandı */
    OTA_STATUS_ERROR   = 0xFFU,
} ota_status_t;

static ota_status_t s_ota_status     = OTA_STATUS_IDLE;
static uint32_t     s_ota_offset     = 0U;
static uint16_t     s_ota_seq_recv   = 0U;
static ota_header_t s_ota_hdr;

/* Control char write handler */
void ota_handle_control(const uint8_t *data, uint16_t len)
{
    ota_cmd_t cmd = (ota_cmd_t)data[0];

    switch (cmd) {
        case OTA_CMD_START:
            if (len < sizeof(ota_header_t) + 1U) { ota_error(); return; }
            memcpy(&s_ota_hdr, &data[1], sizeof(ota_header_t));
            if (s_ota_hdr.magic != OTA_MAGIC) { ota_error(); return; }
            if (s_ota_hdr.fw_size > OTA_STAGING_SIZE) { ota_error(); return; }
            /* Flash staging area'yı sil */
            flash_erase_region(OTA_STAGING_BASE, s_ota_hdr.fw_size);
            s_ota_offset   = 0U;
            s_ota_seq_recv = 0U;
            s_ota_status   = OTA_STATUS_READY;
            ota_notify_status(OTA_STATUS_READY, 0U);
            break;

        case OTA_CMD_COMPLETE:
            /* CRC32 doğrula */
            if (ota_verify_crc()) {
                s_ota_status = OTA_STATUS_CRC_OK;
                ota_notify_status(OTA_STATUS_CRC_OK, 100U);
            } else {
                ota_error();
            }
            break;

        case OTA_CMD_APPLY:
            if (s_ota_status != OTA_STATUS_CRC_OK) { ota_error(); return; }
            /* Bootloader flag'ını set et, reset at */
            set_boot_bank(1U);
            HAL_NVIC_SystemReset();
            break;

        case OTA_CMD_ABORT:
            s_ota_status = OTA_STATUS_IDLE;
            break;

        default:
            break;
    }
}

/* Data char write handler — firmware chunk */
void ota_handle_data(const uint8_t *data, uint16_t len)
{
    if (s_ota_status != OTA_STATUS_READY && s_ota_status != OTA_STATUS_ONGOING) {
        return;
    }
    if (s_ota_offset + len > OTA_STAGING_SIZE) { ota_error(); return; }

    flash_write(OTA_STAGING_BASE + s_ota_offset, data, len);
    s_ota_offset += len;
    s_ota_seq_recv++;
    s_ota_status = OTA_STATUS_ONGOING;

    /* Her 10 chunk'ta bir ilerleme bildir */
    if ((s_ota_seq_recv % 10U) == 0U) {
        uint8_t pct = (uint8_t)((s_ota_offset * 100U) / s_ota_hdr.fw_size);
        ota_notify_status(OTA_STATUS_ONGOING, pct);
    }
}

static bool ota_verify_crc(void)
{
    /* CRC32 (IEEE 802.3 poly) staging area üzerinde hesapla */
    uint32_t crc = crc32_compute((uint8_t*)OTA_STAGING_BASE, s_ota_hdr.fw_size);
    return (crc == s_ota_hdr.crc32);
}
```

---

### F. BLE Stack Init — BLE_STACK_Init_Params_t

```c
/* BlueNRG-LP stack v3.x init — parametreler yanlışsa stack crash */

#include "bluenrg_lp_stack.h"

/* Static memory pool — heap kullanma */
static uint8_t s_ble_stack_buf[BLE_STACK_TOTAL_BUFFER_SIZE(
    /* max conn     */ 2U,
    /* ATT MTU      */ 247U,
    /* max services */ 5U,
    /* max chars    */ 20U,
    /* GATT DB size */ 512U
)];

void ble_stack_init(void)
{
    BLE_STACK_InitTypeDef params = {
        .BLEStartRamAddress    = s_ble_stack_buf,
        .TotalBufferSize       = sizeof(s_ble_stack_buf),
        .NumAttrRecords        = 20U,        /* toplam attribute sayısı */
        .MaxNumOfClientProcs   = 1U,         /* GATT client işlemleri */
        .NumOfLinks            = 2U,         /* max eş zamanlı bağlantı */
        .NumBlockCount         = 8U,         /* ATT PDU block sayısı */
        .ATT_MTU               = 247U,       /* server advertised MTU */
        .MaxConnEventLength    = 0xFFFFU,    /* max connection event length */
        .SleepClockAccuracy    = 500U,       /* ppm — HSE ile 100ppm mümkün */
        .NumOfBleLinks         = 2U,
        .IsDeepSleepEnabled    = 1U,         /* deep sleep aktif */
        .BleLinkLayerParams    = {
            .masterSleepClockAccuracy = 100U,  /* peer clock accuracy (worst case) */
        },
    };

    uint8_t ret = BLE_STACK_Init(&params);
    if (ret != BLE_STATUS_SUCCESS) {
        /* Init başarısız — büyük olasılıkla buffer çok küçük */
        /* BLE_STACK_TOTAL_BUFFER_SIZE macro'sunu kontrol et */
        Error_Handler();
    }
}

/* ⚠ Kritik parametreler: */
/* ATT_MTU: yanlışsa MTU negotiate başarısız olur */
/* SleepClockAccuracy: yanlışsa connection drop artar */
/* NumBlockCount: çok az → TX buffer yetersiz → INSUFFICIENT_RESOURCES hatası */
/* TotalBufferSize: macro hesabından küçük → immediate crash */
```

---

### G. ATT / GATT Hata Kodları

```c
/* aci_gatt_update_char_value_ext() dönüş değerleri */
/* BLE_STATUS_* makrolar: bluenrg_lp_types.h */

void ble_send_notification(uint16_t conn_handle, const uint8_t *data, uint16_t len)
{
    tBleStatus ret = aci_gatt_update_char_value_ext(
        conn_handle, s_svc_handle, s_char_handle,
        0x02U,  /* 0x01=notify, 0x02=indicate */
        len, 0U, len, data
    );

    switch (ret) {
        case BLE_STATUS_SUCCESS:
            break;  /* gönderildi */

        case BLE_STATUS_INSUFFICIENT_RESOURCES:
            /* TX buffer dolu — aci_gatt_tx_pool_available_event bekle */
            s_tx_pending = true;
            break;

        case BLE_STATUS_FAILED:
            /* CCCD aktif değil — client notify'ı enable etmedi */
            /* veya bağlantı yok */
            break;

        case BLE_STATUS_NOT_ALLOWED:
            /* Encryption required but not established */
            ble_request_pairing(conn_handle);
            break;

        case BLE_ERROR_UNKNOWN_CONNECTION_ID:
            /* Bağlantı kesildi — conn_handle geçersiz */
            s_conn_state = CONN_STATE_DISCONNECTED;
            break;

        default:
            /* 0x4E: Controller Busy — retry sonraki CI'da */
            break;
    }
}

/* ATT error codes (GATT protocol level) */
/*
   0x01: Invalid Handle
   0x02: Read Not Permitted
   0x04: Invalid PDU
   0x05: Insufficient Authentication
   0x06: Request Not Supported
   0x07: Invalid Offset
   0x08: Insufficient Authorization
   0x0F: Insufficient Encryption Key Size
   0x11: Insufficient Encryption
   0x80-0x9F: Application-defined error codes
*/
```

---

### H. RF Coexistence

```c
/* BlueNRG-355: 2.4GHz ISM bandı — Wi-Fi, Zigbee, 802.15.4 ile çakışma */

/*
   Frekans haritası (2.4GHz ISM):
   BLE Channel 37 (ADV): 2402 MHz ← Wi-Fi Ch1 (2412 MHz) yakın
   BLE Channel 38 (ADV): 2426 MHz ← Wi-Fi Ch6 (2437 MHz) yakın
   BLE Channel 39 (ADV): 2480 MHz ← Wi-Fi Ch11 (2462 MHz) yakın

   LE 2M PHY + DLE: daha uzun radio ocupancy → çakışma artar
   BLE Adaptive Frequency Hopping (AFH): otomatik aktif — çakışan kanallardan kaçınır
*/

/* AFH bilgilendirme — host, stack'e "bu kanallar meşgul" der */
void ble_notify_channel_map(void)
{
    /* 37 data kanalı için 5 byte bitmask */
    /* BIT set = kanal kullanılabilir, BIT clear = meşgul/engellenmiş */
    uint8_t channel_map[5] = { 0xFF, 0xFF, 0xFF, 0xFF, 0x1F };  /* tümü açık */

    /* Belirli kanalları kapat (Wi-Fi Ch1 = BLE Ch0-3 arası): */
    /* channel_map[0] &= ~0x0F;  kanallar 0-3 kapat */

    hci_le_set_host_channel_classification(channel_map);
    /* Stack bir sonraki connection update'te kanal haritasını günceller */
}

/* Co-existence pin (harici — bazı modüllerde): */
/* BLE_GRANT / WLAN_ACTIVE pinleri → time-division multiplexing */
/* BlueNRG-355: yazılım tabanlı coex — harici pin yok */
/* Çözüm: BLE + Wi-Fi aynı anda kullanılıyorsa CI'ı artır (daha az radio time) */

/* RSSI tabanlı link kalite monitörü */
static int8_t s_last_rssi = 0;

void ble_rssi_monitor(uint16_t conn_handle)
{
    int8_t rssi;
    hci_read_rssi(conn_handle, &rssi);
    s_last_rssi = rssi;

    /* RSSI eşikleri (tipik): */
    /* > -70 dBm: çok iyi */
    /* -70 .. -85 dBm: kabul edilebilir */
    /* < -85 dBm: zayıf — LE 1M PHY'ye düş (menzil kazanımı) */
    if (rssi < -85) {
        /* PHY'yi 1M'e düşür: daha uzun menzil, daha az throughput */
        aci_le_set_phy(conn_handle, 0x00U, 0x01U, 0x01U, 0x0000U);
    }
}
```

---

### XXIV. Olmaz sa Olmaz — Özet Kontrol Listesi

```
Üretim BLE uygulaması için minimum gereksinimler:

Güvenlik:
□ Pairing modu seçildi (Just Works değil — MITM için Passkey veya LE SC)
□ Bonding aktif — LTK NVM'ye kaydediliyor
□ Allow list — bonded peer dışında bağlantı reddediliyor
□ Encryption required karakteristik permission'a işlendi

GATT:
□ CCCD yönetimi — notify/indicate enable/disable doğru işleniyor
□ Characteristic value length — MTU ile tutarlı (244 byte max payload)
□ Service/char handle'ları statik başlatıldı, boot'ta önce profile init çalıştı

Güç:
□ BLEPLAT_CpuPowerSave() main loop'ta çağrılıyor
□ Uygulama wake-up nedeni (uart, timer, interrupt) POWER_SAVE_LEVEL_RUNNING veto ediyor
□ SleepClockAccuracy doğru ayarlandı (HSE kalibre edildi)

OTA:
□ CRC32 doğrulaması staging area üzerinde yapılıyor
□ Magic + version anti-rollback kontrolü var
□ Flash erase/write hataları ele alınıyor
□ OTA sırasında IWDG besleniyor (erase uzun sürebilir)

Stack Init:
□ BLE_STACK_TOTAL_BUFFER_SIZE macro'su doğru parametrelerle hesaplandı
□ ATT_MTU stack init'te 247 set edildi
□ NumBlockCount yeterliliği test edildi (TX buffer overflow yok)

RF:
□ hci_le_set_host_channel_classification() Wi-Fi kanallarına göre ayarlandı
□ RSSI monitörü — zayıf link tespiti ve PHY düşürme
□ BLE_GRANT/WLAN_ACTIVE coex pini varsa konfigüre edildi
```
