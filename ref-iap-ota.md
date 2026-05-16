# IAP / OTA Firmware Update

## Flash Memory Layout

```
/* Single-bank example (F4, G4, L4 128KB sector) */
/* 0x0800_0000  Bootloader       (32 KB, 2 sectors, never erased by app) */
/* 0x0800_8000  Application      (224 KB, 14 sectors)                    */
/* 0x080F_C000  Firmware metadata/ flag page (4 KB, last sector)         */

/* Dual-bank example (H7 / L4+ / WB — atomic swap, no downtime)         */
/* Bank1: 0x0800_0000–0x080F_FFFF  Active                                */
/* Bank2: 0x0810_0000–0x081F_FFFF  Staging (write new FW here)           */
/* Swap banks by toggling FLASH_OPTCR.SWAP_BANK + power cycle            */
```

## Firmware Metadata Page

```c
/* Store at fixed address in last flash sector */
#define FW_META_ADDR   0x080FC000UL
#define FW_META_MAGIC  0xF15A57D0UL   /* arbitrary 32-bit constant — the
                                        previous spelling "0xF1RMWARE" is
                                        not a valid hex literal */

typedef struct __attribute__((packed)) {
    uint32_t magic;          /* FW_META_MAGIC if valid */
    uint32_t version;        /* BCD: 0x01020300 = 1.2.3 */
    uint32_t app_size;       /* bytes of application image */
    uint32_t app_crc32;      /* CRC32 of application */
    uint32_t timestamp;      /* Unix epoch of build */
    uint8_t  git_hash[8];    /* first 8 hex chars of commit */
    uint32_t update_flag;    /* 0xDEADC0DE = new FW in Bank2, apply on boot */
    uint32_t boot_count;     /* incremented every boot, reset on successful start */
    uint32_t reserved[4];
} FwMetadata_t;

#define FW_META ((volatile FwMetadata_t *)FW_META_ADDR)
```

## Flash Write Helper

```c
#include "stm32xx_hal_flash.h"

HAL_StatusTypeDef flash_erase_sector(uint32_t sector, uint32_t bank)
{
    FLASH_EraseInitTypeDef erase = {
        .TypeErase  = FLASH_TYPEERASE_SECTORS,
        .Banks      = bank,
        .Sector     = sector,
        .NbSectors  = 1,
        .VoltageRange = FLASH_VOLTAGE_RANGE_3,  /* 2.7–3.6V */
    };
    uint32_t error;
    HAL_FLASH_Unlock();
    HAL_StatusTypeDef ret = HAL_FLASHEx_Erase(&erase, &error);
    HAL_FLASH_Lock();
    return (error == 0xFFFFFFFF) ? ret : HAL_ERROR;
}

/* Write 256-bit (32-byte) flash word — H7 requires 256-bit writes */
HAL_StatusTypeDef flash_write_256(uint32_t addr, const uint8_t *data)
{
    HAL_FLASH_Unlock();
    HAL_StatusTypeDef ret = HAL_FLASH_Program(
        FLASH_TYPEPROGRAM_FLASHWORD, addr, (uint32_t)data);
    HAL_FLASH_Lock();
    __ISB(); __DSB();
    return ret;
}

/* Verify written data */
bool flash_verify(uint32_t addr, const uint8_t *ref, uint32_t len)
{
    return memcmp((void *)addr, ref, len) == 0;
}
```

## CRC32 Firmware Verification

```c
/* Use STM32 hardware CRC peripheral (CRC-32/MPEG-2 by default) */
uint32_t fw_crc32_hw(uint32_t start_addr, uint32_t size_bytes)
{
    extern CRC_HandleTypeDef hcrc;
    return HAL_CRC_Calculate(&hcrc, (uint32_t *)start_addr,
                             size_bytes / 4); /* 32-bit words */
}

bool fw_verify_image(uint32_t app_addr, uint32_t app_size, uint32_t expected_crc)
{
    uint32_t calc = fw_crc32_hw(app_addr, app_size);
    return (calc == expected_crc);
}
```

## IAP Boot Decision (bootloader main)

```c
#define APP_START_ADDR  0x08008000UL
#define BOOT_RETRY_MAX  3

void bootloader_main(void)
{
    reset_cause_detect();

    /* Check if new firmware staged (single-bank OTA) */
    if (FW_META->update_flag == 0xDEADC0DE) {
        if (fw_verify_image(STAGING_ADDR, FW_META->app_size, FW_META->app_crc32)) {
            fw_copy_and_apply();  /* erase app region, copy from staging */
            FW_META->update_flag = 0;  /* clear flag */
        } else {
            /* Bad image — keep running old app */
            FW_META->update_flag = 0;
        }
    }

    /* Check boot retry counter (detect crash loop) */
    if (FW_META->boot_count >= BOOT_RETRY_MAX) {
        /* Too many failed boots — enter recovery mode */
        system_bootloader_activate();
    }

    /* Increment counter; application clears it on successful init */
    FW_META->boot_count++;

    /* Verify app CRC before jumping */
    if (!fw_verify_image(APP_START_ADDR, FW_META->app_size, FW_META->app_crc32)) {
        system_bootloader_activate();
    }

    app_jump(APP_START_ADDR);
}
```

## Jump to Application

```c
typedef void (*AppEntry_t)(void);

void app_jump(uint32_t app_addr)
{
    /* Verify stack pointer is in SRAM range */
    uint32_t sp = *(volatile uint32_t *)app_addr;
    if (sp < SRAM_BASE || sp > (SRAM_BASE + SRAM_SIZE))
        return; /* invalid — don't jump */

    /* De-init all peripherals used by bootloader */
    HAL_RCC_DeInit();
    HAL_DeInit();

    /* Disable SysTick and all interrupts */
    SysTick->CTRL = 0;
    for (int i = 0; i < 8; i++) {
        NVIC->ICER[i] = 0xFFFFFFFF;  /* disable all */
        NVIC->ICPR[i] = 0xFFFFFFFF;  /* clear pending */
    }

    /* Set vector table offset for application */
    SCB->VTOR = app_addr;
    __DSB();

    /* Set MSP and jump */
    __set_MSP(sp);
    AppEntry_t entry = (AppEntry_t)(*(volatile uint32_t *)(app_addr + 4));
    entry();
    /* Never returns */
}
```

## Application: Signal Successful Boot

```c
/* Application calls this after all peripherals initialized successfully.
 *
 * IMPORTANT: flash is read-only by default; you CANNOT clear boot_count
 * with a direct pointer assignment (`FW_META->boot_count = 0` faults).
 * The flash page holding the metadata must be re-programmed.
 *
 * Two strategies:
 *   (a) Reserve metadata on its OWN flash page; on each "clear", erase the
 *       page then re-write the whole struct with boot_count=0.
 *   (b) Store boot_count in BKPSRAM / RTC backup register / option byte —
 *       avoids flash wear; recommended for production.
 *
 * Below is strategy (a), keeping the metadata page intact otherwise.
 */
void fw_boot_success(void)
{
    FwMetadata_t shadow;
    memcpy(&shadow, (const void *)FW_META, sizeof(shadow));
    shadow.boot_count = 0;

    HAL_FLASH_Unlock();
    FLASH_EraseInitTypeDef erase = {
        .TypeErase    = FLASH_TYPEERASE_SECTORS,
        .Banks        = FLASH_BANK_1,
        .Sector       = FW_META_SECTOR,  /* page/sector that contains FW_META_ADDR */
        .NbSectors    = 1,
        .VoltageRange = FLASH_VOLTAGE_RANGE_3,
    };
    uint32_t err = 0;
    HAL_FLASHEx_Erase(&erase, &err);

    /* Re-program metadata (family-specific granularity — H7=256-bit,
     * H7A3=128-bit, F4=word/halfword/byte selectable). */
    for (uint32_t i = 0; i < sizeof(shadow); i += FLASH_WORD_BYTES) {
        HAL_FLASH_Program(FLASH_TYPEPROGRAM_FLASHWORD,
                          FW_META_ADDR + i,
                          (uint32_t)((const uint8_t *)&shadow + i));
    }
    HAL_FLASH_Lock();
}
```

## Dual-Bank Atomic Swap (H7/L4+/WB)

```c
/* 1. Receive new firmware into Bank2 over CAN/UART/TCP
   2. Verify CRC
   3. Set SWAP_BANK option byte + OPTSTRT
   4. Reset — CPU boots from new Bank1 (was Bank2) */

void dual_bank_swap_and_reset(void)
{
    HAL_FLASH_Unlock();
    HAL_FLASH_OB_Unlock();

    FLASH_OBProgramInitTypeDef ob = {0};
    HAL_FLASHEx_OBGetConfig(&ob);
    ob.OptionType = OPTIONBYTE_USER;
    ob.USERType   = OB_USER_SWAP_BANK;
    /* Toggle the swap-bank bit. The previous expression
     *   (USERConfig & ~OB_SWAP_BANK_ENABLE) ^ OB_SWAP_BANK_ENABLE
     * always SET the bit (mask-out then OR-equivalent), so the second OTA
     * cycle could never swap back. A simple XOR toggles correctly. */
    ob.USERConfig = (ob.USERConfig ^ OB_SWAP_BANK_ENABLE);

    HAL_FLASHEx_OBProgram(&ob);
    HAL_FLASH_OB_Lock();
    HAL_FLASH_Lock();
    HAL_FLASH_OB_Launch();  /* triggers system reset */
}
```

## Activate System Bootloader (UART DFU)

```c
/* Jump to ST ROM bootloader at 0x1FFF0000 (F4) or family-specific */
/* Supports: UART, USB DFU, CAN, SPI, I2C depending on family     */

void system_bootloader_activate(void)
{
    HAL_RCC_DeInit();
    SysTick->CTRL = 0;

    /* System-memory bootloader base is FAMILY-SPECIFIC (AN2606).
     * Setting a single hardcoded 0x1FFF0000 is WRONG for F7/H7/U5/L5 — the
     * CPU will jump into unmapped flash and HardFault.
     *
     *   STM32F0/F1/F3/F4   : 0x1FFF0000   (most parts; verify AN2606)
     *   STM32F7            : 0x1FF00000
     *   STM32G0/G4         : 0x1FFF0000
     *   STM32H7 (H743/53)  : 0x1FF09800
     *   STM32H7 (H7A3/B3)  : 0x1FF00000
     *   STM32H7 (H730/750) : 0x1FF09800
     *   STM32H5  (H563/73) : 0x0BF87000
     *   STM32L0/L1/L4      : 0x1FFF0000
     *   STM32L5/U5         : 0x0BF90000   (TrustZone-aware bootloader)
     *   STM32WB/WBA        : 0x1FFF0000 / 0x0BF88000 (check DS)
     * Always cross-check with AN2606 §5 table for the exact part. */
#if   defined(STM32F7)
    const uint32_t SYS_MEM = 0x1FF00000UL;
#elif defined(STM32H743xx) || defined(STM32H753xx) || \
      defined(STM32H730xx) || defined(STM32H750xx)
    const uint32_t SYS_MEM = 0x1FF09800UL;
#elif defined(STM32H7A3xx) || defined(STM32H7B0xx) || defined(STM32H7B3xx)
    const uint32_t SYS_MEM = 0x1FF00000UL;
#elif defined(STM32H5)
    const uint32_t SYS_MEM = 0x0BF87000UL;
#elif defined(STM32L5) || defined(STM32U5)
    const uint32_t SYS_MEM = 0x0BF90000UL;
#else  /* F0/F1/F3/F4/G0/G4/L0/L1/L4 (most parts) */
    const uint32_t SYS_MEM = 0x1FFF0000UL;
#endif

    __set_MSP(*(volatile uint32_t *)SYS_MEM);
    ((void (*)(void))(*(volatile uint32_t *)(SYS_MEM + 4)))();
}
```

## Rules

- NEVER erase the bootloader sector from application code
- Always verify CRC BEFORE erasing the current application region
- `boot_count` must be in flash (not RAM) — survives IWDG reset
- Application MUST call `fw_boot_success()` after all self-tests pass, or bootloader will roll back
- On dual-bank H7: write new image to Bank2 with IWDG disabled (long erase times)
- `app_jump`: always check SP validity — bad vector table will HardFault
- HAL_FLASH_Unlock must be balanced with HAL_FLASH_Lock even on error paths
