# DTC Format Mapping — J1939 SPN/FMI ↔ OBD-II P-code ↔ WWH-OBD

## Overview

Three protocol families use incompatible DTC encodings. This reference covers:
1. Bit-exact wire format for each protocol
2. Canonical internal DTC representation
3. Conversion rules and mapping tables
4. Practical C implementation

---

## 1. Wire Format Comparison

### J1939 DTC (SAE J1939-73, DM1/DM2)

```
4 bytes per DTC:
  Byte 0:  SPN bits[7:0]
  Byte 1:  SPN bits[15:8]
  Byte 2:  SPN bits[18:16] in bits[7:5] | FMI in bits[4:0]
  Byte 3:  OC (7 bits, saturates at 127) | CM (1 bit conversion method)

SPN: 19-bit number (0..524287)
FMI: 5-bit failure mode identifier (0..31)
OC:  occurrence count (0..126; 127 = overflow)
CM:  0 = SAE-defined FMI, 1 = manufacturer-defined FMI
```

```c
typedef struct {
    uint32_t spn;   /* 19-bit */
    uint8_t  fmi;   /* 5-bit */
    uint8_t  oc;    /* 7-bit, CM=0 */
} j1939_dtc_t;

void j1939_encode_dtc(const j1939_dtc_t *d, uint8_t out[4])
{
    out[0] = (uint8_t)(d->spn & 0xFFU);
    out[1] = (uint8_t)((d->spn >> 8) & 0xFFU);
    out[2] = (uint8_t)(((d->spn >> 16) & 0x07U) << 5) | (d->fmi & 0x1FU);
    out[3] = (d->oc & 0x7FU);   /* CM=0 */
}

void j1939_decode_dtc(const uint8_t in[4], j1939_dtc_t *d)
{
    d->spn = (uint32_t)in[0]
           | ((uint32_t)in[1] << 8)
           | (((uint32_t)in[2] >> 5) << 16);
    d->fmi = in[2] & 0x1FU;
    d->oc  = in[3] & 0x7FU;
}
```

### WWH-OBD DTC (ISO 27145-3, DID 0xF601)

```
10 bytes per DTC:
  Byte 0:  SPN bits[18:11]
  Byte 1:  SPN bits[10:3]
  Byte 2:  SPN bits[2:0] in bits[7:5] | FMI in bits[4:0]
  Byte 3:  Occurrence count (0..126; 127=unknown)
  Byte 4:  WWH Severity (0x00/0x20/0x40/0x60)
  Byte 5:  ISO 14229 statusOfDTC
  Byte 6:  Lamp status (MIL|AWL|RSL|PIL)
  Byte 7:  Reserved 0xFF
  Bytes 8-9: IUMPR OC counter (0xFFFF if unused)

NOTE: WWH byte ordering is DIFFERENT from J1939!
  J1939: bytes 0-1 = SPN[15:0], byte 2[7:5] = SPN[18:16]
  WWH:   byte 0   = SPN[18:11], byte 1      = SPN[10:3], byte 2[7:5] = SPN[2:0]
```

```c
void wwh_encode_dtc(const wwh_dtc_t *d, uint8_t out[10])
{
    out[0] = (d->spn >> 11) & 0xFFU;
    out[1] = (d->spn >>  3) & 0xFFU;
    out[2] = ((d->spn & 7U) << 5) | (d->fmi & 0x1FU);
    out[3] = d->occurrence;
    out[4] = d->severity;
    out[5] = d->status;
    out[6] = d->lamp;
    out[7] = 0xFF;
    out[8] = 0xFF;
    out[9] = 0xFF;
}

void wwh_decode_dtc(const uint8_t in[10], wwh_dtc_t *d)
{
    d->spn        = ((uint32_t)in[0] << 11) | ((uint32_t)in[1] << 3) | (in[2] >> 5);
    d->fmi        = in[2] & 0x1FU;
    d->occurrence = in[3];
    d->severity   = in[4];
    d->status     = in[5];
    d->lamp       = in[6];
}
```

### OBD-II DTC (SAE J1979 Mode 0x03/0x07/0x0A)

```
2 bytes per DTC:
  Byte 0 bits[7:6]: System (00=P, 01=C, 10=B, 11=U)
  Byte 0 bits[5:4]: First digit (0..3 for P0..P3)
  Byte 0 bits[3:0]: Second digit (hex)
  Byte 1:           Third+Fourth digit (hex)

Examples:
  P0100 → 0x01 0x00
  P0301 → 0x03 0x01
  C0001 → 0x40 0x01
  B0001 → 0x80 0x01
  U0001 → 0xC0 0x01
```

```c
typedef struct {
    char     code[7];  /* e.g. "P0100\0" */
    uint8_t  wire[2];  /* wire encoding */
} obd_dtc_t;

void obd_encode_dtc_str(const char *code, uint8_t out[2])
{
    uint8_t sys = 0;
    switch (code[0]) {
        case 'P': sys = 0x00U; break;
        case 'C': sys = 0x40U; break;
        case 'B': sys = 0x80U; break;
        case 'U': sys = 0xC0U; break;
    }
    /* code[1] is digit 1 (0-3 for P/C/B/U) */
    uint8_t d1 = (uint8_t)(code[1] - '0') & 0x03U;
    uint8_t d2 = (uint8_t)((code[2] >= 'A') ? code[2]-'A'+10 : code[2]-'0') & 0x0FU;
    uint8_t d3 = (uint8_t)((code[3] >= 'A') ? code[3]-'A'+10 : code[3]-'0') & 0x0FU;
    uint8_t d4 = (uint8_t)((code[4] >= 'A') ? code[4]-'A'+10 : code[4]-'0') & 0x0FU;
    out[0] = sys | (d1 << 4) | d2;
    out[1] = (d3 << 4) | d4;
}

void obd_decode_dtc(const uint8_t in[2], char *out7)
{
    static const char sys_char[] = "PCBU";
    out7[0] = sys_char[(in[0] >> 6) & 3];
    out7[1] = '0' + ((in[0] >> 4) & 3);
    out7[2] = "0123456789ABCDEF"[in[0] & 0xF];
    out7[3] = "0123456789ABCDEF"[(in[1] >> 4) & 0xF];
    out7[4] = "0123456789ABCDEF"[in[1] & 0xF];
    out7[5] = '\0';
}
```

---

## 2. Canonical Internal DTC Format

Use SPN+FMI as the internal canonical representation. OBD-II P-codes are derived via lookup table.

```c
/* Internal DEM DTC — canonical format */
typedef struct {
    /* Identity */
    uint32_t spn;           /* 19-bit, canonical across J1939/WWH */
    uint8_t  fmi;           /* 5-bit FMI */

    /* OBD-II cross-reference */
    uint8_t  obd_wire[2];   /* 2-byte OBD P-code; {0,0} = not mapped */

    /* State */
    uint8_t  occurrence;    /* 0..126 */
    uint8_t  status;        /* ISO 14229 statusOfDTC bits */
    uint8_t  severity;      /* WWH: 0x00/0x20/0x40/0x60 */
    uint8_t  lamp;          /* MIL|AWL|RSL|PIL */

    /* IUMPR */
    bool     iumpr_frozen;

    /* DEM bookkeeping */
    uint8_t  confirm_count; /* consecutive trips with fault (confirm at 2) */
    uint8_t  heal_count;    /* consecutive trips without fault (heal MIL at 3) */
    bool     active;        /* current trip: fault detected */
    bool     confirmed;     /* statusOfDTC bit 3 */
    bool     pending;       /* statusOfDTC bit 2 */
    bool     mil_requested; /* statusOfDTC bit 7 */
    bool     permanent;     /* OBD-II Mode 0x0A eligible */
    uint8_t  perm_heal;     /* Permanent DTC: drive cycles healed */
} dem_dtc_t;
```

---

## 3. FMI Reference Table (SAE J1939-73 Annex A)

| FMI | Description | Typical Use |
|-----|-------------|-------------|
| 0 | Data valid but above normal operational range (most severe) | Sensor overvoltage, overtemp |
| 1 | Data valid but below normal operational range (most severe) | Sensor undervoltage, low pressure |
| 2 | Data erratic, intermittent, or incorrect | Signal noise, stuck sensor |
| 3 | Voltage above normal, or shorted to high source | Open circuit or short to VCC |
| 4 | Voltage below normal, or shorted to low source | Short to GND |
| 5 | Current below normal, or open circuit | Actuator open circuit |
| 6 | Current above normal, or grounded circuit | Actuator short to GND |
| 7 | Mechanical system not responding or out of adjustment | Stuck valve, blocked DPF |
| 8 | Abnormal frequency, pulse width, or period | Hall sensor failure |
| 9 | Abnormal update rate | Lost ECU communication |
| 10 | Abnormal rate of change | Sensor drift too fast |
| 11 | Root cause not known | Unknown |
| 12 | Bad intelligent device or component | ECU self-test failure |
| 13 | Out of calibration | Sensor calibration required |
| 14 | Special instructions | Manufacturer-defined |
| 15 | Data valid but above normal operating range (least severe) | Mild overvoltage warning |
| 16 | Data valid but above normal operating range (moderately severe) | Moderate overvoltage |
| 17 | Data valid but below normal operating range (least severe) | Mild low-pressure |
| 18 | Data valid but below normal operating range (moderately severe) | Moderate low-pressure |
| 19 | Received network data in error | CAN message CRC/length error |
| 20-30 | Reserved (SAE) | — |
| 31 | Condition exists (no specific failure mode) | Active warning with no FMI detail |

---

## 4. SPN / OBD-II P-Code Mapping Table

There is no universal automatic conversion between SPN and OBD P-codes — SAE J1939-73 Appendix C provides partial mapping for common powertrain SPNs. The table below covers the most frequently mapped SPNs:

| SPN | FMI | Description | OBD P-code | Notes |
|-----|-----|-------------|-----------|-------|
| 51 | 3,4 | Throttle position | P0120 | TPS circuit range |
| 91 | 3,4 | Accelerator pedal 1 | P0120 | APS circuit |
| 92 | 3,4 | Accelerator pedal 2 | P0220 | APS2 circuit |
| 94 | 0,1 | Fuel delivery pressure | P0190 | Fuel rail pressure |
| 97 | 3,4 | Water in fuel indicator | P2269 | Water in fuel sensor |
| 100 | 0,1 | Engine oil pressure | P0520 | Oil pressure sensor |
| 108 | 0,1 | Barometric pressure | P2228 | Baro sensor |
| 110 | 0,1,15,16 | Engine coolant temp | P0116,P0117,P0118 | ECT |
| 157 | 3,4 | Injector metering rail 1 pres | P0190 | Common rail |
| 158 | 3,4 | Injector metering rail 2 pres | P0192 | Rail pressure 2 |
| 171 | 0,1 | Ambient air temp | P0071 | Ambient |
| 174 | 0,1 | Fuel temp 1 | P0180 | Fuel temp |
| 175 | 0,1 | Engine oil temp 1 | P0195 | Oil temp |
| 190 | 0,1 | Engine speed | P0335,P0336 | Crankshaft RPM |
| 636 | 3,4 | Crankshaft position | P0335 | CKP sensor |
| 637 | 3,4 | Camshaft position | P0340 | CMP sensor |
| 723 | 3,4 | Engine speed 2 (cam) | P0340 | CMP circuit |
| 1127 | 0,1 | Turbo boost pressure 1 | P0237,P0238 | Boost |
| 1172 | 0,1 | Turbo inlet pressure 1 | P0235 | Pre-turbo |
| 1569 | 31 | Engine derate (protection) | P1569 | Derate active |
| 2791 | 9 | EGR valve controller | P0403 | EGR valve |
| 3031 | 0,1 | Aftertreat SCR intake NOx | P20EE | SCR NOx in |
| 3216 | 0,1 | Aftertreat SCR outlet NOx | P20EF | SCR NOx out |
| 3251 | 7 | DPF differential pressure | P242F | DPF restriction |
| 3361 | 7 | Injection control pressure | P0088 | HP fuel pressure |
| 4334 | 2 | Aftertreat DEF level | P203A | DEF tank level |
| 4348 | 2 | Aftertreat DEF dosing unit | P20BD | DEF injector |
| 5018 | 0,1 | SCR system reagent | P203F | DEF quality |

**Unmapped SPNs:** Manufacturer-proprietary SPNs (typically >500000 or in manufacturer-assigned ranges) have no OBD P-code equivalent. Store as `obd_wire = {0x00, 0x00}` to indicate "not OBD-mapped."

---

## 5. Conversion Functions

```c
/* Lookup table entry — kept in flash */
typedef struct {
    uint32_t spn;
    uint8_t  fmi_min;   /* 0xFF = any FMI */
    uint8_t  fmi_max;
    uint8_t  obd_wire[2];
} spn_obd_map_t;

static const spn_obd_map_t SMAP[] = {
    { 110, 0,  1,  {0x01, 0x16} },   /* P0116 — ECT range */
    { 110, 3,  4,  {0x01, 0x17} },   /* P0117/P0118 — ECT circuit */
    { 190, 0,  1,  {0x03, 0x35} },   /* P0335 — CKP */
    { 636, 3,  4,  {0x03, 0x35} },   /* P0335 — CKP */
    { 637, 3,  4,  {0x03, 0x40} },   /* P0340 — CMP */
    /* ... extend as needed ... */
};
#define SMAP_COUNT (sizeof(SMAP)/sizeof(SMAP[0]))

bool spn_to_obd(uint32_t spn, uint8_t fmi, uint8_t out_wire[2])
{
    for (size_t i = 0; i < SMAP_COUNT; i++) {
        if (SMAP[i].spn != spn) continue;
        if (SMAP[i].fmi_min != 0xFFU &&
            (fmi < SMAP[i].fmi_min || fmi > SMAP[i].fmi_max)) continue;
        out_wire[0] = SMAP[i].obd_wire[0];
        out_wire[1] = SMAP[i].obd_wire[1];
        return true;
    }
    out_wire[0] = 0;
    out_wire[1] = 0;
    return false;
}

/* WWH severity → J1939 lamp status byte (DM1 byte 0) */
uint8_t wwh_severity_to_j1939_lamps(uint8_t wwh_severity, bool mil)
{
    /* J1939 DM1 byte 0: bits[7:6]=MIL, bits[5:4]=RSL, bits[3:2]=AWL, bits[1:0]=PIL */
    /* Values: 00=off, 01=on, 10=fast blink, 11=slow blink */
    uint8_t lamps = 0x00U;
    if (mil) lamps |= 0x40U;                          /* MIL on */
    switch (wwh_severity) {
        case 0x60: lamps |= 0x10U | 0x04U; break;     /* RSL on + AWL on */
        case 0x40: lamps |= 0x04U;         break;     /* AWL on */
        case 0x20: lamps |= 0x01U;         break;     /* PIL on */
        default:   break;
    }
    return lamps;
}

/* J1939 DM1 lamp byte → WWH lamp byte */
uint8_t j1939_lamps_to_wwh(uint8_t j1939_lamp_byte)
{
    uint8_t wwh = 0;
    if (j1939_lamp_byte & 0x40U) wwh |= 0x01U; /* MIL */
    if (j1939_lamp_byte & 0x10U) wwh |= 0x04U; /* RSL */
    if (j1939_lamp_byte & 0x04U) wwh |= 0x02U; /* AWL */
    if (j1939_lamp_byte & 0x01U) wwh |= 0x08U; /* PIL */
    return wwh;
}
```

---

## 6. DEM Encoding to Each Protocol

```c
/* Encode active DTCs for J1939 DM1 broadcast */
uint16_t dem_encode_j1939_dm1(const dem_dtc_t *dtcs, uint8_t n,
                               uint8_t *out, uint16_t out_sz)
{
    /* DM1: byte 0 = lamp status, byte 1 = 0xFF (protect lamp), then 4 bytes/DTC */
    if (n == 0) {
        out[0] = 0x00U; out[1] = 0xFFU;       /* all lamps off */
        out[2] = 0xFF;  out[3] = 0xFF;
        out[4] = 0xFF;  out[5] = 0xFF;
        return 6;
    }
    bool mil = false;
    for (uint8_t i = 0; i < n; i++) if (dtcs[i].mil_requested) { mil = true; break; }
    /* Find highest severity */
    uint8_t max_sev = 0;
    for (uint8_t i = 0; i < n; i++) if (dtcs[i].severity > max_sev) max_sev = dtcs[i].severity;
    out[0] = wwh_severity_to_j1939_lamps(max_sev, mil);
    out[1] = 0xFFU;
    uint16_t pos = 2;
    for (uint8_t i = 0; i < n && pos + 4 <= out_sz; i++) {
        if (!dtcs[i].active && !dtcs[i].confirmed) continue;
        j1939_dtc_t jd = { dtcs[i].spn, dtcs[i].fmi, dtcs[i].occurrence };
        j1939_encode_dtc(&jd, out + pos);
        pos += 4;
    }
    return pos;
}

/* Encode for OBD-II Mode 0x03 response */
uint16_t dem_encode_obd_mode03(const dem_dtc_t *dtcs, uint8_t n,
                                uint8_t *out, uint16_t out_sz)
{
    uint16_t pos = 0;
    for (uint8_t i = 0; i < n; i++) {
        if (!dtcs[i].confirmed) continue;
        if (dtcs[i].obd_wire[0] == 0 && dtcs[i].obd_wire[1] == 0) continue;
        if (pos + 2 > out_sz) break;
        out[pos++] = dtcs[i].obd_wire[0];
        out[pos++] = dtcs[i].obd_wire[1];
    }
    return pos;
}

/* Encode for OBD-II Mode 0x0A (permanent DTCs — cannot be cleared by Mode 0x04) */
uint16_t dem_encode_obd_mode0A(const dem_dtc_t *dtcs, uint8_t n,
                                uint8_t *out, uint16_t out_sz)
{
    uint16_t pos = 0;
    for (uint8_t i = 0; i < n; i++) {
        if (!dtcs[i].permanent) continue;
        if (dtcs[i].obd_wire[0] == 0 && dtcs[i].obd_wire[1] == 0) continue;
        if (pos + 2 > out_sz) break;
        out[pos++] = dtcs[i].obd_wire[0];
        out[pos++] = dtcs[i].obd_wire[1];
    }
    return pos;
}

/* Encode for UDS SID 0x19 subFn 0x02 (reportDTCByStatusMask) */
uint16_t dem_encode_uds_dtc(const dem_dtc_t *dtcs, uint8_t n, uint8_t mask,
                              uint8_t *out, uint16_t out_sz)
{
    /* UDS DTC: 3-byte big-endian DTCIdentifier + 1-byte status */
    /* We use SPN[18:11] SPN[10:3] (SPN[2:0]|FMI) as the 3-byte ID (same as WWH) */
    uint16_t pos = 0;
    for (uint8_t i = 0; i < n; i++) {
        if (!(dtcs[i].status & mask)) continue;
        if (pos + 4 > out_sz) break;
        out[pos++] = (dtcs[i].spn >> 11) & 0xFFU;
        out[pos++] = (dtcs[i].spn >>  3) & 0xFFU;
        out[pos++] = ((dtcs[i].spn & 7U) << 5) | (dtcs[i].fmi & 0x1FU);
        out[pos++] = dtcs[i].status;
    }
    return pos;
}

/* Encode for WWH DID 0xF601 */
uint16_t dem_encode_wwh_f601(const dem_dtc_t *dtcs, uint8_t n,
                               uint8_t *out, uint16_t out_sz)
{
    if (out_sz < 2U) return 0;
    uint8_t count = 0;
    uint16_t pos  = 2;
    for (uint8_t i = 0; i < n; i++) {
        if (!(dtcs[i].status & 0x0FU)) continue; /* skip if no notable status bits */
        if (pos + 10 > out_sz) break;
        wwh_dtc_t wd = {
            .spn        = dtcs[i].spn,
            .fmi        = dtcs[i].fmi,
            .occurrence = dtcs[i].occurrence,
            .severity   = dtcs[i].severity,
            .status     = dtcs[i].status,
            .lamp       = dtcs[i].lamp,
        };
        wwh_encode_dtc(&wd, out + pos);
        pos += 10;
        count++;
    }
    out[0] = 0;
    out[1] = count;
    return pos;
}
```

---

## 7. DTC Clear Semantics per Protocol

| Protocol | Clear Command | What Clears | What Persists |
|----------|--------------|-------------|---------------|
| OBD-II | Mode 0x04 | Confirmed, pending, testFailed flags; readiness bits | Permanent DTCs (Mode 0x0A) require 3 drive cycles |
| J1939 | DM11 (PGN 0xFEC1) | All stored DTCs; SAE J1939-73 §5.7.11 | N/A |
| UDS | SID 0x14 (group 0xFFFFFF) | All DTC storage, freeze frames | N/A in standard UDS |
| WWH | SID 0x14 (group 0xFFFFFF) | DTC storage + counters 0xF607..0xF60C | IUMPR counters (0xF603) |

```c
void dem_clear_all(dem_ctx_t *ctx)
{
    for (uint8_t i = 0; i < DEM_MAX_DTC; i++) {
        dem_dtc_t *d = &ctx->dtcs[i];
        /* Reset all status bits except testNotCompletedSinceLastClear */
        d->status          = 0x20U;  /* testNotCompletedSinceLastClear */
        d->confirmed       = false;
        d->pending         = false;
        d->active          = false;
        d->mil_requested   = false;
        d->occurrence      = 0;
        d->confirm_count   = 0;
        d->heal_count      = 0;
        /* Permanent DTC: cleared only after perm_heal >= 3 */
        /* d->permanent: NOT cleared here — requires drive cycle completion */
    }
    /* Reset distance/time counters (WWH 0xF607..0xF60C) */
    ctx->dist_with_mil      = 0;
    ctx->dist_since_clear   = 0;
    ctx->min_with_mil       = 0;
    ctx->time_since_clear   = 0;
    ctx->warmup_since_clear = 0;
    /* IUMPR counters: NOT reset */
    /* ctx->iumpr: stays as-is */
    dem_nvm_save(ctx);
}

/* Permanent DTC healing — call at end of each drive cycle */
void dem_perm_dtc_heal_cycle(dem_ctx_t *ctx)
{
    for (uint8_t i = 0; i < DEM_MAX_DTC; i++) {
        dem_dtc_t *d = &ctx->dtcs[i];
        if (!d->permanent) continue;
        if (d->active) {
            d->perm_heal = 0;           /* fault recurred — reset heal counter */
        } else {
            if (++d->perm_heal >= 3U) {
                d->permanent  = false;
                d->perm_heal  = 0;
            }
        }
    }
}
```

---

## 8. J1939 Address-to-ECU Mapping for Multi-Protocol Dispatch

```c
/* Route incoming request to correct protocol handler */
void can_multi_protocol_dispatch(FDCAN_RxHeaderTypeDef *hdr,
                                  const uint8_t *data, uint8_t len,
                                  uint8_t my_j1939_sa)
{
    if (hdr->IdType == FDCAN_STANDARD_ID) {
        /* OBD-II */
        if (hdr->Identifier == 0x7DFU ||
            hdr->Identifier == (0x7E0U + my_j1939_sa))
            obd2_process(data, len);
        return;
    }

    uint32_t id = hdr->Identifier;
    uint8_t  pf = (id >> 16) & 0xFFU;
    uint8_t  da = (id >>  8) & 0xFFU;

    if (pf == 0xDAU && da == my_j1939_sa) {
        /* WWH-OBD physical UDS */
        wwh_uds_process(id, data, len);
    } else if (pf == 0xDBU) {
        /* WWH-OBD functional */
        wwh_uds_process(id, data, len);
    } else {
        /* J1939 (broadcast PGNs, TP, etc.) */
        j1939_process(id, data, len);
    }
}
```

---

## 9. Quick Reference: Byte Position of SPN[18:16] (Most Common Confusion)

```
J1939 DM1/DM2 wire format (4 bytes/DTC):
  [0]        SPN bits  [7:0]   ← LOWEST byte first
  [1]        SPN bits [15:8]
  [2][7:5]   SPN bits [18:16]
  [2][4:0]   FMI
  [3][7]     CM (conversion method)
  [3][6:0]   OC

WWH DID 0xF601 wire format (10 bytes/DTC):
  [0]        SPN bits [18:11]  ← HIGHEST byte first
  [1]        SPN bits [10:3]
  [2][7:5]   SPN bits [2:0]
  [2][4:0]   FMI

Rule: J1939 = little-endian SPN. WWH = big-endian shifted SPN.
Both share the same bit 2 field in the third byte.
```

```c
/* Validate decode: SPN should be identical after round-trip */
void dtc_selftest(void)
{
    uint32_t spn_orig = 3031U;  /* SCR inlet NOx */
    uint8_t  fmi_orig = 0U;

    /* J1939 encode/decode */
    uint8_t j_buf[4];
    j1939_dtc_t jd = { spn_orig, fmi_orig, 5 };
    j1939_encode_dtc(&jd, j_buf);
    j1939_decode_dtc(j_buf, &jd);
    assert(jd.spn == spn_orig && jd.fmi == fmi_orig);

    /* WWH encode/decode */
    uint8_t w_buf[10];
    wwh_dtc_t wd = { spn_orig, fmi_orig, 5, 0x40, 0x08, 0x02 };
    wwh_encode_dtc(&wd, w_buf);
    wwh_decode_dtc(w_buf, &wd);
    assert(wd.spn == spn_orig && wd.fmi == fmi_orig);
}
```
