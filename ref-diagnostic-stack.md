# Multi-Protocol Diagnostic Stack Mimarisi

İşlemciden bağımsız, katmanlı mimari: J1939 + UDS + OBD-II + WWH-OBD aynı anda.
Euro VI ağır araç ve Stage V iş makinesi uygulamaları için üretim kalitesi referans.

---

## Mimari Genel Bakış

```
┌─────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                          │
│   (Sensor değerleri, actuator kontrol, alarm yönetimi)       │
└──────────────────────┬──────────────────────────────────────┘
                       │ DTC event / PID data
┌──────────────────────▼──────────────────────────────────────┐
│                DIAGNOSTIC EVENT MANAGER (DEM)                │
│   DTC storage │ Readiness monitors │ Freeze frame │ NVM      │
│   Unified internal format: SPN/FMI (J1939 natif)            │
└──┬─────────┬──────────┬──────────────────────────┬──────────┘
   │         │          │                          │
┌──▼──┐  ┌───▼───┐  ┌───▼────┐              ┌──────▼──────┐
│ DCM │  │ J1939 │  │ OBD-II │              │  WWH-OBD    │
│ UDS │  │  NM   │  │ Server │              │   Server    │
│     │  │  DM   │  │        │              │ (ISO 27145) │
└──┬──┘  └───┬───┘  └───┬────┘              └──────┬──────┘
   │         │          │                          │
┌──▼─────────▼──────────▼──────────────────────────▼──────────┐
│              TRANSPORT LAYER MULTIPLEXER                      │
│  ISO-TP (ISO 15765-2)  │  J1939 TP (BAM/CMDT)               │
└──────────────────────────────────────────┬──────────────────┘
                                           │
┌──────────────────────────────────────────▼──────────────────┐
│                   CAN DRIVER (HAL)                           │
│  11-bit STD (OBD-II 0x7DF/0x7E0)  │  29-bit EXT (J1939)    │
└─────────────────────────────────────────────────────────────┘
```

---

## CAN Bus — İki ID Uzayı Aynı Bus'ta

J1939 (29-bit EXT) ve OBD-II (11-bit STD) aynı fiziksel CAN bus'ında çalışabilir:

```c
/* CAN RX frame dispatch */
void can_rx_dispatch(uint32_t raw_id, bool is_ext, const uint8_t *data, uint8_t dlc)
{
    if (!is_ext) {
        /* 11-bit Standard ID → OBD-II */
        if (raw_id == 0x7DF || (raw_id >= 0x7E0 && raw_id <= 0x7E7))
            isotp_rx_obd(raw_id, data, dlc);
    } else {
        /* 29-bit Extended ID → J1939 / WWH-OBD / UDS-over-J1939 */
        uint8_t  sa  = raw_id & 0xFF;
        uint8_t  pf  = (raw_id >> 16) & 0xFF;
        uint8_t  ps  = (raw_id >>  8) & 0xFF;
        uint32_t pgn = (pf >= 0xF0)
                     ? ((raw_id >> 8) & 0x03FFFF)   /* PDU2 */
                     : ((raw_id >> 8) & 0x03FF00);  /* PDU1 — PS=DA */

        if (pgn == 0x00EC00 || pgn == 0x00EB00) {
            j1939_tp_rx(sa, ps, pgn, data, dlc);    /* TP frames */
        } else if (pf == 0xDA) {
            /* UDS-over-J1939 (ISO 15765-4 J1939 addressing) */
            /* PF=0xDA, PS=DA → physical UDS; PS=0xFE → functional */
            isotp_rx_j1939(sa, ps, data, dlc);
        } else {
            j1939_pgn_rx(pgn, sa, data, dlc);       /* regular J1939 */
        }
    }
}
```

**FDCAN filter yapılandırması:**
```c
/* Filter 0: OBD-II physical (STD 0x7E0) */
FDCAN_FilterTypeDef f0 = {
    .IdType = FDCAN_STANDARD_ID, .FilterIndex = 0,
    .FilterType = FDCAN_FILTER_MASK, .FilterConfig = FDCAN_FILTER_TO_RXFIFO0,
    .FilterID1 = 0x7E0, .FilterID2 = 0x7FF,
};
/* Filter 1: OBD-II functional (STD 0x7DF) */
FDCAN_FilterTypeDef f1 = {
    .IdType = FDCAN_STANDARD_ID, .FilterIndex = 1,
    .FilterType = FDCAN_FILTER_MASK, .FilterConfig = FDCAN_FILTER_TO_RXFIFO0,
    .FilterID1 = 0x7DF, .FilterID2 = 0x7FF,
};
/* Filter 2: J1939/WWH EXT — tüm EXT frame'ler FIFO1'e */
HAL_FDCAN_ConfigGlobalFilter(&hfdcan1,
    FDCAN_REJECT,              /* non-matching STD → reject */
    FDCAN_ACCEPT_IN_RX_FIFO1, /* non-matching EXT → FIFO1 */
    FDCAN_REJECT, FDCAN_REJECT);
```

---

## Transport Layer Abstraction

İki transport protokolü tek arayüzle:

```c
/* Platform-independent transport context */
typedef struct {
    uint32_t tx_id;           /* CAN TX ID (STD veya EXT) */
    uint32_t rx_id;           /* CAN RX ID */
    bool     is_j1939;        /* true=J1939 TP, false=ISO-TP */
    uint8_t  src_addr;        /* J1939 SA */
    uint8_t  dst_addr;        /* J1939 DA */
    void     (*can_send)(uint32_t id, bool ext, const uint8_t *d, uint8_t l);
} transport_ctx_t;

/* Unified send — hangi transport kullanılacağına context karar verir */
void transport_send(transport_ctx_t *ctx, const uint8_t *data, uint16_t len)
{
    if (len <= 7 && !ctx->is_j1939) {
        /* OBD-II / UDS ISO-TP Single Frame */
        uint8_t frame[8] = { (uint8_t)len };
        memcpy(&frame[1], data, len);
        ctx->can_send(ctx->tx_id, false, frame, len + 1);
    } else if (!ctx->is_j1939) {
        isotp_send_multi(ctx, data, len);   /* FF + FC + CF sequence */
    } else {
        if (len <= 8) {
            /* J1939 single frame (≤8 byte PGN) */
            ctx->can_send(ctx->tx_id, true, data, (uint8_t)len);
        } else {
            j1939_tp_send(ctx, data, len);  /* BAM veya CMDT */
        }
    }
}
```

---

## Diagnostic Event Manager (DEM)

Tüm protokollere hizmet eden merkezi DTC yönetimi:

```c
/* ============================================================
 * DEM — Diagnostic Event Manager
 * İç format: SPN/FMI (J1939 natif)
 * Dış format: Protokol dönüşümü ile sunulur
 * ============================================================ */

/* DTC severity (WWH-OBD tanımı, J1939 ile uyumlu) */
typedef enum {
    DTC_SEV_NO_FAULT     = 0x00,
    DTC_SEV_MAINTENANCE  = 0x20,  /* Maintenance required */
    DTC_SEV_CHECK_NEXT   = 0x40,  /* Check at next halt */
    DTC_SEV_STOP_NOW     = 0x60,  /* Immediately stop vehicle */
} dtc_severity_t;

typedef struct {
    uint32_t       spn;           /* 19-bit SPN */
    uint8_t        fmi;           /* 5-bit FMI */
    dtc_severity_t severity;
    uint8_t        occ_count;     /* occurrence counter (0-126) */
    uint16_t       obd_dtc;       /* OBD-II P-code eşdeğeri (0 = yok) */
    bool           active;        /* şu an aktif */
    bool           confirmed;     /* ≥2 sürüş döngüsü */
    bool           pending;       /* bu sürüş döngüsünde oluştu */
    bool           mil_requested; /* MIL yakılmalı mı */
    bool           permanent;     /* Permanent DTC (OBD-II 0x0A) */
    uint32_t       first_seen_ms; /* ilk görülme timestamp */
    uint8_t        status_byte;   /* ISO 14229 DTC status byte */
} dem_dtc_t;

#define DEM_MAX_DTC       64
#define DEM_MAX_PERM_DTC  10

typedef struct {
    dem_dtc_t  dtc[DEM_MAX_DTC];
    uint8_t    dtc_count;
    dem_dtc_t  perm_dtc[DEM_MAX_PERM_DTC];
    uint8_t    perm_dtc_count;
    uint8_t    readiness;         /* bitmask */
    bool       mil_on;
    bool       awl_on;            /* WWH Amber Warning Lamp */
    bool       rsl_on;            /* WWH Red Stop Lamp */
    bool       pil_on;            /* WWH Protection Indicator Lamp */
    uint32_t   ign_cycle_count;   /* ignition cycle sayacı */
    uint32_t   warmup_count;      /* warmup cycle sayacı */
} dem_ctx_t;

/* DTC set et (uygulama → DEM) */
void dem_set_dtc(dem_ctx_t *dem, uint32_t spn, uint8_t fmi,
                 dtc_severity_t sev, uint16_t obd_code)
{
    dem_dtc_t *d = dem_find_or_alloc(dem, spn, fmi);
    if (!d) return;

    d->spn      = spn;
    d->fmi      = fmi;
    d->severity = sev;
    d->obd_dtc  = obd_code;
    d->active   = true;
    d->pending  = true;
    if (d->occ_count < 126) d->occ_count++;

    /* Status byte — ISO 14229 §11.3.2 */
    d->status_byte |= 0x01;  /* testFailed */
    d->status_byte |= 0x02;  /* testFailedThisMonitoringCycle */
    d->status_byte |= 0x04;  /* pendingDTC */

    /* Lamp güncelle */
    dem_update_lamps(dem);
}

/* DTC temizle (uygulama, monitör passed) */
void dem_clear_dtc(dem_ctx_t *dem, uint32_t spn, uint8_t fmi)
{
    dem_dtc_t *d = dem_find(dem, spn, fmi);
    if (!d) return;
    d->active = false;
    d->status_byte &= ~0x01;  /* testFailed cleared */
    /* confirmed, pending, permanent → drive cycle logic ile temizlenir */
    dem_update_lamps(dem);
}

/* Lamba güncelleme — severity tabanlı */
void dem_update_lamps(dem_ctx_t *dem)
{
    dem->mil_on = false;
    dem->awl_on = false;
    dem->rsl_on = false;
    dem->pil_on = false;

    for (int i = 0; i < dem->dtc_count; i++) {
        if (!dem->dtc[i].active && !dem->dtc[i].confirmed) continue;

        /* OBD-II MIL: emission-related confirmed DTC */
        if (dem->dtc[i].mil_requested && dem->dtc[i].confirmed)
            dem->mil_on = true;

        /* WWH-OBD lamp mapping */
        switch (dem->dtc[i].severity) {
        case DTC_SEV_MAINTENANCE: dem->pil_on = true; break;
        case DTC_SEV_CHECK_NEXT:  dem->awl_on = true; break;
        case DTC_SEV_STOP_NOW:    dem->rsl_on = true; break;
        default: break;
        }
    }
}

/* Ignition cycle sonu — confirmasyon ve healing */
void dem_end_drive_cycle(dem_ctx_t *dem)
{
    dem->ign_cycle_count++;

    for (int i = 0; i < dem->dtc_count; i++) {
        dem_dtc_t *d = &dem->dtc[i];

        /* Confirmasyon: 2 consecutive pending cycles */
        if (d->pending && !d->confirmed) {
            d->confirmed = true;
            d->status_byte |= 0x08;  /* confirmedDTC */
            /* OBD-II Permanent DTC: confirmed + emission-related */
            if (d->obd_dtc && d->mil_requested)
                dem_promote_to_permanent(dem, d);
        }
        d->pending = false;

        /* Healing: aktif değil + monitor passed → confirmed temizle */
        if (!d->active) {
            d->status_byte |= 0x10;  /* testNotCompletedSinceLastClear */
        }
    }

    /* Permanent DTC healing */
    for (int i = 0; i < dem->perm_dtc_count; i++) {
        dem_dtc_t *p = &dem->perm_dtc[i];
        if (!p->active && (p->status_byte & 0x40)) {  /* monitor passed */
            if (++p->occ_count >= 3) {  /* 3 drive cycles healed */
                dem_remove_permanent(dem, i--);
            }
        }
    }

    dem_nvm_save(dem);  /* NVM'e kaydet */
}
```

---

## Protocol Server — Session Multiplexer

Birden fazla protokol aynı anda farklı session state'de olabilir:

```c
typedef struct {
    /* OBD-II: session-less, her zaman hazır */

    /* UDS session */
    uint8_t  uds_session;        /* 0x01/0x02/0x03 */
    bool     uds_sec_unlocked;
    uint32_t uds_s3_timer;

    /* J1939: stateless, ancak TP state var */
    uint8_t  j1939_addr;

    /* WWH session: UDS session ile paylaşılır */
    bool     wwh_active;
} diag_state_t;

void diag_rx(diag_state_t *st, uint32_t can_id, bool is_ext,
             const uint8_t *data, uint8_t dlc)
{
    if (!is_ext && (can_id == 0x7DF || can_id == 0x7E0)) {
        /* OBD-II → her zaman işle, session yok */
        isotp_rx_process(&obd_ctx, can_id, data, dlc);
    } else if (is_ext) {
        uint8_t pf = (can_id >> 16) & 0xFF;
        if (pf == 0xDA) {
            /* UDS over J1939 → WWH-OBD veya UDS */
            isotp_j1939_rx_process(&uds_ctx, can_id, data, dlc);
        } else {
            /* J1939 PGN */
            j1939_rx_process(can_id, data, dlc);
        }
    }
}

/* S3 timer yönetimi — UDS/WWH session koruma */
void diag_tick_1ms(diag_state_t *st)
{
    if (st->uds_session != 0x01) {
        if (++st->uds_s3_timer > 5000U) {
            st->uds_session     = 0x01;
            st->uds_sec_unlocked = false;
            st->wwh_active      = false;
            log_session_timeout();
        }
    }
}

void diag_refresh_s3(diag_state_t *st)
{
    st->uds_s3_timer = 0;
}
```

---

## DTC Format Dönüşüm Katmanı

Her protokol DTC'yi farklı formatta sunar:

```c
/* J1939 DM1 frame için DTC encode */
uint8_t dem_encode_j1939_dm1(dem_ctx_t *dem, uint8_t *buf, uint16_t buflen)
{
    uint8_t pos = 0;
    /* Byte 0: Lamp status */
    buf[pos++] = (dem->mil_on ? 0x40 : 0x00)   /* MIL: bit 6-5 = 01 */
               | (dem->rsl_on ? 0x04 : 0x00)   /* RSL: bit 3-2 = 01 */
               | (dem->awl_on ? 0x10 : 0x00);  /* AWL: bit 5-4 = 01 */
    buf[pos++] = 0xFF;  /* flash: reserved */

    for (int i = 0; i < dem->dtc_count && pos + 4 <= buflen; i++) {
        if (!dem->dtc[i].active) continue;
        dem_dtc_t *d = &dem->dtc[i];
        /* SPN[18:11] */
        buf[pos++] = (d->spn >> 11) & 0xFF;
        /* SPN[10:3] */
        buf[pos++] = (d->spn >> 3) & 0xFF;
        /* SPN[2:0] | FMI[4:0] */
        buf[pos++] = ((d->spn & 0x07) << 5) | (d->fmi & 0x1F);
        /* OC */
        buf[pos++] = d->occ_count & 0x7F;
    }

    return pos;
}

/* OBD-II Mode 03 için DTC encode */
uint8_t dem_encode_obd_mode03(dem_ctx_t *dem, uint8_t *buf, uint16_t buflen)
{
    uint8_t count = 0;
    uint8_t pos   = 1;   /* buf[0] = count, sonra doldurulur */

    for (int i = 0; i < dem->dtc_count; i++) {
        if (!dem->dtc[i].confirmed) continue;
        if (!dem->dtc[i].obd_dtc)  continue;  /* OBD kodu yok */
        if (pos + 2 > buflen)       break;
        buf[pos++] = (dem->dtc[i].obd_dtc >> 8) & 0xFF;
        buf[pos++] =  dem->dtc[i].obd_dtc        & 0xFF;
        count++;
    }

    buf[0] = count;
    return pos;
}

/* UDS ReadDTCInformation (0x19 02) için encode */
uint16_t dem_encode_uds_dtc(dem_ctx_t *dem, uint8_t status_mask,
                            uint8_t *buf, uint16_t buflen)
{
    uint16_t pos = 0;
    for (int i = 0; i < dem->dtc_count; i++) {
        dem_dtc_t *d = &dem->dtc[i];
        if (!(d->status_byte & status_mask)) continue;
        if (pos + 4 > buflen) break;

        /* UDS DTC: 3 byte DTC + 1 byte status */
        /* DTC format: SPN/FMI → proprietary mapping veya SAE J1979-2 */
        uint32_t dtc24 = (d->spn << 5) | d->fmi;  /* simplified */
        buf[pos++] = (dtc24 >> 16) & 0xFF;
        buf[pos++] = (dtc24 >>  8) & 0xFF;
        buf[pos++] =  dtc24        & 0xFF;
        buf[pos++] = d->status_byte;
    }
    return pos;
}
```

---

## NVM Interface — Processor-Independent

```c
/* DEM NVM arayüzü — platforma göre implement edilir */
typedef struct {
    bool (*write)(uint16_t offset, const uint8_t *data, uint16_t len);
    bool (*read) (uint16_t offset, uint8_t *data, uint16_t len);
    void (*sync) (void);  /* write buffer flush */
} dem_nvm_hal_t;

/* Kaydedilen veri yapısı */
typedef struct {
    uint32_t magic;           /* 0xDEAD1939 — geçerli veri kontrolü */
    uint32_t version;         /* yapı versiyonu */
    uint8_t  dtc_count;
    dem_dtc_t dtc[DEM_MAX_DTC];
    uint8_t  perm_dtc_count;
    dem_dtc_t perm_dtc[DEM_MAX_PERM_DTC];
    uint32_t ign_cycle_count;
    uint32_t crc32;           /* yapı bütünlük kontrolü */
} dem_nvm_image_t;

#define DEM_NVM_MAGIC 0xDEAD1939U

void dem_nvm_save(dem_ctx_t *dem)
{
    dem_nvm_image_t img = {0};
    img.magic          = DEM_NVM_MAGIC;
    img.version        = 1;
    img.dtc_count      = dem->dtc_count;
    img.perm_dtc_count = dem->perm_dtc_count;
    img.ign_cycle_count = dem->ign_cycle_count;
    memcpy(img.dtc,      dem->dtc,      sizeof(dem->dtc));
    memcpy(img.perm_dtc, dem->perm_dtc, sizeof(dem->perm_dtc));
    img.crc32 = crc32_calc((uint8_t *)&img, sizeof(img) - 4);

    nvm_hal.write(DEM_NVM_OFFSET, (uint8_t *)&img, sizeof(img));
    nvm_hal.sync();
}

void dem_nvm_load(dem_ctx_t *dem)
{
    dem_nvm_image_t img;
    nvm_hal.read(DEM_NVM_OFFSET, (uint8_t *)&img, sizeof(img));

    uint32_t calc_crc = crc32_calc((uint8_t *)&img, sizeof(img) - 4);
    if (img.magic != DEM_NVM_MAGIC || img.crc32 != calc_crc) {
        /* Bozuk veya ilk kullanım */
        memset(dem, 0, sizeof(*dem));
        return;
    }

    dem->dtc_count      = img.dtc_count;
    dem->perm_dtc_count = img.perm_dtc_count;
    dem->ign_cycle_count = img.ign_cycle_count;
    memcpy(dem->dtc,      img.dtc,      sizeof(dem->dtc));
    memcpy(dem->perm_dtc, img.perm_dtc, sizeof(dem->perm_dtc));
}
```

---

## Freeze Frame Yönetimi

```c
/* Her protokol kendi freeze frame formatını bekler */
typedef struct {
    uint32_t timestamp_ms;
    uint32_t trigger_spn;    /* hangi DTC tetikledi */
    uint8_t  fmi;

    /* Captured data */
    uint16_t engine_rpm;
    uint8_t  vehicle_speed;
    int8_t   coolant_temp;
    uint8_t  engine_load;
    uint16_t fuel_pressure;
    uint8_t  throttle_pos;
    int16_t  intake_temp;
    uint16_t map_kpa;
} freeze_frame_t;

static freeze_frame_t freeze_frame;
static bool           freeze_frame_stored;

void dem_store_freeze_frame(uint32_t spn, uint8_t fmi)
{
    if (freeze_frame_stored) return;  /* ilk DTC'nin freeze frame'i korunur */
    freeze_frame.timestamp_ms  = app_get_tick_ms();
    freeze_frame.trigger_spn   = spn;
    freeze_frame.fmi           = fmi;
    freeze_frame.engine_rpm    = app_get_rpm();
    freeze_frame.vehicle_speed = app_get_speed();
    freeze_frame.coolant_temp  = app_get_coolant_temp();
    freeze_frame.engine_load   = app_get_load();
    freeze_frame_stored        = true;
}

/* OBD-II Mode 02 freeze frame PID encode */
bool obd_get_freeze_pid(uint8_t pid, uint8_t *data, uint8_t *len)
{
    if (!freeze_frame_stored) return false;
    switch (pid) {
    case 0x0C: /* RPM */ data[0]=(freeze_frame.engine_rpm*4)>>8;
                         data[1]=(freeze_frame.engine_rpm*4)&0xFF; *len=2; break;
    case 0x0D: data[0]=freeze_frame.vehicle_speed; *len=1; break;
    case 0x05: data[0]=(uint8_t)(freeze_frame.coolant_temp+40); *len=1; break;
    case 0x04: data[0]=freeze_frame.engine_load; *len=1; break;
    default:   return false;
    }
    return true;
}
```

---

## İnit ve Entegrasyon Akışı

```c
/* Sistem başlangıcında çağrılacak sıra */
void diagnostic_stack_init(void)
{
    /* 1. DEM init ve NVM yükle */
    dem_nvm_load(&dem_ctx);
    dem_ctx.ign_cycle_count++;

    /* 2. Transport layer init */
    isotp_init(&obd_transport, OBD_ECU_TX_ID, OBD_ECU_RX_PHYS);
    isotp_j1939_init(&wwh_transport, J1939_MY_SA);

    /* 3. Protocol server init */
    obd_server_init(&obd_ctx, &dem_ctx);
    j1939_stack_init(&j1939_ctx, J1939_MY_SA, J1939_MY_NAME);
    uds_server_init(&uds_ctx, &dem_ctx);
    wwh_server_init(&wwh_ctx, &dem_ctx);

    /* 4. CAN filter setup (platforma göre) */
    can_setup_filters();

    /* 5. Address claiming başlat (J1939) */
    j1939_start(&j1939_ctx);
}

/* Ana döngü görevi (veya RTOS task) */
void diagnostic_task(void *arg)
{
    for (;;) {
        /* DEM periodic: lamp update, drive cycle tracking */
        dem_periodic_10ms(&dem_ctx);

        /* J1939 DM1 periyodik gönderim (1000ms) */
        if (j1939_dm1_due()) {
            uint8_t dm1_buf[72];
            uint8_t len = dem_encode_j1939_dm1(&dem_ctx, dm1_buf, sizeof(dm1_buf));
            j1939_send_pgn(&j1939_ctx, 0x00FECA, dm1_buf, len);
        }

        /* UDS/WWH S3 tick */
        diag_tick_1ms(&diag_state);

        osDelay(10);
    }
}
```

---

## Protokol Uyumluluk Matrisi

| Özellik | OBD-II | J1939 | UDS | WWH-OBD |
|---------|--------|-------|-----|---------|
| Transport | ISO-TP STD | J1939 TP / Direct | ISO-TP EXT/J1939 | ISO-TP over J1939 |
| CAN ID | 11-bit | 29-bit | Her ikisi | 29-bit (PF=0xDA) |
| Session | Yok | Yok | 0x01/0x02/0x03 | Var (UDS ile) |
| Security | Yok | Yok | 0x27 seed/key | Var (UDS ile) |
| DTC format | P/C/B/U code | SPN+FMI | 3-byte custom | SPN+FMI+severity |
| Lamp | MIL | MIL+RSL+AWL | — | MIL+RSL+AWL+PIL |
| Freeze frame | Mode 02 | — | DID 0x1900+sub | DID 0xF601+ |
| NVM | Permanent DTC | Yok | DTC persist | Permanent analog |
| Drive cycle | Readiness | — | — | IUMPR |
| Flash prog | Yok | DM14/15/16 | 0x34/36/37 | UDS ile |