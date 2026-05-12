# Boot Sequence & Clock Tree

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

## Rules

- Always set flash wait states BEFORE increasing SYSCLK — never after
- Verify `HAL_RCC_OscConfig()` return value — HSE timeout = no crystal fitted
- LSE startup can take up to 2 seconds — do NOT block the boot sequence waiting for it
- CSS NMI must reconfigure clocks — system cannot run on dead HSE without fallback
- Backup domain (RTC, BKP registers) survives IWDG and software resets — use for persistent state
- H7: must wait for `PWR_FLAG_VOSRDY` after VOS change before configuring PLL
- PLLM must produce 1–2 MHz VCO input on F4 — violating this causes unstable VCO
