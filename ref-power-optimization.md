# Power Optimization Reference

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, errata workarounds, protocol-spec content** here is authoritative — that is why this file exists.
> - **Inline HAL/CMSIS/peripheral code snippets** are illustrative. The HAL drifts between versions and parts. For the canonical version of any HAL symbol at your HAL release: `gh search code <SymbolName> --owner=STMicroelectronics --extension=c` — see [ref-st-github-map.md](ref-st-github-map.md) §8 for the full lookup procedure.
> - **CRITICAL bugs identified in the 2026-05-16 audit have been corrected** in this file, but verify against your own HAL version before copy-pasting.
> - **For bootloader / IAP / OTA topics** the canonical checklist + ARM KA001193 + AN5188/2606/3155/3156 references are in [ref-bootloader.md](ref-bootloader.md).


## STM32 Power Mode Hierarchy

```
Run ──────────────────────────────────────── highest power, full SYSCLK
  └─ Sleep (WFI/WFE)                         CPU stopped, peripherals run
      └─ Low-Power Sleep                     CPU + main regulator stopped
          └─ Stop 0                          CPU + clocks stopped, SRAM/regs kept
              └─ Stop 1                      PLL/HSE/HSI off, SmpsLDO low-power
                  └─ Stop 2                  Most clocks off, lowest leakage in STOP
                      └─ Standby             SRAM lost, BKP + RTC survive
                          └─ Shutdown        VCORE off, only VBAT domain survives

Wakeup latency (typical):
  Sleep       → ~0 µs   (CPU resumes next cycle)
  Stop 0      → 8 µs    (clock on, SMPS stabilize)
  Stop 2      → 40 µs   (LDO ramp + PLL relock)
  Standby     → 250 µs  (POR + full boot, no code, just BKP regs)
  Shutdown    → ~1 ms   (full power-on reset)
```

---

## Sleep Mode (WFI — CPU halts, peripherals active)

```c
/* Minimal: CPU stops, SysTick still fires */
__WFI();

/* HAL wrapper — suspends SysTick before sleep */
void enter_sleep(void)
{
    HAL_SuspendTick();          /* stop SysTick to avoid immediate wakeup */
    HAL_PWR_EnterSLEEPMode(PWR_MAINREGULATOR_ON, PWR_SLEEPENTRY_WFI);
    HAL_ResumeTick();           /* restore SysTick on wakeup */
}
```

---

## Stop Mode — STM32L4 / STM32G4 / STM32U5

```c
/* Stop 2: deepest stop with RAM retention; ~2 µA on L4 */
void enter_stop2_with_rtc_wakeup(uint32_t seconds)
{
    /* Configure RTC wakeup timer */
    HAL_RTCEx_SetWakeUpTimer_IT(&hrtc, seconds, RTC_WAKEUPCLOCK_CK_SPRE_16BITS, 0);

    HAL_SuspendTick();
    __HAL_PWR_CLEAR_FLAG(PWR_FLAG_WU);
    HAL_PWREx_EnterSTOP2Mode(PWR_STOPENTRY_WFI);

    /* ── CPU resumes here after wakeup ── */
    SystemClock_Config();       /* PLL stopped in STOP — must reconfigure */
    HAL_ResumeTick();
    HAL_RTCEx_DeactivateWakeUpTimer(&hrtc);
}

/* LPTIM wakeup (no RTC needed — lower power) */
void enter_stop2_with_lptim(uint32_t ms)
{
    /* LPTIM1 runs on LSE (32kHz) in stop mode */
    HAL_LPTIM_TimeOut_Start_IT(&hlptim1, 0xFFFF,
        (uint32_t)(ms * 32 / 1000));   /* LSE ticks */

    HAL_SuspendTick();
    HAL_PWREx_EnterSTOP2Mode(PWR_STOPENTRY_WFI);

    SystemClock_Config();
    HAL_ResumeTick();
}
```

---

## Stop Mode — STM32H7 (Domain-Based Power)

On H7 there are three power domains: D1 (CPU), D2 (AHB/APB peripherals), D3 (autonomous).
D3 can stay active while D1/D2 sleep — key for low-power sensor acquisition.

```c
/* D1 Stop: CPU core sleeps, D2/D3 can keep running.
 * H7 HAL does NOT expose HAL_PWREx_EnterSTOP1Mode — that's an L4/G4 name.
 * On H7 use HAL_PWREx_EnterSTOPMode with a domain selector. */
void h7_enter_d1_stop(void)
{
    HAL_PWREx_EnterSTOPMode(PWR_MAINREGULATOR_ON, PWR_STOPENTRY_WFI,
                            PWR_D1_DOMAIN);
}

/* Full system Stop (all domains): deepest H7 stop with RAM retention */
void h7_enter_system_stop(void)
{
    PWR->CPUCR |= PWR_CPUCR_CSSF; /* clear standby flags */

    /* Configure D1/D2/D3 to stop */
    HAL_PWREx_EnterSTOPMode(PWR_LOWPOWERREGULATOR_ON, PWR_STOPENTRY_WFI,
                             PWR_D1_DOMAIN);

    /* After wakeup: HSI is clock source — must relock PLL */
    SystemClock_Config();
}

/* D3 autonomous mode: D3 stays on, D1+D2 stop */
/* Use case: DMA reading I2C sensor while CPU sleeps           */
void h7_d3_autonomous_sensor(void)
{
    /* Enable BDMA to D3 SRAM4 (only DMA accessible from D3) */
    /* Configure I2C4 (D3 peripheral) + BDMA channel          */
    /* Set D3 autonomous-mode clock enable per peripheral:
     * There is no __HAL_RCC_D3AMR_CLK_ENABLE() — autonomous-mode bits are
     * per-peripheral in RCC_D3AMR. Use the specific macro for the peripheral
     * you want to keep running, e.g. for I2C4 + BDMA + LPUART1: */
    __HAL_RCC_BDMA_CLKAM_ENABLE();
    __HAL_RCC_I2C4_CLKAM_ENABLE();
    __HAL_RCC_LPUART1_CLKAM_ENABLE();
    /* Then enter D1 stop — D3 keeps sampling */
    HAL_PWREx_EnterSTOPMode(PWR_LOWPOWERREGULATOR_ON, PWR_STOPENTRY_WFI,
                             PWR_D1_DOMAIN);
}
```

---

## Standby Mode (SRAM lost, BKP registers survive)

```c
/* Wake sources in standby: WKUP pins, RTC alarm/wakeup, NRST, IWDG */
void enter_standby(void)
{
    /* Configure wakeup pin (PA0 = WKUP1, active rising) */
    HAL_PWR_EnableWakeUpPin(PWR_WAKEUP_PIN1);

    /* Configure RTC alarm as wakeup */
    /* (alarm must be set before entering standby)        */

    HAL_PWR_EnterSTANDBYMode(); /* does not return — full reset on wakeup */
}

/* On wakeup from standby: check RCC_RSR flags */
void check_wakeup_cause(void)
{
    if (__HAL_PWR_GET_FLAG(PWR_FLAG_SB)) {
        /* Woke from standby — BKP registers preserved */
        __HAL_PWR_CLEAR_FLAG(PWR_FLAG_SB);
        uint32_t rtc_bkp = HAL_RTCEx_BKUPRead(&hrtc, RTC_BKP_DR0);
        restore_application_state(rtc_bkp);
    }

    if (__HAL_RCC_GET_FLAG(RCC_FLAG_IWDGRST)) {
        log_event(EVT_WATCHDOG_RESET);
        __HAL_RCC_CLEAR_RESET_FLAGS();
    }
}
```

---

## Voltage Scaling (VOS) — Run Mode Tuning

Reducing VOS when full speed is not needed saves 20–40% run current.

```c
/* STM32L4/G4: VOS1=max speed, VOS2=lower speed (~3 mW saved at 80 MHz) */
void set_vos_low_power(void)
{
    /* Reduce to VOS2 when running at ≤26 MHz */
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE2);
    /* Then reconfigure PLL to lower target; AHB prescaler can reduce HCLK */
}

/* STM32H7 VOS-to-frequency mapping — FAMILY-DEPENDENT, not universal.
 *
 *   H743 / H753 / H730 / H750  (RM0433 §6.6.2):
 *     VOS1 = 400 MHz, VOS2 = 300 MHz, VOS3 = 200 MHz
 *     VOS0 = 480 MHz, but ONLY on rev V silicon AND only after enabling
 *            SYSCFG->PWRCR.ODEN (overdrive) with the sequence in AN5312.
 *            Just writing VOS0 without enabling ODEN keeps the chip at 400 MHz.
 *
 *   H7A3 / H7B0 / H7B3  (RM0455 §6.8.6) — DIFFERENT encoding:
 *     VOS0 = 280 MHz, VOS1 = 225 MHz, VOS2 = 160 MHz, VOS3 = 88 MHz
 *
 * The function below targets H743-class parts. Adapt thresholds per family. */
void h7_set_vos_for_freq(uint32_t target_mhz)
{
    uint32_t vos;
    if      (target_mhz > 400) vos = PWR_REGULATOR_VOLTAGE_SCALE0; /* 480 MHz, needs ODEN */
    else if (target_mhz > 300) vos = PWR_REGULATOR_VOLTAGE_SCALE1; /* 400 MHz */
    else if (target_mhz > 200) vos = PWR_REGULATOR_VOLTAGE_SCALE2; /* 300 MHz */
    else                        vos = PWR_REGULATOR_VOLTAGE_SCALE3; /* 200 MHz */

    __HAL_PWR_VOLTAGESCALING_CONFIG(vos);
    while (!__HAL_PWR_GET_FLAG(PWR_FLAG_VOSRDY)) {} /* MANDATORY wait */

    /* To actually reach 480 MHz on rev V H743: enable overdrive.
     * Skipped above for non-VOS0; on rev Y silicon ODEN write has no effect. */
    if (vos == PWR_REGULATOR_VOLTAGE_SCALE0) {
        __HAL_RCC_SYSCFG_CLK_ENABLE();
        SYSCFG->PWRCR |= SYSCFG_PWRCR_ODEN;
        while (!__HAL_PWR_GET_FLAG(PWR_FLAG_ACTVOSRDY)) {}
    }
}
```

---

## Dynamic Clock Scaling (Adaptive Frequency)

```c
typedef enum { CLK_FULL = 0, CLK_MEDIUM, CLK_LOW } ClkLevel_t;
static ClkLevel_t current_clk = CLK_FULL;

/* Call from scheduler or main loop — reduces clock when system is idle */
void adaptive_clock_update(uint32_t cpu_load_pct)
{
    ClkLevel_t target;
    if      (cpu_load_pct > 70) target = CLK_FULL;
    else if (cpu_load_pct > 30) target = CLK_MEDIUM;
    else                         target = CLK_LOW;

    if (target == current_clk) return;

    /* Transition: must change VOS + flash latency together */
    if (target > current_clk) {
        /* Going slower: reduce freq first, then VOS */
        reconfigure_pll(target);
        set_vos_for_level(target);
    } else {
        /* Going faster: raise VOS first, then freq */
        set_vos_for_level(target);
        while (!__HAL_PWR_GET_FLAG(PWR_FLAG_VOSRDY)) {}
        reconfigure_pll(target);
    }
    current_clk = target;
}
```

---

## Peripheral Clock Gating

```c
/* Disable unused peripherals at init time — ~0.2 mA each */
void disable_unused_peripherals(void)
{
    /* APB1 */
    __HAL_RCC_TIM2_CLK_DISABLE();
    __HAL_RCC_TIM3_CLK_DISABLE();
    __HAL_RCC_USART2_CLK_DISABLE();
    __HAL_RCC_I2C2_CLK_DISABLE();
    __HAL_RCC_SPI2_CLK_DISABLE();

    /* APB2 */
    __HAL_RCC_SPI1_CLK_DISABLE();
    __HAL_RCC_USART1_CLK_DISABLE();

    /* AHB1 */
    __HAL_RCC_DMA2_CLK_DISABLE();      /* if DMA2 unused */
    __HAL_RCC_CRC_CLK_DISABLE();

    /* AHB2 */
    __HAL_RCC_ADC_CLK_DISABLE();       /* disable ADC when not sampling */
    __HAL_RCC_RNG_CLK_DISABLE();
}

/* Re-enable only what's needed for an operation, then disable again */
void adc_read_and_powerdown(void)
{
    __HAL_RCC_ADC_CLK_ENABLE();
    HAL_ADCEx_Calibration_Start(&hadc1, ADC_CALIB_OFFSET, ADC_SINGLE_ENDED);
    HAL_ADC_Start(&hadc1);
    HAL_ADC_PollForConversion(&hadc1, 10);
    uint32_t val = HAL_ADC_GetValue(&hadc1);
    HAL_ADC_Stop(&hadc1);
    __HAL_RCC_ADC_CLK_DISABLE();
    (void)val;
}
```

---

## Unused GPIO — Stop-Mode Leakage Prevention

Floating inputs oscillate and consume 0.5–2 mA each in stop mode.

```c
/* Configure ALL unused GPIOs to analog (lowest leakage state) */
void gpio_configure_unused_analog(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {
        .Mode  = GPIO_MODE_ANALOG,
        .Pull  = GPIO_NOPULL,
        .Speed = GPIO_SPEED_FREQ_LOW,
    };

    /* Configure all pins on unused ports */
    GPIO_InitStruct.Pin = GPIO_PIN_All;
    __HAL_RCC_GPIOC_CLK_ENABLE();
    HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);   /* example: PC unused */
    __HAL_RCC_GPIOD_CLK_ENABLE();
    HAL_GPIO_Init(GPIOD, &GPIO_InitStruct);
    __HAL_RCC_GPIOE_CLK_ENABLE();
    HAL_GPIO_Init(GPIOE, &GPIO_InitStruct);

    /* Now disable their clocks — analog mode holds without clock */
    __HAL_RCC_GPIOC_CLK_DISABLE();
    __HAL_RCC_GPIOD_CLK_DISABLE();
    __HAL_RCC_GPIOE_CLK_DISABLE();
}
```

---

## Battery-Adaptive Behavior

```c
typedef enum {
    BAT_FULL    = 0,   /* >80% */
    BAT_NOMINAL = 1,   /* 30–80% */
    BAT_LOW     = 2,   /* 10–30% */
    BAT_CRITICAL = 3,  /* <10%  */
} BatLevel_t;

typedef struct {
    uint32_t sample_rate_ms;
    ClkLevel_t clk_level;
    bool      ble_advertising;
    bool      display_on;
    uint32_t  sleep_timeout_ms;
} PowerProfile_t;

static const PowerProfile_t POWER_PROFILES[] = {
    /* FULL    */ { 100,  CLK_FULL,   true,  true,  30000 },
    /* NOMINAL */ { 500,  CLK_MEDIUM, true,  true,  10000 },
    /* LOW     */ { 2000, CLK_MEDIUM, false, false,  3000 },
    /* CRITICAL*/ { 5000, CLK_LOW,    false, false,  1000 },
};

void apply_power_profile(BatLevel_t level)
{
    const PowerProfile_t *p = &POWER_PROFILES[level];
    sensor_set_rate(p->sample_rate_ms);
    adaptive_clock_update(p->clk_level == CLK_FULL ? 100 :
                          p->clk_level == CLK_MEDIUM ? 50 : 10);
    if (!p->ble_advertising) ble_stop_advertising();
    if (!p->display_on)      display_off();
    sleep_set_timeout(p->sleep_timeout_ms);
}

BatLevel_t battery_classify(uint16_t mv)
{
    if      (mv > 4000) return BAT_FULL;
    else if (mv > 3600) return BAT_NOMINAL;
    else if (mv > 3400) return BAT_LOW;
    else                return BAT_CRITICAL;
}
```

---

## SMPS vs LDO Selection (H7, U5)

On STM32H7 the supply is controlled by SMPS (switched) + LDO cascade. SMPS is ~85% efficient vs LDO ~50%.

```c
/* Configure SMPS supply — do this EARLY, before PLL */
void h7_configure_smps(void)
{
    /* Direct SMPS: external 1.8V supply on VDD */
    HAL_PWREx_ConfigSupply(PWR_SMPS_1V8_SUPPLIES_LDO);

    /* Or: SMPS supplies LDO (board-dependent) */
    /* HAL_PWREx_ConfigSupply(PWR_SMPS_1V8_SUPPLIES_EXT_AND_LDO); */

    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE0);
    while (!__HAL_PWR_GET_FLAG(PWR_FLAG_VOSRDY)) {}
}

/* Reduce SMPS output voltage in low-power mode */
void h7_smps_low_power(void)
{
    /* In Stop: SMPS switches to 1.2V automatically if PWR_CR3_SMPSEN set */
    /* Nothing needed — HAL handles it when entering Stop mode             */
}
```

---

## Power Measurement with DWT (Current Estimation)

```c
/* DWT-based active-time measurement → estimate charge consumed */
/* Assumes you know current at each clock level from datasheet   */

#define CURR_FULL_UA    30000U   /* µA @ 168MHz, 3.3V (F4 typical) */
#define CURR_SLEEP_UA     500U   /* µA in sleep mode                */
#define CURR_STOP2_UA       3U   /* µA in stop2 (L4 typical)        */

typedef struct {
    uint32_t active_ticks;
    uint32_t sleep_ticks;
    uint32_t stop_ms;
} EnergyAccum_t;

static EnergyAccum_t g_energy;

void energy_mark_active_start(void)
{
    g_energy.active_ticks = DWT->CYCCNT;
}

void energy_mark_active_end(void)
{
    g_energy.active_ticks = DWT->CYCCNT - g_energy.active_ticks;
}

/* Returns estimate in µA·h (micro-amp-hours) over 1 second window */
float energy_estimate_uah(void)
{
    uint32_t clk = SystemCoreClock;
    float active_s = (float)g_energy.active_ticks / (float)clk;
    float stop_s   = (float)g_energy.stop_ms / 1000.0f;
    float sleep_s  = 1.0f - active_s - stop_s;
    if (sleep_s < 0) sleep_s = 0.0f;

    float charge_uas = active_s * CURR_FULL_UA
                     + sleep_s  * CURR_SLEEP_UA
                     + stop_s   * CURR_STOP2_UA;
    return charge_uas / 3600.0f; /* µA·s → µA·h */
}
```

---

## RTC Wakeup Patterns

```c
/* RTC periodic wakeup (1 s – 36 h range) */
void rtc_wakeup_start(uint32_t seconds)
{
    /* Disable first to allow reconfiguration */
    HAL_RTCEx_DeactivateWakeUpTimer(&hrtc);

    /* CK_SPRE = 1 Hz when clock source is LSE/LSI */
    /* Auto-reload value = seconds - 1 for period of `seconds` seconds */
    if (HAL_RTCEx_SetWakeUpTimer_IT(&hrtc,
                                     seconds - 1,
                                     RTC_WAKEUPCLOCK_CK_SPRE_16BITS,
                                     0) != HAL_OK)
        Error_Handler();
}

/* Handle RTC wakeup ISR */
void HAL_RTCEx_WakeUpTimerEventCallback(RTC_HandleTypeDef *hrtc)
{
    /* Called from RTC WKUP ISR */
    wakeup_source = WAKEUP_RTC;
}
```

---

## LPTIM Wakeup Pattern (Better than RTC for sub-second intervals)

```c
/* LPTIM1 runs on LSE in stop mode — down to 30µs resolution */
void lptim_wakeup_start_ms(uint32_t ms)
{
    uint32_t lse_hz = 32768;
    uint32_t autoreload = (lse_hz * ms) / 1000;
    if (autoreload > 0xFFFF) autoreload = 0xFFFF; /* 16-bit counter */

    HAL_LPTIM_TimeOut_Start_IT(&hlptim1, autoreload, autoreload);
}

void HAL_LPTIM_AutoReloadMatchCallback(LPTIM_HandleTypeDef *hlptim)
{
    wakeup_source = WAKEUP_LPTIM;
}
```

---

## Practical Stop/Wakeup State Machine (RTOS-free)

```c
typedef enum {
    PWR_STATE_ACTIVE = 0,
    PWR_STATE_IDLE,
    PWR_STATE_STOP,
} PwrState_t;

static PwrState_t pwr_state = PWR_STATE_ACTIVE;
static uint32_t   idle_entry_tick = 0;

#define IDLE_TO_STOP_MS  2000U  /* enter stop after 2s idle */

void power_manager_tick(void)
{
    bool work_pending = has_pending_work();

    switch (pwr_state) {
    case PWR_STATE_ACTIVE:
        if (!work_pending) {
            idle_entry_tick = HAL_GetTick();
            pwr_state = PWR_STATE_IDLE;
        }
        break;

    case PWR_STATE_IDLE:
        if (work_pending) {
            pwr_state = PWR_STATE_ACTIVE;
        } else if ((HAL_GetTick() - idle_entry_tick) > IDLE_TO_STOP_MS) {
            rtc_wakeup_start(WAKEUP_PERIOD_S);
            enter_stop2_with_rtc_wakeup(WAKEUP_PERIOD_S);
            /* ── resumes here after wakeup ── */
            pwr_state = PWR_STATE_ACTIVE;
        }
        break;

    default: break;
    }
}
```

---

## IWDG in Low-Power Modes

```c
/* IWDG uses LSI — continues counting in STOP and STANDBY */
/* Must pet IWDG before entering long stop periods         */
void safe_enter_stop(uint32_t sleep_ms)
{
    uint32_t iwdg_timeout_ms = IWDG_TIMEOUT_MS; /* e.g. 4000 */
    if (sleep_ms > iwdg_timeout_ms - 500) {
        /* Too long — don't enter stop, or configure IWDG for longer window */
        log_warning(WARN_STOP_TOO_LONG);
        return;
    }
    HAL_IWDG_Refresh(&hiwdg);  /* pet before sleeping */
    enter_stop2_with_rtc_wakeup(sleep_ms / 1000);
    HAL_IWDG_Refresh(&hiwdg);  /* pet immediately after wakeup */
}
```

---

## H7 Power Domain Current Budget (Approximate)

| Mode | D1 | D2 | D3 | Total |
|------|----|----|-----|-------|
| Run @ 480 MHz | 140 mA | 30 mA | 5 mA | ~175 mA |
| Sleep (CPU halt) | 5 mA | 30 mA | 5 mA | ~40 mA |
| Stop (D1 stop) | <1 mA | 30 mA | 5 mA | ~36 mA |
| Stop (all domains) | <1 mA | <1 mA | 2 mA | ~4 mA |
| Standby | — | — | 2 mA | ~2 mA |

> Values from STM32H743 datasheet Fig 11–13; vary ±30% with peripherals.

---

## Rules

- **Stop mode: always reconfigure PLL/clocks after wakeup** — PLL stops in STOP; HSI becomes SYSCLK
- **IWDG uses LSI** — survives all stop modes; pet before entering long sleep
- **Unused GPIOs must be analog** — floating inputs oscillate and add 0.5–2 mA each in stop
- **SysTick must be suspended** before stop/sleep or it fires immediately
- **VOS change order**: going faster → VOS up first, then PLL; going slower → PLL down first, then VOS
- **H7 SMPS > LDO** — always configure SMPS when external components allow (~85% vs ~50% efficiency)
- **D3 autonomous mode** — use on H7 when sensor data acquisition can proceed without CPU
- **LPTIM preferred over RTC** for sub-second wakeup — lower power, simpler setup
- **Clock verification after wakeup** — call `clock_verify()` to confirm PLL relocked correctly
- **Batch peripheral use** — enable clock → operate → disable clock; never leave idle peripherals clocked
