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

---

## Mutex — Shared Peripheral Protection

### Standard Mutex (priority inheritance)

FreeRTOS mutexes automatically implement priority inheritance: if a low-priority task holds the mutex and a high-priority task blocks on it, the holder is temporarily promoted to the waiter's priority until release.

```c
// FreeRTOSConfig.h
#define configUSE_MUTEXES  1

// Create (once, at startup or in a task)
static SemaphoreHandle_t xI2CMutex;
xI2CMutex = xSemaphoreCreateMutex();   // returns NULL on malloc failure

// Use in tasks
bool I2C_SafeWrite(uint8_t addr, uint8_t *data, size_t len)
{
    if (xSemaphoreTake(xI2CMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        bool ok = (HAL_I2C_Master_Transmit(&hi2c1, addr << 1,
                                            data, len, 10) == HAL_OK);
        xSemaphoreGive(xI2CMutex);
        return ok;
    }
    return false;  // timeout — caller decides what to do
}
```

**Rules:**
- Never call `xSemaphoreTake` on a mutex from an ISR — use binary semaphore for ISR signaling instead.
- Always pair Take with Give in the same task context.
- Timeout value: match your peripheral's worst-case transaction time; never `portMAX_DELAY` on shared bus.

### Recursive Mutex (same task re-entrant locking)

Use when a function that already holds the mutex calls another function that also tries to take it (e.g., a logging function called from inside a locked section).

```c
// FreeRTOSConfig.h
#define configUSE_RECURSIVE_MUTEXES  1

static SemaphoreHandle_t xSPIMutex;
xSPIMutex = xSemaphoreCreateRecursiveMutex();

// Take: same task can call this multiple times without deadlock
xSemaphoreTakeRecursive(xSPIMutex, pdMS_TO_TICKS(50));
  // ... nested code that also calls xSemaphoreTakeRecursive ...
xSemaphoreGiveRecursive(xSPIMutex);   // must Give once per Take
```

### Static Allocation (no heap — production code)

```c
static StaticSemaphore_t xMutexBuffer;
static SemaphoreHandle_t xMutex;

// In vApplicationDaemonTaskStartupHook or main before scheduler
xMutex = xSemaphoreCreateMutexStatic(&xMutexBuffer);
configASSERT(xMutex != NULL);
```

---

## Semaphore — Binary vs Counting

### Binary Semaphore (signaling, ISR → task)

A binary semaphore is a synchronization primitive with only two states (available/unavailable). Unlike a mutex, it has no ownership — any task or ISR can give it.

```c
// FreeRTOSConfig.h
#define configUSE_COUNTING_SEMAPHORES  1  // needed for counting, not binary

static SemaphoreHandle_t xDMASem;
xDMASem = xSemaphoreCreateBinary();   // initially NOT available

// ISR gives — wakes the waiting task
void HAL_SPI_TxRxCpltCallback(SPI_HandleTypeDef *hspi)
{
    BaseType_t woken = pdFALSE;
    xSemaphoreGiveFromISR(xDMASem, &woken);
    portYIELD_FROM_ISR(woken);
}

// Task blocks until DMA complete
void vSPITask(void *arg)
{
    for (;;) {
        HAL_SPI_TransmitReceive_DMA(&hspi1, tx_buf, rx_buf, LEN);
        xSemaphoreTake(xDMASem, portMAX_DELAY);   // wait for ISR
        // process rx_buf here
    }
}
```

### Counting Semaphore (event queue / resource pool)

Use when multiple events can fire before the consumer processes them, or to manage a pool of N identical resources.

```c
// Max count = queue depth, initial count = 0 (no events pending)
static SemaphoreHandle_t xCANRxSem;
xCANRxSem = xSemaphoreCreateCounting(8, 0);

// ISR: each frame gives once (count++)
void HAL_FDCAN_RxFifo0Callback(FDCAN_HandleTypeDef *hfdcan, uint32_t flags)
{
    BaseType_t woken = pdFALSE;
    xSemaphoreGiveFromISR(xCANRxSem, &woken);
    portYIELD_FROM_ISR(woken);
}

// Task: drain all pending frames
void vCANTask(void *arg)
{
    for (;;) {
        xSemaphoreTake(xCANRxSem, portMAX_DELAY);
        FDCAN_RxHeaderTypeDef hdr;
        uint8_t data[64];
        HAL_FDCAN_GetRxMessage(&hfdcan1, FDCAN_RX_FIFO0, &hdr, data);
        ProcessCANFrame(&hdr, data);
    }
}
```

### Binary Semaphore vs Mutex — Decision Table

| Feature | Binary Semaphore | Mutex |
|---------|-----------------|-------|
| Purpose | Signaling (ISR→task) | Mutual exclusion |
| Ownership | None | Task that took it |
| Priority inheritance | No | Yes |
| ISR Give | Yes (FromISR) | No |
| ISR Take | No | No |
| Initial state | Unavailable | Available |

---

## Round-Robin Scheduling (Time-Slicing)

Equal-priority tasks share CPU time in fixed-duration slices. No task starves another at the same priority level.

```c
// FreeRTOSConfig.h
#define configUSE_PREEMPTION         1   // preemptive scheduler (required)
#define configUSE_TIME_SLICING       1   // round-robin among equal-priority tasks
#define configTICK_RATE_HZ           1000
// One tick = 1ms. Each task at the same priority runs for 1 tick (1ms)
// before the scheduler switches to the next ready task at that priority.
```

```c
// Three equal-priority tasks — each runs for configTICK_RATE_HZ / 1000 = 1ms
// then yields automatically

void vLED1Task(void *arg) {
    for (;;) {
        HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_0);
        // No delay needed for round-robin demo; in real code use vTaskDelay
        // to yield voluntarily and allow other tasks to run
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

void vLED2Task(void *arg) {
    for (;;) {
        HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_1);
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

void vLED3Task(void *arg) {
    for (;;) {
        HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_2);
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

// All three tasks at the same priority
xTaskCreate(vLED1Task, "LED1", 128, NULL, tskIDLE_PRIORITY + 1, NULL);
xTaskCreate(vLED2Task, "LED2", 128, NULL, tskIDLE_PRIORITY + 1, NULL);
xTaskCreate(vLED3Task, "LED3", 128, NULL, tskIDLE_PRIORITY + 1, NULL);
```

**Note:** In practice, tasks that use `vTaskDelay` or block on semaphores voluntarily yield before their time slice expires — round-robin only matters for CPU-bound tasks that never block. For peripheral drivers, always use blocking primitives (semaphore, queue) rather than spinning.

### Cooperative yield (voluntary context switch)

```c
// Force a context switch without sleeping — useful in tight compute loops
taskYIELD();

// Equivalent: give up CPU to any equal or higher priority ready task
```

---

## Task Notification — Lighter Alternative to Semaphore

Each task has a built-in 32-bit notification value. Notifications are ~45% faster than semaphores and require no separate object.

```c
// Pattern 1: binary signal (replaces binary semaphore)
// ISR:
xTaskNotifyGiveFromISR(xTaskHandle, &woken);   // increment notification count
// Task:
ulTaskNotifyTake(pdTRUE, portMAX_DELAY);       // pdTRUE = clear on exit (binary)

// Pattern 2: bitmask event flags (replaces event group for single task)
// ISR:
xTaskNotifyFromISR(xTaskHandle, EVENT_RX | EVENT_ERR, eSetBits, &woken);
// Task:
uint32_t bits;
xTaskNotifyWait(0, 0xFFFFFFFF, &bits, portMAX_DELAY);
if (bits & EVENT_RX)  HandleRx();
if (bits & EVENT_ERR) HandleError();

// Pattern 3: pass a value (replaces single-item queue)
// Sender:
xTaskNotify(xTaskHandle, sensor_value, eSetValueWithOverwrite);
// Receiver:
uint32_t val;
xTaskNotifyWait(0, 0, &val, portMAX_DELAY);
```

**Limitation:** Only one notifier at a time per task. If multiple ISRs or tasks need to signal the same receiver, use a queue or event group instead.

---

## Event Groups (multi-task synchronization)

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
    // Wait until ALL init bits set (pdTRUE = clear on exit, pdTRUE = wait ALL)
    xEventGroupWaitBits(xEvents, EV_ALL, pdTRUE, pdTRUE, portMAX_DELAY);
    for (;;) { RunMainLoop(); vTaskDelay(pdMS_TO_TICKS(10)); }
}
```

Event groups can be set from ISR with `xEventGroupSetBitsFromISR` — requires the timer daemon task (`configUSE_TIMERS 1`).

---

## Queue — Passing Data Between Tasks / ISR

```c
// UART frame queue: ISR pushes raw bytes, task parses protocol
#define UART_QUEUE_LEN  16
typedef struct { uint8_t buf[128]; uint16_t len; } UartFrame_t;

static QueueHandle_t xUartQueue;
xUartQueue = xQueueCreate(UART_QUEUE_LEN, sizeof(UartFrame_t));

// In UART IDLE ISR callback
void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *h, uint16_t size)
{
    UartFrame_t frame;
    memcpy(frame.buf, dma_rx_buf, size);
    frame.len = size;
    BaseType_t woken = pdFALSE;
    xQueueSendFromISR(xUartQueue, &frame, &woken);
    portYIELD_FROM_ISR(woken);
    // Restart DMA circular — no action needed in circular mode
}

// Parser task
void vUartParserTask(void *arg)
{
    UartFrame_t frame;
    for (;;) {
        if (xQueueReceive(xUartQueue, &frame, portMAX_DELAY) == pdTRUE)
            ParseProtocol(frame.buf, frame.len);
    }
}
```

---

## Stack High-Water Mark Monitoring

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

// Periodic monitor task — run at lowest priority
void vStackMonitorTask(void *arg)
{
    extern TaskHandle_t xCtrlHandle, xCommHandle, xSensorHandle;
    TaskHandle_t tasks[]   = { xCtrlHandle, xCommHandle, xSensorHandle };
    const char  *names[]   = { "ctrl",      "comm",      "sensor" };
    const size_t N = sizeof(tasks) / sizeof(tasks[0]);

    for (;;) {
        for (size_t i = 0; i < N; i++) {
            UBaseType_t hwm = uxTaskGetStackHighWaterMark(tasks[i]);
            if (hwm < 32)  // < 32 words (128 bytes) remaining → warn
                log_warning(WARN_STACK_LOW, names[i], hwm);
        }
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}
```

Size stacks: measure HWM during stress test, then set final stack = peak usage × 1.5.

---

## Watchdog Pattern (multi-task checklist)

```c
// Each task must kick its own bit — watchdog only pets IWDG when ALL alive
static volatile uint32_t wdg_checklist;
#define WDG_TASK_CTRL   (1u << 0)
#define WDG_TASK_COMMS  (1u << 1)
#define WDG_TASK_SENSOR (1u << 2)
#define WDG_ALL_TASKS   (WDG_TASK_CTRL | WDG_TASK_COMMS | WDG_TASK_SENSOR)

void ctrl_task(void *arg) {
    for (;;) {
        wdg_checklist |= WDG_TASK_CTRL;
        // work ...
        osDelay(10);
    }
}

// Highest-priority watchdog monitor
void wdg_task(void *arg) {
    for (;;) {
        if ((wdg_checklist & WDG_ALL_TASKS) == WDG_ALL_TASKS) {
            wdg_checklist = 0;
            HAL_IWDG_Refresh(&hiwdg);
        }
        osDelay(IWDG_FEED_PERIOD_MS);
    }
}
```

---

## RTX5 / CMSIS-RTOS2 Equivalents

All patterns above have direct RTX5 equivalents:

| FreeRTOS | RTX5 / CMSIS-RTOS2 |
|----------|-------------------|
| `xSemaphoreCreateMutex()` | `osMutexNew(&attr)` with `osMutexPrioInherit` |
| `xSemaphoreCreateRecursiveMutex()` | `osMutexNew(&attr)` with `osMutexRecursive` |
| `xSemaphoreCreateBinary()` | `osSemaphoreNew(1, 0, NULL)` |
| `xSemaphoreCreateCounting(max, init)` | `osSemaphoreNew(max, init, NULL)` |
| `xQueueCreate(len, size)` | `osMessageQueueNew(len, size, NULL)` |
| `xEventGroupCreate()` | `osEventFlagsNew(NULL)` |
| `xTaskNotifyGiveFromISR` | `osEventFlagsSet(id, flag)` (ISR-safe) |
| `vTaskDelayUntil` | `osDelayUntil(tick)` |
| `uxTaskGetStackHighWaterMark` | `osThreadGetStackSpace(tid)` |

### RTX5 Mutex with Robust Flag

```c
// osMutexRobust: mutex is released if owner task terminates unexpectedly
const osMutexAttr_t i2c_mutex_attr = {
    .name = "i2c",
    .attr_bits = osMutexPrioInherit | osMutexRobust,
};
static osMutexId_t xI2CMutex;
xI2CMutex = osMutexNew(&i2c_mutex_attr);

bool I2C_SafeWrite(uint8_t addr, uint8_t *data, size_t len)
{
    if (osMutexAcquire(xI2CMutex, 100) == osOK) {
        bool ok = (HAL_I2C_Master_Transmit(&hi2c1, addr<<1, data, len, 10) == HAL_OK);
        osMutexRelease(xI2CMutex);
        return ok;
    }
    return false;
}
```

### RTX5 Static Thread (no heap)

```c
static uint64_t ctrl_stack[256];        // 64-bit aligned, 2KB
static osStaticThreadDef_t ctrl_cb;
const osThreadAttr_t ctrl_attr = {
    .name       = "ctrl",
    .stack_mem  = ctrl_stack,
    .stack_size = sizeof(ctrl_stack),
    .cb_mem     = &ctrl_cb,
    .cb_size    = sizeof(ctrl_cb),
    .priority   = osPriorityHigh,
};
osThreadId_t tid = osThreadNew(ctrl_task, NULL, &ctrl_attr);
```

---

## Key Rules

- `vTaskDelayUntil` over `vTaskDelay` for periodic tasks (prevents drift)
- Task notifications > semaphores for ISR signaling (one slot, ~45% faster)
- Mutex > `taskENTER_CRITICAL` for shared peripherals (allows context switch while waiting)
- Binary semaphore (not mutex) for ISR → task signaling (no ownership, ISR can give)
- `configUSE_TIME_SLICING 1` for round-robin; CPU-bound equal-priority tasks share time automatically
- Size stacks: measure `uxTaskGetStackHighWaterMark()` under stress, target > 30% free
- Watchdog from multi-task checklist — never from daemon or single task only
- Static allocation everywhere in hard-RT code — no heap fragmentation risk
