# OBD-II Protokol Referansı (SAE J1979 / ISO 15031)

İşlemciden bağımsız, tam protokol seviyesinde referans. OBD-II; emisyon ilişkili teşhis için zorunlu tutulan standart (CARB/EPA/EOBD). Tüm özellikler dahildir.

---

## Fiziksel Katman ve CAN Adresleme

```
Baud rate:  500 kbps (ISO 15765-4 CAN) — modern araçlar
            250 kbps (eski / bazı ticari araçlar)

CAN ID şeması (11-bit Standard ID):
  Functional:  0x7DF  → tüm ECU'lara broadcast (tester→ECU)
  Physical:    0x7E0  → ECU #1 (Engine)     tester→ECU
               0x7E1  → ECU #2 (Transmission)
               ...
               0x7E7  → ECU #8
  Response:    0x7E8  → ECU #1 yanıtı       ECU→tester
               0x7E9  → ECU #2 yanıtı
               ...
               0x7EF  → ECU #8 yanıtı

ISO-TP (ISO 15765-2) — transport katmanı
  OBD-II mesajları ISO-TP üzerinden taşınır
  Single Frame (≤7 byte): PCI byte = 0x0N (N=length)
  Multi Frame: First Frame + Flow Control + Consecutive
```

---

## Mode (Servis) Tablosu

| Mode | SAE J1979 | ISO 15031-5 | Açıklama |
|------|-----------|-------------|----------|
| 0x01 | Mode 1 | Service 1 | Anlık powertrain verisi (current data) |
| 0x02 | Mode 2 | Service 2 | Freeze frame verisi (DTC anındaki snapshot) |
| 0x03 | Mode 3 | Service 3 | Saklı emisyon DTC'leri |
| 0x04 | Mode 4 | Service 4 | DTC'leri sil + readiness sıfırla |
| 0x05 | Mode 5 | Service 5 | O2 sensörü izleme sonuçları (CAN'da desteklenmiyor) |
| 0x06 | Mode 6 | Service 6 | On-board monitör test sonuçları |
| 0x07 | Mode 7 | Service 7 | Onaylanmamış / bekleyen DTC'ler |
| 0x08 | Mode 8 | Service 8 | On-board sistem kontrolü (opsiyonel) |
| 0x09 | Mode 9 | Service 9 | Araç bilgileri (VIN, kalibrasyonlar) |
| 0x0A | Mode A | Service A | Kalıcı DTC'ler (Permanent DTC — silinmez) |

**İstek/Yanıt formatı:**
```
İstek:  [Mode] [PID]
Yanıt:  [Mode+0x40] [PID] [Data bytes]

Örnek Mode 01 PID 0D (araç hızı):
  İstek:  01 0D
  Yanıt:  41 0D 64      → 0x64 = 100 km/h
```

---

## Mode 0x01 — Anlık Veri (Current Data PIDs)

### PID Destek Bitmap (PID 0x00, 0x20, 0x40, 0x60, 0x80, 0xA0, 0xC0)

```c
/* PID 0x00: hangi PID'ler destekleniyor (0x01-0x20) */
/* Yanıt: 4 byte bitmap — bit31=PID01, bit30=PID02, ..., bit0=PID20 */
/* PID 0x20: 0x21-0x40 desteği, vs. */

bool obd_is_pid_supported(uint8_t pid)
{
    uint8_t group   = (pid - 1) / 32;  /* 0x00, 0x20, 0x40 ... */
    uint8_t bit_pos = 31 - ((pid - 1) % 32);
    return (supported_pids[group] >> bit_pos) & 1;
}
```

### Temel PID Tablosu

| PID | Adı | Birim | Çözünürlük | Formula |
|-----|-----|-------|-----------|---------|
| 0x04 | Calculated Load | % | 100/255 | A×100/255 |
| 0x05 | Engine Coolant Temp | °C | 1 | A−40 |
| 0x0B | Intake MAP | kPa | 1 | A |
| 0x0C | Engine RPM | rpm | 0.25 | (A×256+B)/4 |
| 0x0D | Vehicle Speed | km/h | 1 | A |
| 0x0E | Timing Advance | ° | 0.5 | A/2−64 |
| 0x0F | Intake Air Temp | °C | 1 | A−40 |
| 0x10 | MAF Air Flow | g/s | 0.01 | (A×256+B)/100 |
| 0x11 | Throttle Position | % | 100/255 | A×100/255 |
| 0x1C | OBD Standards | — | — | A (bitmask) |
| 0x1F | Run Time Since Start | s | 1 | A×256+B |
| 0x21 | Distance with MIL on | km | 1 | A×256+B |
| 0x2F | Fuel Level | % | 100/255 | A×100/255 |
| 0x31 | Distance since DTC cleared | km | 1 | A×256+B |
| 0x33 | Barometric Pressure | kPa | 1 | A |
| 0x42 | Control Module Voltage | V | 0.001 | (A×256+B)/1000 |
| 0x43 | Absolute Load Value | % | 100/255 | (A×256+B)×100/255 |
| 0x45 | Relative Throttle | % | 100/255 | A×100/255 |
| 0x46 | Ambient Air Temp | °C | 1 | A−40 |
| 0x4D | Time with MIL on | min | 1 | A×256+B |
| 0x4E | Time since DTC cleared | min | 1 | A×256+B |
| 0x5C | Engine Oil Temp | °C | 1 | A−40 |
| 0x67 | Engine Coolant Temp (2 sensor) | °C | 1 | B−40, C−40 |

### Readiness Monitor Status (PID 0x01)

```
PID 0x01 Yanıt: 4 byte

Byte A:
  bit 7: MIL on/off
  bit 6-4: DTC sayısı (0-7)
  bit 3: reserved
  bit 2-0: Readiness not complete (continuous monitors)
    bit 2: Fuel system monitor
    bit 1: Fuel trim monitor
    bit 0: Misfire monitor

Byte B (non-continuous monitors — bit=0: complete, bit=1: not complete):
  Compression ignition (diesel):
    bit 3: PM filter
    bit 2: Exhaust gas sensor
    bit 1: Boost pressure
    bit 0: NOx/SCR monitor

  Spark ignition (benzin):
    bit 3: EGR/VVT
    bit 2: Oxygen sensor heater
    bit 1: Oxygen sensor
    bit 0: AC refrigerant

Byte C: Support status (1=supported), Byte D: Completion status (0=complete)
```

---

## Mode 0x02 — Freeze Frame

DTC oluştuğu andaki PID snapshot'ı. Her ECU sadece bir freeze frame saklar (ilk DTC).

```
İstek:  02 [PID] [Frame#=0x00]
Yanıt:  42 [PID] [Frame#] [Data]

Freeze frame sil: Mode 0x04 (DTC silme ile birlikte)
PID destekleri: 02 00 00 → byte map (Mode 01 ile aynı format)
```

---

## Mode 0x03 — Saklı Emisyon DTC'leri

```
İstek:  03
Yanıt:  43 [DTC sayısı] [DTC1 MSB] [DTC1 LSB] [DTC2 MSB] [DTC2 LSB] ...

DTC Formatı (2 byte):
  bits[15:14]: Sistem
    00 = Powertrain (P)
    01 = Chassis (C)
    10 = Body (B)
    11 = Network (U)
  bits[13:12]: Tip
    0x0 = Generic (SAE)
    0x1 = Manufacturer specific
    0x2 = Generic (SAE) — bazı kullanımlar
    0x3 = Manufacturer specific
  bits[11:0]: Arıza kodu (BCD veya hex)

Örnekler:
  0x0171 = P0171 (System Too Lean, Bank 1)
  0x0300 = P0300 (Random/Multiple Misfire)
  0x1000 = P1000 (OBD-II drive cycle not complete — özel)
```

---

## Mode 0x04 — DTC Temizleme

```
İstek:  04
Yanıt:  44

Temizleme etkileri:
  - Mode 03, 07, 0A DTC listeleri sıfırlanır (0A hariç — aşağıya bak)
  - Readiness monitors "not complete" durumuna döner
  - Freeze frame verisi silinir
  - Mode 06 sonuçları sıfırlanır
  - MIL söner (ancak Permanent DTC yoksa)
  NOT: Permanent DTC (Mode 0x0A) Mode 04 ile SİLİNEMEZ
```

---

## Mode 0x06 — On-Board Monitor Test Sonuçları

```
İstek:  06 [TID] [CID]
Yanıt:  46 [TID] [CID] [Unit] [Value MSB] [Value LSB] [Min MSB] [Min LSB] [Max MSB] [Max LSB]

TID (Test ID): hangi monitör testi
CID (Component ID): hangi bileşen

Örnek — O2 sensor response:
  TID 0x01 CID 0x11 → Bank1 Sensor1 Rich-to-Lean response
```

---

## Mode 0x07 — Bekleyen DTC'ler (Pending)

Bir sürüş döngüsünde tespit edilmiş ama henüz onaylanmamış DTC'ler.

```
İstek:  07
Yanıt:  47 [DTC sayısı] [DTC1] [DTC2] ...
Format: Mode 03 ile aynı
```

---

## Mode 0x09 — Araç Bilgileri

| InfoType | Adı | Açıklama |
|----------|-----|---------|
| 0x01 | VIN message count | VIN kaç mesajda gelecek |
| 0x02 | VIN | 17 karakter ASCII |
| 0x03 | Calibration ID count | |
| 0x04 | Calibration ID | Her ECU için kalibrasyon ID |
| 0x05 | Calibration verification count | |
| 0x06 | CVN | Calibration Verification Number (CRC) |
| 0x09 | ECU name count | |
| 0x0A | ECU name | ASCII |
| 0x0B | In-use performance tracking (benzin) | IUPR numerator/denominator |
| 0x0D | In-use performance tracking (dizel) | |

```c
/* VIN okuma — multi-frame yanıt */
/* İstek: 09 02 */
/* Yanıt: ISO-TP multi-frame, 20 byte */
/* Byte 0: message count (genellikle 0x01) */
/* Byte 1-17: VIN ASCII */

void obd_parse_vin(const uint8_t *data, uint16_t len, char *vin)
{
    if (len < 18) return;
    /* data[0] = message count */
    memcpy(vin, &data[1], 17);
    vin[17] = '\0';
}
```

---

## Mode 0x0A — Kalıcı DTC (Permanent DTC)

**OBD-II'nin en az bilinen özelliği.** EPA 40 CFR Part 86 ile zorunlu (2010+).

```
Özellikler:
  - Mode 04 ile SİLİNEMEZ
  - Yalnızca ECU kendi kendine silebilir (drive cycle + monitor complete + no fault)
  - NVM'de saklanmalı (güç kaybında korunmalı)
  - Silme koşulları:
    1. DTC artık mevcut değil (monitör passed)
    2. İlgili readiness monitor "complete" durumuna geldi
    3. MIL söndü (iki consecutive drive cycle)

İstek:  0A
Yanıt:  4A [DTC sayısı] [DTC1] [DTC2] ...
Format: Mode 03 ile aynı

Uygulama gereksinimleri:
  - Ayrı NVM alanı (regular DTC'den bağımsız)
  - Güvenli yazma (power-fail tolerant)
  - Silme koşulları kontrol state machine
```

```c
typedef struct {
    uint16_t dtc_code;      /* 2-byte OBD-II DTC */
    uint8_t  heal_count;    /* kaç drive cycle geçti (maks 3) */
    bool     monitor_passed; /* ilgili monitor passed mı */
} permanent_dtc_t;

#define MAX_PERMANENT_DTC 10

static permanent_dtc_t perm_dtc_table[MAX_PERMANENT_DTC];

/* Her drive cycle sonunda çağrılır */
void permanent_dtc_heal_cycle(void)
{
    for (int i = 0; i < MAX_PERMANENT_DTC; i++) {
        if (perm_dtc_table[i].dtc_code == 0) continue;
        if (!dtc_is_active(perm_dtc_table[i].dtc_code)
            && perm_dtc_table[i].monitor_passed) {
            if (++perm_dtc_table[i].heal_count >= 3) {
                perm_dtc_table[i].dtc_code = 0;  /* NVM'den sil */
                nvm_write_permanent_dtc_table();
            }
        } else {
            perm_dtc_table[i].heal_count = 0;  /* başa dön */
        }
    }
}
```

---

## Readiness Monitors — Tam Liste

```
Continuous monitors (her zaman aktif):
  □ Misfire detection
  □ Fuel system (closed-loop lambda)
  □ Comprehensive component (sensor rationality)

Non-continuous monitors (drive cycle gerekli):
  Benzin:
  □ Catalyst (TWC efficiency)
  □ Heated catalyst
  □ Evaporative system (EVAP)
  □ Secondary air system
  □ A/C refrigerant
  □ Oxygen sensor
  □ Oxygen sensor heater
  □ EGR/VVT system

  Dizel:
  □ NOx/SCR aftertreatment monitor
  □ PM (Particulate Matter) filter
  □ Exhaust gas sensor (lambda)
  □ Boost pressure control
  □ EGR/VVT system
  □ Fuel system
```

**Drive cycle tanımı (EPA/EOBD):**
```
Minimum sürüş döngüsü (monitor completion için):
1. Cold start: soak ≥ 6 saat, coolant < 35°C
2. Idle: 2-3 dakika (O2 sensor heater için)
3. Moderate acceleration: 50-80 km/h, %30-40 load
4. Highway: 80+ km/h, ≥5 dakika (catalyst monitor)
5. Deceleration: fuel cut (EVAP için)

Kısa sürüş döngüsü:
  Sadece continuous + bazı non-continuous
  Tüm monitörler için 1+ tam sürüş döngüsü şart
```

---

## OBD-II ECU Implementasyon Şablonu (İşlemciden Bağımsız)

```c
/* ========================================
 * OBD-II abstraction layer
 * İşlemciden bağımsız — HAL ile bağlan
 * ======================================== */

/* Platform HAL — uygulamada doldur */
typedef struct {
    void     (*send)(uint32_t can_id, const uint8_t *data, uint8_t len);
    uint32_t (*get_tick_ms)(void);
    bool     (*nvm_write)(uint8_t *data, uint16_t len);
    bool     (*nvm_read)(uint8_t *data, uint16_t len);
} obd_hal_t;

/* OBD-II context */
typedef struct {
    obd_hal_t hal;
    uint32_t  ecu_tx_id;          /* 0x7E8 tipik */
    uint32_t  ecu_rx_phys;        /* 0x7E0 */
    uint32_t  ecu_rx_func;        /* 0x7DF */
    uint32_t  supported_pids[8];  /* PID 0x00/0x20/.../0xE0 bitmap */
    uint32_t  dtc_count;
    uint16_t  dtc_list[32];
    uint8_t   perm_dtc_count;
    permanent_dtc_t perm_dtc[10];
    bool      mil_on;
    uint8_t   readiness_status;   /* bitmask: non-complete monitors */
} obd_ctx_t;

/* Gelen CAN frame işleme */
void obd_process_frame(obd_ctx_t *ctx, uint32_t can_id,
                       const uint8_t *data, uint8_t dlc)
{
    if (can_id != ctx->ecu_rx_phys && can_id != ctx->ecu_rx_func) return;

    /* ISO-TP single frame: data[0] = 0x0N, data[1] = Mode, data[2] = PID */
    if ((data[0] >> 4) != 0) return;  /* multi-frame: daha büyük handler */
    uint8_t len  = data[0] & 0x0F;
    uint8_t mode = data[1];
    uint8_t pid  = (len > 1) ? data[2] : 0;

    switch (mode) {
    case 0x01: obd_mode01(ctx, pid); break;
    case 0x02: obd_mode02(ctx, pid, data[3]); break;
    case 0x03: obd_mode03(ctx); break;
    case 0x04: obd_mode04(ctx); break;
    case 0x07: obd_mode07(ctx); break;
    case 0x09: obd_mode09(ctx, pid); break;
    case 0x0A: obd_mode0A(ctx); break;
    default:   obd_send_nrc(ctx, mode, 0x11); break; /* serviceNotSupported */
    }
}

/* Mode 01 dispatcher */
static void obd_mode01(obd_ctx_t *ctx, uint8_t pid)
{
    uint8_t buf[8] = { 0x04, 0x41, pid, 0, 0, 0, 0, 0 };
    /* buf[0] = ISO-TP SF length, buf[1] = mode+0x40, buf[2] = pid */

    switch (pid) {
    case 0x00: {  /* PID support 01-20 */
        uint32_t bm = ctx->supported_pids[0];
        buf[0] = 0x06; buf[3] = (bm>>24)&0xFF; buf[4] = (bm>>16)&0xFF;
        buf[5] = (bm>>8)&0xFF; buf[6] = bm&0xFF;
        break;
    }
    case 0x01: {  /* Monitor status */
        buf[0] = 0x06;
        buf[3] = (ctx->mil_on ? 0x80 : 0x00) | (ctx->dtc_count & 0x7F);
        buf[4] = 0x00; buf[5] = ctx->readiness_status; buf[6] = 0x00;
        break;
    }
    case 0x0C: {  /* Engine RPM */
        uint16_t rpm4 = app_get_engine_rpm() * 4;
        buf[0] = 0x04; buf[3] = (rpm4 >> 8) & 0xFF; buf[4] = rpm4 & 0xFF;
        break;
    }
    case 0x0D: {  /* Vehicle speed */
        buf[0] = 0x03; buf[3] = app_get_vehicle_speed_kmh();
        break;
    }
    default:
        obd_send_nrc(ctx, 0x01, 0x31);  /* requestOutOfRange */
        return;
    }
    ctx->hal.send(ctx->ecu_tx_id, buf, buf[0] + 1);
}

/* Mode 03 — DTC listesi gönder */
static void obd_mode03(obd_ctx_t *ctx)
{
    /* Max 3 DTC per frame, multi-frame gerekebilir */
    uint8_t buf[2 + 2 * 32] = { 0 };
    uint8_t n = (uint8_t)ctx->dtc_count;
    buf[0] = 1 + 2 * n;   /* ISO-TP SF length (max 6 DTC = 13 byte = multi-frame) */
    buf[1] = 0x43;
    buf[2] = n;
    for (uint8_t i = 0; i < n; i++) {
        buf[3 + i*2]     = (ctx->dtc_list[i] >> 8) & 0xFF;
        buf[3 + i*2 + 1] = ctx->dtc_list[i] & 0xFF;
    }
    /* TODO: 7+ DTC için ISO-TP multi-frame kullan */
    ctx->hal.send(ctx->ecu_tx_id, buf, buf[0] + 1);
}

/* Mode 04 — Temizle */
static void obd_mode04(obd_ctx_t *ctx)
{
    ctx->dtc_count       = 0;
    ctx->mil_on          = false;
    ctx->readiness_status = 0xFF;  /* tüm non-continuous: not complete */
    memset(ctx->dtc_list, 0, sizeof(ctx->dtc_list));
    /* Permanent DTC temizlenmez! */
    app_clear_freeze_frame();
    uint8_t buf[2] = { 0x01, 0x44 };
    ctx->hal.send(ctx->ecu_tx_id, buf, 2);
}

/* NRC gönder */
static void obd_send_nrc(obd_ctx_t *ctx, uint8_t mode, uint8_t nrc)
{
    uint8_t buf[4] = { 0x03, 0x7F, mode, nrc };
    ctx->hal.send(ctx->ecu_tx_id, buf, 4);
}
```

---

## OBD-II Tester Tarafı — Protokol Akışı

```c
/* Tester implementasyonu (diagnostic tool tarafı) */

/* 1. ECU discovery */
void obd_discover_ecus(void)
{
    uint8_t req[3] = { 0x02, 0x01, 0x00 };  /* Mode 01, PID 0x00 */
    can_send(0x7DF, req, 3);
    /* 200ms bekle — tüm yanıtları topla (0x7E8-0x7EF) */
}

/* 2. Supported PID bitmap okuma */
void obd_read_all_pids(uint32_t ecu_id)
{
    uint8_t group_pids[] = { 0x00, 0x20, 0x40, 0x60, 0x80, 0xA0, 0xC0 };
    for (int i = 0; i < 7; i++) {
        uint8_t req[3] = { 0x02, 0x01, group_pids[i] };
        can_send(ecu_id, req, 3);
        /* Yanıt bitmap'i parse et */
    }
}

/* 3. VIN okuma */
void obd_read_vin(uint32_t ecu_id)
{
    uint8_t req[3] = { 0x02, 0x09, 0x02 };
    can_send(ecu_id, req, 3);
    /* ISO-TP multi-frame yanıt: FF + FC + CF×2 */
}
```

---

## OBD-II ↔ J1939 DTC Dönüşüm Tablosu

```
OBD-II DTC format:  [Sistem(2)] [Tip(2)] [Kod(12)]   2 byte
J1939 DTC format:   SPN(19-bit) + FMI(5-bit) + OC(7-bit)  4 byte

Örnek dönüşümler:
  P0171 (Too lean Bank1) → SPN 1239, FMI 1 (data below range)
  P0300 (Misfire)        → SPN 1323, FMI 7 (mechanical system)
  P0401 (EGR flow low)   → SPN 2659, FMI 1

Dönüşüm tablosu zorunlu — otomatik hesaplanamaz.
SAE J1939-73 Appendix C: OBD↔J1939 mapping tablosu referans alınmalı.
```

---

## Yaygın Hatalar

| Hata | Kök Neden | Çözüm |
|------|-----------|-------|
| Functional req yanıtsız | Filtre 0x7DF'yi almıyor | Functional CAN ID'yi de filtrele |
| Mode 03 yanıt yanlış | DTC byte order hatalı | MSB first (ISO 15031) |
| Permanent DTC silinemedi | Mode 04 silmeye çalışıyor | Permanent DTC sadece drive cycle ile silinir |
| Readiness sıfırlanmıyor | Mode 04 sonrası kontrol | Sıfır sonrası flag = 0xFF (all not complete) |
| PID 0x01 MIL yanlış | bit7 ayarlı değil | buf[3] |= (mil_on ? 0x80 : 0x00) |
| VIN uzun yanıt yok | Multi-frame desteklenmiyor | ISO-TP FF+FC+CF implement et |
| Mode 09 CVN | CRC algoritması belirsiz | CRC-32 (SAE J1979 Appendix) |