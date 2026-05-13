# WWH-OBD (ISO 27145 / UN/ECE R49 Annex 9B) — Implementation Reference

## Standards Stack

- ISO 27145-1: General requirements
- ISO 27145-2: Common data dictionary
- ISO 27145-3: CAN implementation (J1939-based)
- ISO 27145-4: Connection between vehicle and test equipment
- UN/ECE R49 Annex 9B: Euro VI mandatory OBD requirements
- UN/ECE R96 Annex 5: Stage V agricultural/construction

---

## 1. Transport Layer — CAN ID Scheme (ISO 27145-3)

WWH-OBD uses SAE J1939 **29-bit extended** CAN IDs, NOT the 11-bit OBD-II 0x7E0/0x7E8 scheme.

### PGN 0x00DA — UDS-on-J1939 Physical Addressing

```
CAN ID structure:
  bits[28:26] Priority  = 6 (diagnostic default)
  bit[25]     R         = 0
  bit[24]     DP        = 0
  bits[23:16] PF        = 0xDA  (PDU1, peer-to-peer)
  bits[15:8]  DA        = Destination Address
  bits[7:0]   SA        = Source Address

Tester → ECU:  CAN_ID = 0x18DA[ECU_SA][TESTER_SA]
ECU → Tester:  CAN_ID = 0x18DA[TESTER_SA][ECU_SA]

Standard addresses:
  External tester SA = 0xF9
  Engine ECU SA      = 0x00 (J1939 default)
  Aftertreatment SA  = 0xFB

Example — Tester to Engine ECU (SA=0x00):
  Request:  CAN_ID = 0x18DA00F9
  Response: CAN_ID = 0x18DAF900

Functional (broadcast):
  PGN 0x00DB (PF=0xDB): CAN_ID = 0x18DBFEF9
  (DA=0xFE = functional address per ISO 27145-3)
```

### Contrast with Standard OBD-II / UDS

| | OBD-II (ISO 15031) | WWH-OBD (ISO 27145) |
|-|---------------------|---------------------|
| Frame type | 11-bit standard ID | 29-bit extended J1939 |
| Tester→ECU | 0x7E0 (fixed) | 0x18DA[ECU_SA][TESTER_SA] |
| ECU→Tester | 0x7E8 (fixed) | 0x18DA[TESTER_SA][ECU_SA] |
| Functional | 0x7DF | 0x18DBFEF9 |
| Transport | ISO-TP (ISO 15765-2) | ISO-TP over J1939 (ISO 27145-3) |

```c
#define WWH_PRIORITY       6U
#define WWH_PF_PHYSICAL    0xDAU
#define WWH_PF_FUNCTIONAL  0xDBU
#define WWH_TESTER_SA      0xF9U
#define WWH_FUNC_DA        0xFEU

uint32_t wwh_make_request_id(uint8_t ecu_sa) {
    return ((uint32_t)WWH_PRIORITY     << 26)
         | ((uint32_t)WWH_PF_PHYSICAL  << 16)
         | ((uint32_t)ecu_sa           <<  8)
         | WWH_TESTER_SA;
}

uint32_t wwh_make_response_id(uint8_t ecu_sa) {
    return ((uint32_t)WWH_PRIORITY     << 26)
         | ((uint32_t)WWH_PF_PHYSICAL  << 16)
         | ((uint32_t)WWH_TESTER_SA    <<  8)
         | ecu_sa;
}
```

### STM32 FDCAN Filter Setup for WWH ECU

```c
void wwh_fdcan_filter_init(uint8_t my_sa) {
    FDCAN_FilterTypeDef f;

    /* Physical: 0x18DA[MY_SA][F9] — exact match */
    f.IdType       = FDCAN_EXTENDED_ID;
    f.FilterIndex  = 0;
    f.FilterType   = FDCAN_FILTER_MASK;
    f.FilterConfig = FDCAN_FILTER_TO_RXFIFO0;
    f.FilterID1    = 0x18DA0000U | ((uint32_t)my_sa << 8) | 0xF9U;
    f.FilterID2    = 0x1FFFFFFFU;
    HAL_FDCAN_ConfigFilter(&hfdcan1, &f);

    /* Functional: 0x18DBFExx */
    f.FilterIndex = 1;
    f.FilterID1   = 0x18DBFE00U;
    f.FilterID2   = 0x1FFFFF00U;
    HAL_FDCAN_ConfigFilter(&hfdcan1, &f);

    HAL_FDCAN_ConfigGlobalFilter(&hfdcan1,
        FDCAN_REJECT, FDCAN_ACCEPT_IN_RX_FIFO1,
        FDCAN_FILTER_REMOTE, FDCAN_FILTER_REMOTE);
}
```

---

## 2. ISO-TP Timing Parameters (ISO 27145-3 §7.2)

Same frame structure as standard ISO-TP but different timeouts:

| Parameter | Value | Direction |
|-----------|-------|-----------|
| N_As | 25 ms | Sender transmit timeout |
| N_Bs | 75 ms | Sender wait for FC after FF |
| N_Cs | 25 ms | Sender inter-CF gap |
| N_Ar | 25 ms | Receiver FC transmit timeout |
| N_Cr | 150 ms | Receiver CF reception timeout |

---

## 3. WWH Sessions

| Session | subFn | WWH Rule |
|---------|-------|----------|
| defaultSession | 0x01 | Always active; ReadDTCInfo + ReadDataByID **mandatory** here |
| extendedDiagSession | 0x03 | Full access; ClearDTC requires this |
| programmingSession | 0x02 | Not required for OBD compliance |

**Critical: SID 0x19 and SID 0x22 (0xF6xx DIDs) MUST work in defaultSession (0x01).**
Regulatory requirement per R49 Annex 9B — roadside inspectors use default session.

---

## 4. WWH DIDs — 0xF600..0xF6FF

### Mandatory DID List (R49 Annex 9B)

| DID | Name | Session |
|-----|------|---------|
| 0xF600 | WWH-OBD Readiness Groups | Default |
| 0xF601 | WWH DTC List with Severity | Default |
| 0xF602 | Active DTCs (DM1-equivalent) | Default |
| 0xF603 | IUMPR (In-Use Monitor Performance Ratio) | Default |
| 0xF605 | Continuous MI counter | Default |
| 0xF606 | OBD certification requirements | Default |
| 0xF607 | Warm-up cycles since DTCs cleared | Default |
| 0xF609 | Distance traveled with MI active | Default |
| 0xF60A | Distance since DTCs cleared | Default |
| 0xF60B | Minutes run with MI active | Default |
| 0xF60C | Time since DTCs cleared | Default |
| 0xF60D | Engine run time | Default |
| 0xF60F | Engine hours | Default |
| 0xF610 | ECU software version | Default |
| 0xF611 | ECU hardware number | Default |

### DID 0xF600 — Readiness Groups

```
Byte 0:     Count (N) of readiness groups
Byte 1..N:  One byte per group:
  bits[7:4]  Group ID
  bits[3:2]  Availability: 00=not supported, 01=supported
  bits[1:0]  Status: 00=not complete, 01=complete, 10=N/A, 11=failed

WWH Group IDs:
  0x00 Misfire               0x08 O2 sensor
  0x01 Fuel system           0x09 O2 heater
  0x02 Components            0x0A EGR/VVT
  0x03 Catalyst              0x0B NOx aftertreatment (SCR/LNT) — HD specific
  0x04 Heated catalyst       0x0C DPF — HD specific
  0x05 Evap                  0x0D Boost pressure — HD specific
  0x06 Secondary air
  0x07 A/C
```

### DID 0xF601 — WWH DTC List with Severity

**Exact byte layout — 2-byte header + 10 bytes per DTC:**

```
Bytes 0-1:  DTC count (uint16, big-endian)

Per DTC (10 bytes):
  Byte 0:   SPN bits[18:11]
  Byte 1:   SPN bits[10:3]
  Byte 2:   SPN bits[2:0] in positions [7:5] | FMI bits[4:0] in positions [4:0]
  Byte 3:   Occurrence count (0..126; 127=unknown)
  Byte 4:   WWH Severity (0x00/0x20/0x40/0x60)
  Byte 5:   ISO 14229 statusOfDTC byte
  Byte 6:   Lamp status (bit0=MIL, bit1=AWL, bit2=RSL, bit3=PIL)
  Byte 7:   Reserved (0xFF)
  Bytes 8-9: IUMPR OC counter (0xFFFF if unused)
```

```c
typedef struct {
    uint32_t spn;        /* 19-bit SPN */
    uint8_t  fmi;        /* 5-bit FMI */
    uint8_t  occurrence; /* 0..126; 127=unknown */
    uint8_t  severity;   /* 0x00/0x20/0x40/0x60 */
    uint8_t  status;     /* ISO 14229 statusOfDTC byte */
    uint8_t  lamp;       /* MIL|AWL|RSL|PIL bits */
} wwh_dtc_t;

#define WWH_LAMP_MIL  (1U << 0)
#define WWH_LAMP_AWL  (1U << 1)
#define WWH_LAMP_RSL  (1U << 2)
#define WWH_LAMP_PIL  (1U << 3)

uint16_t wwh_encode_f601(const wwh_dtc_t *dtcs, uint8_t n,
                          uint8_t *out, uint16_t out_sz)
{
    if (out_sz < 2U + (uint16_t)n * 10U) return 0;
    out[0] = 0;
    out[1] = n;
    for (uint8_t i = 0; i < n; i++) {
        uint8_t *p = out + 2 + i * 10;
        p[0] = (dtcs[i].spn >> 11) & 0xFFU;
        p[1] = (dtcs[i].spn >>  3) & 0xFFU;
        p[2] = ((dtcs[i].spn & 7U) << 5) | (dtcs[i].fmi & 0x1FU);
        p[3] = dtcs[i].occurrence;
        p[4] = dtcs[i].severity;
        p[5] = dtcs[i].status;
        p[6] = dtcs[i].lamp;
        p[7] = 0xFF;
        p[8] = 0xFF;
        p[9] = 0xFF;
    }
    return 2U + (uint16_t)n * 10U;
}
```

**statusOfDTC bits (ISO 14229 §D.3):**
```
bit 0: testFailed
bit 1: testFailedThisMonitoringCycle
bit 2: pendingDTC
bit 3: confirmedDTC
bit 4: testNotCompletedSinceLastClear
bit 5: testFailedSinceLastClear
bit 6: testNotCompletedThisMonitoringCycle
bit 7: warningIndicatorRequested (MIL trigger)
```

---

## 5. DTC Severity — Exact Values and Meaning

| Byte | Name | When | Lamp |
|------|------|------|------|
| 0x00 | No failure | Informational / no fault | None |
| 0x20 | Maintenance required | Degraded performance, service needed | PIL |
| 0x40 | Check at next halt | Stop vehicle when safe, check system | AWL |
| 0x60 | Immediately stop vehicle | Critical safety fault | RSL + AWL |

```c
typedef enum {
    WWH_SEV_NONE        = 0x00,
    WWH_SEV_MAINTENANCE = 0x20,
    WWH_SEV_HALT        = 0x40,
    WWH_SEV_STOP_NOW    = 0x60,
} wwh_severity_t;
```

---

## 6. Lamp Activation Rules

| Lamp | Color | Activation Trigger |
|------|-------|-------------------|
| MIL (Malfunction Indicator) | Amber | Emission-related confirmed DTC (statusOfDTC bit 7 set) |
| AWL (Amber Warning Lamp) | Amber | severity 0x40 DTC confirmed, OR RSL condition |
| RSL (Red Stop Lamp) | Red | severity 0x60 DTC confirmed |
| PIL (Protection Indicator Lamp) | Amber | severity 0x20 DTC confirmed |

```c
void wwh_update_lamps(const wwh_dtc_t *dtcs, uint8_t n,
                      bool *mil, bool *awl, bool *rsl, bool *pil)
{
    *mil = *awl = *rsl = *pil = false;
    for (uint8_t i = 0; i < n; i++) {
        bool active = (dtcs[i].status & 0x09U) != 0U; /* confirmed | testFailed */
        if (!active) continue;
        if (dtcs[i].status   & 0x80U)             *mil = true; /* warningIndicatorRequested */
        if (dtcs[i].severity == WWH_SEV_STOP_NOW) { *rsl = true; *awl = true; }
        if (dtcs[i].severity == WWH_SEV_HALT)       *awl = true;
        if (dtcs[i].severity == WWH_SEV_MAINTENANCE) *pil = true;
    }
}
```

**MIL deactivation:** Requires **3 consecutive drive cycles** without the fault confirming.
RSL/AWL deactivate immediately when severity fault resolves.
PIL deactivates when maintenance condition resolves.

```c
void wwh_trip_end(bool fault_this_trip, uint8_t *no_fail_trips, bool *mil_active)
{
    if (fault_this_trip) {
        *no_fail_trips = 0;
        *mil_active    = true;
    } else if (++(*no_fail_trips) >= 3U && *mil_active) {
        *mil_active    = false;
        *no_fail_trips = 0;
    }
}
```

---

## 7. IUMPR — In-Use Monitor Performance Ratio

### DID 0xF603 Byte Layout

```
Bytes 0-1:  General Denominator (uint16 BE)
Bytes 2-3:  Ignition Cycle Counter (uint16 BE)
Byte 4:     Number of monitor entries (N)

Per monitor (8 bytes):
  Byte 0:    Monitor ID (see table)
  Bytes 1-2: Numerator   (uint16 BE, max 0xFAFF)
  Bytes 3-4: Denominator (uint16 BE, max 0xFAFF)
  Bytes 5-7: Reserved (0xFF)

Monitor IDs:
  0x01 NOx catalyst (SCR)    0x06 Boost pressure
  0x02 NOx adsorber (LNT)    0x07 Fuel system
  0x03 DPF                   0x08 O2 sensor
  0x04 Oxidation catalyst    0x09 Misfire
  0x05 EGR                   0x0A Components
```

### Key Differences from OBD-II Readiness

| | OBD-II Mode 0x01 | WWH IUMPR |
|-|-----------------|-----------|
| What measured | Binary bit (done/not done) | Ratio (numerator/denominator) |
| Persistence | Resets each drive cycle | Accumulates over vehicle life |
| Regulatory threshold | Must be complete | Min ratio 0.1 (1 per 10 eligible trips) |
| Reset trigger | DTC clear, battery disconnect | Counters persist; R49 restricts reset |

### Denominator Increment Conditions (General Denominator)

All of these must be satisfied **in the same drive cycle**, once per trip:
1. Engine coolant reached ≥70°C at some point
2. Vehicle speed exceeded 40 km/h for ≥10 minutes cumulative
3. Engine running ≥10 minutes total
4. One increment per ignition cycle (not per mile)

### Numerator Increment

Per monitor: numerator increments once when monitor completes evaluation (pass or fail). Monitor-specific denominators may have additional conditions (DPF requires cold start; SCR requires DEF temp above threshold).

### IUMPR Freeze Conditions

Counters MUST NOT increment when:
- Active confirmed DTC for that specific monitor
- Monitor disabled by active faults
- ECU in extended diagnostic session (service mode)
- Counter at 0xFAFF (saturates, no rollover)

```c
#define IUMPR_MAX  0xFAFFU

typedef struct {
    uint16_t num;
    uint16_t den;
    bool     frozen;
} iumpr_mon_t;

void iumpr_monitor_done(iumpr_mon_t *m, bool eligible)
{
    if (m->frozen) return;
    if (eligible && m->den < IUMPR_MAX) m->den++;
    if (m->num < IUMPR_MAX)             m->num++;
}

void iumpr_general_den_trip(uint16_t *gen_den)
{
    if (*gen_den < IUMPR_MAX) (*gen_den)++;
}
```

---

## 8. Mandatory Services in WWH

| SID | Service | Mandatory | Minimum Session |
|-----|---------|-----------|----------------|
| 0x10 | DiagnosticSessionControl | YES | Any |
| 0x14 | ClearDiagnosticInformation | YES | Extended (0x03) |
| 0x19 | ReadDTCInformation | YES | Default (0x01) |
| 0x22 | ReadDataByIdentifier (0xF6xx) | YES | Default (0x01) |
| 0x3E | TesterPresent | YES | Any |
| 0x7F | NegativeResponse | YES | Any |
| 0x11 | ECUReset | Optional | Extended |
| 0x27 | SecurityAccess | Optional | Extended |

**Mandatory SID 0x19 sub-functions:**
- 0x02 reportDTCByStatusMask — MANDATORY
- 0x0A reportSupportedDTC — MANDATORY
- 0x04 reportDTCSnapshotRecordByDTCNumber — optional

**SID 0x14 in WWH:** Group 0xFFFFFF (clear all) is the only required group. Clears DTC storage + resets distance/time counters (0xF607..0xF60C). IUMPR counters (0xF603) do NOT reset.

---

## 9. OBD-II + J1939 + WWH-OBD Coexistence on Same ECU

No CAN ID collision — different frame formats are hardware-separated:
- OBD-II: 11-bit STD IDs (0x7E0, 0x7DF, 0x7E8)
- WWH/J1939: 29-bit EXT IDs (0x18DA…)

```c
void can_rx_dispatch(FDCAN_RxHeaderTypeDef *hdr, const uint8_t *data)
{
    if (hdr->IdType == FDCAN_STANDARD_ID) {
        obd2_isotp_rx(hdr->Identifier, data);
    } else {
        uint8_t pf = (hdr->Identifier >> 16) & 0xFFU;
        if (pf == 0xDAU || pf == 0xDBU)
            wwh_isotp_rx(hdr->Identifier, data);
        else
            j1939_rx(hdr->Identifier, data);
    }
}

void dual_obd_fdcan_init(uint8_t wwh_ecu_sa)
{
    FDCAN_FilterTypeDef f;

    /* OBD-II physical 0x7E0 */
    f.IdType=FDCAN_STANDARD_ID; f.FilterIndex=0;
    f.FilterType=FDCAN_FILTER_MASK; f.FilterConfig=FDCAN_FILTER_TO_RXFIFO0;
    f.FilterID1=0x7E0U; f.FilterID2=0x7FFU;
    HAL_FDCAN_ConfigFilter(&hfdcan1, &f);

    /* OBD-II functional 0x7DF */
    f.FilterIndex=1; f.FilterID1=0x7DFU; f.FilterID2=0x7FFU;
    HAL_FDCAN_ConfigFilter(&hfdcan1, &f);

    /* WWH physical 0x18DA[SA][F9] */
    f.IdType=FDCAN_EXTENDED_ID; f.FilterIndex=2;
    f.FilterID1=0x18DA0000U | ((uint32_t)wwh_ecu_sa << 8) | 0xF9U;
    f.FilterID2=0x1FFFFFFFU;
    HAL_FDCAN_ConfigFilter(&hfdcan1, &f);

    /* WWH functional 0x18DBFExx */
    f.FilterIndex=3;
    f.FilterID1=0x18DBFE00U; f.FilterID2=0x1FFFFF00U;
    HAL_FDCAN_ConfigFilter(&hfdcan1, &f);

    /* J1939 catch-all → FIFO1 */
    HAL_FDCAN_ConfigGlobalFilter(&hfdcan1,
        FDCAN_REJECT, FDCAN_ACCEPT_IN_RX_FIFO1,
        FDCAN_FILTER_REMOTE, FDCAN_FILTER_REMOTE);
}
```

---

## 10. Permanent DTCs in WWH

WWH has no direct Mode 0x0A equivalent, but achieves similar intent:

1. **confirmedDTC persistence:** bit 3 of statusOfDTC persists across ignition cycles until 3 no-fault trips OR SID 0x14
2. **MIL 3-trip rule:** MIL stays on for 3 clean trips after fault heals
3. **testFailedSinceLastClear (bit 5):** Persists until SID 0x14 even if fault resolved
4. **IUMPR counters:** Do NOT reset on SID 0x14

The practical difference: OBD-II Mode 0x0A cannot be cleared by Mode 0x04 at all (requires drive cycle completion). WWH uses the 3-trip healing rule + NVM persistence to achieve similar tamper resistance.

---

## 11. J1939 Address Assignment on WWH Bus

```
0x00  Engine #1 (primary OBD ECU)
0x03  Transmission #1
0xFB  Aftertreatment #1 (SCR/DPF)
0xF9  External diagnostic tester (ISO 27145-3 assigned)
0xFA  OBD tester alternate
```

No separate diagnostic bus needed — WWH shares the production J1939 bus.

**Baud rate:** 250 kbps mandatory (shared J1939 bus). 500 kbps optional if all nodes support it.

**STM32H7 @ 80 MHz FDCAN clock for 250 kbps:**
```c
hfdcan1.Init.NominalPrescaler     = 20;  /* 80MHz / (250kHz × 16) = 20 */
hfdcan1.Init.NominalTimeSeg1      = 13;  /* SP = 87.5% */
hfdcan1.Init.NominalTimeSeg2      = 2;
hfdcan1.Init.NominalSyncJumpWidth = 1;
```

---

## 12. Protocol Comparison Matrix

| Feature | OBD-II (J1979) | J1939 DM1/DM2 | WWH-OBD (ISO 27145) |
|---------|---------------|--------------|---------------------|
| CAN bits | 11-bit STD | 29-bit EXT | 29-bit EXT |
| Protocol | ISO 15765-2 | J1939-TP | ISO-TP over J1939 |
| Request ID | 0x7DF / 0x7E0 | PGN 0xFECA broadcast | 0x18DA[SA][F9] |
| DTC encoding | P/C/B/U code | SPN+FMI | SPN+FMI + ISO status byte |
| Severity | None | None (lamp status in DM1) | 0x00/0x20/0x40/0x60 |
| Lamps | MIL only | MIL+RSL+AWL+PIL | MIL+AWL+RSL+PIL |
| Readiness | Mode 0x01 bits (binary) | Not standardized | IUMPR ratios (0xF603) |
| Clear DTC | Mode 0x04 | DM11 (PGN 0xFEC1) | SID 0x14, extended session |
| Live data | Mode 0x01 PIDs | SPN via PGN | SID 0x22, 0xF6xx DIDs |
| Permanent DTC | Mode 0x0A | No | 3-trip MIL rule + NVM |
| Legislation | CARB/EPA (US) | Voluntary | Euro VI, Stage V (EU) |

---

## 13. AUTOSAR DCM Configuration Notes

```
DcmDsl → DcmDslProtocol → DcmDslProtocolRow[WWH]:
  DcmDslProtocolID: DCM_UDS_ON_CAN
  RxBuffer: ≥4095 bytes
  TxBuffer: ≥4095 bytes
  DcmDslConnection → DcmDslMainConnection:
    Physical Rx PDU: 29-bit extended, CAN_ID = 0x18DA[MY_SA][F9]
    Functional Rx PDU: 29-bit extended, CAN_ID = 0x18DBFEF9
    Tx PDU: 29-bit extended, CAN_ID = 0x18DA[F9][MY_SA]

DEM lamp indicators:
  DemIndicator[MIL]: DemWWHOBDDTCSeverity = emission-related (bit 7 statusOfDTC)
  DemIndicator[AWL]: DemWWHOBDDTCSeverity = WWH_SEV_HALT (0x40)
  DemIndicator[RSL]: DemWWHOBDDTCSeverity = WWH_SEV_STOP_NOW (0x60)
  DemIndicator[PIL]: DemWWHOBDDTCSeverity = WWH_SEV_MAINTENANCE (0x20)
```

---

## 14. Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| 11-bit CAN IDs for WWH | Tester cannot connect | Use 29-bit extended, PGN 0xDA |
| Wrong ECU SA in filter | All requests dropped | Filter exact `0x18DA[MY_SA][F9]` |
| SPN byte order wrong in 0xF601 | Garbage DTC codes | Byte 0=bits[18:11], byte 1=bits[10:3], byte 2=[2:0]in[7:5]\|FMI |
| IUMPR reset on SID 0x14 | R49 compliance failure | IUMPR counters survive DTC clear |
| MIL off after 1 clean trip | R49 §3.4 violation | Require 3 consecutive clean trips |
| AWL/RSL not activating | Missing severity mapping | Check severity byte → lamp logic |
| SID 0x14 in default session | R49 violation | Require extended session (0x03) |
| SID 0x19 unavailable in default | Roadside inspection fails | Mandatory in default session |
| General denominator stuck at 0 | IUMPR always 0 | Check 70°C coolant + 40 km/h + 10 min conditions |
| Functional address 0x7DF for WWH | Requests missed | Use 0x18DBFEF9 for WWH functional |
| ClearDTC clears IUMPR | R49 §6.1 violation | Separate IUMPR NVM region, no reset on SID 0x14 |
| Missing FDCAN GlobalFilter config | J1939 frames accepted, WWH dropped | `HAL_FDCAN_ConfigGlobalFilter()` mandatory after per-filter setup |
