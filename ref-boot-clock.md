# Boot Sequence & Clock Tree

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, errata workarounds, protocol-spec content** here is authoritative — that is why this file exists.
> - **Inline HAL/CMSIS/peripheral code snippets** are illustrative. The HAL drifts between versions and parts. For the canonical version of any HAL symbol at your HAL release: `gh search code <SymbolName> --owner=STMicroelectronics --extension=c` — see [ref-st-github-map.md](ref-st-github-map.md) §8 for the full lookup procedure.
> - **CRITICAL bugs identified in the 2026-05-16 audit have been corrected** in this file, but verify against your own HAL version before copy-pasting.
> - **For bootloader / IAP / OTA topics** the canonical checklist + ARM KA001193 + AN5188/2606/3155/3156 references are in [ref-bootloader.md](ref-bootloader.md).


## Startup Order (mandatory sequence)

```c
int main(void)
{
    /* 1. Reset cause — BEFORE HAL_Init (HAL clears RCC->CSR) */
    reset_cause_detect();
    boot_counter_update();

    /* 2. HAL tick init (SysTick @ 1 kHz) */
    HAL_Init();

    /* 3. Clock tree — SYSCLK, AHB, APB buses */
    SystemClock_Config();

    /* 4. Fault traps */
    fault_traps_enable();

    /* 5. MPU */
    mpu_setup();

    /* 6. Backup domain (RTC, LSE) */
    rtc_backup_domain_init();

    /* 7. Application peripherals */
    peripheral_init_all();

    /* 8. Check and report any persisted fault log */
    fault_log_check_and_report();

    /* 9. RTOS / main loop */
    osKernelStart(); /* or application_main_loop() */
}
```

---

## PLL Configuration (HSE → SYSCLK)

### STM32F4 Example — 168 MHz from 8 MHz HSE

```c
void SystemClock_Config(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};

    /* 1. Enable power controller, set VOS Scale 1 for max freq */
    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

    /* 2. Configure HSE + PLL */
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState       = RCC_HSE_ON;
    osc.PLL.PLLState   = RCC_PLL_ON;
    osc.PLL.PLLSource  = RCC_PLLSOURCE_HSE;
    /* VCO = 8 MHz * (N/M) = 8 * 168/4 = 336 MHz */
    osc.PLL.PLLM       = 4;    /* HSE / M = 2 MHz (VCO input must be 1–2 MHz) */
    osc.PLL.PLLN       = 168;  /* VCO = 336 MHz */
    osc.PLL.PLLP       = RCC_PLLP_DIV2; /* SYSCLK = 336/2 = 168 MHz */
    osc.PLL.PLLQ       = 7;   /* USB/SDIO = 336/7 = 48 MHz */
    HAL_RCC_OscConfig(&osc);

    /* 3. Enable overdrive for 168 MHz */
    HAL_PWREx_EnableOverDrive();

    /* 4. Set flash latency — F4@168MHz needs 5 WS */
    __HAL_FLASH_SET_LATENCY(FLASH_LATENCY_5);

    /* 5. Configure bus clocks */
    clk.ClockType = RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK
                  | RCC_CLOCKTYPE_PCLK1  | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource   = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider  = RCC_SYSCLK_DIV1;   /* AHB = 168 MHz */
    clk.APB1CLKDivider = RCC_HCLK_DIV4;     /* APB1 = 42 MHz (max 42) */
    clk.APB2CLKDivider = RCC_HCLK_DIV2;     /* APB2 = 84 MHz (max 84) */
    HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_5);
}
```

### STM32H7 Example — 480 MHz from 25 MHz HSE

```c
void SystemClock_Config(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};

    HAL_PWREx_ConfigSupply(PWR_LDO_SUPPLY);
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE0); /* VOS0 for 480 MHz */
    while (!__HAL_PWR_GET_FLAG(PWR_FLAG_VOSRDY)) {} /* wait for VOS */

    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState       = RCC_HSE_ON;
    osc.PLL.PLLState   = RCC_PLL_ON;
    osc.PLL.PLLSource  = RCC_PLLSOURCE_HSE;
    /* VCO_in = 25/5 = 5 MHz; VCO = 5 * 192 = 960 MHz */
    osc.PLL.PLLM       = 5;
    osc.PLL.PLLN       = 192;
    osc.PLL.PLLP       = 2;   /* SYSCLK = 960/2 = 480 MHz */
    osc.PLL.PLLQ       = 4;   /* 240 MHz for peripherals */
    osc.PLL.PLLR       = 2;
    osc.PLL.PLLRGE     = RCC_PLL1VCIRANGE_2; /* VCO input 4–8 MHz */
    osc.PLL.PLLVCOSEL  = RCC_PLL1VCOWIDE;    /* wide range VCO */
    osc.PLL.PLLFRACN   = 0;
    HAL_RCC_OscConfig(&osc);

    clk.ClockType = RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK
                  | RCC_CLOCKTYPE_D1PCLK1 | RCC_CLOCKTYPE_PCLK1
                  | RCC_CLOCKTYPE_PCLK2   | RCC_CLOCKTYPE_D3PCLK1;
    clk.SYSCLKSource     = RCC_SYSCLKSOURCE_PLLCLK;
    clk.SYSCLKDivider    = RCC_SYSCLK_DIV1;   /* CPU = 480 MHz */
    clk.AHBCLKDivider    = RCC_HCLK_DIV2;     /* AHB = 240 MHz */
    clk.APB3CLKDivider   = RCC_APB3_DIV2;
    clk.APB1CLKDivider   = RCC_APB1_DIV2;     /* APB1 = 120 MHz */
    clk.APB2CLKDivider   = RCC_APB2_DIV2;
    clk.APB4CLKDivider   = RCC_APB4_DIV2;
    HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_4);
}
```

### Flash Wait States Table

| SYSCLK (F4) | VCC 2.7–3.6V | VCC 2.4–2.7V |
|-------------|--------------|--------------|
| ≤ 30 MHz    | 0 WS         | 0 WS         |
| ≤ 60 MHz    | 1 WS         | 2 WS         |
| ≤ 90 MHz    | 2 WS         | 3 WS         |
| ≤ 120 MHz   | 3 WS         | 4 WS         |
| ≤ 150 MHz   | 4 WS         | 5 WS         |
| ≤ 168 MHz   | 5 WS         | 6 WS         |

> H7: datasheet Table 15 (VOS0: max 4WS @ 480 MHz with ART enabled)

---

## Clock Security System (CSS)

```c
/* Enable CSS: if HSE fails, MCU auto-switches to HSI and triggers NMI */
HAL_RCC_EnableCSS();

/* NMI handler — called on HSE failure */
void NMI_Handler(void)
{
    if (__HAL_RCC_GET_IT(RCC_IT_CSS)) {
        __HAL_RCC_CLEAR_IT(RCC_IT_CSS);

        /* Log the event */
        log_critical(FAULT_CLOCK_FAILURE);

        /* Reconfigure to safe HSI-based clock for continued operation */
        RCC_OscInitTypeDef osc = {.OscillatorType = RCC_OSCILLATORTYPE_HSI,
                                   .HSIState = RCC_HSI_ON,
                                   .HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT};
        HAL_RCC_OscConfig(&osc);

        RCC_ClkInitTypeDef clk = {
            .ClockType = RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK
                       | RCC_CLOCKTYPE_PCLK1  | RCC_CLOCKTYPE_PCLK2,
            .SYSCLKSource = RCC_SYSCLKSOURCE_HSI,
            .AHBCLKDivider = RCC_SYSCLK_DIV1,
            .APB1CLKDivider = RCC_HCLK_DIV1,
            .APB2CLKDivider = RCC_HCLK_DIV1,
        };
        HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_0);

        /* Optional: trigger safe mode */
        safe_mode_enter();
    }
}
```

---

## Backup Domain Init (RTC + LSE)

```c
void rtc_backup_domain_init(void)
{
    /* Enable backup domain access */
    HAL_PWR_EnableBkUpAccess();

    /* Only initialize LSE/RTC if backup domain was reset */
    if (__HAL_RCC_GET_FLAG(RCC_FLAG_BORRST) ||
        __HAL_RCC_GET_FLAG(RCC_FLAG_PINRST)) {

        /* Force backup domain reset to recover from corrupt state */
        __HAL_RCC_BACKUPRESET_FORCE();
        __HAL_RCC_BACKUPRESET_RELEASE();

        /* Start LSE — external 32.768 kHz crystal */
        RCC_OscInitTypeDef osc = {
            .OscillatorType = RCC_OSCILLATORTYPE_LSE,
            .LSEState       = RCC_LSE_ON,
        };
        HAL_RCC_OscConfig(&osc);

        /* Select LSE as RTC clock source */
        __HAL_RCC_RTC_CONFIG(RCC_RTCCLKSOURCE_LSE);
        __HAL_RCC_RTC_ENABLE();

        HAL_RTC_Init(&hrtc); /* CubeMX-generated handle */
    }
    /* If backup domain intact: RTC keeps running, BKP registers preserved */
}
```

## Clock Frequency Verification

```c
/* Verify actual SYSCLK matches expected — catch PLL misconfiguration */
void clock_verify(uint32_t expected_hz)
{
    uint32_t actual = HAL_RCC_GetSysClockFreq();
    if (actual != expected_hz) {
        /* Clock config failed — this is fatal */
        log_fatal(FAULT_CLOCK_WRONG_FREQ, actual);
        NVIC_SystemReset();
    }
}

/* Call after SystemClock_Config() */
/* clock_verify(168000000); for F4@168MHz */
```

## PLL Calculation Cheat Sheet

```
VCO_input  = HSE / PLLM          → must be 1–2 MHz (F4) or 1–16 MHz (H7)
VCO_output = VCO_input * PLLN    → must be 100–432 MHz (F4) or 192–836 MHz (H7)
SYSCLK     = VCO_output / PLLP   → (PLLP = 2, 4, 6, 8 on F4)
USB/SDIO   = VCO_output / PLLQ   → must be 48 MHz for USB

Example (F4, HSE=8 MHz, SYSCLK=168 MHz):
  VCO_input  = 8 / 4 = 2 MHz
  VCO_output = 2 * 168 = 336 MHz
  SYSCLK     = 336 / 2 = 168 MHz  ✓
  USB        = 336 / 7 = 48 MHz   ✓
```

---

## STM32H7 Dual-PLL Configuration (PLL1 + PLL2 + PLL3)

H7 has three independent PLLs. PLL1 → SYSCLK; PLL2/PLL3 → peripherals (FDCAN, USB, OCTOSPI, SAI, ADC).

```c
void SystemClock_Config_H7_Dual_PLL(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};
    RCC_PeriphCLKInitTypeDef periph = {0};

    HAL_PWREx_ConfigSupply(PWR_LDO_SUPPLY);
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE0); /* VOS0: 480 MHz */
    while (!__HAL_PWR_GET_FLAG(PWR_FLAG_VOSRDY)) {}

    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState       = RCC_HSE_ON;

    /* PLL1: SYSCLK = 480 MHz (from HSE=25MHz) */
    /* VCO_in = 25/5 = 5 MHz; VCO = 5×192 = 960 MHz; P=2 → 480 MHz */
    osc.PLL.PLLState   = RCC_PLL_ON;
    osc.PLL.PLLSource  = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLM       = 5;
    osc.PLL.PLLN       = 192;
    osc.PLL.PLLP       = 2;   /* SYSCLK = 480 MHz */
    osc.PLL.PLLQ       = 4;   /* PLL1_Q = 240 MHz */
    osc.PLL.PLLR       = 2;
    osc.PLL.PLLRGE     = RCC_PLL1VCIRANGE_2;  /* VCO input 4–8 MHz */
    osc.PLL.PLLVCOSEL  = RCC_PLL1VCOWIDE;
    osc.PLL.PLLFRACN   = 0;
    HAL_RCC_OscConfig(&osc);

    /* PLL2: for FDCAN (104 MHz) and OCTOSPI (200 MHz) */
    /* VCO_in = 25/5 = 5 MHz; VCO = 5×160 = 800 MHz */
    /* Q=8 → 100 MHz for FDCAN; P=4 → 200 MHz for OCTOSPI */
    periph.PeriphClockSelection |= RCC_PERIPHCLK_FDCAN;
    periph.FdcanClockSelection   = RCC_FDCANCLKSOURCE_PLL2;
    periph.PLL2.PLL2M            = 5;
    periph.PLL2.PLL2N            = 160;
    periph.PLL2.PLL2P            = 4;   /* 200 MHz → OCTOSPI */
    periph.PLL2.PLL2Q            = 8;   /* 100 MHz → FDCAN   */
    periph.PLL2.PLL2R            = 2;
    periph.PLL2.PLL2RGE          = RCC_PLL2VCIRANGE_2;
    periph.PLL2.PLL2VCOSEL       = RCC_PLL2VCOWIDE;
    periph.PLL2.PLL2FRACN        = 0;

    /* PLL3: for USB (48 MHz exact) and SAI/I2S audio */
    /* VCO_in = 25/5 = 5 MHz; VCO = 5×96 = 480 MHz; Q=10 → 48 MHz */
    periph.PeriphClockSelection |= RCC_PERIPHCLK_USB;
    periph.UsbClockSelection     = RCC_USBCLKSOURCE_PLL3;
    periph.PLL3.PLL3M            = 5;
    periph.PLL3.PLL3N            = 96;
    periph.PLL3.PLL3P            = 2;
    periph.PLL3.PLL3Q            = 10;  /* 48 MHz → USB */
    periph.PLL3.PLL3R            = 2;
    periph.PLL3.PLL3RGE          = RCC_PLL3VCIRANGE_2;
    periph.PLL3.PLL3VCOSEL       = RCC_PLL3VCOWIDE;
    periph.PLL3.PLL3FRACN        = 0;

    HAL_RCCEx_PeriphCLKConfig(&periph);

    /* System clock configuration */
    clk.ClockType        = RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK
                         | RCC_CLOCKTYPE_D1PCLK1 | RCC_CLOCKTYPE_PCLK1
                         | RCC_CLOCKTYPE_PCLK2   | RCC_CLOCKTYPE_D3PCLK1;
    clk.SYSCLKSource     = RCC_SYSCLKSOURCE_PLLCLK;
    clk.SYSCLKDivider    = RCC_SYSCLK_DIV1;   /* CPU1 = 480 MHz */
    clk.AHBCLKDivider    = RCC_HCLK_DIV2;     /* AHB = 240 MHz  */
    clk.APB3CLKDivider   = RCC_APB3_DIV2;     /* APB3 = 120 MHz */
    clk.APB1CLKDivider   = RCC_APB1_DIV2;     /* APB1 = 120 MHz */
    clk.APB2CLKDivider   = RCC_APB2_DIV2;     /* APB2 = 120 MHz */
    clk.APB4CLKDivider   = RCC_APB4_DIV2;     /* APB4 = 120 MHz */
    HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_4);

    /* Enable instruction cache (ART Accelerator on H7 is AXI) */
    SCB_EnableICache();
    SCB_EnableDCache();
}
```

---

## STM32H5 / U5 Clock Tree (Different from H7)

H5 and U5 use a different RCC structure: ICACHE (not ART), one main PLL + two secondary PLLs, no D1/D2/D3 domain split.

```c
/* STM32H563 / H573 — up to 250 MHz from HSE */
void SystemClock_Config_H5(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};

    /* VOS0 required for 250 MHz */
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE0);
    while (!__HAL_PWR_GET_FLAG(PWR_FLAG_VOSRDY)) {}

    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState       = RCC_HSE_ON;
    osc.PLL.PLLState   = RCC_PLL_ON;
    osc.PLL.PLLSource  = RCC_PLLSOURCE_HSE;
    /* VCO_in = 25/5 = 5 MHz (H5 VCI range: 4–16 MHz) */
    /* VCO_out = 5×100 = 500 MHz; P=2 → 250 MHz */
    osc.PLL.PLLM       = 5;
    osc.PLL.PLLN       = 100;
    osc.PLL.PLLP       = 2;   /* SYSCLK = 250 MHz */
    osc.PLL.PLLQ       = 2;   /* PLL1_Q = 250 MHz → FDCAN, OCTOSPI */
    osc.PLL.PLLR       = 2;
    osc.PLL.PLLRGE     = RCC_PLL1VCIRANGE_1; /* 4–8 MHz — H5 uses different enum! */
    osc.PLL.PLLVCOSEL  = RCC_PLL1VCOMEDIUM;  /* 150–420 MHz VCO — H5 range */
    osc.PLL.PLLFRACN   = 0;
    HAL_RCC_OscConfig(&osc);

    clk.ClockType      = RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK
                       | RCC_CLOCKTYPE_PCLK1  | RCC_CLOCKTYPE_PCLK2
                       | RCC_CLOCKTYPE_PCLK3;
    clk.SYSCLKSource   = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider  = RCC_SYSCLK_DIV1;   /* AHB = 250 MHz */
    clk.APB1CLKDivider = RCC_HCLK_DIV2;     /* APB1 = 125 MHz */
    clk.APB2CLKDivider = RCC_HCLK_DIV2;     /* APB2 = 125 MHz */
    clk.APB3CLKDivider = RCC_HCLK_DIV2;     /* APB3 = 125 MHz */
    HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_5); /* H5@250MHz: 5 WS */

    /* H5: enable ICACHE (replaces F4/H7 ART Accelerator) */
    __HAL_RCC_ICACHE_CLK_ENABLE();
    HAL_ICACHE_Enable();
}

/* STM32U575 / U585 — 160 MHz, ultra-low-power focus */
void SystemClock_Config_U5(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};

    /* U5: MSIS or HSE as PLL source. MSIS (16MHz default) avoids external crystal */
    osc.OscillatorType = RCC_OSCILLATORTYPE_MSIS;
    osc.MSISState      = RCC_MSI_ON;
    osc.MSISClockRange = RCC_MSIRANGE_4;  /* 4 MHz (internal) */
    osc.PLL.PLLState   = RCC_PLL_ON;
    osc.PLL.PLLSource  = RCC_PLLSOURCE_MSIS;
    /* VCO_in = 4/1 = 4 MHz; VCO = 4×40 = 160 MHz; P=1 → 160 MHz */
    osc.PLL.PLLM       = 1;
    osc.PLL.PLLN       = 40;
    osc.PLL.PLLP       = 1;   /* SYSCLK = 160 MHz */
    osc.PLL.PLLQ       = 2;   /* 80 MHz for USB/SAI */
    osc.PLL.PLLR       = 1;
    HAL_RCC_OscConfig(&osc);

    clk.SYSCLKSource   = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider  = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV1;
    clk.APB2CLKDivider = RCC_HCLK_DIV1;
    clk.APB3CLKDivider = RCC_HCLK_DIV1;
    HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_4); /* U5@160MHz: 4 WS */

    /* U5: enable ICACHE */
    HAL_ICACHE_Enable();
}
```

---

## ICACHE (H5, U5, G0, C0 — replaces ART Accelerator)

```c
/* Enable before executing from flash at high frequency */
/* Must be called AFTER SystemClock_Config() sets flash wait states */

void icache_enable(void)
{
    __HAL_RCC_ICACHE_CLK_ENABLE();

    /* Choose mapping mode: direct-mapped (faster) or 2-way set-associative */
    ICACHE->CR = ICACHE_CR_WAYSEL;   /* 2-way set-associative (better for real code) */

    HAL_ICACHE_Enable();

    /* Invalidate before first enable or after XIP flash update */
    /* HAL_ICACHE_Invalidate(); */
}

/* After in-application flash write: MUST invalidate I-Cache */
void icache_invalidate_after_flash_write(void)
{
    HAL_ICACHE_Disable();
    HAL_ICACHE_Invalidate();    /* waits for BSYENDF flag */
    HAL_ICACHE_Enable();
}
```

---

## Clock Frequency Map — Family Comparison

| Family | Max SYSCLK | VCO Input | Flash WS@Max | I-Cache |
|--------|-----------|-----------|-------------|---------|
| STM32F4 | 168 MHz | 1–2 MHz | 5 WS | ART Accelerator |
| STM32F7 | 216 MHz | 1–2 MHz | 7 WS | ART + L1 cache |
| STM32H7 | 480 MHz | 1–16 MHz | 4 WS (VOS0) | AXI + I/D-Cache |
| STM32G4 | 170 MHz | 2.66–16 MHz | 4 WS | ICACHE |
| STM32H5 | 250 MHz | 4–16 MHz | 5 WS | ICACHE |
| STM32U5 | 160 MHz | 2.66–16 MHz | 4 WS | ICACHE |

---

## Rules

- Always set flash wait states BEFORE increasing SYSCLK — never after
- Verify `HAL_RCC_OscConfig()` return value — HSE timeout = no crystal fitted
- LSE startup can take up to 2 seconds — do NOT block the boot sequence waiting for it
- CSS NMI must reconfigure clocks — system cannot run on dead HSE without fallback
- Backup domain (RTC, BKP registers) survives IWDG and software resets — use for persistent state
- H7: must wait for `PWR_FLAG_VOSRDY` after VOS change before configuring PLL
- PLLM must produce 1–2 MHz VCO input on F4 — violating this causes unstable VCO
- H7 PLL2/PLL3: configure via `HAL_RCCEx_PeriphCLKConfig()`, NOT `HAL_RCC_OscConfig()`
- H5/U5 ICACHE: must invalidate after any in-application flash write; plain enable at boot is enough
- H5 VCO range enum values differ from H7 — check `RCC_PLL1VCIRANGE_x` in your family's header
- U5 MSIS: usable as PLL source without external crystal — useful for low-cost, low-BOM designs
