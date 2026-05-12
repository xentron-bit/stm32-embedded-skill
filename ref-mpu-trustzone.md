# MPU Setup & TrustZone

## MPU — Why Use It

| Protection | How MPU Enforces It |
|-----------|---------------------|
| Stack overflow | Guard region below stack → MemManage fault |
| Null-pointer dereference | Region 0 (0x0000_0000–0x1FF) no-access |
| DMA buffer cache isolation | Mark buffer non-cacheable on M7 |
| Code execution from RAM | XN (Execute Never) on data regions |
| Peripheral access control | Task can only access its own peripheral |

## Basic MPU Setup (Cortex-M4/M7, CMSIS)

```c
#include "core_cm7.h"  /* or core_cm4.h */

/* Region numbers — highest wins for overlapping regions */
typedef enum {
    MPU_REGION_FLASH        = 0,
    MPU_REGION_SRAM         = 1,
    MPU_REGION_PERIPH       = 2,
    MPU_REGION_DMA_BUF      = 3,  /* non-cacheable on M7 */
    MPU_REGION_STACK_GUARD  = 4,
    MPU_REGION_NULL_TRAP    = 5,
} MpuRegion_t;

/* Shorthand: size must be power-of-2, encoded as (log2(size) - 1) */
/* e.g. 256B = 0x07, 4KB = 0x0B, 512KB = 0x12, 1MB = 0x13         */

void mpu_region_config(uint8_t region, uint32_t base,
                       uint8_t size_enc,   /* MPU_REGION_SIZE_xxx  */
                       uint8_t ap,         /* MPU_REGION_xxx_ACCESS */
                       uint8_t tex_scb,    /* tex[2:0]|S|C|B        */
                       bool xn)
{
    MPU->RNR  = region;
    MPU->RBAR = (base & MPU_RBAR_ADDR_Msk);
    MPU->RASR = (xn       ? MPU_RASR_XN_Msk    : 0)
              | (ap   << MPU_RASR_AP_Pos)
              | (tex_scb << MPU_RASR_TEX_Pos)   /* includes S/C/B */
              | (size_enc << MPU_RASR_SIZE_Pos)
              | MPU_RASR_ENABLE_Msk;
}

void mpu_setup(void)
{
    ARM_MPU_Disable();

    /* Region 0: Full flash — RO, cacheable, executable */
    mpu_region_config(MPU_REGION_FLASH,
        FLASH_BASE, MPU_REGION_SIZE_2MB,
        MPU_REGION_PRIV_RO_URO,
        0x06, /* TEX=0, S=1, C=1, B=0 — normal, write-through */
        false);

    /* Region 1: Full SRAM — RW, cacheable, XN */
    mpu_region_config(MPU_REGION_SRAM,
        SRAM_BASE, MPU_REGION_SIZE_512KB,
        MPU_REGION_FULL_ACCESS,
        0x06, /* normal WB */
        true);

    /* Region 2: Peripherals — RW, device (strongly ordered), XN */
    mpu_region_config(MPU_REGION_PERIPH,
        0x40000000, MPU_REGION_SIZE_512MB,
        MPU_REGION_FULL_ACCESS,
        0x00, /* TEX=0, S=1, C=0, B=1 — device */
        true);

    /* Region 3: DMA buffer — RW, non-cacheable, XN (M7 cache bypass) */
    /* Place your DMA_BUF section here */
    extern uint32_t _dma_buf_start[];
    mpu_region_config(MPU_REGION_DMA_BUF,
        (uint32_t)_dma_buf_start, MPU_REGION_SIZE_4KB,
        MPU_REGION_FULL_ACCESS,
        0x04, /* TEX=1, S=0, C=0, B=0 — strongly ordered / non-cacheable */
        true);

    /* Region 4: Stack guard (32 bytes below main stack) — no access */
    extern uint32_t _estack[];
    mpu_region_config(MPU_REGION_STACK_GUARD,
        (uint32_t)_estack - 32, MPU_REGION_SIZE_32B,
        MPU_REGION_NO_ACCESS,
        0x00, true);

    /* Region 5: Null pointer trap (0x0–0x1FF) — no access */
    mpu_region_config(MPU_REGION_NULL_TRAP,
        0x00000000, MPU_REGION_SIZE_512B,
        MPU_REGION_NO_ACCESS,
        0x00, true);

    ARM_MPU_Enable(MPU_CTRL_PRIVDEFENA_Msk); /* default map for privileged */
}
```

## CMSIS ARM_MPU API (preferred — portable M0+/M3/M4/M7/M33)

```c
#include "mpu_armv7.h"  /* for M3/M4/M7 */
/* #include "mpu_armv8.h" for M33/M55 */

void mpu_setup_cmsis(void)
{
    ARM_MPU_Disable();

    /* Flash: cacheable, read-only, executable */
    ARM_MPU_SetRegion(0,
        ARM_MPU_RBAR(FLASH_BASE, ARM_MPU_SH_NON, 1/*RO*/, 1/*NP*/, 0/*XN=0 exec*/),
        ARM_MPU_RLAR(FLASH_BASE + FLASH_SIZE - 1,
                     ARM_MPU_ATTR_IDX_WB_WA)); /* Write-Back, Write-Allocate */

    /* SRAM: cacheable, RW, no-exec */
    ARM_MPU_SetRegion(1,
        ARM_MPU_RBAR(SRAM_BASE, ARM_MPU_SH_INNER, 0/*RW*/, 1/*NP*/, 1/*XN*/),
        ARM_MPU_RLAR(SRAM_BASE + SRAM_SIZE - 1, ARM_MPU_ATTR_IDX_WB_WA));

    ARM_MPU_Enable(MPU_CTRL_PRIVDEFENA_Msk);
}
```

## FreeRTOS MPU Port (task isolation)

```c
/* Use FreeRTOS MPU port: portUSING_MPU_WRAPPERS = 1 in FreeRTOSConfig.h */

/* Define task-private regions in MemoryRegion_t */
static StackType_t sensor_stack[512];
static StaticTask_t sensor_tcb;

/* Allow sensor task to access only sensor peripheral + its buffer */
static MemoryRegion_t sensor_regions[] = {
    { (void *)SPI1_BASE, 0x400, portMPU_REGION_READ_WRITE },
    { sensor_dma_buf,    512,   portMPU_REGION_READ_WRITE },
    { NULL, 0, 0 }
};

static TaskParameters_t sensor_params = {
    .pvTaskCode    = sensor_task,
    .pcName        = "sensor",
    .usStackDepth  = 512,
    .pvParameters  = NULL,
    .uxPriority    = 3 | portPRIVILEGE_BIT,  /* remove portPRIVILEGE_BIT for unprivileged */
    .puxStackBuffer = sensor_stack,
    .xRegions      = sensor_regions,
};

xTaskCreateRestricted(&sensor_params, &sensor_handle);
```

---

## TrustZone (Cortex-M33: STM32L5, U5, H5, WBA)

### Concept

```
┌──────────────────────┬──────────────────────┐
│   Secure World       │   Non-Secure World   │
│  (TF-M / bare-metal) │  (Application RTOS)  │
│  - Crypto keys       │  - CAN / UART comms  │
│  - Secure boot       │  - Sensor drivers    │
│  - TrustZone setup   │  - HMI / display     │
│  FLASH: Bank1 lower  │  FLASH: Bank1 upper  │
│  SRAM: SRAM1 lower   │  SRAM: SRAM1 upper   │
└──────────────────────┴──────────────────────┘
         ↑ IDAU / SAU configures boundary
```

### SAU Configuration (Secure Firmware)

```c
/* Called from secure reset handler BEFORE non-secure code starts */
void sau_setup(void)
{
    SAU->CTRL = 0; /* disable SAU while configuring */

    /* Region 0: Non-secure callable (NSC) flash gate — veneer functions */
    SAU->RNR  = 0;
    SAU->RBAR = 0x0C000000 & SAU_RBAR_BADDR_Msk; /* example NSC region */
    SAU->RLAR = (0x0C003FFF & SAU_RLAR_LADDR_Msk)
              | SAU_RLAR_NSC_Msk      /* Non-Secure Callable */
              | SAU_RLAR_ENABLE_Msk;

    /* Region 1: Non-secure SRAM */
    SAU->RNR  = 1;
    SAU->RBAR = 0x20018000 & SAU_RBAR_BADDR_Msk;
    SAU->RLAR = (0x2003FFFF & SAU_RLAR_LADDR_Msk) | SAU_RLAR_ENABLE_Msk;

    /* Region 2: Non-secure peripheral (APB1) */
    SAU->RNR  = 2;
    SAU->RBAR = 0x40000000 & SAU_RBAR_BADDR_Msk;
    SAU->RLAR = (0x4FFFFFFF & SAU_RLAR_LADDR_Msk) | SAU_RLAR_ENABLE_Msk;

    /* Enable SAU, all other regions are Secure by default */
    SAU->CTRL = SAU_CTRL_ENABLE_Msk;
    __DSB();
    __ISB();
}
```

### NSC Gateway — Secure API Callable from Non-Secure

```c
/* secure_api.h — shared header between secure and non-secure */
#ifdef __cplusplus
extern "C" {
#endif

/* Mark as Non-Secure Callable — compiler places in NSC FLASH region */
__attribute__((cmse_nonsecure_entry))
int32_t secure_crypto_sign(const uint8_t *data, uint32_t len,
                            uint8_t *sig_out);

__attribute__((cmse_nonsecure_entry))
bool secure_key_exists(uint32_t key_id);

#ifdef __cplusplus
}
#endif
```

```c
/* secure_api.c — compiled as SECURE */
#include "cmse_nonsecure_entry.h"

__attribute__((cmse_nonsecure_entry))
int32_t secure_crypto_sign(const uint8_t *data_ns, uint32_t len,
                            uint8_t *sig_out_ns)
{
    /* CRITICAL: validate non-secure pointers before use */
    if (cmse_check_pointed_object((void *)data_ns, CMSE_NONSECURE) == NULL)
        return -1;
    if (cmse_check_address_range((void *)sig_out_ns, 64, CMSE_NONSECURE) == NULL)
        return -2;

    /* Now safe to use pointers */
    return mbedtls_pk_sign(&secure_key, data_ns, len, sig_out_ns, NULL, NULL);
}
```

### Non-Secure Boot Sequence

```c
/* Last thing secure main() does: hand off to non-secure */
typedef void (*NonSecureReset_t)(void) __attribute__((cmse_nonsecure_call));

void secure_hand_off_to_ns(void)
{
    uint32_t ns_msp   = *(volatile uint32_t *)NS_APP_BASE;
    uint32_t ns_entry = *(volatile uint32_t *)(NS_APP_BASE + 4);

    /* Validate MSP range */
    if (ns_msp < NS_SRAM_BASE || ns_msp > NS_SRAM_END)
        fault_infinite_loop();

    __TZ_set_MSP_NS(ns_msp);

    NonSecureReset_t ns_reset = (NonSecureReset_t)(ns_entry | 1);
    ns_reset(); /* never returns */
}
```

## Rules

- MPU regions must be power-of-2 size, naturally aligned (base = N × size)
- Always enable MPU with `PRIVDEFENA` — prevents privileged code from accessing undefined regions
- M7 DMA buffers: MPU must mark them strongly-ordered or non-cacheable (TEX=001, C=0, B=0)
- Stack guard region: 32 bytes is enough — MemManage fires on first overflow word
- TrustZone: ALWAYS validate non-secure pointer with `cmse_check_*` before dereferencing in secure context
- `__DSB()` + `__ISB()` required after SAU/MPU enable to flush pipeline
- STM32L5/U5: option bytes control which peripherals are assigned secure/non-secure — set before SAU
- Never share a mutex or RTOS object across secure/non-secure boundary — use NSC API calls only
