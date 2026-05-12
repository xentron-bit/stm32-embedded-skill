# UDS — ISO 14229 Protokol Referansı (STM32 / FDCAN)

ISO 14229 Unified Diagnostic Services: araç ECU'larında tanı, programlama ve konfigürasyon hizmetleri standardı. STM32 FDCAN + ISO-TP (ISO 15765-2) üzerinde uygulanır.

---

## Temel Kavramlar

| Kavram | Açıklama |
|--------|----------|
| Tester | Dış teşhis aleti (PC, araç tarayıcı, BLE cihaz) |
| ECU (Server) | Araç içi kontrolör — servisleri uygular |
| CAN ID | Tester→ECU: 0x7E0..0x7E7; ECU→Tester: 0x7E8..0x7EF |
| Functional | 0x7DF — tüm ECU'lara broadcast |
| Physical | 0x7E0/0x7E8 — belirli ECU |
| Session | Aktif hizmet kümesini belirler |
| SID | Service Identifier (1 byte, istek) |
| RSID | Response SID = SID + 0x40 (pozitif yanıt) |
| NRC | Negative Response Code |
| P2 | ECU yanıt süresi (default 50ms) |
| P2* | Uzatılmış yanıt süresi (0x78 NRC sonrası, default 5000ms) |

---

## Session Tipleri (SID 0x10)

```
0x01 defaultSession         — Sadece temel servisler, güvenlik kilit
0x02 programmingSession     — Flash yazma, bootloader aktif
0x03 extendedDiagSession    — Tüm servisler, kalibrasyon, live data
0x04..0x5F ISO reserved
0x40..0x5E vehicleManufacturerSpecific
0x60..0x7E systemSupplierSpecific
```

**Session geçişi:**
```
[Request]  10 03           → extendedDiagSession iste
[Response] 50 03 00 32 01 F4   → RSID(50) + session + P2(50ms) + P2*(500ms)
```

**Session timeout:** Tester her 2-3 saniyede `3E 00` (TesterPresent) göndermezse ECU defaultSession'a döner.

---

## Servis Tablosu

| SID (hex) | Servis Adı | Yön | Yaygın Kullanım |
|-----------|-----------|-----|-----------------|
| 0x10 | DiagnosticSessionControl | Tester→ECU | Session değiştir |
| 0x11 | ECUReset | Tester→ECU | 01=hard, 02=keyOff/On, 03=soft |
| 0x14 | ClearDiagnosticInformation | Tester→ECU | DTC sil |
| 0x19 | ReadDTCInformation | Tester→ECU | DTC oku (çok subfn) |
| 0x22 | ReadDataByIdentifier | Tester→ECU | Live data okuma |
| 0x23 | ReadMemoryByAddress | Tester→ECU | Ham bellek oku |
| 0x27 | SecurityAccess | Tester→ECU | Seed/key authentication |
| 0x28 | CommunicationControl | Tester→ECU | CAN mesaj gönderimi aç/kapa |
| 0x2A | ReadDataByPeriodicIdentifier | Tester→ECU | Periyodik live data |
| 0x2C | DynamicallyDefineDataIdentifier | Tester→ECU | Custom DID |
| 0x2E | WriteDataByIdentifier | Tester→ECU | Parametre yaz |
| 0x2F | InputOutputControlByIdentifier | Tester→ECU | Aktuatör kontrolü |
| 0x31 | RoutineControl | Tester→ECU | Rutin başlat/durdur/sonuç |
| 0x34 | RequestDownload | Tester→ECU | Flash programlama başlat |
| 0x35 | RequestUpload | Tester→ECU | Bellek yükle |
| 0x36 | TransferData | Tester→ECU | Veri bloğu transferi |
| 0x37 | RequestTransferExit | Tester→ECU | Transfer bitir |
| 0x38 | RequestFileTransfer | Tester→ECU | Dosya transferi |
| 0x3D | WriteMemoryByAddress | Tester→ECU | Ham bellek yaz |
| 0x3E | TesterPresent | Tester→ECU | Session canlı tut |
| 0x7F | NegativeResponse | ECU→Tester | Hata yanıtı |
| 0x83 | AccessTimingParameters | Tester→ECU | P2/P2* ayarla |
| 0x84 | SecuredDataTransmission | Tester→ECU | Şifreli iletişim |
| 0x85 | ControlDTCSetting | Tester→ECU | DTC kaydını aç/kapa |
| 0x86 | ResponseOnEvent | Tester→ECU | Olay tetikli yanıt |
| 0x87 | LinkControl | Tester→ECU | Baud hızı değiştir |

---

## Byte-Level Örnekler

### DiagnosticSessionControl (0x10)
```
İstek:  10 03               → Extended Diagnostic Session gir
Yanıt:  50 03 00 32 01 F4   → OK; P2=50ms (0x0032); P2*=500ms (0x01F4)
```

### ReadDataByIdentifier (0x22)
```
İstek:  22 F1 90            → VIN oku (DID 0xF190)
Yanıt:  62 F1 90 57 30 4C 30 41 43 4D 45 30 30 30 30 30 30 30  (17 bayt VIN)
```

### WriteDataByIdentifier (0x2E)
```
İstek:  2E F1 01 12 34      → DID 0xF101'e 0x1234 yaz
Yanıt:  6E F1 01            → OK
```

### SecurityAccess (0x27) — Seed/Key
```
İstek:  27 01               → requestSeed (subfn 0x01 = seed iste)
Yanıt:  67 01 12 34 56 78   → seed = 0x12345678

İstek:  27 02 AA BB CC DD   → sendKey (key = seed XOR secret veya algoritma)
Yanıt:  67 02               → OK — kilit açıldı
```

### RoutineControl (0x31)
```
İstek:  31 01 02 02         → startRoutine (0x01), routineID=0x0202
Yanıt:  71 01 02 02 00      → OK, sonuç=0x00 (başarı)

İstek:  31 03 02 02         → requestRoutineResults
Yanıt:  71 03 02 02 AB CD   → sonuç verisi
```

### RequestDownload + TransferData (Flash Programlama)
```
İstek:  34 00 44 08 00 00 00 FF FF FF
        34       → RequestDownload
        00       → dataFormatIdentifier (sıkıştırma yok)
        44       → addressAndLengthFormatID (4 byte addr, 4 byte length)
        08000000 → başlangıç adresi (flash 0x08000000)
        0000FFFF → blok boyutu
Yanıt:  74 20 01 00          → OK; maxBlockSize=0x0100 (256 byte blok)

İstek:  36 01 [256 byte data]   → TransferData, blockSeqCounter=1
Yanıt:  76 01               → OK

İstek:  37                  → RequestTransferExit
Yanıt:  77                  → OK
```

### TesterPresent (0x3E)
```
İstek:  3E 00               → subFn=0x00 → responseRequired (ECU yanıt verir)
Yanıt:  7E 00               → OK

İstek:  3E 80               → subFn=0x80 → suppressPositiveResponse (yanıt yok)
(Yanıt yok)
```

---

## Negative Response Code (NRC) Tablosu

| NRC (hex) | Adı | Açıklama |
|-----------|-----|---------|
| 0x10 | generalReject | Genel ret |
| 0x11 | serviceNotSupported | Servis desteklenmiyor |
| 0x12 | subFunctionNotSupported | Alt fonksiyon desteklenmiyor |
| 0x13 | incorrectMessageLengthOrInvalidFormat | Uzunluk yanlış |
| 0x14 | responseTooLong | Yanıt çok uzun |
| 0x21 | busyRepeatRequest | Meşgul, tekrar dene |
| 0x22 | conditionsNotCorrect | Koşullar sağlanmadı (yanlış session vs) |
| 0x24 | requestSequenceError | Adım sırası yanlış (örn: seed almadan key gönderme) |
| 0x25 | noResponseFromSubnetComponent | Alt ağ bileşeni yanıt vermedi |
| 0x26 | failurePreventsExecutionOfRequestedAction | Arıza engeli |
| 0x31 | requestOutOfRange | DID / adres menzil dışı |
| 0x33 | securityAccessDenied | Güvenlik kilidi kapalı |
| 0x35 | invalidKey | Yanlış key |
| 0x36 | exceededNumberOfAttempts | Çok fazla hatalı deneme → geçici kilit |
| 0x37 | requiredTimeDelayNotExpired | Bekleme süresi dolmadı |
| 0x70 | uploadDownloadNotAccepted | Upload/download reddedildi |
| 0x71 | transferDataSuspended | Transfer askıya alındı |
| 0x72 | generalProgrammingFailure | Programlama hatası |
| 0x73 | wrongBlockSequenceCounter | Blok sıra numarası yanlış |
| 0x78 | requestCorrectlyReceivedResponsePending | İşlem sürüyor, bekle (P2* başlar) |
| 0x7E | subFunctionNotSupportedInActiveSession | Bu session'da subfn yok |
| 0x7F | serviceNotSupportedInActiveSession | Bu session'da servis yok |

**NRC format:**
```
7F [SID] [NRC]
Örn: 7F 22 31 → ReadDataByID (0x22) isteği OutOfRange (0x31)
```

---

## ISO-TP (ISO 15765-2) Çerçeveleme

ISO-TP, 8 byte'lık klasik CAN veya 64 byte'lık CAN FD çerçevelerini birleştirerek büyük UDS mesajları taşır.

### Frame Tipleri

```
Single Frame (SF):   [N_PCI=0x0N] [data...]    N = toplam bayt (1..7)
First Frame (FF):    [N_PCI=0x10] [LEN_H] [LEN_L] [data (6 byte)]
Consecutive Frame:   [N_PCI=0x2N] [data (7 byte)]   N = sıra numarası (1..15, döner)
Flow Control (FC):   [N_PCI=0x30] [BS] [STmin]
  BS  = BlockSize (0=limit yok)
  STmin = minimum frame aralığı (0x00..0x7F ms, 0xF1..0xF9 µs)
```

### 40 Byte Yanıt Örneği (FF + 5 CF)

```
FF: 10 28 62 F1 90 57 30 4C   → LEN=0x28=40, ilk 6 data byte
FC: 30 00 00                  → Tester: BS=0, STmin=0 (devam et)
CF1: 21 30 41 43 4D 45 30 30  → SN=1
CF2: 22 30 30 30 30 30 30 30  → SN=2
CF3: 23 AB CD EF 12 34 56 78  → SN=3
CF4: 24 ... (son data)        → SN=4
CF5: 25 ...                   → SN=5
```

---

## STM32 FDCAN — UDS Filtre Yapılandırması

```c
/* UDS: Tester→ECU (physical) = 0x7E0, ECU→Tester = 0x7E8 */
/* Functional broadcast = 0x7DF */

/* Filtre 0: Physical adres */
FDCAN_FilterTypeDef filter_phys = {
    .IdType       = FDCAN_STANDARD_ID,
    .FilterIndex  = 0,
    .FilterType   = FDCAN_FILTER_MASK,
    .FilterConfig = FDCAN_FILTER_TO_RXFIFO0,
    .FilterID1    = 0x7E0,    /* ID */
    .FilterID2    = 0x7FF,    /* mask: tam eşleşme */
};

/* Filtre 1: Functional broadcast */
FDCAN_FilterTypeDef filter_func = {
    .IdType       = FDCAN_STANDARD_ID,
    .FilterIndex  = 1,
    .FilterType   = FDCAN_FILTER_MASK,
    .FilterConfig = FDCAN_FILTER_TO_RXFIFO0,
    .FilterID1    = 0x7DF,
    .FilterID2    = 0x7FF,
};

HAL_FDCAN_ConfigFilter(&hfdcan1, &filter_phys);
HAL_FDCAN_ConfigFilter(&hfdcan1, &filter_func);

/* Eşleşmeyen çerçeveleri reddet */
HAL_FDCAN_ConfigGlobalFilter(&hfdcan1,
    FDCAN_REJECT, FDCAN_REJECT,
    FDCAN_FILTER_REMOTE, FDCAN_FILTER_REMOTE);
```

---

## STM32 ISO-TP / UDS Minimal Uygulama İskeleti

```c
/* ISO-TP state machine */
typedef enum { ISOTP_IDLE, ISOTP_FF, ISOTP_CF } isotp_state_t;

typedef struct {
    uint8_t  buf[4096];
    uint16_t total_len;
    uint16_t received;
    uint8_t  sn_expected;
    isotp_state_t state;
} isotp_ctx_t;

static isotp_ctx_t isotp;

/* CAN RX callback'inde çağrılır */
void isotp_rx(const uint8_t *frame, uint8_t dlc)
{
    uint8_t pci = frame[0] >> 4;

    if (pci == 0) {                        /* Single Frame */
        uint8_t len = frame[0] & 0x0F;
        memcpy(isotp.buf, &frame[1], len);
        uds_process(isotp.buf, len);

    } else if (pci == 1) {                 /* First Frame */
        isotp.total_len   = ((uint16_t)(frame[0] & 0x0F) << 8) | frame[1];
        isotp.received    = 6;
        isotp.sn_expected = 1;
        memcpy(isotp.buf, &frame[2], 6);
        isotp.state = ISOTP_CF;
        isotp_send_fc();                   /* Flow Control gönder */

    } else if (pci == 2 && isotp.state == ISOTP_CF) { /* Consecutive Frame */
        uint8_t sn = frame[0] & 0x0F;
        if (sn != isotp.sn_expected) { isotp.state = ISOTP_IDLE; return; }
        uint8_t copy = (uint8_t)MIN(7U, isotp.total_len - isotp.received);
        memcpy(&isotp.buf[isotp.received], &frame[1], copy);
        isotp.received += copy;
        isotp.sn_expected = (isotp.sn_expected + 1) & 0x0F;
        if (isotp.received >= isotp.total_len) {
            isotp.state = ISOTP_IDLE;
            uds_process(isotp.buf, isotp.total_len);
        }
    }
}

/* UDS dispatcher */
void uds_process(const uint8_t *data, uint16_t len)
{
    uint8_t sid = data[0];
    switch (sid) {
    case 0x10: uds_session_ctrl(data, len); break;
    case 0x22: uds_read_did(data, len);     break;
    case 0x27: uds_security_access(data, len); break;
    case 0x3E: uds_tester_present(data, len);  break;
    default:
        uds_send_nrc(sid, 0x11);  /* serviceNotSupported */
        break;
    }
}

/* NRC gönder */
void uds_send_nrc(uint8_t sid, uint8_t nrc)
{
    uint8_t resp[3] = { 0x7F, sid, nrc };
    isotp_send(0x7E8, resp, 3);   /* ECU→Tester CAN ID */
}
```

---

## Security Access — Seed/Key Örneği

```c
static uint32_t pending_seed;

void uds_security_access(const uint8_t *data, uint16_t len)
{
    uint8_t subfn = data[1];

    if (subfn == 0x01) {                   /* requestSeed */
        if (security_unlocked) {
            uint8_t r[4] = { 0x67, 0x01, 0x00, 0x00 };  /* seed=0 zaten açık */
            isotp_send(0x7E8, r, 4);
            return;
        }
        pending_seed = generate_seed();    /* TRNG veya timer-based */
        uint8_t r[6] = { 0x67, 0x01,
            (pending_seed >> 24) & 0xFF, (pending_seed >> 16) & 0xFF,
            (pending_seed >>  8) & 0xFF,  pending_seed        & 0xFF };
        isotp_send(0x7E8, r, 6);

    } else if (subfn == 0x02) {            /* sendKey */
        if (len < 6) { uds_send_nrc(0x27, 0x13); return; }
        uint32_t key = ((uint32_t)data[2] << 24) | ((uint32_t)data[3] << 16)
                     | ((uint32_t)data[4] <<  8) |  data[5];
        uint32_t expected_key = compute_key(pending_seed);
        if (key == expected_key) {
            security_unlocked = true;
            uint8_t r[2] = { 0x67, 0x02 };
            isotp_send(0x7E8, r, 2);
        } else {
            failed_attempts++;
            if (failed_attempts >= 3)
                security_locked_until = osKernelGetTickCount() + 10000U;
            uds_send_nrc(0x27, (failed_attempts >= 3) ? 0x36 : 0x35);
        }
    }
}
```

---

## DTC — Diagnostic Trouble Code Formatı

```
DTC = 3 byte (ISO 14229) veya 2 byte OBD-II P/C/B/U prefix
  Byte 0-1: DTC code
    bits[15:14]: system group — 00=Powertrain(P), 01=Chassis(C), 10=Body(B), 11=Network(U)
    bits[13:12]: type (0x0=generic, 0x1..0x3=manufacturer specific)
    bits[11:0]:  fault code
  Byte 2: DTC status byte
    bit 0: testFailed (şu an arızalı)
    bit 1: testFailedThisMonitoringCycle
    bit 2: pendingDTC (bir devre test başarısız)
    bit 3: confirmedDTC (2 sürüş döngüsü)
    bit 4: testNotCompletedSinceLastClear
    bit 5: testFailedSinceLastClear
    bit 6: testNotCompletedThisMonitoringCycle
    bit 7: warningIndicatorRequested (MIL lambası)
```

**ReadDTCInformation (0x19) örneği:**
```
İstek:  19 02 09          → subfn=0x02 (reportDTCByStatusMask), mask=0x09 (testFailed + confirmed)
Yanıt:  59 02 09          → RSID + subfn + availabilityMask
        00 AB CD 08       → DTC 0x00ABCD, status=0x08 (confirmed)
        00 12 34 09       → DTC 0x001234, status=0x09 (failed + confirmed)
```

---

## Yaygın Hatalar ve Çözümleri

| Hata | Neden | Çözüm |
|------|-------|-------|
| Sürekli NRC 0x22 | Yanlış session | `10 03` ile extended session aç |
| NRC 0x24 (sequenceError) | Seed almadan key gönder | Önce `27 01`, sonra `27 02` |
| NRC 0x78 sonrası timeout | P2* süresi aşıldı | P2* ≥ 5000ms kabul et, tekrar bekle |
| Yanıt yok (silent) | SF/FF ayrımı yanlış | >7 byte = FF+CF kullan |
| CAN filter drop | Yanlış filtre | 0x7E0 ve 0x7DF ikisi de filtrede olmalı |
| 3E 80 görmezden gelme | suppress flag atlanıyor | bit7=1 → yanıt gönderme |
| Flash yazma başarısız | Programming session yok | Önce `10 02`, sonra `34` gönder |
| Security kilit | 3 hatalı key | 10+ saniye bekle, 0x37 NRC |
