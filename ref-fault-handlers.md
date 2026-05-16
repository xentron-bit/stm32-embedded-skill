# Fault Handlers & Reset Cause Detection

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, errata workarounds, protocol-spec content** here is authoritative — that is why this file exists.
> - **Inline HAL/CMSIS/peripheral code snippets** are illustrative. The HAL drifts between versions and parts. For the canonical version of any HAL symbol at your HAL release: `gh search code <SymbolName> --owner=STMicroelectronics --extension=c` — see [ref-st-github-map.md](ref-st-github-map.md) §8 for the full lookup procedure.
> - **CRITICAL bugs identified in the 2026-05-16 audit have been corrected** in this file, but verify against your own HAL version before copy-pasting.
> - **For bootloader / IAP / OTA topics** the canonical checklist + ARM KA001193 + AN5188/2606/3155/3156 references are in [ref-bootloader.md](ref-bootloader.md).

## Canonical External References (use these in `ref:` for every fault finding)

| Source | URL / file | Use case |
|--------|-----------|----------|
| **ARM AN209 v5.0** (Summer 2017) — Using Cortex-M3/M4/M7 Fault Exceptions | PDF: https://www.keil.com/appnotes/files/apnt209.pdf (catalog: www.keil.com/appnotes/docs/apnt_209.asp) | **THE** canonical fault decode + escalation reference; CFSR/HFSR/MMFAR/BFAR bit names; sync vs async BusFault; priority escalation rules |
| **ARM KAN209** (web) | https://developer.arm.com/documentation/kan209/latest/ | Same content as AN209, web version |
| **ARM Faults_and_Handler example** (Apache-2.0, 2017) | downloadable from AN209 prerequisites | Canonical naked `HardFault_Handler` + C decoder; copy-paste ready |
| **FreeRTOS — Debugging Hard Faults on Cortex-M** | https://www.freertos.org/Documentation/02-Kernel/03-Supported-devices/04-Demos/Others/Debugging-Hard-Faults-On-Cortex-M-Microcontrollers | RTOS-context stack frame unwind; `_pulFaultStackAddress` pattern |
| **ARM KA001162** | https://developer.arm.com/documentation/ka001162/1-0 | Memory fault handler test |
| **ARM KA001198** | https://developer.arm.com/documentation/ka001198/latest/ | BusFault re-entry / stuck-loop diagnosis |
| **ARMv7-M ARM §B3.2.15** (CFSR) | ARM DDI 0403E | Authoritative register bit definitions |
| **SEGGER KB — Cortex-M Fault** | https://kb.segger.com/Cortex-M_Fault | J-Link RTT + Ozone live fault decode |

**Skill rule (enforced by SKILL.md Fault-Evidence-First gate):** every HardFault
finding MUST cite at least one of the above in `ref:` (in addition to user-code
file:line citation).

## Critical AN209 facts to internalize (don't memorize — verify in the PDF)

- **HardFault priority = -1** (fixed, higher than all configurable IRQs, lower than NMI = -2). Cannot be disabled.
- **MemManage / BusFault / UsageFault**: **DISABLED after reset.** Must enable via `SCB->SHCSR |= SCB_SHCSR_MEMFAULTENA_Msk | BUSFAULTENA_Msk | USGFAULTENA_Msk;` to get sub-class faults instead of HardFault escalation.
- **Priority escalation to HardFault** happens when: (a) a fault handler causes the same fault, (b) a fault occurs with same-or-lower priority as currently executing handler, (c) the handler for the new fault is not enabled.
- **Async BusFault never escalates to lockup** — but is often unrecoverable (you don't know which instruction caused it). Use `SCB->BFSR.IMPRECISERR` to identify.
- **Cache maintenance operations on M7 can trigger BusFault** if performed on unmapped/strongly-ordered regions.
- **`HFSR.FORCED`** bit set = sub-class fault escalated to HardFault → read CFSR to find which sub-class.
- **`HFSR.VECTTBL`** set = bus fault occurred while reading the vector table → indicates VTOR is wrong OR the memory at VTOR is unmapped.

## Canonical Naked Handler (ARM Apache-2.0, AN209 example — verbatim from `Faults_and_Handler/HardFault_handler.c`)

> Attribution: Copyright (c) 2017 ARM Limited. SPDX-License-Identifier: Apache-2.0.
> Adapt printf/output mechanism to your target (UART/RTT/EventRecorder/BKPSRAM noinit).

```c
/* Keil armclang/armasm-compatible inline asm wrapper */
__asm void HardFault_Handler(void)
{
    TST    LR, #4               /* test EXC_RETURN.SPSEL */
    ITE    EQ
    MRSEQ  R0, MSP              /* if SPSEL=0 → kernel was on MSP */
    MRSNE  R0, PSP              /* if SPSEL=1 → task was on PSP */
    MOV    R1, LR                /* pass EXC_RETURN as arg2 */
    B      __cpp(HardFault_Handler_C)
}

void HardFault_Handler_C(unsigned long *args, unsigned int lr_value)
{
    unsigned long stacked_r0  = args[0];
    unsigned long stacked_r1  = args[1];
    unsigned long stacked_r2  = args[2];
    unsigned long stacked_r3  = args[3];
    unsigned long stacked_r12 = args[4];
    unsigned long stacked_lr  = args[5];
    unsigned long stacked_pc  = args[6];   /* address of faulting instruction (if precise) */
    unsigned long stacked_psr = args[7];

    unsigned long cfsr  = SCB->CFSR;
    unsigned long hfsr  = SCB->HFSR;
    unsigned long dfsr  = SCB->DFSR;
    unsigned long afsr  = SCB->AFSR;
    unsigned long bfar  = SCB->BFAR;       /* valid only if CFSR.BFARVALID */
    unsigned long mmfar = SCB->MMFAR;      /* valid only if CFSR.MMARVALID */

    printf("[HardFault] PC=%lx LR=%lx PSR=%lx EXC_RETURN=%lx\n",
           stacked_pc, stacked_lr, stacked_psr, lr_value);
    printf("R0=%lx R1=%lx R2=%lx R3=%lx R12=%lx\n",
           stacked_r0, stacked_r1, stacked_r2, stacked_r3, stacked_r12);
    printf("CFSR=%lx HFSR=%lx DFSR=%lx AFSR=%lx\n", cfsr, hfsr, dfsr, afsr);
    if (cfsr & 0x0080) printf("MMFAR=%lx\n", mmfar);   /* MMARVALID */
    if (cfsr & 0x8000) printf("BFAR=%lx\n",  bfar);    /* BFARVALID */
    while (1);
}
```

**GCC/armclang variant** (use this if not using legacy Keil `__asm`):

```c
__attribute__((naked)) void HardFault_Handler(void)
{
    __asm volatile (
        "tst   lr, #4               \n"
        "ite   eq                   \n"
        "mrseq r0, msp              \n"
        "mrsne r0, psp              \n"
        "mov   r1, lr               \n"
        "b     HardFault_Handler_C  \n"
    );
}
```

**For RTOS (FreeRTOS/RTX5) variant** — pass MSP/PSP unchanged, the FreeRTOS doc
above shows the same pattern with `_pulFaultStackAddress` global so the debugger
can inspect after the handler enters its infinite loop. Set a breakpoint on the
`while(1)`, then in your debugger:

```
View → Memory → enter SCB->CFSR  → decode bits
View → Disassembly → at stacked_pc → see faulting instruction
```

## Enable Separate Fault Handlers (MANDATORY before main loop)

AN209 v5.0 §"Implementing fault handlers" — without this, all sub-class faults
escalate to HardFault and the sub-class register is harder to inspect (still
readable via `HFSR.FORCED=1` → CFSR sub-class, but cleaner to handle individually):

```c
/* Call in HAL_Init or main() before peripheral init */
SCB->SHCSR |= SCB_SHCSR_USGFAULTENA_Msk    /* enable UsageFault   */
           |  SCB_SHCSR_BUSFAULTENA_Msk    /* enable BusFault     */
           |  SCB_SHCSR_MEMFAULTENA_Msk;   /* enable MemManage    */

/* Optional UsageFault traps */
SCB->CCR |= SCB_CCR_DIV_0_TRP_Msk          /* trap divide-by-zero */
         |  SCB_CCR_UNALIGN_TRP_Msk;       /* trap unaligned access */
```

## Quick Decode Tables (from AN209 v5.0 §"Status and address registers")

### HFSR (0xE000ED2C) — Hard Fault Status

| Bit | Name | Meaning |
|-----|------|---------|
| 31  | DEBUGEVT | Debug event (BKPT escalated) — must write 0 |
| 30  | FORCED   | **Sub-class fault escalated** → read CFSR for actual cause |
| 1   | VECTTBL  | BusFault while reading vector table → VTOR wrong OR memory unmapped |

### MMFSR (CFSR[7:0]) — MemManage Fault Status

| Bit | Name | When set |
|-----|------|----------|
| 0 | IACCVIOL  | Instruction fetch from XN region (MPU disabled-or-enabled both); branch to non-exec / corrupted return |
| 1 | DACCVIOL  | Data load/store to forbidden region; MMFAR holds the address |
| 3 | MUNSTKERR | Unstacking on exception return caused access violation (SP corrupt / MPU region for stack changed) |
| 4 | MSTKERR   | Stacking on exception entry caused access violation (SP corrupt / stack OOB) |
| 5 | MLSPERR   | Cortex-M4 FPU lazy state preservation fault |
| 7 | MMARVALID | MMFAR holds a valid fault address |

### BFSR (CFSR[15:8]) — Bus Fault Status

| Bit | Name | When set |
|-----|------|----------|
| 0 | IBUSERR    | Bus error on instruction prefetch (bad func ptr, corrupt LR/SP, bad vector table entry) |
| 1 | PRECISERR  | **Precise** data bus error → stacked PC = faulting instruction; BFAR holds address |
| 2 | IMPRECISERR| **Imprecise** data bus error (async, write-buffered) → PC may not be faulting instruction; BFAR NOT written |
| 3 | UNSTKERR   | BusFault on unstacking from exception return |
| 4 | STKERR     | BusFault on stacking for exception entry (SP corrupt or stack OOB) |
| 5 | LSPERR     | BusFault during FPU lazy state preservation |
| 7 | BFARVALID  | BFAR holds a valid fault address |

### UFSR (CFSR[31:16]) — Usage Fault Status

| Bit | Name | When set |
|-----|------|----------|
| 16 | UNDEFINSTR | Undefined instruction (unsupported opcode / corrupt code memory) |
| 17 | INVSTATE   | Branched to non-Thumb address (LSB=0) / stacked PSR T-bit cleared / vector LSB=0 |
| 18 | INVPC      | Invalid EXC_RETURN value (bad context switch) |
| 19 | NOCP       | Coprocessor instruction without CP present (FPU not enabled in CPACR but VFP used) |
| 24 | UNALIGNED  | Unaligned load/store (LDM/STM/LDRD/STRD always trap; others when CCR.UNALIGN_TRP=1) |
| 25 | DIVBYZERO  | SDIV/UDIV with divisor 0 (when CCR.DIV_0_TRP=1) |

**Sticky bits:** UFSR bits are sticky — clear by writing 1 to the bit or by reset.

### ABFSR (0xE000ED3C, **Cortex-M7 only**) — Auxiliary Bus Fault Status

| Bit | Name | Bus interface that caused async fault |
|-----|------|---------------------------------------|
| 0 | ITCM | Instruction TCM interface |
| 1 | DTCM | Data TCM interface |
| 2 | AHBP | AHB peripheral interface (0x40000000-0x5FFFFFFF, 0xA0000000-0xDFFFFFFF) |
| 3 | AXIM | AXI master interface (most external memory; if AXIM=1, AXIMTYPE[9:8] gives sub-type) |
| 4 | EPPB | External PPB |
| 9:8 | AXIMTYPE | When AXIM=1: 0b00=OKAY, 0b01=EXOKAY, 0b10=SLVERR, 0b11=DECERR |

**Critical for STM32H7 debugging:** if a HardFault has BFSR.IMPRECISERR=1, read
ABFSR to find which bus interface failed. DTCM async fault is rare (TCM is CPU-only,
no async source) — most common: AXIM (peripheral / external memory / DMA region).

## M7-Specific Fault Handling Considerations (AN209 v5.0 §"Fault handling considerations for ARM Cortex-M7")

1. **Cache maintenance ops can trigger BusFault** (async / imprecise). Does NOT
   escalate to HardFault when BusFault is enabled (SHCSR.BUSFAULTENA=1). Never
   causes lockup. Use `__DSB()` after cache maintenance so the fault is observed
   immediately.
2. **M7 caches support ECC** — uncorrectable ECC errors trigger BusFault. Read
   IEBR0-1 (instruction error bank) and DEBR0-1 (data error bank) registers to
   diagnose ECC events.
3. **Bus error precision differs M3/M4 vs M7:**
   - On M3/M4, writes to strongly-ordered memory → precise bus error (stacked PC = faulting instruction).
   - On M7, the **same operation can trigger imprecise bus error**.
4. **Stacked PC unreliable for imprecise BusFault on M7** — the exception sequence
   can start before the write buffer drains, so stacked PC may be a later context
   (e.g., the IRQ handler that ran shortly after the buffered write took place).
   For M7 async BusFault, **do not rely on stacked PC**; instead use ABFSR + the
   memory region the code was working on at fault time.

## µVision Fault Reports shortcut

In Keil µVision while halted in a fault handler:
**Peripherals → Core Peripherals → Fault Reports** opens a dialog showing every
CFSR/HFSR/BFAR/MMFAR field decoded as checkboxes. This is the fastest path to a
root cause when the user has Keil; capture a screenshot or copy values.

For CubeIDE: use **SFRs** view + filter for `SCB` → expand `CFSR`/`HFSR`/`BFAR`.
For SEGGER J-Link: `monitor reg cfsr`, `monitor reg hfsr` (gdb session).

## EXC_RETURN decoding (which stack was active at fault)

`LR` (link register) on entry to a fault handler holds EXC_RETURN, not a return
address. Bits:

| EXC_RETURN value | Stack used | Mode |
|------------------|------------|------|
| `0xFFFFFFF1` | MSP | Handler mode (nested fault) |
| `0xFFFFFFF9` | MSP | Thread mode |
| `0xFFFFFFFD` | PSP | Thread mode (typical RTOS task fault) |
| `0xFFFFFFE1` | MSP | Handler mode, FP context stacked (M4/M7 FPU) |
| `0xFFFFFFE9` | MSP | Thread mode, FP context stacked |
| `0xFFFFFFED` | PSP | Thread mode, FP context stacked |

**Bit 2 of EXC_RETURN:** 0 = MSP, 1 = PSP. This is what the naked handler tests
via `tst lr, #4`.


## HardFault Handler — Register Dump

```c
/* fault_handler.h */
typedef struct {
    uint32_t r0, r1, r2, r3;
    uint32_t r12, lr, pc, xpsr;
} CortexM_StackFrame_t;

typedef struct {
    uint32_t cfsr;   /* Configurable Fault Status */
    uint32_t hfsr;   /* HardFault Status */
    uint32_t dfsr;   /* Debug Fault Status */
    uint32_t mmfar;  /* MemManage Fault Address */
    uint32_t bfar;   /* BusFault Address */
    uint32_t afsr;   /* Auxiliary Fault Status */
    CortexM_StackFrame_t frame;
} FaultLog_t;

/* Persist across reset in BKPSRAM or noinit section */
__attribute__((section(".noinit"))) volatile FaultLog_t fault_log;
__attribute__((section(".noinit"))) volatile uint32_t fault_magic; /* 0xDEADBEEF = valid */
```

```c
/* fault_handler.c */
#include "stm32xx.h"

/* Called from assembly stub — do NOT inline */
__attribute__((noinline)) void hard_fault_handler_c(uint32_t *stack_ptr)
{
    fault_log.cfsr  = SCB->CFSR;
    fault_log.hfsr  = SCB->HFSR;
    fault_log.dfsr  = SCB->DFSR;
    fault_log.mmfar = SCB->MMFAR;
    fault_log.bfar  = SCB->BFAR;
    fault_log.afsr  = SCB->AFSR;

    fault_log.frame.r0   = stack_ptr[0];
    fault_log.frame.r1   = stack_ptr[1];
    fault_log.frame.r2   = stack_ptr[2];
    fault_log.frame.r3   = stack_ptr[3];
    fault_log.frame.r12  = stack_ptr[4];
    fault_log.frame.lr   = stack_ptr[5];
    fault_log.frame.pc   = stack_ptr[6];
    fault_log.frame.xpsr = stack_ptr[7];

    fault_magic = 0xDEADBEEF;

    /* Force write to SRAM before reset */
    __DSB();
    __DMB();

    /* Trigger debugger breakpoint if attached, then reset */
    if (CoreDebug->DHCSR & CoreDebug_DHCSR_C_DEBUGEN_Msk)
        __BKPT(0);

    NVIC_SystemReset();
}

/* Assembly stub — extracts correct stack pointer */
__attribute__((naked)) void HardFault_Handler(void)
{
    __asm volatile (
        "tst    lr, #4          \n"  /* Test EXC_RETURN bit 2 */
        "ite    eq              \n"
        "mrseq  r0, msp         \n"  /* Main stack */
        "mrsne  r0, psp         \n"  /* Process stack (RTOS task) */
        "b      hard_fault_handler_c \n"
    );
}

/* Same pattern for other fault handlers */
__attribute__((naked)) void MemManage_Handler(void)
{
    __asm volatile (
        "tst    lr, #4          \n"
        "ite    eq              \n"
        "mrseq  r0, msp         \n"
        "mrsne  r0, psp         \n"
        "b      hard_fault_handler_c \n"
    );
}

__attribute__((naked)) void BusFault_Handler(void)
{
    __asm volatile (
        "tst    lr, #4          \n"
        "ite    eq              \n"
        "mrseq  r0, msp         \n"
        "mrsne  r0, psp         \n"
        "b      hard_fault_handler_c \n"
    );
}

__attribute__((naked)) void UsageFault_Handler(void)
{
    __asm volatile (
        "tst    lr, #4          \n"
        "ite    eq              \n"
        "mrseq  r0, msp         \n"
        "mrsne  r0, psp         \n"
        "b      hard_fault_handler_c \n"
    );
}
```

## CFSR Decode Table

| CFSR Bit | Name | Meaning |
|----------|------|---------|
| `[0]` IACCVIOL | MemManage | Instruction access violation (MPU) |
| `[1]` DACCVIOL | MemManage | Data access violation (MPU) |
| `[3]` MUNSTKERR | MemManage | Fault on exception return unstacking |
| `[4]` MSTKERR | MemManage | Fault on exception entry stacking |
| `[5]` MLSPERR | MemManage | FPU lazy stacking fault |
| `[7]` MMARVALID | MemManage | MMFAR holds valid address |
| `[8]` IBUSERR | BusFault | Instruction bus error |
| `[9]` PRECISERR | BusFault | Precise data bus error — BFAR valid |
| `[10]` IMPRECISERR | BusFault | Imprecise bus error (async DMA) |
| `[11]` UNSTKERR | BusFault | Unstack error (fault on exception return) |
| `[12]` STKERR | BusFault | Fault on stacking |
| `[13]` LSPERR | BusFault | Lazy FP stack error |
| `[15]` BFARVALID | BusFault | BFAR holds valid address — check before reading BFAR |
| `[16]` UNDEFINSTR | UsageFault | Undefined instruction |
| `[17]` INVSTATE | UsageFault | Invalid EPSR.T/IT state |
| `[18]` INVPC | UsageFault | Invalid EXC_RETURN |
| `[19]` NOCP | UsageFault | No coprocessor (FPU disabled but used) |
| `[24]` UNALIGNED | UsageFault | Unaligned access trap |
| `[25]` DIVBYZERO | UsageFault | Divide by zero trap |

## Enable Traps (call before main loop)

```c
void fault_traps_enable(void)
{
    /* Enable UsageFault: divide-by-zero + unaligned access */
    SCB->CCR |= SCB_CCR_DIV_0_TRP_Msk | SCB_CCR_UNALIGN_TRP_Msk;

    /* Enable MemManage, BusFault, UsageFault handlers (not just HardFault) */
    SCB->SHCSR |= SCB_SHCSR_USGFAULTENA_Msk
               |  SCB_SHCSR_BUSFAULTENA_Msk
               |  SCB_SHCSR_MEMFAULTENA_Msk;
}
```

## Fault Log Readout on Boot

```c
void fault_log_check_and_report(void)
{
    if (fault_magic != 0xDEADBEEF)
        return; /* No pending fault log */

    fault_magic = 0; /* Clear so it doesn't repeat */

    log_error("=== FAULT DUMP ===");
    log_error("PC:    0x%08lX", fault_log.frame.pc);
    log_error("LR:    0x%08lX", fault_log.frame.lr);
    log_error("CFSR:  0x%08lX", fault_log.cfsr);
    log_error("HFSR:  0x%08lX", fault_log.hfsr);
    log_error("BFAR:  0x%08lX", fault_log.bfar);
    log_error("MMFAR: 0x%08lX", fault_log.mmfar);
    /* Optionally persist to external flash or send over CAN */
}
```

---

## Reset Cause Detection

```c
/* reset_cause.h */
typedef enum {
    RESET_CAUSE_UNKNOWN     = 0x00,
    RESET_CAUSE_POWER_ON    = 0x01,
    RESET_CAUSE_PIN         = 0x02,
    RESET_CAUSE_SOFTWARE    = 0x04,
    RESET_CAUSE_IWDG        = 0x08,
    RESET_CAUSE_WWDG        = 0x10,
    RESET_CAUSE_LOW_POWER   = 0x20,
    RESET_CAUSE_BOR         = 0x40,
    RESET_CAUSE_FAULT       = 0x80,  /* fault_magic was set */
} ResetCause_t;

extern ResetCause_t reset_cause;
```

```c
/* reset_cause.c — call BEFORE HAL_Init to preserve RCC->CSR */
ResetCause_t reset_cause;

/* RCC reset-flag register name differs by family:
 *   F4/F7/G4/L4: RCC->CSR, flags RCC_CSR_<event>RSTF (e.g., IWDGRSTF)
 *   H7:         RCC->RSR, flags RCC_RSR_<event>RSTF (e.g., IWDG1RSTF)
 *   H5/U5:      RCC->RSR, flags RCC_RSR_<event>RSTF
 * On H7 wrong register name silently returns 0. Check `#if defined(STM32H7)` etc. */
void reset_cause_detect(void)
{
    uint32_t csr = RCC->CSR;

    /* Clear reset flags immediately (write 1 to RMVF) */
    RCC->CSR |= RCC_CSR_RMVF;

    if (fault_magic == 0xDEADBEEF)     reset_cause = RESET_CAUSE_FAULT;
    else if (csr & RCC_CSR_IWDGRSTF)   reset_cause = RESET_CAUSE_IWDG;
    else if (csr & RCC_CSR_WWDGRSTF)   reset_cause = RESET_CAUSE_WWDG;
    else if (csr & RCC_CSR_SFTRSTF)    reset_cause = RESET_CAUSE_SOFTWARE;
    else if (csr & RCC_CSR_PORRSTF)    reset_cause = RESET_CAUSE_POWER_ON;  /* check POR before PIN — POR also sets PINRSTF on most families */
    else if (csr & RCC_CSR_PINRSTF)    reset_cause = RESET_CAUSE_PIN;
    else if (csr & RCC_CSR_BORRSTF)    reset_cause = RESET_CAUSE_BOR;
    else if (csr & RCC_CSR_LPWRRSTF)   reset_cause = RESET_CAUSE_LOW_POWER;
    else                               reset_cause = RESET_CAUSE_UNKNOWN;
}
```

## Boot Counter / Watchdog Loop Detection

```c
/* Use RTC backup registers — survive reset, preserved across power cycles
   if VBAT present. BKP0R = boot count, BKP1R = last reset cause */

#define RTC_BOOT_COUNT_REG  RTC->BKP0R
#define RTC_RESET_CAUSE_REG RTC->BKP1R
#define BOOT_LOOP_THRESHOLD 5

void boot_counter_update(void)
{
    /* Enable RTC backup register access */
    HAL_PWR_EnableBkUpAccess();

    uint32_t count = RTC_BOOT_COUNT_REG;

    if (reset_cause == RESET_CAUSE_POWER_ON || reset_cause == RESET_CAUSE_PIN)
        count = 0; /* Clean boot — reset counter */
    else
        count++;

    RTC_BOOT_COUNT_REG  = count;
    RTC_RESET_CAUSE_REG = (uint32_t)reset_cause;

    if (count >= BOOT_LOOP_THRESHOLD && reset_cause == RESET_CAUSE_IWDG) {
        /* Repeated watchdog resets → enter safe mode (minimal config) */
        safe_mode_enter();
    }
}
```

## Startup Sequence Integration

```c
/* main.c — order matters */
int main(void)
{
    reset_cause_detect();     /* 1st: before HAL_Init clears RCC->CSR */
    boot_counter_update();    /* 2nd: increment + check boot loop */
    HAL_Init();               /* 3rd: standard HAL init */
    SystemClock_Config();     /* 4th: PLL / clock tree */
    fault_traps_enable();     /* 5th: enable UsageFault/BusFault traps */
    peripheral_init();        /* 6th: application peripherals */
    fault_log_check_and_report(); /* 7th: report any pending fault */
    /* ... */
}
```

## HFSR Forced Hard Fault Check

```c
/* If HFSR.FORCED is set, the real cause is in CFSR */
static inline bool hfault_is_forced(void)
{
    return (fault_log.hfsr & SCB_HFSR_FORCED_Msk) != 0;
}
/* If HFSR.VECTTBL is set: fault occurred during vector table read */
static inline bool hfault_is_vectbl(void)
{
    return (fault_log.hfsr & SCB_HFSR_VECTTBL_Msk) != 0;
}
```

## Rules

- **NEVER** use `while(1)` in fault handlers without a watchdog to reset
- Always place `fault_magic` and `fault_log` in `.noinit` — linker must NOT zero-initialize
- On M7 (H7/F7): call `SCB_CleanDCache()` before reset to flush log to SRAM
- Read `RCC->CSR` BEFORE calling `HAL_Init()` — HAL clears the reset flags
- On F4/F7: register is `RCC->CSR`; on H7: use `RCC->RSR` instead
