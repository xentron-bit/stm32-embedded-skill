# Fault Handlers & Reset Cause Detection

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, errata workarounds, protocol-spec content** here is authoritative — that is why this file exists.
> - **Inline HAL/CMSIS/peripheral code snippets** are illustrative. The HAL drifts between versions and parts. For the canonical version of any HAL symbol at your HAL release: `gh search code <SymbolName> --owner=STMicroelectronics --extension=c` — see [ref-st-github-map.md](ref-st-github-map.md) §8 for the full lookup procedure.
> - **CRITICAL bugs identified in the 2026-05-16 audit have been corrected** in this file, but verify against your own HAL version before copy-pasting.
> - **For bootloader / IAP / OTA topics** the canonical checklist + ARM KA001193 + AN5188/2606/3155/3156 references are in [ref-bootloader.md](ref-bootloader.md).


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
