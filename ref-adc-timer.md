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

## Rules

- ADC calibration MUST run after every power-on, not just once at factory
- Always check `HAL_ADC_PollForConversion` return — timeout = hardware fault
- M7 DMA: `SCB_InvalidateDCache_by_Addr` BEFORE reading `adc_dma_buf`
- PWM: set CCR before ARR or glitches occur at 100% duty
- Encoder: use signed int16_t cast for correct wrap-around arithmetic
- Input capture: handle timer overflow (period longer than ARR)
- Never use `HAL_Delay()` inside ISR or RTOS task — use `vTaskDelay` or `sw_timer_expired`
