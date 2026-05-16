# STM32 Gerçek Dünya Sorunları — Errata ve HAL Tuzakları

Datasheet'te yazmayan, tutorialda göremeyeceğin, ancak üretim firmware'inde saatlerce/günlerce debug ettiren sorunlar. Her madde: **Semptom → Kök Neden → Doğru Çözüm**.

---

## USB FS — 48MHz PLL Sorunu (Çok Yaygın)

**Semptom:** USB cihaz enumerate olmuyor, cihaz görünmüyor, bağlantı kesiliyor.

**Kök neden:** USB FS fiziksel katmanı kesinlikle 48MHz ister. STM32 HAL USB sürücüsü PLL48CLK'ın 48.000.000 Hz (±500ppm) olduğunu varsayar. Bu sağlanmazsa USB başlatılır ama enumerate olmaz — hata kodu yoktur.

**Sorun:** HSE 8MHz değilse (örn. 16MHz, 25MHz kristal) PLLM/PLLN/PLLQ kombinasyonuyla 48MHz'e ulaşmak matematiksel olarak imkânsız olabilir.

```c
/* STM32F4/F7: PLL48CLK = HSE * PLLN / (PLLM * PLLQ) = 48MHz şart */
/* HSE=8MHz, PLLM=8, PLLN=336, PLLQ=7 → 48MHz ✓ */
/* HSE=25MHz, PLLM=25, PLLN=336, PLLQ=7 → 48MHz ✓ */
/* HSE=16MHz, PLLM=16, PLLN=336, PLLQ=7 → 48MHz ✓ */
/* !! HSE=12MHz, PLLM=12, PLLN=336, PLLQ=7 → 48MHz ✓ (ama SYSCLK hesabı değişir) */

/* STM32H7: USB clock = PLL1Q veya PLL3Q (seçim RCC_USBCLKSOURCE_PLL) */
/* CubeMX'te "USB Clock Mux" kısmını kontrol et — her zaman 48MHz olmalı */

/* STM32L4/G4/U5: HSI48 + CRS (Clock Recovery System) en güvenli çözüm */
RCC_OscInitTypeDef osc = {0};
osc.OscillatorType = RCC_OSCILLATORTYPE_HSI48;
osc.HSI48State     = RCC_HSI48_ON;
HAL_RCC_OscConfig(&osc);
/* CRS ile USB SOF'tan clock kitleme */
RCC_CRSInitTypeDef crs = {0};
crs.Prescaler    = RCC_CRS_SYNC_DIV1;
crs.Source       = RCC_CRS_SYNC_SOURCE_USB;
crs.ErrorLimitValue = 34;
HAL_RCCEx_CRSConfig(&crs);
```

**Çözüm sırası:**
1. CubeMX Clock Configuration ekranında USB PLL path'ini görsel olarak doğrula
2. Projedeki kristal frekansı ile 48MHz'in bölünebilirliğini hesapla
3. L4/G4/U5 ailesi için HSI48 + CRS kullan — PLL'ye bağımlılık yok
4. H7 için `HAL_RCCEx_GetPeriphCLKFreq(RCC_PERIPHCLK_USB)` ile çalışma zamanında kontrol et

---

## USB 3.3V VDD Gereksinimi

**Semptom:** USB 5V'dan beslenen sistemde USB çalışıyor, 3.3V'dan beslenince çalışmıyor veya enumerate olmak için 10+ saniye gerekiyor.

**Kök neden:** USB D+ pull-up direnci 1.5kΩ ile 3.3V arasında olmalı. Bazı STM32 ailelerinde VDD_USB pini 3.3V'dan ayrı beslenmeli. STM32H7'de VDDUSB = 3.3V zorunlu (VDD_USB pinini 3.3V'a bağla, SYSCFG_PMCR.USB33DEN bitini ayarla).

```c
/* STM32H7: USB 3.3V power domain etkinleştir */
HAL_PWREx_EnableUSBVoltageDetector();
/* VCCA değil VDDUSB = 3.3V olmalı (schematic kontrolü) */
```

---

## GPIO Çıkış Hızı — 3.3V VDD Limitleri

**Semptom:** OCTOSPI/SPI/SDMMC sinyalleri scope'ta yuvarlak, setup/hold ihlali, veri bozulması.

**Kök neden:** STM32 GPIO output driver gücü VDD ve hız ayarına göre değişir. 3.3V'da MEDIUM speed 50MHz çıkış frekansına yetmez.

```
GPIO Output Speed vs VDD (STM32H7 — DS örneği):
┌──────────────┬──────────┬──────────┬──────────┐
│ OSPEEDR Ayar │ VDD=1.2V │ VDD=1.8V │ VDD=3.3V │
├──────────────┼──────────┼──────────┼──────────┤
│ LOW          │  4 MHz   │  8 MHz   │  8 MHz   │
│ MEDIUM       │ 25 MHz   │ 50 MHz   │ 50 MHz   │
│ HIGH         │ 50 MHz   │ 85 MHz   │ 85 MHz   │
│ VERY HIGH    │ 80 MHz   │120 MHz   │100 MHz   │
└──────────────┴──────────┴──────────┴──────────┘

Not: Frekanslar max kapasitif yük (10 pF) ile, 50pF'da %30-40 düşer.
PCB trace > 10cm: VERY HIGH bile yetersiz kalabilir.
```

```c
/* OCTOSPI pinleri için VERY HIGH speed zorunlu (> 40MHz kullanımda) */
GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
/* Pull-up/down: OCTOSPI SCK pin için NOPULL, IO pinler için NOPULL */
```

**Pratik kural:** Peripheral clock / 2 > GPIO_MAX_FREQ ise sinyal bozulur.
Scope'ta signal integrity sorunları görünce ilk bakılacak yer GPIO speed.

---

## I2C Bus Hang — BUSY Biti Takılması

**Semptom:** `HAL_I2C_Master_Transmit()` `HAL_BUSY` döndürüyor, I2C tamamen donuyor, reset etmeden kurtulmuyor.

**Kök neden:** I2C slave cevap veremeden reset olursa, slave SCL cevabını beklerken veri bitini low'da tutar. Master BUSY görür ve START gönderemez.

**Yanlış çözüm:** HAL_I2C_Init() tekrar çağırmak (BUSY biti temizlenmez).

**Doğru çözüm — GPIO SCL toggle ile kurtarma:**
```c
void i2c_bus_recover(I2C_HandleTypeDef *hi2c, GPIO_TypeDef *scl_port, uint16_t scl_pin,
                     GPIO_TypeDef *sda_port, uint16_t sda_pin)
{
    /* 1. I2C peripheral'ı devre dışı bırak */
    __HAL_RCC_I2C1_FORCE_RESET();
    HAL_Delay(10);
    __HAL_RCC_I2C1_RELEASE_RESET();

    /* 2. SCL/SDA'yı GPIO output moduna al */
    GPIO_InitTypeDef g = {0};
    g.Mode  = GPIO_MODE_OUTPUT_OD;
    g.Pull  = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    g.Pin   = scl_pin;
    HAL_GPIO_Init(scl_port, &g);
    HAL_GPIO_WritePin(scl_port, scl_pin, GPIO_PIN_SET);

    /* 3. 9 SCL pulse — slave'i serbest bırak */
    for (int i = 0; i < 9; i++) {
        HAL_GPIO_WritePin(scl_port, scl_pin, GPIO_PIN_RESET);
        HAL_Delay(1);
        HAL_GPIO_WritePin(scl_port, scl_pin, GPIO_PIN_SET);
        HAL_Delay(1);
        /* SDA high oldu mu kontrol et — slave serbest kaldıysa */
        if (HAL_GPIO_ReadPin(sda_port, sda_pin) == GPIO_PIN_SET) break;
    }

    /* 4. STOP condition üret */
    HAL_GPIO_WritePin(sda_port, sda_pin, GPIO_PIN_RESET);
    HAL_Delay(1);
    HAL_GPIO_WritePin(scl_port, scl_pin, GPIO_PIN_SET);
    HAL_Delay(1);
    HAL_GPIO_WritePin(sda_port, sda_pin, GPIO_PIN_SET);
    HAL_Delay(1);

    /* 5. Pinleri AF moduna geri al ve I2C'yi yeniden başlat */
    g.Mode      = GPIO_MODE_AF_OD;
    g.Alternate = GPIO_AF4_I2C1;  /* gerçek AF değeri datasheet'ten */
    g.Pin       = scl_pin | sda_pin;
    HAL_GPIO_Init(scl_port, &g);
    HAL_I2C_Init(hi2c);
}
```

**Önleyici tedbir:** Her I2C transferine timeout koy, timeout sonrası `i2c_bus_recover()` çağır. `HAL_MAX_DELAY` kullanma.

---

## ADC Kalibrasyon Zorunluluğu

**Semptom:** ADC okumaları ±2-5% sapıyor, düşük voltajlarda (< 0.5V) doğrusallık kaybı, offset hatası.

**Kök neden:** STM32 ADC güç açılışında fabrika kalibrasyon değerini yükler ancak gain error drift yaşar. HAL_ADC_Init() kalibrasyonu tetiklemez.

```c
/* ZORUNLU: Her güç açılışında kalibrasyon */
HAL_ADCEx_Calibration_Start(&hadc1, ADC_CALIB_OFFSET, ADC_SINGLE_ENDED);

/* STM32H7: offset + linearity kalibrasyonu (çok daha doğru) */
HAL_ADCEx_Calibration_Start(&hadc1, ADC_CALIB_OFFSET_LINEARITY, ADC_SINGLE_ENDED);

/* Kalibrasyon sonrası en az 4 ADC clock bekle (datasheet §15.4) */
HAL_Delay(1);

/* VREF değişikliği sonrası (farklı Vref+ seçilirse) tekrar kalibrasyon şart */
```

**STM32H7 ADC errata ES0480 §2.1.3:** LBWM bit ayarlanmazsa 18-bit oversampling'de offset hatası oluşur.

---

## SDMMC / FatFS — 3.3V Hız Limiti

**Semptom:** SD kart 50MHz'de çalışıyor ama zaman zaman read/write hatası, kart çıkarılıp takıldığında sorun yok, frekansı düşürünce stabil.

**Kök neden:** SDMMC HS (High Speed) modu maksimum 50MHz'dir ve 3.3V sinyalizasyon gerektirir. SDR50 (100MHz), SDR104 (200MHz) modları 1.8V sinyal gerektirir. 3.3V'da 50MHz üstü kullanılamaz.

```
SD Hız Modları:
┌────────────┬─────────────┬───────────┐
│ Mod        │ Max Frekans │ Voltaj    │
├────────────┼─────────────┼───────────┤
│ Default    │  25 MHz     │  3.3V     │
│ High Speed │  50 MHz     │  3.3V     │
│ SDR50      │ 100 MHz     │  1.8V (!) │
│ SDR104     │ 208 MHz     │  1.8V (!) │
└────────────┴─────────────┴───────────┘
```

```c
/* FatFS diskio.c: 3.3V sistemde güvenli max clock */
#define SDMMC_CLK_TRANSFER  50000000UL  /* 3.3V'da max 50 MHz */
/* SDMMC_CLK_TRANSFER > 50MHz: sadece 1.8V sistemde, voltage switch gerekli */

/* Hız belirsizliği varsa konservatif başla: */
#define SDMMC_CLK_TRANSFER  25000000UL  /* %100 uyumlu, tüm kartlar */
```

---

## FDCAN — Filtre Yapılandırma Tuzağı

**Semptom:** FDCAN başlıyor, hata yok, ama hiçbir mesaj alınmıyor.

**Kök neden 1:** Global filtre ayarlanmadığında STM32 FDCAN varsayılan olarak eşleşmeyen tüm çerçeveleri REDDEDER. HAL_FDCAN_ConfigGlobalFilter() çağrılmazsa FIFO0/FIFO1 boş kalır.

```c
/* BU SATIRLAR OLMADAN mesaj almak imkânsız */
HAL_FDCAN_ConfigGlobalFilter(&hfdcan1,
    FDCAN_ACCEPT_IN_RX_FIFO0,   /* eşleşmeyen STD frame → FIFO0 */
    FDCAN_ACCEPT_IN_RX_FIFO0,   /* eşleşmeyen EXT frame → FIFO0 */
    FDCAN_REJECT,               /* remote STD → reject */
    FDCAN_REJECT);              /* remote EXT → reject */
```

**Kök neden 2:** NominalPrescaler hesabı yanlış saat kaynağına göre yapılıyor.
```c
/* FDCAN clock gerçekten ne? */
uint32_t fdcan_clk = HAL_RCCEx_GetPeriphCLKFreq(RCC_PERIPHCLK_FDCAN);
/* CubeMX'te gösterilen SYSCLK/PCLK değil — ayrı PLL1Q veya PCLK1 olabilir */
```

**Kök neden 3:** CAN transceiver TXD dominant timeout (TXD pin 0'da takılı kalırsa transceiver bus-off'a iter). STM32 TXD pin AF assignment yanlışsa bu olur.

---

## OCTOSPI / QSPI — Sample Shift ve Yüksek Hız Sorunları

**Semptom:** Flash okuma above 40MHz çalışıyor ama zaman zaman data yanlış, reboot sonrası farklı değer okunuyor.

**Kök neden:** OCTOSPI'de CLK-DATA gecikme uyumsuzluğu. PCB trace ve flash çıkış gecikmesi (tCO) nedeniyle yüksek frekanslarda veri setup zamanı ihlal ediliyor.

```c
/* CubeMX üretilen — genellikle eksik */
hospi1.Init.SampleShifting = HAL_OSPI_SAMPLE_SHIFTING_HALFCYCLE;  /* eklenmeli */
hospi1.Init.DelayHoldQuarterCycle = HAL_OSPI_DHQC_ENABLE;         /* H7: DTR için */

/* Flash write/erase sonrası MANDATORY cache temizliği */
SCB_InvalidateDCache_by_Addr((uint32_t *)0x90000000UL, FLASH_SIZE);
SCB_InvalidateICache();
```

STM32H7 errata ES0480 §2.4.1: OCTOSPI memory-mapped modunda DHQC (Delay Hold Quarter Cycle) bazı HCLK/OSPI clock oranlarında enable edilmeden çalışmıyor.

---

## Flash Programming — Cache ve SRAM Gereksinimleri

**Semptom:** `HAL_FLASH_Program()` `HAL_ERROR` döndürüyor, veya yazar ama veri yanlış, veya kilitlenme oluyor.

**Kök neden 1:** D-Cache açıkken internal flash'a yazmak tutarsız sonuç verir (M7).

```c
/* Flash yazma ÖNCESİ D-Cache kapat */
SCB_DisableDCache();
HAL_FLASH_Unlock();
/* ... FLASH write operations ... */
HAL_FLASH_Lock();
SCB_EnableDCache();
/* Cache invalidate — yeni flash içeriği okunabilsin */
SCB_InvalidateDCache();
```

**Kök neden 2:** Bootloader'dan çalışan flash yazma kodu, yazdığı flash bölgesinde çalışıyorsa hard fault.

```c
/* Flash yazma fonksiyonları SRAM'da çalışmalı (internal flash yazarken) */
__attribute__((section(".RamFunc"), noinline))
static HAL_StatusTypeDef flash_write_word(uint32_t addr, uint32_t data)
{
    return HAL_FLASH_Program(FLASH_TYPEPROGRAM_FLASHWORD, addr, data);
}
/* Linker script: .RamFunc → .data'ya kopyalanmalı */
```

**Kök neden 3:** STM32H7 flash write granularity 256 bit (32 byte). Daha küçük yazma FLASH_SR.OPERR'e yol açar.

```c
/* STM32H7: minimum write = FLASH_TYPEPROGRAM_FLASHWORD = 32 byte */
/* Buffer 32-byte aligned olmalı */
__attribute__((aligned(32))) uint8_t flash_buf[32];
```

---

## IWDG — LSI Frekans Varyasyonu

**Semptom:** IWDG timeout hesaplanan değerden %30-50 farklı. Reset düşündüğünden erken oluyor.

**Kök neden:** STM32 LSI osilatörü nominal 32kHz ama gerçekte 17kHz-47kHz arasında değişebilir (sıcaklık, voltaj, parçadan parçaya). IWDG prescaler/reload bu frekansa göre hesaplanıyor.

```c
/* LSI frekansını ölç: TIM ile capture */
uint32_t lsi_freq = measure_lsi_with_tim5();  /* gerçek frekans */

/* Hesaplama: konservatif timeout için LSI_MIN kullan */
#define LSI_MIN_HZ   17000UL   /* worst case */
#define IWDG_TIMEOUT_MS  1000U

/* prescaler=64, reload = LSI_MIN * timeout_ms / (prescaler * 1000) */
uint32_t reload = (LSI_MIN_HZ * IWDG_TIMEOUT_MS) / (64UL * 1000UL);
/* reload max 4095 — prescaler'ı buna göre ayarla */

/* Erken reset önleme: pet'i timeout süresinin %50'sinde yap */
#define IWDG_FEED_MS  (IWDG_TIMEOUT_MS / 2)
```

**Güvenli yaklaşım:** LPTIM + LSE (32.768kHz kristal, ±20ppm) ile watchdog — LSI yerine LSE kullan, frekans varyasyonu %0.01.

---

## STM32H7 DTCM — DMA Erişim Yasağı

**Semptom:** DMA transfer başarılı görünüyor (HAL_OK), ama alınan/gönderilen veri sıfır veya çöp.

**Kök neden:** STM32H7 DTCM (0x20000000-0x2001FFFF) CPU'ya özel bölge — DMA1, DMA2, BDMA erişemez. CubeMX default stack/heap DTCM'de olabilir.

```c
/* YANLIŞ: Stack veya global değişken DTCM'de, DMA buffer olarak kullanılıyor */
uint8_t rx_buf[256];   /* .bss → DTCM'de → DMA okuyamaz! */

/* DOĞRU: DMA buffer AXI SRAM'da (0x24000000) */
__attribute__((section(".dma_buffer"), aligned(32)))
uint8_t rx_buf[256];   /* linker .dma_buffer → AXI_SRAM */

/* Linker script'te: */
/* .dma_buffer (NOLOAD) : { *(.dma_buffer) } >AXI_SRAM */
```

**Test:** `(uint32_t)&rx_buf >= 0x24000000` kontrolü ile assertion ekle.

---

## HAL_Delay() — Debug'da Çalışıyor, Release'de Takılıyor

**Semptom:** -O0'da çalışıyor, -Os ile bootloopluyor veya belirli satırda takılıyor.

**Kök neden:** SysTick interrupt NVIC'de disable edilmiş veya HAL_Init() çağrılmadan HAL_Delay() kullanılıyor. Veya ISR içinde HAL_Delay() çağrısı (SysTick ISR'dan yüksek veya eşit öncelikte çalışan ISR içinde).

```c
/* KURAL: HAL_Delay() sadece SysTick'ten düşük öncelikli bağlamda */
/* ISR içinde HAL_Delay() → sonsuz döngü (SysTick gelmez) */

/* KURAL: NVIC_SetPriorityGrouping() çağrısı HAL_Init() ÖNCESİ ise HAL bozulur */
HAL_Init();  /* önce */
/* sonra NVIC priority group değiştirme — ama genellikle HAL'in kullandığını koru */

/* Doğru SysTick priority (FreeRTOS ile): */
HAL_NVIC_SetPriority(SysTick_IRQn, 15, 0);  /* en düşük — FreeRTOS scheduler'ın altında */
```

---

## HAL UART Receive DMA — Overrun ve Sonsuz Bekleme

**Semptom:** HAL_UART_Receive_DMA() sonrası callback hiç çağrılmıyor, veya ilk transfer sonrası ikinci transfer başlamıyor.

**Kök neden 1:** UART RX FIFO overflow (ORE flag). DMA tamamlanmadan veri gelirse ORE set olur, UART hata kesmesine girer, DMA durdurulur.

```c
/* ORE'yi disable et: DMA RX'te FIFO overflow error'ü görmezden gel */
__HAL_UART_DISABLE_IT(&huart1, UART_IT_ERR);
/* Veya: OVRDIS bit (STM32F3/L4/H7) */
huart1.Init.OverSampling = UART_OVERSAMPLING_16;
/* huart1.AdvancedInit.AdvFeatureInit |= UART_ADVFEATURE_RXOVERRUNDISABLE_INIT;
   huart1.AdvancedInit.OverrunDisable = UART_ADVFEATURE_OVERRUN_DISABLE; */
HAL_UART_Init(&huart1);
```

**Kök neden 2:** DMA çift tampon modunda HAL_UART_Receive_DMA() tekrar çağrılmıyor. Circular mode veya manuel yeniden başlatma gerekli.

```c
/* IDLE + DMA yöntemi — production-grade RX (kayan pencere) */
HAL_UARTEx_ReceiveToIdle_DMA(&huart1, rx_buf, sizeof(rx_buf));
/* Callback: HAL_UARTEx_RxEventCallback */
```

---

## STM32H7 Power Supply — VCAP ve SMPS

**Semptom:** MCU erratic reset, brownout resets, yüksek frekansta çalışmama.

**Kök neden:** STM32H7 internal LDO'su iç regülatöre (VCORE) için VCAP pinine kondansatör gerektirir. Datasheet minimum 2.2µF × 2 (her VCAP için) der, ancak PCB layout'ta unutulabiliyor.

```
Gereksinimler:
  VCAP1: 2.2µF (ceramic, 10V rating)
  VCAP2: 2.2µF (ceramic, 10V rating)
  Her VCAP pinine ayrı, MCU'ya yakın (< 5mm trace)

SMPS modu (H7B0, H730):
  VFBSM: 100nF + 1µF
  VDD_SMPS: 3.3V besleme
  SMPS etkinleştirme: HAL_PWREx_ConfigSupply(PWR_SMPS_1V8_SUPPLIES_LDO)

LDO modu ile SMPS karıştırma → brownout → erratic reset
Option byte PWR_CR3.SMPSEN MCU güvenilirliğini etkiler
```

---

## RCC HSE Bypass Modu — Osilatör Sorunları

**Semptom:** MCU HSE kristal ile çalışmıyor, HSE timeout hatası, sistem 8MHz HSI'da kalıyor.

**Kök neden:** PCB'de aktif osilatör (TCXO) kullanılmış ama CubeMX'te Crystal/Resonator seçili. Active oscillator = Bypass mode gerektirir.

```c
/* Crystal / Resonator (pasif kristal + load kapasitörler): */
RCC_OscInitStruct.HSEState = RCC_HSE_ON;        /* ← doğru */

/* Active oscillator (TCXO, VCTCXO — kendi clock'unu üretiyor): */
RCC_OscInitStruct.HSEState = RCC_HSE_BYPASS;    /* ← bypass modda doğru */
/* Bypass'ta OSC_OUT pini sürülmez — tristated kalır */
/* OSC_IN = clock input pini */
```

---

## STM32 Option Bytes — Geri Dönüşsüz Hatalar

**Semptom:** RDP=1 ayarlandı, artık debug bağlanamıyoruz, tüm flash içeriği silindi.

```
RDP (Readout Protection) seviyeleri:
  Level 0: Tam erişim (default, factory)
  Level 1: Flash okuma koruması — debug'da register okuma OK, flash dump yok
           Level 0'a geçiş: mass erase zorunlu (flash içeriği silinir!)
  Level 2: Tam kilit — DEBUG PORT KALICI KAPATILIR, geri dönüşsüz!
           JTAG/SWD tamamen devre dışı, mass erase bile çalışmaz
           !! Gerçek projede Level 2 son aşamada, test edilmiş firmware'de uygulanmalı

nBOOT_SEL (STM32G0, G4, C0):
  = 1 (default): BOOT0 pin dikkate alınır
  = 0: Boot mode sadece option bytes'tan (BOOT0 pin görmezden gelinir)
  Bu bit yanlış ayarlanırsa cihaz bootloader moduna giremez

FLASH_OPTCR.nBOOT0 (H7):
  = 1: BOOT0 pin HIGH → System Bootloader aktif
  = 0: Her zaman flash boot (BOOT0 pini önemsiz)
```

---

## STM32H7 Errata — Önemli Başlıklar (ES0480)

```
§2.1.1  AXIRAM veri bütünlüğü: Burst transfer + write buffer hatası
        → AXI matrix timeout ayarla (AXIRAM_AMSPCR)

§2.4.1  OCTOSPI: Yüksek frekansta DHQC gerekli
        → hospi.Init.DelayHoldQuarterCycle = HAL_OSPI_DHQC_ENABLE

§2.4.4  OCTOSPI memory-mapped mode: SON BYTE okuma AXI stall yapar
        → CPU/MDMA mem-mapped region'ın son byte'ını okuyunca AXI matrix
          takılır, CPU askıya alınır. Prefetch'li read'ler kolayca tetikler.
        → Workaround: mem-mapped region'ı bir cache-line altında deklare et
          (örn. 16MB flash için region'ı 16MB - 32B olarak ayarla); veya
          MPU ile son cache-line'ı non-accessible işaretle.
        → Symptom: işlem rastgele askıya alınıyor, breakpoint'le yakalanmaz.
        → Forum thread: community.st.com td-p/169513

OSPI HAL state-machine bug (ES değil, HAL bug):
        HAL_OSPI_MemoryMapped() bazen state'i geçirmiyor, return HAL_OK
        olduğu halde MM aktive olmamış oluyor.
        → Workaround: çağrı öncesi HAL_OSPI_Abort() + state reset
        → Symptom: read at 0x90000000 → bus fault (MM mode değil)
        → Forum thread: community.st.com td-p/586945

§2.5.1  FDCAN: TX buffer underflow düşük öncelikte oluşabilir
        → TX FIFO mode yerine TX Queue mode kullan

§2.9.1  Ethernet MAC: Checksum offload bazı paketlerde yanlış
        → Software checksum kullan, ETH_DMAOMR.TSF=1 set et

§2.3.1  FMC (NOR/SRAM): Burst mode bazı çevrim kombinasyonlarında hatalı
        → Burst mode devre dışı bırak veya timing parametrelerini artır

§2.2.1  ADC: LBWM bit olmadan 18-bit oversampling offset hatası
        → LBWM bit'i set et (ADC_CFGR2)
```

---

## Hızlı Teşhis Kontrol Listesi

Açıklanamayan davranış için ilk kontroller:

```
□ Peripheral çalışmıyor, hata kodu yok:
    → Global filtre / interrupt enable / clock enable kontrol et
    → HAL_RCCEx_GetPeriphCLKFreq() ile saat frekansını doğrula

□ -O0'da çalışıyor, -Os'de bozuluyor:
    → volatile eksikliği (ISR paylaşılan değişken)
    → DMA cache coherency (SCB_CleanDCache / SCB_InvalidateDCache)
    → __attribute__((used)) eksikliği (ISR/callback LTO tarafından silindi)

□ DMA veri sıfır / çöp:
    → Buffer adresi DTCM'de mi? (0x20000000) → AXI SRAM'a taşı
    → Cache clean/invalidate yapıldı mı?
    → DMA stream/channel/request doğru mu?

□ Reset döngüsü / erratic davranış:
    → VCAP kondansatörü var mı? (H7)
    → IWDG besleniyor mu? Pet interval LSI varyasyonunu hesaba katıyor mu?
    → Stack overflow? (RTX5: osThreadGetStackSize - osThreadGetStackSpace)
    → Option bytes yanlış? (nBOOT0, nBOOT_SEL)

□ USB enumerate olmuyor:
    → USB clock tam 48MHz mi? (HSI48 veya PLL48CLK)
    → VDD_USB = 3.3V bağlı mı?
    → D+ pull-up 1.5kΩ doğru konumda mı?

□ I2C / SPI veri bozuk:
    → GPIO speed VERY_HIGH mı? (> 20MHz peripheral clock için)
    → PCB trace uzunluğu ve kapasitans
    → I2C: BUSY takılı → 9 SCL pulse kurtarma
    → SPI: CPOL/CPHA slave ile eşleşiyor mu?

□ ADC okumaları saplı / sapmalı:
    → HAL_ADCEx_Calibration_Start() çağrıldı mı?
    → VREF+ gerilimi stabil mi? (ayrı filtre kondansatörü var mı?)
    → ADC sampling time sensör kaynak empedansına göre ayarlandı mı?
```