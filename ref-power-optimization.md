# Power Optimization Reference

## Sleep Mode Selection

```c
void EnterLowPower(uint32_t sleep_ms) {
    if      (sleep_ms < 10)   __WFI();          // CPU halt, peripherals run
    else if (sleep_ms < 1000) EnterSleepMode(); // SysTick stopped
    else                      EnterStopMode(sleep_ms); // clocks stopped
}

void EnterStopMode(uint32_t sleep_ms) {
    if (sleep_ms > 0) RTC_SetWakeup(sleep_ms);
    DisableUnusedPeripherals();
    PWR->CR |= PWR_CR_LPDS;
    PWR->CR &= ~PWR_CR_PDDS;
    SCB->SCR |= SCB_SCR_SLEEPDEEP_Msk;
    __WFI();
    SystemClock_Config();  // PLL stopped in STOP → must reconfigure
    RestorePeripherals();
}
```

## Dynamic Clock Scaling

```c
// Reduce frequency when load is light
void AdaptiveClock(uint32_t load_percent) {
    if      (load_percent > 80) SetSystemClock(CLOCK_HIGH);   // 168MHz
    else if (load_percent > 40) SetSystemClock(CLOCK_MEDIUM); // 84MHz
    else                        SetSystemClock(CLOCK_LOW);    // 48MHz
}
```

## Peripheral Clock Gating

```c
void DisableUnusedPeripherals(void) {
    RCC->APB1ENR &= ~RCC_APB1ENR_I2C1EN;
    RCC->APB1ENR &= ~RCC_APB1ENR_USART2EN;
    RCC->AHB1ENR &= ~(RCC_AHB1ENR_DMA1EN | RCC_AHB1ENR_DMA2EN);
}
```

## Unused Pin Configuration (critical for stop mode leakage)

```c
void ConfigureUnusedPins(void) {
    GPIOD->MODER = 0xFFFFFFFF;  // All analog (lowest leakage)
    GPIOE->MODER = 0xFFFFFFFF;
}
```

## ADC with Power-Down

```c
uint16_t ADC_ReadLowPower(uint8_t ch) {
    ADC1->CR2 |= ADC_CR2_ADON;
    for (volatile int i = 0; i < 100; i++);  // startup delay
    ADC1->SQR3 = ch;
    ADC1->CR2 |= ADC_CR2_SWSTART;
    while (!(ADC1->SR & ADC_SR_EOC));
    uint16_t r = ADC1->DR;
    ADC1->CR2 &= ~ADC_CR2_ADON;
    return r;
}
```

## Battery-Adaptive Behavior

```c
void AdaptToBattery(BatteryState_t state) {
    switch (state) {
        case BATTERY_FULL:   SetClock(HIGH);   SetRate(100); break;
        case BATTERY_LOW:    SetClock(MEDIUM); SetRate(10);  break;
        case BATTERY_CRITICAL: SetClock(LOW);  SetRate(1);
            DisableNonEssentialFeatures(); break;
    }
}
```

## Rules

- Stop mode: always reconfigure PLL/clocks after wakeup (CSS doesn't restart PLL)
- Unused GPIOs: analog mode = lowest leakage; input floating can oscillate
- RTC wakeup (not SysTick) in stop mode — SysTick stops in STOP
- Batch I2C/SPI reads to minimize bus active time
- IWDG uses LSI — survives STOP mode (HSE stops)
