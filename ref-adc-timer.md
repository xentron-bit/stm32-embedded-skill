# ADC & Timer Reference

## ADC — Calibration + Single Conversion (LL)

```c
/* Calibrate before first use — required for accurate readings */
void adc_init(ADC_HandleTypeDef *hadc)
{
    /* Calibrate for single-ended input */
    HAL_ADCEx_Calibration_Start(hadc, ADC_CALIB_OFFSET, ADC_SINGLE_ENDED);
    HAL_ADC_Start(hadc);
}

uint16_t adc_read_blocking(ADC_HandleTypeDef *hadc)
{
    HAL_ADC_Start(hadc);
    if (HAL_ADC_PollForConversion(hadc, 10) != HAL_OK)
        return 0xFFFF; /* timeout sentinel */
    return (uint16_t)HAL_ADC_GetValue(hadc);
}
```

## ADC — DMA Circular Mode (continuous multi-channel)

```c
/* Place in DMA-safe region; align for M7 cache */
#define ADC_CH_COUNT 4
#define ADC_OVERSAMPLE 16   /* average 16 samples per channel */
#define ADC_BUF_LEN  (ADC_CH_COUNT * ADC_OVERSAMPLE)

ALIGN_32BYTES(static volatile uint16_t adc_dma_buf[ADC_BUF_LEN])
    __attribute__((section(".dma_buf")));

static uint16_t adc_result[ADC_CH_COUNT]; /* averaged results */

/* Start continuous DMA — call once */
void adc_dma_start(ADC_HandleTypeDef *hadc)
{
    HAL_ADCEx_Calibration_Start(hadc, ADC_CALIB_OFFSET, ADC_SINGLE_ENDED);
    HAL_ADC_Start_DMA(hadc, (uint32_t *)adc_dma_buf, ADC_BUF_LEN);
}

/* HAL callback — called when full buffer complete */
void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
    /* M7 only: invalidate cache before reading DMA buffer */
    SCB_InvalidateDCache_by_Addr((uint32_t *)adc_dma_buf, sizeof(adc_dma_buf));

    /* Average ADC_OVERSAMPLE readings per channel */
    for (int ch = 0; ch < ADC_CH_COUNT; ch++) {
        uint32_t sum = 0;
        for (int s = 0; s < ADC_OVERSAMPLE; s++)
            sum += adc_dma_buf[ch + s * ADC_CH_COUNT];
        adc_result[ch] = (uint16_t)(sum / ADC_OVERSAMPLE);
    }
}

/* Read averaged value — safe from any task */
uint16_t adc_get(int channel)
{
    /* adc_result[ch] is uint16_t — single-word reads are atomic on ARM */
    return adc_result[channel];
}
```

## ADC — Oversampling Hardware Shift (G0/G4/U5 feature)

```c
/* CubeMX: OversamplingMode=ENABLE, OversamplingRatio=256x, RightBitShift=8
   Effective resolution: 12-bit + 8-bit = 20-bit → shifted right 8 → 12-bit clean */
/* No software averaging needed; hardware does it. Result in 12-bit range. */
```

## ADC — Temperature Sensor (internal)

```c
float adc_read_temp_celsius(ADC_HandleTypeDef *hadc)
{
    /* Enable temperature sensor channel in CubeMX first */
    HAL_ADC_Start(hadc);
    HAL_ADC_PollForConversion(hadc, 10);
    uint32_t raw = HAL_ADC_GetValue(hadc);

    /* STM32 datasheet: TS_CAL1 at 30°C, TS_CAL2 at 110°C (3V3 VDDA) */
    float ts_cal1 = (float)(*TEMPSENSOR_CAL1_ADDR);
    float ts_cal2 = (float)(*TEMPSENSOR_CAL2_ADDR);
    float slope   = (110.0f - 30.0f) / (ts_cal2 - ts_cal1);
    return slope * ((float)raw - ts_cal1) + 30.0f;
}
```

## ADC Conversion: Raw → Voltage → Engineering Unit

```c
#define VREF_MV  3300U  /* or read VREFINT for precision */
#define ADC_BITS 12

static inline uint32_t adc_to_mv(uint16_t raw)
{
    return ((uint32_t)raw * VREF_MV) / ((1U << ADC_BITS) - 1);
}

/* Example: pressure sensor 0.5–4.5 V → 0–100 bar */
static inline float mv_to_bar(uint32_t mv)
{
    if (mv < 500)  return -1.0f; /* sensor fault */
    if (mv > 4500) return -2.0f; /* sensor fault */
    return ((float)(mv - 500) / 4000.0f) * 100.0f;
}
```

---

## Timer — PWM Generation (TIM, HAL)

```c
/* CubeMX: TIMx, Channel1, PWM mode 1, ARR=period, CCR1=duty */

/* Set duty cycle 0–100% at runtime */
void pwm_set_duty(TIM_HandleTypeDef *htim, uint32_t channel, float duty_pct)
{
    uint32_t arr  = __HAL_TIM_GET_AUTORELOAD(htim);
    uint32_t ccr  = (uint32_t)(duty_pct * arr / 100.0f);
    __HAL_TIM_SET_COMPARE(htim, channel, ccr);
}

/* Start PWM */
void pwm_start(TIM_HandleTypeDef *htim, uint32_t channel)
{
    HAL_TIM_PWM_Start(htim, channel);
}

/* Dead-time complementary PWM (motor H-bridge) */
void complementary_pwm_start(TIM_HandleTypeDef *htim, uint32_t channel)
{
    HAL_TIMEx_PWMN_Start(htim, channel);  /* N channel */
    HAL_TIM_PWM_Start(htim, channel);     /* P channel */
}
```

## Timer — Input Capture (frequency / pulse width measurement)

```c
static volatile uint32_t ic_capture1 = 0, ic_capture2 = 0;
static volatile bool ic_ready = false;

void HAL_TIM_IC_CaptureCallback(TIM_HandleTypeDef *htim)
{
    if (htim->Channel == HAL_TIM_ACTIVE_CHANNEL_1) {
        ic_capture1 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_1);
        HAL_TIM_IC_Start_IT(htim, TIM_CHANNEL_2); /* arm second edge */
    }
    if (htim->Channel == HAL_TIM_ACTIVE_CHANNEL_2) {
        ic_capture2 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_2);
        ic_ready = true;
    }
}

/* Get period in timer ticks */
uint32_t ic_get_period_ticks(void)
{
    if (!ic_ready) return 0;
    ic_ready = false;
    return (ic_capture2 >= ic_capture1)
           ? (ic_capture2 - ic_capture1)
           : ((__HAL_TIM_GET_AUTORELOAD(&htim1) + 1) + ic_capture2 - ic_capture1);
}

/* Convert to Hz given timer clock */
float ic_get_frequency_hz(uint32_t timer_clk_hz)
{
    uint32_t ticks = ic_get_period_ticks();
    if (ticks == 0) return 0.0f;
    return (float)timer_clk_hz / (float)ticks;
}
```

## Timer — Encoder Interface (quadrature)

```c
/* CubeMX: TIMx, Encoder mode, Channel1+2, TI1FP1+TI2FP2,
   CounterMode=Up, Prescaler=0, Period=0xFFFF (or 4x counts per cycle) */

int32_t encoder_get_count(TIM_HandleTypeDef *htim)
{
    /* Signed 32-bit from 16-bit counter — track overflows if needed */
    return (int32_t)(int16_t)__HAL_TIM_GET_COUNTER(htim);
}

void encoder_reset(TIM_HandleTypeDef *htim)
{
    __HAL_TIM_SET_COUNTER(htim, 0);
}

/* Velocity from position delta — call at fixed interval */
int32_t encoder_get_velocity(TIM_HandleTypeDef *htim, int32_t *prev_count)
{
    int32_t current = encoder_get_count(htim);
    int32_t delta   = current - *prev_count;
    *prev_count     = current;
    return delta; /* ticks per interval */
}
```

## Timer — Drift-Free Periodic Callback (no RTOS)

```c
/* Replace FreeRTOS vTaskDelayUntil for bare-metal precise timing */
static uint32_t last_tick = 0;

void control_loop_10ms(void)
{
    uint32_t now = HAL_GetTick();
    if ((now - last_tick) < 10) return; /* not yet */
    last_tick += 10; /* drift-free: don't set to 'now' */

    /* 10 ms control tick */
    sensor_update();
    pid_compute();
    pwm_set_duty(&htim1, TIM_CHANNEL_1, pid_output);
}
```

## Timer — One-Shot Software Timeout

```c
typedef struct {
    uint32_t start;
    uint32_t period_ms;
    bool     armed;
} SwTimer_t;

static inline void sw_timer_start(SwTimer_t *t, uint32_t ms)
{
    t->start     = HAL_GetTick();
    t->period_ms = ms;
    t->armed     = true;
}

static inline bool sw_timer_expired(SwTimer_t *t)
{
    if (!t->armed) return false;
    if ((HAL_GetTick() - t->start) >= t->period_ms) {
        t->armed = false;
        return true;
    }
    return false;
}
```

---

## ADC — Injected Channel (Fast Acquisition in ISR)

Injected channels interrupt a regular conversion sequence and return immediately — ideal for current sensing triggered by a PWM timer.

```c
/* CubeMX: ADC1, Injected group, Trigger = TIM1_CC4, 1 rank */
/* Auto-injection: injected runs after last regular conversion     */

/* In CubeMX: ExternalTrigInjecConv = ADC_EXTERNALTRIGINJECCONV_T1_CC4 */
/* ExternalTrigInjecConvEdge = ADC_EXTERNALTRIGINJECCONVEDGE_RISING     */

void adc_injected_init(ADC_HandleTypeDef *hadc)
{
    HAL_ADCEx_Calibration_Start(hadc, ADC_CALIB_OFFSET, ADC_SINGLE_ENDED);

    /* Start injected group — trigger comes from TIM1_CC4 automatically */
    HAL_ADCEx_InjectedStart_IT(hadc);
}

/* Called at TIM1_CC4 event rate (e.g. PWM switching frequency = 20 kHz) */
void HAL_ADCEx_InjectedConvCpltCallback(ADC_HandleTypeDef *hadc)
{
    int32_t raw = HAL_ADCEx_InjectedGetValue(hadc, ADC_INJECTED_RANK_1);

    /* Convert: Vref=3.3V, 12-bit, shunt=10mΩ, gain=20 */
    /* V_shunt = raw * 3300 / 4095 / 20 mV → I = V/R mA */
    int32_t current_ma = (int32_t)((raw * 3300L) / (4095L * 20L * 10));

    motor_current_update(current_ma);
}
```

---

## ADC — Multi-ADC Synchronized Sampling (ADC1 + ADC2 Dual Mode)

Simultaneous sampling on two channels — required for three-phase current sensing in motor control.

```c
/* CubeMX: Multi-mode = Regular simultaneous, DMA = ADC1 (master) */
/* ADC1 channel → Iu, ADC2 channel → Iv */

#define ADC_DUAL_BUF_LEN  32  /* pairs × oversampling */

ALIGN_32BYTES(static volatile uint32_t adc_dual_buf[ADC_DUAL_BUF_LEN])
    __attribute__((section(".dma_buf")));

/* Each uint32 contains [ADC2:16 | ADC1:16] */

void adc_dual_start(ADC_HandleTypeDef *hadc1)
{
    HAL_ADCEx_Calibration_Start(hadc1, ADC_CALIB_OFFSET, ADC_SINGLE_ENDED);
    /* ADC2 calibration done by HAL internally in dual mode */

    HAL_ADCEx_MultiModeStart_DMA(hadc1,
        (uint32_t *)adc_dual_buf, ADC_DUAL_BUF_LEN);
}

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
    SCB_InvalidateDCache_by_Addr((uint32_t *)adc_dual_buf,
                                  sizeof(adc_dual_buf));

    int32_t iu_sum = 0, iv_sum = 0;
    for (int i = 0; i < ADC_DUAL_BUF_LEN; i++) {
        iu_sum += (int16_t)(adc_dual_buf[i] & 0xFFFF);         /* ADC1 */
        iv_sum += (int16_t)((adc_dual_buf[i] >> 16) & 0xFFFF); /* ADC2 */
    }
    int32_t iu = iu_sum / ADC_DUAL_BUF_LEN;
    int32_t iv = iv_sum / ADC_DUAL_BUF_LEN;
    int32_t iw = -(iu + iv);   /* Kirchhoff: Iu + Iv + Iw = 0 */

    foc_update_currents(iu, iv, iw);
}
```

---

## Timer — Complementary PWM with Dead-Time (H-Bridge / Motor)

Dead-time prevents shoot-through when both high and low FETs briefly switch.

```c
/* CubeMX: TIM1, Channel1 + Channel1N, Complementary mode, Dead Time = 100 ns */
/* Dead time register: DTG field in BDTR — value depends on clock prescaler   */

/* Calculate DTG for desired dead time:
   dt_ns < 128 * T_DTS: DTG = dt_ns / T_DTS (where T_DTS = 1/TIM_CLK)
   At TIM_CLK = 168 MHz: T_DTS ≈ 5.95 ns → 100 ns → DTG = 17 */

void complementary_pwm_init(TIM_HandleTypeDef *htim)
{
    TIM_BreakDeadTimeConfigTypeDef bdt = {
        .OffStateRunMode    = TIM_OSSR_ENABLE,
        .OffStateIDLEMode   = TIM_OSSI_ENABLE,
        .LockLevel          = TIM_LOCKLEVEL_1,
        .DeadTime           = 17,         /* 17 × T_DTS ≈ 101 ns at 168 MHz */
        .BreakState         = TIM_BREAK_ENABLE,
        .BreakPolarity      = TIM_BREAKPOLARITY_HIGH,
        .AutomaticOutput    = TIM_AUTOMATICOUTPUT_ENABLE,
    };
    HAL_TIMEx_ConfigBreakDeadTime(htim, &bdt);

    HAL_TIM_PWM_Start(htim, TIM_CHANNEL_1);      /* CHn high side */
    HAL_TIMEx_PWMN_Start(htim, TIM_CHANNEL_1);   /* CHnN low side */
}

/* Center-aligned (up/down counting) for symmetric current sensing */
/* CubeMX: Counter Mode = Center Aligned mode 1 */
/* Period = ARR/2 for same switching frequency as edge-aligned     */

void pwm_set_duty_deadtime_safe(TIM_HandleTypeDef *htim,
                                 uint32_t channel, float duty_pct)
{
    uint32_t arr = __HAL_TIM_GET_AUTORELOAD(htim);
    uint32_t dtg = 17;   /* same as configured in BDTR */
    uint32_t max_ccr = arr - dtg - 1;  /* limit: CCR must leave room for DT */
    uint32_t ccr = (uint32_t)(duty_pct * max_ccr / 100.0f);
    __HAL_TIM_SET_COMPARE(htim, channel, ccr);
}
```

---

## HRTIM — High-Resolution Timer (G4, H7: sub-nanosecond PWM)

HRTIM has 217 ps resolution on STM32G4 (vs 5.9 ns for TIM). Used for digital power (LLC, buck/boost, PFC).

```c
/* CubeMX: HRTIM1, Master + Timer A, Continuous mode, PWM on TA1 */
/* Period = 0xFFFF × DLL-calibrated resolution (~217 ps on G4 @ 170 MHz) */

/* Equivalent frequency for HRTIM period register:
   f_HRTIM = 5.12 GHz (G4: 170 MHz × 32 = 5.44 GHz high-res clock)
   Period reg for 100 kHz: PERIOD = f_HRTIM / f_target - 1 = 54400 - 1 */

void hrtim_init_buck(HRTIM_HandleTypeDef *hhrtim)
{
    /* DLL calibration must complete before use */
    HAL_HRTIM_DLLCalibrationStart(hhrtim, HRTIM_CALIBRATIONRATE_14);
    HAL_HRTIM_PollForDLLCalibration(hhrtim, 100); /* wait up to 100ms */

    /* Configure Timer A for 100 kHz PWM */
    HRTIM_TimerCfgTypeDef timer_cfg = {
        .DMARequests   = HRTIM_TIM_DMA_NONE,
        .DMASrcAddress = 0,
        .DMADstAddress = 0,
        .DMASize       = 0,
        .HalfModeEnable = HRTIM_HALFMODE_DISABLED,
        .StartOnSync    = HRTIM_SYNCSTART_DISABLED,
        .ResetOnSync    = HRTIM_SYNCRESET_DISABLED,
        .DACSynchro     = HRTIM_DACSYNC_NONE,
        .PreloadEnable  = HRTIM_PRELOAD_ENABLED,   /* IMPORTANT: double buffer */
        .UpdateGating   = HRTIM_UPDATEGATING_INDEPENDENT,
        .BurstMode      = HRTIM_TIMERBURSTMODE_MAINTAINCLOCK,
        .RepetitionUpdate = HRTIM_UPDATEONREPETITION_ENABLED,
        .ResetUpdate    = HRTIM_TIMUPDATEONRESET_DISABLED,
        .InterruptRequests = HRTIM_TIM_IT_REP,     /* rep interrupt for control loop */
        .PushPull       = HRTIM_TIMPUSHPULLMODE_DISABLED,
        .FaultEnable    = HRTIM_TIMFAULTENABLE_FAULT1,
        .FaultLock      = HRTIM_TIMFAULTLOCK_READWRITE,
        .DeadTimeInsertion = HRTIM_TIMDEADTIMEINSERTION_ENABLED,
        .DelayedProtectionMode = HRTIM_TIMER_A_B_C_DELAYEDPROTECTION_DISABLED,
        .UpdateTrigger  = HRTIM_TIMUPDATETRIGGER_NONE,
        .ResetTrigger   = HRTIM_TIMRESETTRIGGER_NONE,
    };
    HAL_HRTIM_WaveformTimerConfig(hhrtim, HRTIM_TIMERINDEX_TIMER_A, &timer_cfg);

    /* Set period (100 kHz) and compare (50% duty) */
    HRTIM_TimeBaseCfgTypeDef tb = {
        .Period         = 54400,          /* 5.44 GHz / 100 kHz */
        .RepetitionCounter = 0,
        .PrescalerRatio = HRTIM_PRESCALERRATIO_MUL32,
        .Mode           = HRTIM_MODE_CONTINUOUS,
    };
    HAL_HRTIM_TimeBaseConfig(hhrtim, HRTIM_TIMERINDEX_TIMER_A, &tb);

    /* Start PWM output on TA1 */
    HAL_HRTIM_WaveformOutputStart(hhrtim,
        HRTIM_OUTPUT_TA1 | HRTIM_OUTPUT_TA2); /* TA2 = complementary */
    HAL_HRTIM_WaveformCountStart_IT(hhrtim, HRTIM_TIMERID_TIMER_A);
}

/* Update duty cycle at control loop rate (called from HRTIM Rep ISR) */
void HAL_HRTIM_RepetitionEventCallback(HRTIM_HandleTypeDef *hhrtim,
                                        uint32_t TimerIdx)
{
    if (TimerIdx == HRTIM_TIMERINDEX_TIMER_A) {
        float duty = pid_compute();   /* 0.0–1.0 */
        uint32_t period = 54400;
        uint32_t cmp1 = (uint32_t)(duty * period);

        HRTIM1->sTimerxRegs[HRTIM_TIMERINDEX_TIMER_A].CMP1xR = cmp1;
        /* Preload enabled: register update takes effect at next period */
    }
}
```

---

## Timer — Dead-Time Calculation Helper

```c
/* Calculate DTG register value for desired dead time in nanoseconds */
/* Returns DTG byte to write to TIMx_BDTR.DTG field                  */
uint8_t deadtime_calc_dtg(uint32_t tim_clk_hz, uint32_t deadtime_ns)
{
    /* T_DTS = 1 / tim_clk_hz in ns */
    uint32_t t_dts_ps = 1000000000UL / (tim_clk_hz / 1000); /* picoseconds */
    uint32_t dt_ps    = deadtime_ns * 1000;

    if (dt_ps <= 127 * t_dts_ps) {
        /* DTG[7:5] = 0: DT = DTG[6:0] * T_DTS */
        return (uint8_t)(dt_ps / t_dts_ps);
    } else if (dt_ps <= 254 * 2 * t_dts_ps) {
        /* DTG[7:5] = 10: DT = (64 + DTG[5:0]) * 2 * T_DTS */
        uint8_t n = (uint8_t)(dt_ps / (2 * t_dts_ps)) - 64;
        return (uint8_t)(0x80 | n);
    } else {
        /* DTG[7:5] = 110: DT = (32 + DTG[4:0]) * 8 * T_DTS */
        uint8_t n = (uint8_t)(dt_ps / (8 * t_dts_ps)) - 32;
        return (uint8_t)(0xC0 | n);
    }
}
```

---

## Rules

- ADC calibration MUST run after every power-on, not just once at factory
- Always check `HAL_ADC_PollForConversion` return — timeout = hardware fault
- M7 DMA: `SCB_InvalidateDCache_by_Addr` BEFORE reading `adc_dma_buf`
- PWM: set CCR before ARR or glitches occur at 100% duty
- Encoder: use signed int16_t cast for correct wrap-around arithmetic
- Input capture: handle timer overflow (period longer than ARR)
- Never use `HAL_Delay()` inside ISR or RTOS task — use `vTaskDelay` or `sw_timer_expired`
- Injected ADC: trigger from timer (not software) for deterministic current sampling; results in `ADC_INJECTED_RANK_x` registers
- Dual-mode ADC: only ADC1 (master) needs DMA; each sample is 32-bit containing both ADC1 and ADC2 values
- HRTIM: DLL calibration MUST complete before any output starts; `HAL_HRTIM_PollForDLLCalibration` blocks until done
- Complementary PWM: CCR must never exceed ARR minus dead-time ticks or shoot-through risk on trailing edge
- HRTIM preload: always enable for output buffering — otherwise writing CMP during period causes glitch
