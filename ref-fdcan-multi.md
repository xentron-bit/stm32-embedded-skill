# Multi-FDCAN — STM32 (H7, G4, H5)

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, errata workarounds, protocol-spec content** here is authoritative — that is why this file exists.
> - **Inline HAL/CMSIS/peripheral code snippets** are illustrative. The HAL drifts between versions and parts. For the canonical version of any HAL symbol at your HAL release: `gh search code <SymbolName> --owner=STMicroelectronics --extension=c` — see [ref-st-github-map.md](ref-st-github-map.md) §8 for the full lookup procedure.
> - **CRITICAL bugs identified in the 2026-05-16 audit have been corrected** in this file, but verify against your own HAL version before copy-pasting.
> - **For bootloader / IAP / OTA topics** the canonical checklist + ARM KA001193 + AN5188/2606/3155/3156 references are in [ref-bootloader.md](ref-bootloader.md).


## Donanım Gerçekleri

```
STM32H730/H743 FDCAN instance'ları:
  FDCAN1  — APB1 bus, Message RAM paylaşımlı
  FDCAN2  — APB1 bus, Message RAM paylaşımlı
  FDCAN3  — APB1 bus, Message RAM paylaşımlı (H743'te var, H730'da yok)

STM32G4 (G431/G473/G474):
  FDCAN1, FDCAN2, FDCAN3 — hepsi APB1

STM32H5 (H563/H573):
  FDCAN1, FDCAN2          — APB1_2 bus

Kritik: Tüm FDCAN instance'ları TEK Message RAM'i paylaşır.
  H7   : 2560 words (10KB)
  G4   : 212 words  (848B) — çok kısıtlı
  H5   : 2560 words (10KB)
```

## Soru: Bit Timing Hesabı İçin Hangi Değerleri Bilmem Gerekiyor?

Kod yazmadan önce şunları sor:

```
□ Osilatör: HSE (external crystal) mı, HSI (internal) mı?
  → HSE ise frekansı kaç MHz? (8? 12? 16? 25?)
  → HSI ise hangi MCU? (H7=64MHz, G4=16MHz, F4=16MHz)

□ PLL yapılandırması:
  → HCLK kaç MHz? (H7 max 480MHz, G4 max 170MHz, H5 max 250MHz)
  → PCLK1 (APB1) kaç MHz? (FDCAN clock source)

□ CAN bit rate:
  → Nominal (Arbitration phase): 125/250/500 Kbit/s veya 1 Mbit/s?
  → CAN-FD Data phase kullanılıyor mu? Kaç Mbit/s?
  → İzole transceiver var mı? (propagation delay'i etkiler)

□ Sample point:
  → Automotive ISO 11898: 75–87.5% önerilir
  → CANopen: genellikle 87.5%
  → Özel gereksinim var mı?
```

## Bit Timing Formülü

```
FDCAN_CLK = PCLK1 (varsayılan) veya HSE veya PLL'den seçilebilir

Bir bit süresi:
  T_bit = 1 / BitRate

Time Quanta (TQ) süresi:
  T_q = (NominalPrescaler + 1) / FDCAN_CLK
        ↑ NOT: HAL'da 0=1, 1=2, yani Prescaler+1 = divisor

Toplam TQ sayısı:
  TQ_total = 1 + NominalTimeSeg1 + NominalTimeSeg2
             ↑ SYNC_SEG her zaman 1 TQ

Bit rate doğrulama:
  BitRate = FDCAN_CLK / ((Prescaler + 1) × TQ_total)

Sample Point (%):
  SP = (1 + NominalTimeSeg1) / TQ_total × 100

Örnek — STM32H7, PCLK1=120MHz, hedef 500Kbit/s, SP=80%:
  TQ_total hedefi = 120MHz / (Prescaler×500000)
  Prescaler=1 → TQ_total = 120000000 / (1×500000) = 240 → çok büyük
  Prescaler=12 → TQ_total = 120000000 / (12×500000) = 20 → ideal
  SP=80% → SP_seg = 20×0.80 = 16 → NominalTimeSeg1=15 (15+1+1=17≠20?)
  Düzeltme: 1 + NominalTimeSeg1 = 20×0.80 = 16 → NominalTimeSeg1=15
             NominalTimeSeg2 = 20 - 16 = 4
             SJW ≤ min(TimeSeg1, TimeSeg2) = 4 → SJW=4
```

## Osilatör Seçimi: HSE vs HSI

```
                    HSE (external crystal)    HSI (internal RC)
Doğruluk            ±20–50 ppm               ±1% (±10,000 ppm)
Tolerans (CAN-FD)   Excellent (8Mbit/s kadar) Marginal (500Kbit/s max)
Tolerans (Classic)  Excellent                 OK (±1% < ±2.5% limit)
Başlangıç süresi    ~1–10ms                  Anında
Güç                 +0.1–2mA (crystal)       0mA ek
CAN bus node uyumu  Tüm hızlar               Classic CAN max 500K önerilir

ISO 11898-1 osilatör toleransı limiti:
  df = 1 / (2 × (13×BitRate/NominalBitRate - 11)) × (1 - SP/100)
  Klasik CAN 500Kbit/s için df_max ≈ ±1.58% → HSI OK (barely)
  CAN-FD 2Mbit/s için df_max ≈ ±0.5% → HSI FAIL, HSE gerekli
```

## H7 Message RAM Bölümlendirme (3 Instance)

```c
/* H7 toplam Message RAM: 2560 words (10KB), 0x4000_AC00 base */
/* Her instance için ayrı aralık ayırmalısın */

/* Instance başına tipik dağılım (3 instance paylaşım): */
/*   FDCAN1: 0..849   (850 words)  */
/*   FDCAN2: 850..1699 (850 words) */
/*   FDCAN3: 1700..2559 (860 words) */

/* HAL yapılandırmasında StartAddress = RAM_BASE + offset × 4 */
#define FDCAN_MESSAGE_RAM_BASE  0x4000AC00UL
#define FDCAN1_RAM_OFFSET       0U
#define FDCAN2_RAM_OFFSET       850U
#define FDCAN3_RAM_OFFSET       1700U

/* Her instance için RAM hesaplama:
   Std Filter:    1 word/filter      → N_SF × 1
   Ext Filter:    2 words/filter     → N_EF × 2
   Rx FIFO0:      18 words/element   → N_RF0 × 18 (Classic) veya N×18+data
   Rx FIFO1:      18 words/element   → N_RF1 × 18
   Rx Buffer:     18 words/element   → N_RB × 18
   Tx Event FIFO: 2 words/element    → N_TEF × 2
   Tx Buffer:     18 words/element   → N_TB × 18

   Toplam = SF×1 + EF×2 + RF0×18 + RF1×18 + RB×18 + TEF×2 + TB×18
   Bu toplamı 2560/3 ≈ 853 altında tut (3 instance paylaşımında)
*/
```

## 3 FDCAN Instance Başlatma (H7)

```c
/* Önce sor:
   □ Her instance için FIFO mu, dedicated Rx Buffer mi?
   □ Hangi CAN ID aralıklarını filtrele?
   □ CAN-FD data phase kullanılacak mı?
   □ FDCAN clock source: PCLK1 mı, HSE mı?
   Bu değerlere göre aşağıdaki şablonu doldur.
*/

FDCAN_HandleTypeDef hfdcan1, hfdcan2, hfdcan3;

/* Bit timing için: PCLK1=120MHz, 500Kbit/s nominal, 2Mbit/s data, SP=80% */
#define FDCAN_NOM_PRESCALER   12U   /* 120MHz / 12 / 20TQ = 500Kbit/s */
#define FDCAN_NOM_TSEG1       15U   /* 1+15 = 16TQ → 80% SP */
#define FDCAN_NOM_TSEG2        4U   /* TQ_total = 20 */
#define FDCAN_NOM_SJW          4U

#define FDCAN_DAT_PRESCALER    3U   /* 120MHz / 3 / 20TQ = 2Mbit/s */
#define FDCAN_DAT_TSEG1       15U
#define FDCAN_DAT_TSEG2        4U
#define FDCAN_DAT_SJW          4U

static void fdcan_configure_timing(FDCAN_HandleTypeDef *hfdcan,
                                   FDCAN_Instance_t *inst)
{
    hfdcan->Init.NominalPrescaler    = FDCAN_NOM_PRESCALER;
    hfdcan->Init.NominalTimeSeg1     = FDCAN_NOM_TSEG1;
    hfdcan->Init.NominalTimeSeg2     = FDCAN_NOM_TSEG2;
    hfdcan->Init.NominalSyncJumpWidth = FDCAN_NOM_SJW;
    hfdcan->Init.DataPrescaler       = FDCAN_DAT_PRESCALER;
    hfdcan->Init.DataTimeSeg1        = FDCAN_DAT_TSEG1;
    hfdcan->Init.DataTimeSeg2        = FDCAN_DAT_TSEG2;
    hfdcan->Init.DataSyncJumpWidth   = FDCAN_DAT_SJW;
}

void fdcan1_init(void)
{
    hfdcan1.Instance                 = FDCAN1;
    hfdcan1.Init.ClockDivider        = FDCAN_CLOCK_DIV1;
    hfdcan1.Init.FrameFormat         = FDCAN_FRAME_FD_BRS;
    hfdcan1.Init.Mode                = FDCAN_MODE_NORMAL;
    hfdcan1.Init.AutoRetransmission  = ENABLE;
    hfdcan1.Init.TransmitPause       = DISABLE;
    hfdcan1.Init.ProtocolException   = ENABLE;
    fdcan_configure_timing(&hfdcan1, NULL);

    /* Message RAM — FDCAN1'e ayrılan bölge */
    hfdcan1.Init.MessageRAMOffset    = FDCAN1_RAM_OFFSET;
    hfdcan1.Init.StdFiltersNbr       = 8U;   /* standart ID filtre sayısı */
    hfdcan1.Init.ExtFiltersNbr       = 4U;   /* extended ID filtre sayısı */
    hfdcan1.Init.RxFifo0ElmtsNbr    = 8U;   /* FIFO0 element sayısı */
    hfdcan1.Init.RxFifo0ElmtSize    = FDCAN_DATA_BYTES_64;
    hfdcan1.Init.RxFifo1ElmtsNbr    = 0U;   /* FIFO1 kullanılmıyor */
    hfdcan1.Init.RxFifo1ElmtSize    = FDCAN_DATA_BYTES_8;
    hfdcan1.Init.RxBuffersNbr       = 0U;   /* dedicated buffer yok */
    hfdcan1.Init.TxEventsNbr        = 4U;
    hfdcan1.Init.TxBuffersNbr       = 0U;   /* Tx FIFO kullan */
    hfdcan1.Init.TxFifoQueueElmtsNbr = 4U;
    hfdcan1.Init.TxFifoQueueMode    = FDCAN_TX_FIFO_OPERATION;
    hfdcan1.Init.TxElmtSize         = FDCAN_DATA_BYTES_64;

    HAL_FDCAN_Init(&hfdcan1);
}
/* fdcan2_init / fdcan3_init: aynı yapı, farklı Instance + RAM offset */
```

## Rx FIFO vs Dedicated Rx Buffer — Seçim Rehberi

```
Seçim sorusu: "FIFO mu, Buffer mı?"

FIFO modu (RxFifo0 / RxFifo1):
  + Birden fazla farklı ID aynı FIFO'ya düşer
  + Herhangi bir frame gelince tek interrupt
  + RTOS task'ları için ideal (semaphore → process all)
  - Frame sırası FIFO ile korunur, ID bazlı sıralama yok
  - Overrun riski: FIFO dolarsa yeni frame düşer

Dedicated Rx Buffer:
  + Her buffer ID'ye özgü — frame garantili tutulur (overwrite yok)
  + Belirli bir ID için message lost riski sıfır
  + Gerçek zamanlı güvenlik kritik mesajlar için (safety msg)
  - Her buffer 1 frame tutar, poll veya interrupt ile okuma
  - Message RAM daha çok kullanır

Tavsiye:
  Normal veri trafiği → FIFO (işlem kolaylığı)
  Safety-critical ID (e.g., emergency stop 0x000) → Dedicated Buffer
```

## Filter Yapılandırması (Her Instance İçin)

```c
/* FDCAN filtreler: her instance kendi filter set'ine sahip */

void fdcan1_config_filters(void)
{
    FDCAN_FilterTypeDef f = {0};

    /* Standart ID range filter: 0x100–0x1FF kabul, geri kalan reddet */
    f.IdType       = FDCAN_STANDARD_ID;
    f.FilterIndex  = 0U;
    f.FilterType   = FDCAN_FILTER_RANGE;
    f.FilterConfig = FDCAN_FILTER_TO_RXFIFO0;
    f.FilterID1    = 0x100U;
    f.FilterID2    = 0x1FFU;
    HAL_FDCAN_ConfigFilter(&hfdcan1, &f);

    /* Global: eşleşmeyen frame'leri reddet */
    HAL_FDCAN_ConfigGlobalFilter(&hfdcan1,
        FDCAN_REJECT, FDCAN_REJECT,
        FDCAN_FILTER_REMOTE, FDCAN_FILTER_REMOTE);
}

void fdcan2_config_filters(void)
{
    FDCAN_FilterTypeDef f = {0};

    /* Extended ID exact match: sadece 0x18FF0001 kabul */
    f.IdType       = FDCAN_EXTENDED_ID;
    f.FilterIndex  = 0U;
    f.FilterType   = FDCAN_FILTER_DUAL;   /* dual = exact match */
    f.FilterConfig = FDCAN_FILTER_TO_RXFIFO0;
    f.FilterID1    = 0x18FF0001UL;
    f.FilterID2    = 0x18FF0001UL;
    HAL_FDCAN_ConfigFilter(&hfdcan2, &f);

    HAL_FDCAN_ConfigGlobalFilter(&hfdcan2,
        FDCAN_REJECT, FDCAN_REJECT,
        FDCAN_FILTER_REMOTE, FDCAN_FILTER_REMOTE);
}
```

## IRQ Yönlendirme — Her Instance Ayrı

```c
/* H7: Her FDCAN instance'ının kendi IT0 ve IT1 interrupt line'ı var */

void HAL_FDCAN_MspInit(FDCAN_HandleTypeDef *hfdcan)
{
    if (hfdcan->Instance == FDCAN1) {
        HAL_NVIC_SetPriority(FDCAN1_IT0_IRQn, 5, 0);
        HAL_NVIC_EnableIRQ(FDCAN1_IT0_IRQn);
    } else if (hfdcan->Instance == FDCAN2) {
        HAL_NVIC_SetPriority(FDCAN2_IT0_IRQn, 5, 0);
        HAL_NVIC_EnableIRQ(FDCAN2_IT0_IRQn);
    } else if (hfdcan->Instance == FDCAN3) {
        HAL_NVIC_SetPriority(FDCAN3_IT0_IRQn, 5, 0);
        HAL_NVIC_EnableIRQ(FDCAN3_IT0_IRQn);
    }
}

/* IRQ handler'ları — her instance için ayrı */
void FDCAN1_IT0_IRQHandler(void) { HAL_FDCAN_IRQHandler(&hfdcan1); }
void FDCAN2_IT0_IRQHandler(void) { HAL_FDCAN_IRQHandler(&hfdcan2); }
void FDCAN3_IT0_IRQHandler(void) { HAL_FDCAN_IRQHandler(&hfdcan3); }

/* Notifikasyon aktifleştirme */
void fdcan_start_all(void)
{
    uint32_t active_its = FDCAN_IT_RX_FIFO0_NEW_MESSAGE
                        | FDCAN_IT_ERROR_WARNING
                        | FDCAN_IT_ERROR_PASSIVE
                        | FDCAN_IT_BUS_OFF;

    HAL_FDCAN_ActivateNotification(&hfdcan1, active_its, 0);
    HAL_FDCAN_ActivateNotification(&hfdcan2, active_its, 0);
    HAL_FDCAN_ActivateNotification(&hfdcan3, active_its, 0);

    HAL_FDCAN_Start(&hfdcan1);
    HAL_FDCAN_Start(&hfdcan2);
    HAL_FDCAN_Start(&hfdcan3);
}
```

## RTOS Task Tasarımı (3 Instance)

```c
/* Her FDCAN instance'ı için ayrı osSemaphore ve task */

osSemaphoreId_t sem_fdcan1_rx, sem_fdcan2_rx, sem_fdcan3_rx;

/* ISR → semaphore pattern */
void HAL_FDCAN_RxFifo0Callback(FDCAN_HandleTypeDef *hfdcan, uint32_t RxFifo0ITs)
{
    if (hfdcan->Instance == FDCAN1) {
        osSemaphoreRelease(sem_fdcan1_rx);
    } else if (hfdcan->Instance == FDCAN2) {
        osSemaphoreRelease(sem_fdcan2_rx);
    } else if (hfdcan->Instance == FDCAN3) {
        osSemaphoreRelease(sem_fdcan3_rx);
    }
}

/* Task — FDCAN1 işleme */
void task_fdcan1(void *arg)
{
    FDCAN_RxHeaderTypeDef hdr;
    uint8_t data[64];

    for (;;) {
        /* 50ms timeout: periyodik kontrol + semaphore bekleme */
        osSemaphoreAcquire(sem_fdcan1_rx, 50U);

        while (HAL_FDCAN_GetRxFifoFillLevel(&hfdcan1, FDCAN_RX_FIFO0) > 0U) {
            HAL_FDCAN_GetRxMessage(&hfdcan1, FDCAN_RX_FIFO0, &hdr, data);
            fdcan1_process_message(&hdr, data);
        }
    }
}
/* task_fdcan2 ve task_fdcan3 aynı yapı */
```

## Bus-Off Kurtarma (Her Instance)

```c
/* Bus-Off: TX error counter > 255, node pasif → manuel kurtarma gerekir */
/* Güvenlik kritik uygulamalarda AUTOMATIC recovery YASAK (SAE J1939) */

void HAL_FDCAN_ErrorStatusCallback(FDCAN_HandleTypeDef *hfdcan, uint32_t ErrorStatusITs)
{
    FDCAN_ProtocolStatusTypeDef status;
    HAL_FDCAN_GetProtocolStatus(hfdcan, &status);

    if (status.BusOff) {
        /* Log et, uygulama katmanını bildir — DOĞRUDAN kurtarma yapma */
        if (hfdcan->Instance == FDCAN1) {
            log_error(ERR_CAN1_BUSOFF);
            osEventFlagsSet(evt_can, CAN1_BUSOFF_FLAG);
        } else if (hfdcan->Instance == FDCAN2) {
            log_error(ERR_CAN2_BUSOFF);
            osEventFlagsSet(evt_can, CAN2_BUSOFF_FLAG);
        }
        /* Uygulama karar verir: ne zaman kurtarma yapılacak */
    }
}

/* Uygulama kurtarma prosedürü */
void can_recover_busoff(FDCAN_HandleTypeDef *hfdcan)
{
    HAL_FDCAN_Stop(hfdcan);
    osDelay(100U);             /* bus sakinleşmesi için bekle */
    HAL_FDCAN_Start(hfdcan);
    /* 128 recessive bit gönderilince node otomatik error-active'e döner */
}
```

## CAN-FD TDC (Transceiver Delay Compensation) Kalibrasyonu

```c
/* CAN-FD data phase > 2Mbit/s için transceiver propagation delay'i
 * kompanse etmek zorunludur, yoksa sample point kayar → frame error */

/* TDC nedir:
   TX line → transceiver delay → CAN bus → geri dönüş → RX line
   Bu gecikme tipik 50–300 ns arasında (transceiver datasheet'ten bak)

   TDC Offset = gecikme / T_q_data_phase (data phase TQ süresi)

   Örnek: TXD prop. delay = 150ns, Data TQ = 500ns (2Mbit/s, Prescaler=3, 120MHz)
   TDC_offset = 150/500 = 0.3 → değer 1 (minimum, HAL 0=kapalı) */

/* TDC konfigürasyonu */
FDCAN_TdcTypeDef tdc_cfg = {
    .TdcMode   = FDCAN_TDC_SP_1,   /* Secondary Sample Point: 1 TQ */
    .TdcOffset = 1U,                /* gecikme TQ sayısı */
};

/* FDCAN Init sonrası, Start öncesi */
HAL_FDCAN_ConfigTxDelayCompensation(&hfdcan1, &tdc_cfg);
HAL_FDCAN_EnableTxDelayCompensation(&hfdcan1);

/* TDC pratik ölçüm:
   1. TDC kapalıyken 4Mbit/s+ gönder → frame error sayısını izle
   2. TDC_Offset'i 1'den başlayıp artır → error sıfırlandığında dur
   Veya: transceiver datasheet'ten TXD-to-RXD prop delay al */
```

## HSI Dahili Osilatör Kalibrasyonu

```c
/* HSI classic CAN için yeterli (±1% < ±1.58% limit), ama CAN-FD için yetersiz.
 * HSI'ı factory trim üzerinden ince ayar yapabilirsin. */

/* HSI trim değerini oku */
uint32_t hsitrim = (RCC->ICSCR >> RCC_ICSCR_HSITRIM_Pos) & 0x7FU;

/* ±1% hata: 16MHz × 0.01 = ±160KHz — 500Kbit/s CAN için sınırda
 * CAN-FD 2Mbit/s → df_max ≈ ±0.5% — HSI ile güvenilir değil
 *
 * Üretim kalibrasyonu: CAN frame gönderip bit rate hatası ölç,
 * HSITRIM'i ±birkaç trim step'le düzelt. Her step ≈ ±40KHz (H7).
 * Bu işlem fabrikada yapılmalı, sahada yapılmamalı.
 *
 * Tavsiye: CAN-FD kullanacaksan HSE external crystal zorunlu. */
```

## Yaygın Hatalar ve Teşhis

| Hata | Belirti | Kök Neden | Çözüm |
|------|---------|-----------|-------|
| Message RAM çakışması | Başlatma sonrası HardFault | Instance'lar aynı RAM adresini kullanıyor | `MessageRAMOffset` değerlerini instance başına hesapla |
| Yanlış bit timing | Error frame, CAN bus trafiği yok | Prescaler/TimeSeg formülü hatalı | Formülü yeniden hesapla, logic analyzer ile doğrula |
| FIFO overrun | Frame drop (sessizce) | Task yetişemiyor | FIFO'yu büyüt veya task önceliğini yükselt |
| TDC kapalı, 4Mbit/s | Aralıklı CRC error | Sample point kayması | TDC_Offset = transceiver delay / T_q |
| Bus-Off otomatik recovery | Network reset storm | Auto-recovery loop | Manuel recovery, uygulama kararı |
| `FDCAN_BRS_OFF` yerine `FDCAN_FRAME_CLASSIC` | Enum mismatch, warning | HAL enum yanlış alan | `BitRateSwitch = FDCAN_BRS_OFF` kullan |
| CAN-FD > 1Mbit/s + HSI | Aralıklı frame error | HSI ±1% osilatör toleransı aşımı | HSE external crystal kullan |
| Aynı filter index iki instance'ta | İkinci instance filtre yok | Her instance bağımsız filter set | Her instance için filtreleri ayrı yapılandır |

## Bit Timing Hızlı Hesap Tablosu (PCLK1 = 120 MHz)

```
Hedef     Prescaler  TQ_total  TimeSeg1  TimeSeg2  SJW   SP%   Gerçek hız
---------  ---------  --------  --------  --------  ---   ----  ----------
125Kbit/s     48        20        15         4       4    80%   125.000Kbit/s
250Kbit/s     24        20        15         4       4    80%   250.000Kbit/s
500Kbit/s     12        20        15         4       4    80%   500.000Kbit/s
1Mbit/s        6        20        15         4       4    80%   1.000Mbit/s
2Mbit/s (FD)   3        20        15         4       4    80%   2.000Mbit/s
4Mbit/s (FD)   1        30        23         6       6    80%   4.000Mbit/s
5Mbit/s (FD)   1        24        19         4       4    83%   5.000Mbit/s

NOT: TQ_total = 1 + TimeSeg1 + TimeSeg2
     SP% = (1 + TimeSeg1) / TQ_total × 100
     4Mbit/s ve üzeri için TDC zorunlu
```
