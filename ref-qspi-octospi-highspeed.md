# STM32 QSPI / OCTOSPI Yüksek Hız Sorunları ve Çözümleri

Kaynak: ST Community, AN5050 (Rev 13, Mar 2026), saha deneyimi

---

## Hızlı Tanı: "Düşük hızda çalışıyor, yüksekte bozuluyor"

```
Semptom → Olası kök neden
────────────────────────────────────────────────────────────────
Veri bozulması (0x88, 0xFF sabit) → Dummy cycle yanlış / sample shift eksik
Verify pass, boot zıpladı        → XIP'te cache/MPU uyumsuzluğu veya dummy cycle
Memory-mapped okunan veri yanlış → GPIO hızı düşük (Low speed) veya SSHIFT yok
AutoPolling timeout              → Prescaler tek sayı (even zorunlu bazı serilerde)
>40 MHz'de iletişim kesildi      → Delay block (DLYB) ayarlanmamış
1V8 supply'da daha erken bozulur → I/O compensation cell etkin değil
```

---

## 1. Frekans Sınırları — Gerçekçi Üst Limitler

| STM32 Serisi | QSPI / OCTOSPI maks (pin) | Pratik güvenli limit | Not |
|---|---|---|---|
| F4, F7 (QUADSPI) | 90 MHz | 50–66 MHz | Trace >5 cm ise 40 MHz |
| H7 (OCTOSPI) | 110 MHz | 40–80 MHz | GPIO pin seçimi kritik |
| H7RS, U5 (XSPI) | 200 MHz (DDR) | 100 MHz STR | DLYB zorunlu >80 MHz |
| G0, G4 (QUADSPI) | 80 MHz | 40 MHz | Low-power, dikkat |
| L4+, L5 (OCTOSPI) | 100 MHz | 66 MHz | DLYB var, kullan |

> **Not:** H7'de IO8–IO15 pinleri (PC2, PI11, PF0/1 gibi) kullanılırsa her birine +3.5 ns timing cezası gelir. Bu pinlerden kaçın ya da frekansı düşür.

---

## 2. Sample Shift (SSHIFT) ve DHQC

```
STR (Single Transfer Rate) modu:
  SSHIFT = 1  → Veriyi saat sinyalinin yarı periyot sonrasında örnekle
  DHQC   = 0  → Devre dışı

DTR (Double Transfer Rate) modu:
  SSHIFT = 0  → Etkin değil (DTR'da anlamsız)
  DHQC   = 1  → Çıkışı 1/4 periyot kaydır; bellek tarafındaki hold ihlalini önler
               → DLYB ile birlikte kullan
```

```c
/* STR — sample shift ETKİN */
hospi.Init.SampleShifting = HAL_OSPI_SAMPLE_SHIFTING_HALFCYCLE;
hospi.Init.DelayHoldQuarterCycle = HAL_OSPI_DHQC_DISABLE;

/* DTR — DHQC ETKİN, sample shift KAPALI */
hospi.Init.SampleShifting = HAL_OSPI_SAMPLE_SHIFTING_NONE;
hospi.Init.DelayHoldQuarterCycle = HAL_OSPI_DHQC_ENABLE;
```

> Sample shift, H7'de "Delay Hold Quarter Cycle" değil — ikisi ayrı register bitleri. İkisini aynı anda açma.

---

## 3. Delay Block (DLYB) Kalibrasyonu

DLYB; PVT (Process-Voltage-Temperature) bağımlı analog bir gecikme hattıdır. Sıcaklık veya VCore değişirse yeniden kalibrasyon gerekir.

### 3a. Fast Tuning (hızlı, üretimde yeterli)

```c
/* DLYB lives in a SEPARATE peripheral driver (stm32hxx_hal_dlyb.c). The
 * correct API is HAL_DLYB_* with a DLYB_OCTOSPIx handle, NOT HAL_OSPI_DLYB_*
 * (which does not exist). See ST AN5050 §4.4 and STM32CubeH7 example
 * DLYB_OSPI_NOR_FastTuning. */
HAL_DLYB_CfgTypeDef dlyb_cfg;

/* Step 1: probe input clock period (auto-calibrates DLYB taps) */
if (HAL_DLYB_GetClockPeriod(DLYB_OCTOSPI1, &dlyb_cfg) != HAL_OK)
    Error_Handler();

/* Step 2: centre the sampling phase */
dlyb_cfg.PhaseSel /= 2U;
if (HAL_DLYB_SetConfig(DLYB_OCTOSPI1, &dlyb_cfg) != HAL_OK)
    Error_Handler();
```

### 3b. Exhaustive Tuning (kapsamlı; fırın/saha şartları için)

ST örnek kodu: `DLYB_OSPI_NOR_FastTuning` ve `DLYB_OSPI_PSRAM_Exhaustive` (STM32CubeH7 / STM32CubeU5 örnekleri).

```c
/* Exhaustive: tüm gecikme adımlarını tara, geçerli pencereyi bul */
uint8_t window_start = 0, window_end = 0;
for (uint8_t ph = 0; ph < MAX_PHASE; ph++) {
    dlyb_cfg.PhaseSel = ph;
    HAL_DLYB_SetConfig(DLYB_OCTOSPI1, &dlyb_cfg);
    if (ospi_verify_read() == HAL_OK) {
        if (!window_start) window_start = ph;
        window_end = ph;
    }
}
/* Pencerenin ortasına ayarla */
dlyb_cfg.PhaseSel = (window_start + window_end) / 2;
HAL_DLYB_SetConfig(DLYB_OCTOSPI1, &dlyb_cfg);
```

> **Uyarı:** VCore (voltaj ölçeği) veya çalışma sıcaklığı değiştiğinde DLYB yeniden kalibre edilmeli. CubeMX bug: DLYB konfigürasyonu V6.12.0'dan önce yanlış üretiliyordu — güncelle.

---

## 4. GPIO Hızı ve I/O Compensation Cell

### Yaygın hata: CubeMX GPIO hızını "Low" üretiyor

```c
/* YANLIŞ — CubeMX default, QSPI'da veri bozulmasına yol açar */
GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;

/* DOĞRU — tüm QSPI/OCTOSPI pinleri Very High olmalı */
GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
```

### Kısa trace / az yük varsa slew rate geri al

Kısa trace + düşük kapasitif yük → ringing riski:
```c
/* Ringing varsa bir kademe düşür (scope ile doğrula) */
GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;  /* Very High yerine */
```

> Kural: önce Very High ile başla. Scope'ta ringing görürsen High'a in.

### I/O Compensation Cell (zorunlu >50 MHz'de)

```c
/* main() içinde, SystemClock_Config() sonrasında */
HAL_EnableCompensationCell();

/* H7 için ayrıca DBGMCU üzerinden de kontrol et */
/* RCC_APB4ENR'de SYSCFGEN biti set edilmeli */
__HAL_RCC_SYSCFG_CLK_ENABLE();
HAL_SYSCFG_EnableIOSpeedOptimize(SYSCFG_IO_XSPI1_HSLV);  /* H7RS/U5 */
```

> 1.8V I/O supply kullanan tasarımlarda compensation cell daha da kritik — bu olmadan >40 MHz güvensiz.

---

## 5. Dummy Cycle Yapılandırması

Dummy cycle, flash'ın hıza göre ayarlanması gereken bekleme periyodudur. Yanlış değer → bozuk veri veya timeout.

### Flash Hız / Dummy Cycle Tablosu (yaygın çipler)

| Flash Chip | Komut | Frekans | Dummy Cycles |
|---|---|---|---|
| AT25SF128A | Fast Read Quad I/O (0xEB) | ≤85 MHz | 4 |
| AT25SF128A | Fast Read Quad I/O (0xEB) | ≤104 MHz | 6 |
| W25Q128/256 | Fast Read Quad I/O (0xEB) | ≤80 MHz | 4 |
| W25Q128/256 | Fast Read Quad I/O (0xEB) | ≤104 MHz | 6 |
| MX25L12835F | Fast Read Quad (0x6B) | ≤84 MHz | 8 |
| MT25QL256 | Fast Read Quad (0x6B) | ≤84 MHz | 10 |
| IS25LP128 | Fast Read Quad (0xEB) | ≤104 MHz | 6 |

```c
/* Örnek: AT25SF128A, 40 MHz STR, 4 dummy cycle */
OSPI_RegularCmdTypeDef cmd = {0};
cmd.Instruction         = 0xEB;     /* Fast Read Quad I/O */
cmd.InstructionMode     = HAL_OSPI_INSTRUCTION_1_LINE;
cmd.AddressMode         = HAL_OSPI_ADDRESS_4_LINES;
cmd.AddressSize         = HAL_OSPI_ADDRESS_24_BITS;
cmd.AlternateByteMode   = HAL_OSPI_ALTERNATE_BYTES_4_LINES;
cmd.AlternateBytes      = 0xFF;     /* mode bits — sürekli okuma için */
cmd.AlternateBytesSize  = HAL_OSPI_ALTERNATE_BYTES_8_BITS;
cmd.DummyCycles         = 4;        /* 40 MHz → 4 | >85 MHz → 6 */
cmd.DataMode            = HAL_OSPI_DATA_4_LINES;
```

> **Altın kural:** Dummy cycle'ı datasheet'ten al; tahmin etme. "Çalışıyor gibi" görünebilir ama çevre sıcaklığı veya supply değiştiğinde bozulur.

---

## 6. Prescaler — Tek/Çift Sayı Sorunu

Bazı STM32 serilerinde (özellikle F4/F7 QUADSPI) memory-mapped modda prescaler **çift sayı** olmalıdır.

```c
/* QUADSPI ve OCTOSPI prescaler alanlarının HER İKİSİ DE 0-based bölücüdür:
 *   ClockPrescaler = N  →  FCLK = kernel_clock / (N + 1)
 *
 * Erratum / bilinmesi gerekenler:
 *   - F4/F7 QUADSPI memory-mapped modda BAZI revizyonlarda prescaler'ın
 *     çift toplam-bölme değerine denk gelmesi (yani N tek olması) önerilir;
 *     bu bir hard kural değil, AutoPolling timeout görürsen prescaler'ı
 *     bir üste (daha düşük frekansa) çek.
 *   - H7 OCTOSPI DCR2.PRESCALER: 8-bit, FCLK = kernel / (PRESCALER+1).
 *     RM0433 §23.7.4 — formül ikisinde aynıdır. */

/* 200 MHz kernel, hedef 40 MHz: bölücü = 5 → ClockPrescaler = 4. */
hqspi.Init.ClockPrescaler = 4;  /* QUADSPI: 200/(4+1) = 40 MHz */
hospi.Init.ClockPrescaler = 4;  /* OCTOSPI: 200/(4+1) = 40 MHz, SAME formula */
```

> F7/H7'de AutoPolling timeout alıyorsan prescaler'ı bir üste (daha düşük frekansa) çek ve test et.

---

## 7. Memory-Mapped (XIP) Modu — Kısıtlamalar

```
Memory-Mapped moddayken YAPILMAZ:
  ✗ Flash'a yazma (write/erase)
  ✗ HAL_OSPI_Command / HAL_OSPI_Transmit çağrısı
  ✗ QUADSPI/OCTOSPI register değişikliği

Yazma öncesi ZORUNLU:
  1. HAL_OSPI_Abort(&hospi)        ← memory-mapped'ı iptal et
  2. Flash komutlarını gönder (write enable, erase, program)
  3. HAL_OSPI_MemoryMappedMode'a geri dön

XIP'te cache sorunları (H7 D-cache):
  - XIP bölgesi için MPU: strongly-ordered veya write-through/no-write-allocate
  - Flash'a yaz → geri dön → önce SCB_InvalidateDCache ile cache temizle
```

```c
/* XIP → yazma → XIP döngüsü */
HAL_OSPI_Abort(&hospi);
ospi_flash_write_enable();
ospi_flash_sector_erase(addr);
ospi_flash_wait_ready();
ospi_flash_page_program(addr, data, len);
ospi_enter_memory_mapped();         /* XIP'e geri dön */

/* D-cache invalidate — yazdığın bölgeyi kapsayacak şekilde */
SCB_InvalidateDCache_by_Addr((uint32_t *)OCTOSPI1_BASE + (addr & ~31U),
                              (len + 63U) & ~31U);
```

---

## 8. Voltaj Ölçeği (VOS) — H7 Özeli

H7'de maksimum OCTOSPI frekansı için CPU çekirdeği **VOS0** olmalı:

```c
/* main() içinde, SystemClock_Config() öncesinde */
HAL_PWREx_ConfigSupply(PWR_DIRECT_SMPS_SUPPLY);
__HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE0);
while (!__HAL_PWR_GET_FLAG(PWR_FLAG_VOSRDY));

/* VOS0 ile H7 → 480 MHz CPU, OCTOSPI ~110 MHz pin limitine ulaşılabilir */
/* VOS1 (default) ile H7 → OCTOSPI güvenli üst limit ~80 MHz */
```

---

## 9. PCB Layout Kuralları (Yüksek Hız)

```
✓ Trace empedansı ~50 Ω (differential pair yok, single-ended)
✓ CLK ve DATA traceları eşit uzunlukta (length matching ±5 mm)
✓ Trace uzunluğu < 5 cm (>80 MHz için < 3 cm önerilir)
✓ Flash altında ground plane sürekli olmalı
✓ Decoupling: 100 nF + 10 µF flash VCC pininin hemen yanına
✓ STM32 tarafında da 100 nF VDDIO yakınına

✗ Via gerektiren sinyal yönlendirmesinden kaçın (CLK ve IO0–3'te)
✗ Flash ve STM32 arasında başka yüksek hızlı sinyal geçirme
✗ Paralel trace: CLK yanında IO sinyalleri (crosstalk)
```

---

## 10. Hata Tanı Akışı

```
[Yüksek hızda çalışmıyor]
          │
          ▼
GPIO Speed = Very High?  → Hayır → Tüm QSPI/OCTOSPI pinlerini Very High yap
          │ Evet
          ▼
Dummy cycle datasheet'e uygun?  → Hayır → Doğru değeri ayarla
          │ Evet
          ▼
Sample Shift (SSHIFT=1 STR'da)?  → Hayır → Etkinleştir
          │ Evet
          ▼
I/O Compensation Cell etkin?  → Hayır → HAL_EnableCompensationCell()
          │ Evet
          ▼
DLYB mevcut ve kalibre edildi?  → Hayır → DLYB Fast Tuning uygula
          │ Evet
          ▼
Frekansı 40 MHz'e düşür, test et  → Çalışıyorsa → PCB layout / trace sorunu
          │ Yine bozuluyorsa
          ▼
Prescaler çift sayı mı?  → Hayır → Bir üst çift değere çek
          │ Evet
          ▼
Logic analyzer ile CLK ve IO0 capture al → Setup/hold ihlali var mı?
          │ Var
          ▼
Trace uzunluğu veya empedans sorunu — donanım revizyonu gerekebilir
```

---

## 11. Sık Yapılan Hatalar Özeti

| Hata | Semptom | Çözüm |
|------|---------|-------|
| GPIO Speed = Low | Veri bozulması, yüksek BER | Very High Speed |
| SSHIFT kapalı, STR mod | Intermittent read error | `SAMPLE_SHIFTING_HALFCYCLE` |
| Dummy cycle az | 0xFF veya 0x88 sabit veri | Datasheet'ten doğru değer |
| DLYB yok, >80 MHz | Ortama göre bozulma | DLYB Fast Tuning |
| Compensation cell yok | 1V8'de erken bozulma | `HAL_EnableCompensationCell()` |
| XIP'te write → corrupt | Hard fault veya yanlış kod | `HAL_OSPI_Abort()` + D-cache invalidate |
| Prescaler tek sayı | AutoPolling timeout | Çift sayıya çek |
| VOS1 ile >80 MHz | H7: intermittent crash | VOS0 etkinleştir |
| IO8–IO15 pinleri H7 | +3.5 ns ek gecikme | IO0–IO7 pinlerini kullan |
| CubeMX <6.12 DLYB | DLYB yanlış config | CubeMX güncelle |

---

## Kaynaklar

- [AN5050 Rev 13 (Mar 2026) — OCTOSPI/XSPI Getting Started](https://www.st.com/resource/en/application_note/an5050-getting-started-with-octospi-hexadecaspi-and-xspi-interface-on-stm32-mcus-stmicroelectronics.pdf)
- [ST Community: How to reach the maximum OCTOSPI frequency](https://community.st.com/t5/stm32-mcus/how-to-reach-the-maximum-octospi-frequency/ta-p/798294)
- [ST Community: How to calibrate the delay block with OCTOSPI](https://community.st.com/t5/stm32-mcus/how-to-calibrate-the-delay-block-with-the-octospi-interface/ta-p/748789)
- [ST Community: Overall FAQs for QUADSPI/OCTOSPI/HSPI/XSPI](https://community.st.com/t5/stm32-mcus/overall-faqs-for-quadspi-octospi-hspi-xspi/ta-p/670534)
- [ST Community: QSPI frequency sensitivity fix](https://community.st.com/t5/stm32-mcus-products/solved-how-can-i-fix-frequency-sensitivity-in-quadspi/td-p/111838)
- [ST Community: STM32H750 Quad SPI memory mapped mode error data 0x88](https://community.st.com/t5/stm32-mcus-products/stm32h750-quad-spi-flash-memory-mapped-mode-error-data-is-0x88/td-p/573330)
