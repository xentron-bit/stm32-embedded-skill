# RTOS Patterns Reference

## FreeRTOS — Periodic Task (precise timing)

```c
void vSensorTask(void *pvParameters) {
    TickType_t xLastWake = xTaskGetTickCount();
    const TickType_t xPeriod = pdMS_TO_TICKS(100);
    for (;;) {
        uint16_t v = ADC_Read();
        xQueueSend(xProcessQueue, &v, pdMS_TO_TICKS(10));
        vTaskDelayUntil(&xLastWake, xPeriod);  // drift-free
    }
}
```

## ISR → Task (semaphore from ISR)

```c
// ADC complete callback → wake processing task
void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc) {
    BaseType_t woken = pdFALSE;
    xSemaphoreGiveFromISR(xDataReadySemaphore, &woken);
    portYIELD_FROM_ISR(woken);
}

void vADCTask(void *pvParameters) {
    for (;;) {
        if (xSemaphoreTake(xDataReadySemaphore, portMAX_DELAY))
            ProcessADCValue(HAL_ADC_GetValue(&hadc1));
    }
}
```

## ISR → Task (task notification — preferred, lower overhead)

```c
void EXTI_IRQHandler(void) {
    BaseType_t woken = pdFALSE;
    xTaskNotifyFromISR(xWorkerHandle, 0x01, eSetBits, &woken);
    portYIELD_FROM_ISR(woken);
}

void vWorkerTask(void *pvParameters) {
    uint32_t notif;
    for (;;) {
        xTaskNotifyWait(0, 0xFFFFFFFF, &notif, portMAX_DELAY);
        HandleEvent(notif);
    }
}
```

## Mutex for shared peripheral

```c
bool I2C_SafeWrite(uint8_t addr, uint8_t *data, size_t len) {
    if (xSemaphoreTake(xI2CMutex, pdMS_TO_TICKS(100))) {
        bool r = HAL_I2C_Write(addr, data, len);
        xSemaphoreGive(xI2CMutex);
        return r;
    }
    return false;
}
```

## Event Groups (multi-subsystem sync)

```c
#define EV_SENSOR  (1<<0)
#define EV_COMM    (1<<1)
#define EV_CALIB   (1<<2)
#define EV_ALL     (EV_SENSOR | EV_COMM | EV_CALIB)

void vInitTask(void *arg) {
    InitSensor(); xEventGroupSetBits(xEvents, EV_SENSOR);
    InitComm();   xEventGroupSetBits(xEvents, EV_COMM);
    Calibrate();  xEventGroupSetBits(xEvents, EV_CALIB);
    vTaskDelete(NULL);
}

void vMainTask(void *arg) {
    xEventGroupWaitBits(xEvents, EV_ALL, pdFALSE, pdTRUE, portMAX_DELAY);
    for (;;) { RunMainLoop(); vTaskDelay(pdMS_TO_TICKS(10)); }
}
```

## Memory / Stack Monitoring

```c
// FreeRTOSConfig.h
#define configUSE_MALLOC_FAILED_HOOK    1
#define configCHECK_FOR_STACK_OVERFLOW  2

void vApplicationStackOverflowHook(TaskHandle_t t, char *name) {
    log_fatal(FAULT_STACK_OVF, name);
    NVIC_SystemReset();
}
void vApplicationMallocFailedHook(void) {
    log_fatal(FAULT_MALLOC_FAIL, 0);
    NVIC_SystemReset();
}
```

## Key Rules

- `vTaskDelayUntil` over `vTaskDelay` for periodic tasks (prevents drift)
- Task notifications > semaphores for ISR signaling (one slot, faster)
- Mutex > taskENTER_CRITICAL for shared peripherals (allows context switch)
- Size stacks: measure with `uxTaskGetStackHighWaterMark()`, target > 30% free
- Watchdog from multi-task checklist — never from daemon or single task
