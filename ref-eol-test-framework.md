# End-of-Line (EOL) Test Framework — Production-Line Validation

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Test architecture, test-case taxonomy, decision criteria, and supply-chain checks** here are authoritative — these are the patterns that catch production escapes.
> - **Specific test thresholds** (RAM pattern timing, ADC noise floor, voltage tolerances) are illustrative; calibrate to your hardware design's nominal values + 3σ window.
> - **Boundary-scan TAP commands** depend on the BSDL file of your exact part. Always download the BSDL from ST's website for your part-number revision.
> - **Calibration storage layout** here is one defensible pattern; many valid alternatives exist — pick once, version it, and live with it.

## Why EOL testing is mandatory

The cost of a defect shifts dramatically by stage of detection:

| Detected at | Repair cost | Customer impact |
|------------|-------------|-----------------|
| Component supplier (incoming inspection) | Component price | None |
| EOL test (production line) | Rework: ~30 min labor + de-solder | None |
| Final pack-out (warehouse) | Scrap unit | None |
| Customer hands (field return) | Logistics + RMA + brand damage | **High** |

Industrial rule of thumb (Lockheed/Boeing reliability handbook): cost
multiplier of 10× per stage downstream. A defect costing $1 to catch at
EOL costs $10000 to catch in the field. EOL test design is therefore an
investment, not a cost.

## EOL Test Stages — what runs and when

```
   ┌────────────────────────────────────────────────────────────────┐
   │  ICT (In-Circuit Test) — bare PCB before any firmware          │
   │  - Boundary scan: opens/shorts/missing components              │
   │  - Power rail measurement (DMM probe)                          │
   │  - Flash empty check                                           │
   └─────────────────────────────────┬──────────────────────────────┘
                                     │
   ┌─────────────────────────────────▼──────────────────────────────┐
   │  Provisioning — SFI/HSM secure firmware install                │
   │  - See ref-key-provisioning.md                                 │
   │  - At completion: device runs in BL2 self-test mode            │
   └─────────────────────────────────┬──────────────────────────────┘
                                     │
   ┌─────────────────────────────────▼──────────────────────────────┐
   │  Self-Test — bootloader runs builtin BIST suite                │
   │  - RAM pattern test (March-C, abbreviated)                     │
   │  - Flash CRC verify against signed manifest                    │
   │  - Peripheral ping (every enabled IP responds to its IDR)      │
   │  - Clock validation (HSE/HSI/PLL lock with bounds check)       │
   │  - Brown-out / VBAT measurement                                │
   │  - Reports pass/fail via UART/SWO/GPIO LED to test fixture     │
   └─────────────────────────────────┬──────────────────────────────┘
                                     │
   ┌─────────────────────────────────▼──────────────────────────────┐
   │  Functional Test — application loaded, real I/O exercised      │
   │  - CAN/Ethernet/RS485 loopback                                 │
   │  - ADC noise floor + linearity (golden ref voltage applied)    │
   │  - Sensor read-out (golden sensor on bed-of-nails)             │
   │  - Actuator drive (motor/solenoid stub, current measured)      │
   │  - RTC/backup domain (battery voltage check, oscillator drift) │
   └─────────────────────────────────┬──────────────────────────────┘
                                     │
   ┌─────────────────────────────────▼──────────────────────────────┐
   │  Calibration — per-unit constants written to dedicated region  │
   │  - ADC gain/offset, sensor zero, motor offset, RF trim         │
   │  - See §"Calibration Storage Strategy" below                   │
   └─────────────────────────────────┬──────────────────────────────┘
                                     │
   ┌─────────────────────────────────▼──────────────────────────────┐
   │  Lock-down — final option bytes / life-cycle CLOSED            │
   │  - RDP=1, WRP, PCROP, BOOT_LOCK, nDBOOT0                       │
   │  - HDP latch on next boot                                      │
   │  - Production-test self-test mode disabled                     │
   │  - Verify post-lock: ALL the above is actually in effect       │
   └────────────────────────────────────────────────────────────────┘
```

## Self-Test (BIST) Suite — what to run in bootloader

### 1. RAM Pattern Test (abbreviated March-C)

Full March-C runs O(6n) writes — too slow on a production line for 1 MB SRAM.
Use the **abbreviated March-C** which catches stuck-at, transition, coupling
faults at O(2n):

```c
/* Test SRAM block — call BEFORE app data is loaded into the region under test */
static int ram_test_march_c_minus(uint32_t *base, size_t words)
{
    /* Pass 1: write 0 ascending */
    for (size_t i = 0; i < words; i++) base[i] = 0;

    /* Pass 2: read 0, write ~0 ascending */
    for (size_t i = 0; i < words; i++) {
        if (base[i] != 0)             return -1;  /* stuck-at-1 */
        base[i] = 0xFFFFFFFF;
    }

    /* Pass 3: read ~0, write 0 descending */
    for (size_t i = words; i-- > 0; ) {
        if (base[i] != 0xFFFFFFFF)    return -1;  /* coupling */
        base[i] = 0;
    }

    /* Pass 4: read 0 descending */
    for (size_t i = words; i-- > 0; ) {
        if (base[i] != 0)             return -1;
    }
    return 0;
}
```

**Apply to:** SRAM1, SRAM2, SRAM3, AXISRAM, DTCM, ITCM, BKPSRAM, SRAMCAN.
Each block must be tested separately because each has its own controller.

**Timing budget on H7 @ 480 MHz:** AXI SRAM 512 KB ≈ 12 ms. DTCM 128 KB ≈ 3 ms.
ITCM 64 KB ≈ 1.5 ms. Total ~18 ms — acceptable for production line.

### 2. Flash CRC Verify

The firmware was signed at SFI creation time. On boot, recompute CRC over the
.text/.rodata regions and compare against the manifest. Catches:

- Programming errors (bit-flips during flash write)
- Aging / radiation upset (years after shipment)
- Tampering attempts (firmware modified, signature not refreshed)

```c
/* Hardware CRC32 — H7 CRC peripheral, ~10 cycles per word */
extern uint32_t __manifest_crc;     // from linker
extern uint32_t _stext, _etext_rodata;

bool flash_crc_verify(void)
{
    __HAL_RCC_CRC_CLK_ENABLE();
    CRC->CR = CRC_CR_RESET;
    uint32_t *p = (uint32_t *)&_stext;
    uint32_t *end = (uint32_t *)&_etext_rodata;
    while (p < end) CRC->DR = *p++;
    return CRC->DR == __manifest_crc;
}
```

For TrustZone parts (H5/U5/L5), the bootloader's signature verification
already does this with ECDSA — separate CRC not strictly needed but cheap
defense-in-depth.

### 3. Peripheral Ping

Every peripheral has an **identification register** (`IDR` / `IDCODE` /
`HWCFGR`) at a fixed offset, typically with the silicon revision encoded.
Read each enabled peripheral's IDR; mismatch = peripheral clock dead,
peripheral missing on this die (wrong part-number programmed), or bus
fault.

```c
typedef struct {
    const char *name;
    volatile uint32_t *idr;
    uint32_t expected;
    uint32_t mask;
} Periph_Ping_t;

static const Periph_Ping_t pings[] = {
    { "USART1", &USART1->IDR,    0x00220020, 0xFFFFFFFF },
    { "FDCAN1", (uint32_t *)0x4000A4FC, 0x32302E33, 0xFFFFFFFF }, /* CREL */
    { "SPI1",   &SPI1->IDR,      0x00220020, 0xFFFFFFFF },
    /* ... one row per peripheral your firmware uses ... */
};

int peripheral_ping_all(void)
{
    for (size_t i = 0; i < ARRAY_SIZE(pings); i++) {
        uint32_t v = *pings[i].idr;
        if ((v & pings[i].mask) != pings[i].expected) {
            log_fail(pings[i].name, v);
            return -1;
        }
    }
    return 0;
}
```

**Caveat:** ST sometimes changes IDR encoding between silicon revs. Check
the RM for the exact field for your rev — don't assume across revs.

### 4. Clock Validation

After `SystemClock_Config()`, the clock tree should be at the target frequency.
Two confirmations:

```c
/* (a) PLL/HSE lock bits — RCC->CR should show all expected lock flags */
uint32_t cr = RCC->CR;
if (!(cr & RCC_CR_HSERDY) || !(cr & RCC_CR_PLL1RDY)) return -1;

/* (b) Measure SYSCLK against a known-good reference (LSE or HSI) */
/* Use TIM timing capture of LSI/LSE edges against SYSCLK-driven counter */
/* If SYSCLK ±0.5% of nominal → pass */
uint32_t measured_sysclk_hz = clock_measure_via_lsi();
uint32_t nominal = 480000000;
uint32_t tolerance = nominal / 200;  // ±0.5%
if (abs((int)(measured_sysclk_hz - nominal)) > tolerance) return -1;
```

The cross-clock measurement is the only way to catch a **PLL that locked but
to the wrong frequency** (e.g., HSE crystal is the wrong value, but PLL ratio
still locks).

### 5. Brown-Out / VBAT / VREF Check

```c
/* PWR->CSR2 (H7) → AVDO/AVDORDY for analog supply
 * PWR_FLAG_BRR  → backup domain regulator
 * VBAT through internal channel of ADC (channel 18 typical) */
HAL_ADC_Start(&hadc_internal);
HAL_ADC_PollForConversion(&hadc_internal, 10);
uint16_t vbat_mv = (HAL_ADC_GetValue(&hadc_internal) * VREF_INT) / 4096 * 2;
if (vbat_mv < 2700 || vbat_mv > 3600) return -1;  /* coin cell dead or wrong */
```

VBAT below 2.7V → battery installed but discharged (factory inventory aging).
Catch at EOL, replace battery, ship with full backup-domain budget.

### 6. UID Read + Logging

```c
/* 96-bit unique ID — log to MES system for traceability */
uint32_t uid[3] = {
    *(volatile uint32_t *)0x1FF1E800,   /* H7 UID base — verify per family RM */
    *(volatile uint32_t *)0x1FF1E804,
    *(volatile uint32_t *)0x1FF1E808,
};
mes_log_serial(uid);  /* fixture-side: serial+batch+timestamp+test results */
```

UID is non-secret but globally unique — use it as the production-line serial
number. Customer-visible serial can be derived (HMAC of UID with OEM key)
so it's stable but not enumerable.

## Boundary-Scan / JTAG IEEE 1149.1

For PCB-level test (opens, shorts, missing parts) the JTAG TAP controller
runs **boundary-scan instructions** that drive every I/O pin from outside
the chip, without needing firmware. Run BEFORE first firmware load.

### Standard instructions

| Instruction | What it does |
|------------|--------------|
| `BYPASS` | Skip this chip in chain |
| `IDCODE` | Read 32-bit JEDEC + part ID (verify correct chip placed) |
| `SAMPLE/PRELOAD` | Snapshot or set pin state without disturbing chip |
| `EXTEST` | Drive pin state from boundary-scan register (test traces) |
| `INTEST` | Drive internal logic from BSR (rarely supported on STM32) |

### Workflow

1. **IDCODE check** — verify chip's JEDEC code matches expected part-number
   (catches wrong-part-placed).
2. **Chain integrity** — issue BYPASS to all, verify expected chain length
   (catches missing chip in chain).
3. **Net interconnect test** — for each net connecting two BSC-capable chips,
   `EXTEST` one chip's output, `SAMPLE` other's input, verify expected value.
   Repeat with 0 then 1 — catches opens (no propagation) and shorts (multi-net
   coupling).

### Required: BSDL file

ST publishes a `.bsdl` file per part on the part's product page (search
"STM32H730 BSDL" on st.com). The BSDL describes:

- Pin → BSC register cell mapping
- Cell type (input/output/control/bidir)
- Boundary register length
- Supported instructions

Tools that consume BSDL: JTAG Technologies ProVision, Xilinx Vivado (for
boards mixing FPGAs+MCUs), ASSET InterTest, free `jtag` Linux package.

### Common boundary-scan pitfalls

- **JTAG_TRST not asserted** before EXTEST → chip held in reset state, no
  pin response. Drive TRST low first.
- **Power up sequence** — boundary scan requires VCC + VDD_IO. Some
  test fixtures forget to power VDD_USB on STM32H7 → BSC fails on USB pins.
- **Open-drain pins** (I2C SCL/SDA) need external pull-up on fixture to see
  HIGH; without pull-up, all reads return 0.
- **Pin-multiplexed JTAG** (e.g., PA13/PA14) — if firmware re-purposes these
  pins as GPIO, BSC stops working **after firmware runs**. So always run
  BSC before flashing.

## Calibration Storage Strategy

Per-unit calibration constants (ADC offset/gain, sensor zero, motor offset)
need to survive firmware updates. The storage layout has three valid options:

### Option A — OTP (One-Time Programmable) flash

```
Pros: Cannot be erased by mass-erase. Survives firmware update.
Cons: One-shot, no in-field recalibration. Limited size (typically 1 KB).
Use when: cal constants are factory-set, never change.
Address:  STM32H7 OTP = 0x08FFF000 (1 KB, 512 bytes for user data)
```

### Option B — Dedicated flash sector (WRP-protected)

```
Pros: Re-writable in field (with auth), large size (one sector typ. 128 KB).
Cons: Mass-erase wipes it unless RDP→2 transition is blocked.
Use when: calibration may need field update (re-zero after drift).
```

### Option C — Backup SRAM (BKPSRAM, battery-backed)

```
Pros: Re-writable runtime, fast.
Cons: Lost if VBAT dies. Wrong choice for "permanent" cal.
Use when: cal is fast-changing runtime state, not factory data.
```

**Recommended pattern for industrial:** Option A (OTP) for factory burn,
Option B (WRP flash) for field re-zero with manifest:

```c
typedef struct __attribute__((packed)) {
    uint32_t magic;            /* 0xCA1B2026 */
    uint16_t version;          /* layout revision */
    uint16_t length;           /* payload length */
    uint8_t  payload[256];     /* calibration data */
    uint32_t crc32;            /* CRC over magic..payload */
} CalibrationBlob_t;
```

- **Magic + version** — gate firmware load: if version mismatch, fall back
  to last-known-good (CalibrationBlob N-1 in adjacent slot).
- **Length-prefixed payload** — supports adding fields without breaking
  existing firmware.
- **CRC32** — catches corruption from incomplete writes (power-loss during
  field re-calibration).

Store TWO blobs in alternating slots ("ping-pong"). Always write the
inactive slot first, verify CRC, then update an active-slot pointer.
If power dies mid-write, the still-valid slot is loaded next boot.

## Life-Cycle Lock Test (post-lockdown verification)

After running the `Lock-down` stage in the EOL flow, **verify it actually
locked**. Skipping this is the #1 production escape on secure-mode devices.

```bash
# Production test fixture, after option bytes written
EXPECTED_RDP=0xBB                    # RDP level 1
EXPECTED_WRP_STRT=0
EXPECTED_WRP_END=15
EXPECTED_BOOT_LOCK=1

# Read option bytes back
STM32_Programmer_CLI -c port=SWD -ob displ > ob.dump

# Strict checks
grep "RDP\s*:\s*0x${EXPECTED_RDP}"        ob.dump || fail "RDP not locked"
grep "WRP1A_STRT\s*:\s*${EXPECTED_WRP_STRT}" ob.dump || fail "WRP wrong"
grep "BOOT_LOCK\s*:\s*${EXPECTED_BOOT_LOCK}" ob.dump || fail "BOOT_LOCK not set"

# Attempt READ that should now fail (negative test)
STM32_Programmer_CLI -c port=SWD -r 0x08000000 16 read.bin 2>&1 | \
    grep -q "Error" || fail "Readback succeeded — RDP=1 not active"

# Confirm DBGAUTH (M33 parts) actually denies anonymous connect
# (separate test — see ref-secure-debug.md)
```

If ANY of these fails, **the unit cannot ship.** Move to repair bin, do not
mark "EOL pass".

## Bed-of-nails fixture design checklist

| Item | Why |
|------|-----|
| Pogo pins for VCC, GND, SWDIO, SWCLK, NRST, BOOT0 | Minimum for SWD program |
| Pogo pins for one UART (TX from DUT) | Self-test log readout without SWD bandwidth |
| Pogo pins for every enabled CAN/RS485/Ethernet | Loopback test |
| Pogo pin for each ADC input wired to fixture-side voltage source | ADC linearity sweep |
| Golden sensor connected to each sensor bus (I2C/SPI) | Realistic sensor-stack test |
| Active motor/actuator load (current shunt) | Drive-strength validation |
| Programmer + HSM card slot | SFI install |
| MES integration (read UID, log results, drive label printer) | Traceability |
| 12V/24V/48V supply tap with current monitor | Catches shorts immediately, before chip damage |
| Bed grounded to ESD-safe surface | Prevents test-induced damage |
| Cycle counter on fixture | Detect probe pin wear (replace pins every ~100k cycles) |

## EOL test pass criteria

| Stage | Pass criterion | Action on fail |
|-------|---------------|---------------|
| ICT (boundary scan) | All nets pass continuity | Reroute to rework |
| Provisioning | SFI completion ACK + UID logged | Retry once, then scrap |
| Self-test (BIST) | All RAM/Flash CRC/peripheral pings pass | Reroute to debug bench |
| Functional | All loopback / sensor reads / actuator drives within spec | Reroute to debug bench |
| Calibration | All cal constants written, CRC verified, ping-pong slots both valid | Re-run cal once, then reroute |
| Lock-down verify | RDP/WRP/BOOT_LOCK match expected; debug attach denied | **DO NOT SHIP** — repair bin |
| Final functional | Self-test passes after lock, with locked-mode firmware | Same as above |

**Throughput target:** total EOL test < 60 seconds per unit. Stretch
goals add more stages; production line speed is the constraint that
disciplines the test design.

## Canonical references

| Doc | Coverage | URL |
|-----|----------|-----|
| AN5054 | SFI provisioning (covered in [ref-key-provisioning.md](ref-key-provisioning.md)) | as above |
| UM2237 | STM32CubeProgrammer CLI — `-ob displ`, `-r`, `-sfi` flags | https://www.st.com/resource/en/user_manual/um2237-stm32cubeprogrammer-software-description-stmicroelectronics.pdf |
| IEEE 1149.1-2013 | Boundary-Scan standard | https://standards.ieee.org/ieee/1149.1/4906/ |
| ST BSDL files | Per part-number, search "<partno> BSDL site:st.com" | st.com |
| AN5421 | STM32H7 OTP byte layout for cal storage | https://www.st.com/resource/en/application_note/an5421-getting-started-with-stm32cubeh7-and-stm32cubemx-for-stm32h7-series-stmicroelectronics.pdf |
| March-C / March-C− memory test theory | "Open Defects in CMOS RAMs" (Sachdev/Pradhan) | academic |

## Cross-references

- Provisioning step inputs (SFI package + HSM) → [ref-key-provisioning.md](ref-key-provisioning.md)
- Lock-down step option-byte details → [ref-secure-boot.md](ref-secure-boot.md) §"Option Byte Programming"
- Lock-down verification of debug → [ref-secure-debug.md](ref-secure-debug.md) §"Common secure-debug mistakes"
- Boundary scan pin re-purposing risks (DTCM/MPU side) → [ref-compiler-hardening.md](ref-compiler-hardening.md)
- Self-test report format / fault log readout → [ref-fault-handlers.md](ref-fault-handlers.md) §"Fault Log Readout on Boot"
