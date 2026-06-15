# BLE — BlueNRG-LP / BlueNRG-LPS SoC Reference

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Device architecture, memory map, power modes, errata workarounds, security-advisory content, OTA architecture, radio-timer model** here is authoritative — that is why this file exists. Sourced from ST datasheets, reference manuals, errata and application notes (catalog below).
> - **Inline HAL/LL/ACI code snippets** are illustrative. Verified against the **STSW-BNRGLP-DK v1.5.0** source (BLE Stack Library v3.2a). The API can drift between stack versions; for the canonical symbol at your SDK release confirm in your local DK tree or `gh search code <SymbolName> --owner=STMicroelectronics` — see §XI and [ref-st-github-map.md](ref-st-github-map.md).
> - **API-NAMING TRAP (read §V):** two independent things, don't conflate them. **(a)** ACI generation: old **BlueNRG-1/2/MS** ACI (`aci_gatt_add_serv`, `aci_gatt_update_char_value`, `aci_gatt_init`) vs the **BlueNRG-LP** ACI (`aci_gatt_srv_*` / `aci_gatt_clt_*`) — the DK v3.x already uses the new names. **(b)** Usage model: **standalone-SoC** stack tick `BLE_STACK_Tick()` vs **network-coprocessor host** tick `BTLE_StackTick()` (SimpleBlueNRG-LP_HCI).
> - **For generic BLE protocol topics** (PHY, MTU, throughput, connection params, iOS/Android quirks, GATT, pairing/bonding, RF coexistence) see the sister file [ref-ble-bluenrg355.md](ref-ble-bluenrg355.md) — this file does **not** duplicate them; it covers the SoC/silicon layer.
> - **For generic bootloader / IAP / OTA theory** the canonical checklist is in [ref-bootloader.md](ref-bootloader.md); the BlueNRG-specific OTA flow is §VIII here.

Platform: BlueNRG-LP & BlueNRG-LPS — standalone programmable BLE SoC (Arm Cortex-M0+, up to 64 MHz)
Radio: BlueNRG-LP = BLE 5.2 · BlueNRG-LPS = BLE 5.3 · +8 dBm TX · −97 dBm @1M / −104 dBm @125k · AoA/AoD
SDK: **STSW-BNRGLP-DK v1.5.0** (01-Dec-2023, son sürüm; BLE Stack Library **v3.2a**)
ACI = Application Command Interface (Bluetooth HCI + ST vendor extensions)

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

| Bölüm | Konu |
|-------|------|
| [I. Aile ve Part Numarası](#i-aile-ve-part-numarası) | LP vs LPS, order-code decode, silikon cut'ları |
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

---

## I. Aile ve Part Numarası

### I.1 Ailenin yeri

BlueNRG-LP ve BlueNRG-LPS, BlueNRG ailesinin **2. nesil "tek-yonga" (standalone, programlanabilir)** BLE SoC'leridir. Önceki nesil BlueNRG-1/-2 (Cortex-M0) yerine **Cortex-M0+ @ 64 MHz** kullanırlar. Bunlar bir host MCU'ya bağlanan harici BLE modülü (BlueNRG-M0/MS) değildir — uygulama kodu doğrudan SoC üzerinde çalışır.

| Cihaz | Çekirdek | BLE | Flash | RAM | Konumu |
|-------|----------|-----|-------|-----|--------|
| BlueNRG-LP  | Cortex-M0+ 64 MHz | 5.2 | 256 KB | 64 KB / 32 KB | Üst segment, zengin çevre birimi |
| BlueNRG-LPS | Cortex-M0+ 64 MHz | 5.3 | 192 KB | 24 KB (+4 KB PKA) | Küçük/ucuz, direction-finding odaklı |

> **BlueNRG-355 = BlueNRG-LP (AYNI SİLİKON).** BlueNRG-355 (ve -345), BlueNRG-LP ailesinin sipariş kodlarıdır — ayrı bir çip değil; bu dosyadaki **tüm** silikon/bellek/güç/errata/secure-boot içeriği BlueNRG-355'e birebir uygulanır. "BlueNRG-355" adı genelde *network coprocessor* (harici host'a HCI/ACI veren; DK'da `Projects/External_Micro/*_NWK`) konfigürasyonu için kullanılır. Throughput/PHY/MTU/protokol detayları için kardeş dosya [ref-ble-bluenrg355.md](ref-ble-bluenrg355.md); SoC katmanı (bu dosya) LP+LPS+355'i kapsar.

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

> Bağlantı/PHY/MTU/throughput state machine'leri ve ACI komut örnekleri için [ref-ble-bluenrg355.md](ref-ble-bluenrg355.md) (BlueNRG-355 ACI isimleriyle) — LP'de GATT için `aci_gatt_srv_*` / `aci_gatt_clt_*` kullan.

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

> Bu, mevcut [ref-ble-bluenrg355.md](ref-ble-bluenrg355.md) cihazlarını (BlueNRG-3x5yz) **de** etkiler — secure boot kullanan her LP/LPS/355 projesinde kontrol et.

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
