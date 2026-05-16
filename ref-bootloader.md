# Bootloader — Canonical Reference & Jump Checklist

> **Scope:** Cortex-M3/M4/M7/M33 bootloader → application handoff. Particularly
> XIP from external memory (H730/H7B0/H750), dual-bank OTA, secure boot, and
> ST ROM bootloader recovery paths.
>
> **Why a dedicated file:** Bootloader is a high-risk, low-volume domain where
> bugs are 100% silent (everything compiles; device just bricks). Memorized
> "I think the jump sequence is..." → guaranteed wrong. This file is the
> authoritative pointer-list + checklist; full code comes from ST GitHub via
> `gh search code`.

## 0. Interface-Agnostic Principle

The recovery / update interface (UART / USB DFU / CAN / I2C / SPI / XIP-only)
is a VARIANT. The bootloader discipline is the same across all of them:

1. **Identify resources** — which flash banks, which RAM regions, which
   peripherals does the BL own; which does it hand off; which does it
   share with the App.
2. **Use those resources consistently across the boundary** — App must
   either accept or fully reconfigure each resource. No half-state.
3. **Frequency management** — BL's clock setup vs App's clock expectation:
   must be one of:
     (a) BL configures fully, App accepts (no reconfigure call) — XIP pattern
     (b) BL leaves at reset defaults, App configures — IAP/reset-everything pattern
     (c) BL configures partial, App completes — explicit handoff document required
4. **Memory management** — partition is the contract:
     - BL code region (0x08000000 typically)
     - App code region (0x08020000 / 0x90000000 / wherever)
     - Shared data page (magic, version, boot_count, watchdog state)
     - Stack/heap regions (BL clears before jump)
     - DMA-capable regions (App must respect cache attributes)

These four concerns are the bug surface. The interface determines only HOW
recovery happens, not WHAT must be done at the handoff.

### Two canonical handoff patterns

| Pattern | Used by | Sequence |
|---------|---------|----------|
| **Reset-everything** | Flash-based IAP, keshikan/STM32H7_USB-DFU_Bootloader | BL calls `HAL_RCC_DeInit()` + `HAL_DeInit()` before jump → App re-runs full SystemClock_Config + HAL_Init. Works only when App is NOT running from the same memory BL configured. |
| **Keep-state** | AN5188 ExtMem (XIP from OSPI/QSPI/FMC) | BL keeps clocks + ext-mem peripheral live → App must NOT call HAL_RCC_DeInit / HAL_RCC_OscConfig (would deconfigure the memory it's executing from → bus fault). |

Pick one explicitly. Mixed pattern = silent brick.

---

## 1. Authoritative References (read these — do not invent)

### Cortex-M boot semantics (ARM)

| Reference | What it covers | URL |
|-----------|----------------|-----|
| **ARM KA001193** | Booting a Cortex-M7 system — 3 example boot flows incl. TCM + remap | https://developer.arm.com/documentation/ka001193/1-0/ |
| ARMv7-M ARM §B1.5 | Reset behaviour, vector table, exception entry | https://developer.arm.com/documentation/ddi0403/latest/ |
| ARMv8-M ARM §B3.2 | Cortex-M33/M55 boot, with TrustZone-M differences | https://developer.arm.com/documentation/ddi0553/latest/ |
| ARM AN279 | Cortex-M3 Embedded Software Development | (older — superseded by KA001193) |
| Cortex-M7 TRM | TCM enable, cache controls, MPU/CCR setup | https://developer.arm.com/documentation/ddi0489/latest/ |

### ST application notes (per use case)

#### XIP / External memory boot
| AN | Subject | Notes |
|----|---------|-------|
| **AN5188** | External memory boot with reduced internal flash | **The** doc for H730/H7B0/H750 XIP — canonical ExtMem_CodeExecution example references this. |
| AN5152 | H7 cache + memory configuration | DMA / D-cache safety after handoff |

#### ST ROM bootloader (recovery / DFU fallback)
| AN | Subject | Notes |
|----|---------|-------|
| **AN2606** | System memory boot mode — per-part bootloader address + entry conditions | Use this to verify BOOT0/BOOT1/Option byte fallback. Family addresses are documented in ref-iap-ota.md. |
| **AN3155** | USART protocol used in STM32 bootloader | UART command set (GET, GO, READ_MEM, WRITE_MEM, ERASE, EXTENDED_ERASE, ...) — needed for any AN3155-compatible host tool. |
| AN3156 | USB DFU protocol used in STM32 bootloader | DFU 1.1 superset; recovery via USB |
| AN3154 | CAN bootloader protocol | For CAN-based field recovery |
| AN4221 | I2C bootloader protocol | For I2C-attached bootloader |
| AN5405 | SPI bootloader protocol | For SPI-attached bootloader |
| AN4286 | Customizing STM32 bootloader behaviour | Patching, custom commands, branding |

#### IAP / dual-bank OTA
| AN | Subject |
|----|---------|
| AN4441 | IAP using OTA for STM32 |
| AN4767 | F4/F7 dual-bank IAP |
| AN4861 | H7 dual-bank IAP + bank swap |
| AN5447 | SBSFU — Secure Boot + Secure Firmware Update (ST canonical secure pattern) |

### Canonical code (gh search / clone)

| Project | Repo path | Description |
|---------|-----------|-------------|
| **H730/H735 XIP boot** | `STMicroelectronics/STM32CubeH7/Projects/STM32H735G-DK/Applications/ExtMem_CodeExecution/ExtMem_Boot/` | The most directly applicable canonical reference for STM32H730 product. |
| **H730/H735 XIP App** | `STMicroelectronics/STM32CubeH7/Projects/STM32H735G-DK/Applications/ExtMem_CodeExecution/ExtMem_Application/{FreeRTOS,LedToggling}/` | Companion App side — shows how App must accept BL's state. |
| H743/H750 dual-bank | `STMicroelectronics/STM32CubeH7/Projects/STM32H743I-EVAL/Applications/FLASH/FLASH_DualBoot/` | Per-bank OTA pattern. |
| H7B0/H7A3 OSPI app | `STMicroelectronics/STM32CubeH7/Projects/STM32H7B3I-EVAL/Examples/OSPI/` | OSPI memory-mapped variants. |
| SBSFU canonical | `STMicroelectronics/x-cube-sbsfu` | Secure boot + signed FW update reference. |
| OpenBootloader (IAP) | `STMicroelectronics/stm32-mw-openbootloader` | ST middleware bootloader (AN3155-compatible). |

### Community references (battle-tested, not ST-authoritative)

| Project | Description |
|---------|-------------|
| `keshikan/STM32H7_USB-DFU_Bootloader` | NUCLEO-H723ZG USB-DFU bootloader, CubeIDE 1.10, "reset-everything" pattern. Blog: https://www.keshikan.net/gohantabeyo/?p=2279 |
| `viktorvano/STM32_USB_DFU_Bootloader` | F4/F7 USB DFU IAP example |
| `akospasztor/stm32-bootloader` | UART/CAN/SD-card multi-channel BL, MIT licensed |

Community refs are useful for cross-checking philosophy and finding edge cases ST examples don't cover. Always cross-validate against ARM KA001193 + ST AN before adopting a pattern.

---

## 2. Canonical BL → App Jump Checklist

This is the bug-hunt surface for any project that has a bootloader. Skip nothing.

### Before jump (BL side responsibilities)

```
□ Application image present + valid?
    □ Magic word at known offset
    □ CRC over application_size matches header
    □ Optional: ECDSA signature verify (SBSFU/AN5447 if used)
    □ If invalid → enter recovery (UART/DFU AN3155 fallback) OR halt

□ External memory ready (for XIP products)?
    □ OCTOSPI / QSPI / FMC in memory-mapped mode
    □ HAL_OSPI_MemoryMapped() returned HAL_OK
    □ DLYB calibrated if high-speed (AN5050) — read works at temperature
    □ Read-test at APPLICATION_ADDRESS returns expected first word (stack value)

□ Caches:
    □ Decision: keep enabled / disable / clean+invalidate?
    □ If disable: SCB_DisableDCache() + SCB_DisableICache() — followed by __DSB; __ISB
    □ If keep: cache must be coherent across handoff (D-cache invalidate ranges App will read)
    □ App must agree with BL choice (else cache misses / stale reads)

□ Flash lock state:
    □ HAL_FLASH_Lock() (don't leave unlocked across jump)
    □ HAL_FLASH_OB_Lock() (option byte register locked)
    □ If user code wrote OB without OB_Launch() → unflushed; halt or commit

□ Peripherals (DeInit selectively):
    □ UART / SPI / I2C used by BL: DeInit (free pins for App's MX_*_Init)
    □ OSPI / FMC: KEEP — these are App's instruction memory!
    □ GPIO: leave AF pins set up (App will re-configure if needed; but already-in-MM-mode OSPI pins MUST stay AF)
    □ DMA streams used by BL: HAL_DMA_DeInit (App will re-claim)
    □ Timers: stop + DeInit

□ Interrupts:
    □ __disable_irq() before MSP/CONTROL writes
    □ NVIC->ICER / NVIC->ICPR: clear all enabled + pending (defensive — App's HAL_Init does this too)
    □ SysTick->CTRL = 0 (stop tick); SysTick->VAL = 0

□ RCC / Clock:
    □ Decision: keep BL's clock or let App reconfigure?
    □ AN5188 / ExtMem readme: "DO NOT touch ExtMem_Boot's clock setup"
        → App must NOT call HAL_RCC_OscConfig / DeInit; just reuse BL's
        → If App's main() calls HAL_Init() + SystemClock_Config() → conflict
    □ If App reconfigures: BL should NOT lock VOS / clock at unusual states

□ Watchdog:
    □ IWDG/WWDG running? If yes — App must refresh within first window
    □ Disable in BL only if App will explicitly re-enable
    □ Window watchdog: cannot be paused — handoff timing critical

□ Stack pointer + Vector table:
    □ Read App's initial MSP: *(uint32_t *)APPLICATION_ADDRESS
    □ Sanity: MSP in valid SRAM range (DTCM 0x20000000-0x20020000, AXI 0x24000000-0x24080000, D2 0x30000000-0x30050000)
        — NOT in flash, NOT in peripheral region
    □ Read App's Reset_Handler: *(uint32_t *)(APPLICATION_ADDRESS + 4)
    □ Reset_Handler bit 0 must be SET (Thumb state)
```

### Jump assembly (canonical — KA001193)

```c
/* C-level (HAL/Keil style) — works but compiler may inline differently
 * with -Os/-O3. Always use __DSB/__ISB barriers around register writes. */
__disable_irq();
SCB->VTOR = APPLICATION_ADDRESS;       /* OPTIONAL here — App's SystemInit
                                        * normally writes VTOR itself */
__DSB();
__ISB();
uint32_t app_msp     = *(volatile uint32_t *)(APPLICATION_ADDRESS);
uint32_t app_reset_h = *(volatile uint32_t *)(APPLICATION_ADDRESS + 4U);
__set_MSP(app_msp);
__set_CONTROL(0);                      /* Thread mode, MSP, privileged */
__ISB();
((void(*)(void))app_reset_h)();        /* never returns */

/* Naked-assembly variant (KA001193 §Example 2 — fewer compiler surprises) */
__attribute__((naked, noreturn))
static void jump_to_app(uint32_t app_base) {
    __asm volatile(
        "ldr  r1, [r0]       \n"   /* initial MSP            */
        "msr  msp, r1        \n"
        "ldr  r1, [r0, #4]   \n"   /* Reset_Handler          */
        "bx   r1             \n"   /* Thumb branch (bit0=1)  */
        ::: "r1"
    );
}
```

### After jump (App side responsibilities)

```
□ Vector table:
    □ Startup code or SystemInit() writes SCB->VTOR = APPLICATION_ADDRESS
        (not 0x08000000 — that's BL's range)
    □ Verify VTOR after main() entry: assert((SCB->VTOR & ~0x1FFU) == APPLICATION_ADDRESS)

□ Clocks:
    □ If accepting BL's clocks: SKIP SystemClock_Config() — or implement no-op
    □ If reconfiguring: call HAL_RCC_DeInit() FIRST, then re-init
    □ AN5188: ExtMem_Application uses identical clock config — accepts BL setup

□ Caches:
    □ If BL left enabled and App expects enabled → no-op
    □ If BL disabled and App wants enabled → SCB_EnableICache() + SCB_EnableDCache()
    □ For App XIP from cacheable OSPI region: D-cache MUST be enabled for performance,
      but DMA buffers MUST be in non-cacheable region (MPU) or cache-managed

□ FPU (M4F/M7/M33-FP):
    □ CPACR.CP10/CP11 enabled? CMSIS SystemInit does this. Verify.

□ MPU:
    □ If App uses MPU regions for non-cacheable DMA zones — configure FIRST,
      BEFORE enabling caches.

□ Watchdog:
    □ Refresh within first window if IWDG inherited from BL

□ RTOS init:
    □ HAL_Init() in App will reconfigure SysTick — RTX5/FreeRTOS use their own tick,
      handoff to RTOS tick before vTaskStartScheduler()
```

---

## 3. Common Bootloader Bugs (production-grade list)

### CRITICAL (silent brick)

| Bug | Symptom | Catch |
|-----|---------|-------|
| App's initial MSP outside valid SRAM | HardFault on first push | Sanity-check MSP range in BL before jump |
| App's Reset_Handler bit 0 = 0 (ARM state) | UsageFault on jump | Check `(reset_h & 1U) == 1` |
| OSPI not in MM mode before jump | Bus fault fetching first App instruction | `HAL_OSPI_MemoryMapped() == HAL_OK` + read-test |
| BL leaves flash unlocked | App's ISR or task corrupts flash on first write to FLASH region | `HAL_FLASH_Lock()` before jump |
| BL leaves OB lock open | Option bytes can be rewritten by stray writes | `HAL_FLASH_OB_Lock()` before jump |
| VTOR not set to APPLICATION_ADDRESS | All ISRs vector to BL's table → bizarre behaviour | App's SystemInit must write VTOR |
| SP/PC swap (MSP set AFTER calling Reset_H) | Stack corruption | Always MSP then jump |
| Cache cleaned BEFORE OSPI MM but App reads stale | Garbage code execution | `SCB_InvalidateICache()` after OSPI MM enable, before jump |
| Cache enabled but DMA buffer in cacheable region | DMA writes invisible to CPU (or stale) | MPU non-cacheable region for DMA |

### HIGH (subtle field failures)

| Bug | Symptom | Catch |
|-----|---------|-------|
| BL doesn't disable IRQs before MSP write | Random ISR runs with wrong stack | `__disable_irq()` first |
| __ISB() missing after CONTROL write | Pipeline may execute next ins with stale CONTROL | Always `__ISB()` after CONTROL/MSP/VTOR |
| Watchdog times out during App init | Hang or reset during boot | Measure App init time; pet watchdog or use IWDG window |
| App calls HAL_RCC_OscConfig but BL already configured clocks | HAL_RCC_OscConfig may return ERROR or hang on PLL re-lock | Use HAL_RCC_DeInit FIRST or accept BL's state |
| BL uses single-shot CRC seed; App expects standard CRC32 | OTA always fails | Document seed/poly explicitly; cross-check w/ host tool |
| AN3155 fallback unreachable (no BOOT0 hold or no option byte) | Cannot recover from corrupted App | Option byte BOOT_ADD0/BOOT_ADD1 or BOOT0 pull-up |
| Flash sector size mismatch between BL and host tool | Erase + write partial sector → data loss | Match sector layout: H7=128KB, F4/F7=variable |
| App's first instruction reads from cacheable region but I-cache stale | Boot at -O3 builds: jumps to garbage | Invalidate I-cache after OSPI MM enable |

### MEDIUM

| Bug | Symptom |
|-----|---------|
| Boot banner UART transmit blocks too long, watchdog fires | Boot loop |
| HAL_Delay(1s) before jump — wasted | Slow boot |
| BL doesn't expose version over UART | Field debugging blind |
| No anti-rollback OTP check | Allows downgrade to vulnerable firmware (see ref-secure-boot.md §Anti-Rollback) |
| App doesn't validate its own metadata page | "Locked-in" failures undetectable |

---

## 4. Bootloader-Specific Faz 6 Benchmark Checklist (for Mode B+)

When comparing user's BL against canonical ExtMem_Boot or equivalent, focus on:

```
[ ] Clock config: PLL_M / N / P, VOS, FLASH_LATENCY, ODEN (if H743), supply config
[ ] OCTOSPI/OSPI init: ClockPrescaler, DummyCycles, DHQC (ES0480 §2.4.1), SampleShifting
[ ] OSPI mem-mapped enable sequence (Read+Write CFG commands)
[ ] OSPI manager (OSPIM_CfgTypeDef): ClkPort, NCSPort, IOLowPort
[ ] GPIO config: AF number, speed, pull
[ ] Cache state at jump time
[ ] VTOR write location (BL? App's SystemInit? both?)
[ ] MSP/CONTROL setup ordering with barriers
[ ] Watchdog state across handoff
[ ] Flash lock state
[ ] Recovery path (UART AN3155 / DFU AN3156 / BOOT0 ROM fallback)
[ ] App's startup makes no clock reconfiguration (or fully reconfigures)
```

---

## 5. Family-Specific Notes

### STM32H730 (XIP target part — only 128 KB internal flash)

- BL must fit in 128 KB. Tight: every byte counts.
- App runs from OSPI at 0x90000000.
- Cache typically enabled for OSPI region (XIP performance critical).
- ExtMem_Boot example is **the** reference; H735G-DK pin-compatible.
- ES0480 errata applies: §2.4.1 OCTOSPI DHQC mandatory at high clocks.

### STM32H7A3/H7B3 (1MB flash, BUT mem-mapped XIP also supported)

- 128-bit flash word (vs 256-bit on H743). Affects HAL_FLASH_Program 3rd arg.
- VOS encoding inverted vs H743 (RM0455). Max VOS0=280 MHz, NOT 480 MHz.
- ES0392 errata sheet (not ES0480).

### STM32H743/H753

- 480 MHz needs ODEN (rev V silicon). SYSCFG_PWRCR.ODEN + ACTVOSRDY.
- 256-bit flash word.
- Dual-bank-capable parts can do A/B OTA.

### STM32H5 (H563/H573)

- ICACHE replaces ART; different cache control API.
- System bootloader at 0x0BF87000.
- TrustZone-M optional — adds SAU/GTZC/NSC complexity.

### STM32L5/U5

- TrustZone-M default. Secure jump = `__TZ_*` intrinsics.
- System bootloader at 0x0BF90000.
- See AN5347.

---

## 6. Cross-Check Plan — When Reviewing a Bootloader

1. Identify BL type: XIP-launcher / IAP-style flash overwrite / SBSFU secure / dual-bank
2. Open canonical equivalent in STMicroelectronics/STM32Cube<F>
3. Compare clock config (Faz 6 Benchmark)
4. Compare OSPI/peripheral init (Faz 6)
5. Compare jump sequence against §2 of this file
6. Check App side respects BL's choices (§4)
7. Verify recovery path exists (AN3155 UART, AN3156 USB DFU, or BOOT0)
8. Cross-reference errata (ES sheet per family)
9. Emit findings using Mode B+ template (severity + confidence + ref + errata)
