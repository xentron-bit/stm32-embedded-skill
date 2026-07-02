# RTOS Patterns Reference

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, errata workarounds, protocol-spec content** here is authoritative — that is why this file exists.
> - **Inline HAL/CMSIS/peripheral code snippets** are illustrative. The HAL drifts between versions and parts. For the canonical version of any HAL symbol at your HAL release: `gh search code <SymbolName> --owner=STMicroelectronics --extension=c` — see [ref-st-github-map.md](ref-st-github-map.md) §8 for the full lookup procedure.
> - **CRITICAL bugs identified in the 2026-05-16 audit have been corrected** in this file, but verify against your own HAL version before copy-pasting.
> - **For bootloader / IAP / OTA topics** the canonical checklist + ARM KA001193 + AN5188/2606/3155/3156 references are in [ref-bootloader.md](ref-bootloader.md).


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
__attribute__((used))   /* LTO guard — Keil AC6 can strip weak-callback overrides */
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
__attribute__((used))
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
__attribute__((used))
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
__attribute__((used))
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
/* NOTE: `osRtxThread_t` is the canonical RTX5 control-block type (from
 * rtx_os.h). The name `osStaticThreadDef_t` is NOT defined by CMSIS-RTOS2
 * and previous docs using it were wrong. */
static uint64_t ctrl_stack[256];        // 64-bit aligned, 2KB
static osRtxThread_t ctrl_cb;
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

---

## CMSIS-RTX5 (Keil RTX5) — Deep Reference

Source: arm-software.github.io/CMSIS-RTX/latest + CMSIS-RTX GitHub source (rtx_system.c, rtx_thread.c, rtx_os.h)

### Kernel Startup Sequence (STM32 / Keil MDK)

```c
#include <cmsis_os2.h>

int main(void) {
    HAL_Init();                               // HAL before RTOS
    SystemClock_Config();
    osKernelInitialize();                     // MUST call before any RTOS API
    osThreadNew(app_main, NULL, NULL);        // launcher thread
    osKernelStart();                          // never returns
    for (;;) {}
}

void app_main(void *arg) {
    // Create all application threads here, not in main()
    osThreadNew(ctrl_task,   NULL, &ctrl_attr);
    osThreadNew(comms_task,  NULL, &comms_attr);
    osDelay(osWaitForever);
}
```

**SysTick:** RTX5 uses Cortex-M SysTick by default. It is configured from `SystemCoreClock` (CMSIS variable set during startup). Default tick = 1 ms (`OS_TICK_FREQ 1000`). Alternative OS tick sources can be used by overriding the OS Tick API. SVC, PendSV, and SysTick handlers must run at the lowest priority group — RTX5 configures this internally; do not override these priorities in your code.

---

### osKernel API

```c
osStatus_t      osKernelInitialize(void);
osStatus_t      osKernelGetInfo(osVersion_t *version, char *id_buf, uint32_t id_size);
osKernelState_t osKernelGetState(void);
osStatus_t      osKernelStart(void);
int32_t         osKernelLock(void);           // returns previous lock state
int32_t         osKernelUnlock(void);
int32_t         osKernelRestoreLock(int32_t lock);
uint32_t        osKernelSuspend(void);        // returns max sleep ticks
void            osKernelResume(uint32_t sleep_ticks);
uint32_t        osKernelGetTickCount(void);
uint32_t        osKernelGetTickFreq(void);
uint32_t        osKernelGetSysTimerCount(void);
uint32_t        osKernelGetSysTimerFreq(void);
// Safety (source variant only):
osStatus_t      osKernelProtect(uint32_t safety_class);
osStatus_t      osKernelDestroyClass(uint32_t safety_class, uint32_t mode);
```

---

### osThread API

```c
osThreadId_t  osThreadNew(osThreadFunc_t func, void *argument, const osThreadAttr_t *attr);
const char   *osThreadGetName(osThreadId_t thread_id);
osThreadId_t  osThreadGetId(void);                          // ISR-callable
osThreadState_t osThreadGetState(osThreadId_t thread_id);
uint32_t      osThreadGetStackSize(osThreadId_t thread_id);
uint32_t      osThreadGetStackSpace(osThreadId_t thread_id); // requires OS_STACK_WATERMARK
osStatus_t    osThreadSetPriority(osThreadId_t thread_id, osPriority_t priority);
osPriority_t  osThreadGetPriority(osThreadId_t thread_id);
osStatus_t    osThreadYield(void);
osStatus_t    osThreadSuspend(osThreadId_t thread_id);
osStatus_t    osThreadResume(osThreadId_t thread_id);
osStatus_t    osThreadDetach(osThreadId_t thread_id);
osStatus_t    osThreadJoin(osThreadId_t thread_id);         // blocks until target exits
__NO_RETURN void osThreadExit(void);
osStatus_t    osThreadTerminate(osThreadId_t thread_id);
uint32_t      osThreadGetCount(void);
uint32_t      osThreadEnumerate(osThreadId_t *array, uint32_t items);
```

**osThreadAttr_t key fields:**

```c
const osThreadAttr_t ctrl_attr = {
    .name       = "ctrl",
    .attr_bits  = osThreadPrivileged,   // or osThreadUnprivileged
    .cb_mem     = &ctrl_cb,             // static control block
    .cb_size    = sizeof(ctrl_cb),
    .stack_mem  = ctrl_stack,           // static stack (8-byte aligned)
    .stack_size = sizeof(ctrl_stack),
    .priority   = osPriorityHigh,
    .tz_module  = 0,                    // TrustZone module ID (0 = none)
};
```

---

### Thread Flags vs Event Flags — Key Distinction

| Property | Thread Flags | Event Flags |
|----------|-------------|-------------|
| Object | Embedded in each thread (no separate handle) | Separate `osEventFlagsId_t` object |
| Target | One specific thread | Multiple threads can wait on same object |
| ISR set | `osThreadFlagsSet()` — ISR-callable | `osEventFlagsSet()` — ISR-callable |
| ISR wait | NOT callable from ISR | ISR-callable with `timeout=0` only |
| Max bits | 31 bits (bit 31 reserved for error) | 31 bits |
| Use case | Signaling a single known thread | Broadcast / multi-consumer synchronization |

**Thread Flags API** (operate on current running thread or a named thread):

```c
uint32_t osThreadFlagsSet(osThreadId_t thread_id, uint32_t flags);  // ISR-callable
uint32_t osThreadFlagsClear(uint32_t flags);    // current thread only, NOT ISR
uint32_t osThreadFlagsGet(void);                // current thread only, NOT ISR
uint32_t osThreadFlagsWait(uint32_t flags, uint32_t options, uint32_t timeout); // NOT ISR
// options: osFlagsWaitAny | osFlagsWaitAll | osFlagsNoClear
```

**Event Flags API** (shared object, multi-thread):

```c
osEventFlagsId_t osEventFlagsNew(const osEventFlagsAttr_t *attr);
uint32_t         osEventFlagsSet(osEventFlagsId_t ef_id, uint32_t flags);   // ISR-callable
uint32_t         osEventFlagsClear(osEventFlagsId_t ef_id, uint32_t flags); // ISR-callable
uint32_t         osEventFlagsGet(osEventFlagsId_t ef_id);                   // ISR-callable
uint32_t         osEventFlagsWait(osEventFlagsId_t ef_id, uint32_t flags,
                                  uint32_t options, uint32_t timeout);       // ISR: timeout=0 only
osStatus_t       osEventFlagsDelete(osEventFlagsId_t ef_id);
```

---

### osMutex API

```c
osMutexId_t  osMutexNew(const osMutexAttr_t *attr);  // NOT ISR
osStatus_t   osMutexAcquire(osMutexId_t mutex_id, uint32_t timeout); // NOT ISR
osStatus_t   osMutexRelease(osMutexId_t mutex_id);   // NOT ISR
osThreadId_t osMutexGetOwner(osMutexId_t mutex_id);  // ISR-callable
osStatus_t   osMutexDelete(osMutexId_t mutex_id);    // NOT ISR

// attr_bits flags:
// osMutexRecursive   (0x1) — same thread can re-acquire
// osMutexPrioInherit (0x2) — priority inheritance (use this for shared peripherals)
// osMutexRobust      (0x8) — auto-release if owner thread terminates
```

**CRITICAL:** No mutex functions callable from ISR. Use `osSemaphoreRelease` for ISR → task signaling instead.

---

### osSemaphore API

```c
osSemaphoreId_t osSemaphoreNew(uint32_t max_count, uint32_t initial_count,
                               const osSemaphoreAttr_t *attr); // NOT ISR
osStatus_t      osSemaphoreAcquire(osSemaphoreId_t sem_id, uint32_t timeout);
                // ISR-callable ONLY when timeout == 0
osStatus_t      osSemaphoreRelease(osSemaphoreId_t sem_id);   // ISR-callable
uint32_t        osSemaphoreGetCount(osSemaphoreId_t sem_id);  // ISR-callable
osStatus_t      osSemaphoreDelete(osSemaphoreId_t sem_id);    // NOT ISR
```

Binary semaphore: `osSemaphoreNew(1, 0, NULL)` — max=1, initial=0 (unavailable).

---

### osTimer API

```c
osTimerId_t osTimerNew(osTimerFunc_t func, osTimerType_t type,
                       void *argument, const osTimerAttr_t *attr); // NOT ISR
osStatus_t  osTimerStart(osTimerId_t timer_id, uint32_t ticks);    // NOT ISR
osStatus_t  osTimerStop(osTimerId_t timer_id);                     // NOT ISR
uint32_t    osTimerIsRunning(osTimerId_t timer_id);                // NOT ISR
osStatus_t  osTimerDelete(osTimerId_t timer_id);                   // NOT ISR
// osTimerOnce = one-shot; osTimerPeriodic = auto-repeat
// Timer callbacks run in a dedicated timer thread (OS_TIMER_THREAD_STACK_SIZE, default 512 B)
// OS_TIMER_CB_QUEUE (default 4) = max concurrent pending callbacks — overflow = silent drop
```

---

### osMemoryPool API

Fixed-size deterministic allocator — no fragmentation. Callable from ISR (alloc with timeout=0).

```c
osMemoryPoolId_t osMemoryPoolNew(uint32_t block_count, uint32_t block_size,
                                  const osMemoryPoolAttr_t *attr); // NOT ISR
void            *osMemoryPoolAlloc(osMemoryPoolId_t mp_id, uint32_t timeout);
                 // ISR-callable when timeout == 0; returns NULL if full
osStatus_t       osMemoryPoolFree(osMemoryPoolId_t mp_id, void *block); // ISR-callable
uint32_t         osMemoryPoolGetCapacity(osMemoryPoolId_t mp_id);       // ISR-callable
uint32_t         osMemoryPoolGetBlockSize(osMemoryPoolId_t mp_id);      // ISR-callable
uint32_t         osMemoryPoolGetCount(osMemoryPoolId_t mp_id);          // ISR-callable (in-use)
uint32_t         osMemoryPoolGetSpace(osMemoryPoolId_t mp_id);          // ISR-callable (free)
osStatus_t       osMemoryPoolDelete(osMemoryPoolId_t mp_id);            // NOT ISR
```

Typical usage — ISR-safe zero-copy CAN buffer:

```c
static osMemoryPoolId_t can_pool;

void init(void) {
    can_pool = osMemoryPoolNew(16, sizeof(CAN_Frame_t), NULL);
}

void FDCAN_IRQHandler(void) {
    CAN_Frame_t *f = osMemoryPoolAlloc(can_pool, 0);  // non-blocking
    if (f) {
        ReadCANFrame(f);
        osMessageQueuePut(can_queue, &f, 0, 0);
    }
    // if f == NULL: pool exhausted, frame dropped
}

void can_task(void *arg) {
    CAN_Frame_t *f;
    for (;;) {
        osMessageQueueGet(can_queue, &f, NULL, osWaitForever);
        ProcessFrame(f);
        osMemoryPoolFree(can_pool, f);
    }
}
```

---

### RTX_Config.h — Complete Knob Reference

All macros live in `Config/RTX_Config.h`. Compiler-line override possible: `-DOS_TICK_FREQ=500`.

#### System Configuration

| Macro | Default | Range | Effect on STM32 |
|-------|---------|-------|-----------------|
| `OS_DYNAMIC_MEM_SIZE` | 32768 | 0–1G (mult of 8) | Global heap for all RTOS objects. Set to 0 to disable dynamic alloc entirely (use static everywhere). |
| `OS_TICK_FREQ` | 1000 | — | SysTick reload = SystemCoreClock / OS_TICK_FREQ. Default 1 ms. |
| `OS_ROBIN_ENABLE` | 1 | 0–1 | Enable round-robin time-slicing among equal-priority threads. |
| `OS_ROBIN_TIMEOUT` | 5 | 1–1000 | Round-robin time slice in ticks (default 5 ms). |
| `OS_ISR_FIFO_QUEUE` | 16 | 4–256 (mult of 4) | ISR post-processing FIFO depth. See overflow behavior below. |
| `OS_OBJ_MEM_USAGE` | 0 | 0–1 | Collect per-object-type usage counters (debug only, adds overhead). |

#### Thread Configuration

| Macro | Default | Range | Notes |
|-------|---------|-------|-------|
| `OS_STACK_SIZE` | 3072 | ≥96 (mult of 8) | Default stack when `stack_size=0` in attr. Very generous — tune per project. |
| `OS_IDLE_THREAD_STACK_SIZE` | 512 | ≥72 | Idle thread stack. Must accommodate tickless idle hook code. |
| `OS_THREAD_NUM` | 1 | 1–1000 | Max user threads (when `OS_THREAD_OBJ_MEM=1`). |
| `OS_THREAD_OBJ_MEM` | 0 | 0–1 | 1 = fixed-size pool per thread (deterministic, no fragmentation). |
| `OS_STACK_CHECK` | — | 0–1 | Enable stack overflow detection (see below). Adds check per context switch. |
| `OS_STACK_WATERMARK` | — | 0–1 | Fill stack with 0xCCCCCCCC at creation; enables `osThreadGetStackSpace()`. |
| `OS_PRIVILEGE_MODE` | 1 | 0–1 | 1=threads run privileged (default), 0=unprivileged (use with MPU). |

#### Timer / Sync Object Configuration

| Macro | Default | Notes |
|-------|---------|-------|
| `OS_TIMER_THREAD_STACK_SIZE` | 512 | Stack for timer callback thread. Increase if callbacks do heavy work. |
| `OS_TIMER_THREAD_PRIO` | 40 | Priority of timer thread (osPriorityAboveNormal). |
| `OS_TIMER_CB_QUEUE` | 4 | Max pending timer callbacks. Silent drop on overflow. |
| `OS_MUTEX_OBJ_MEM` / `OS_MUTEX_NUM` | 0/— | Fixed-size mutex pool when enabled. |
| `OS_SEMAPHORE_OBJ_MEM` / `OS_SEMAPHORE_NUM` | 0/— | Fixed-size semaphore pool when enabled. |
| `OS_EVFLAGS_OBJ_MEM` / `OS_EVFLAGS_NUM` | 0/— | Fixed-size event flags pool when enabled. |
| `OS_MEMPOOL_OBJ_MEM` / `OS_MEMPOOL_DATA_SIZE` | 0/0 | Pool object + data storage area. |
| `OS_MSGQUEUE_OBJ_MEM` / `OS_MSGQUEUE_DATA_SIZE` | 0/0 | Message queue object + data area. |

---

### ISR FIFO Queue — Size & Overflow Behavior

RTX5 defers RTOS API calls made from ISRs through a circular FIFO (`os_isr_queue[]`). The kernel processes this queue in the PendSV handler after all ISRs complete.

**Structure** (from `rtx_os.h`):
```c
struct {
    uint16_t  max;   // = OS_ISR_FIFO_QUEUE
    uint16_t  cnt;   // current count
    uint16_t  in;    // write index
    uint16_t  out;   // read index
    void    **data;  // pointer array
} isr_queue;
```

**Overflow behavior** (from `rtx_system.c` — `osRtxPostProcess`):
```c
void osRtxPostProcess(os_object_t *object) {
    if (isr_queue_put(object) != 0U) {
        SetPendSV();        // trigger deferred processing
    } else {
        // QUEUE FULL: calls error notify with osRtxErrorISRQueueOverflow
        (void)osRtxKernelErrorNotify(osRtxErrorISRQueueOverflow, object);
    }
}
```

On overflow, `osRtxErrorNotify()` is called (user-overridable weak function). The RTOS call that triggered the overflow is **silently dropped** — no retry. Increase `OS_ISR_FIFO_QUEUE` if multiple ISRs fire signals/semaphores simultaneously. Rule of thumb: set to (number of ISRs that call RTOS APIs) × (max burst per tick) × 2.

---

### Stack Overflow Detection (OS_STACK_CHECK) & Watermark

**Canary / magic word** (from `rtx_os.h`):
```c
#define osRtxStackMagicWord   0xE25A2EA5U  // placed at stack base (lowest address)
#define osRtxStackFillPattern 0xCCCCCCCCU  // fill for watermark
```

**How overflow check works** (`#ifdef RTX_STACK_CHECK`):
- Checked at every context switch (SysTick/SVC/PendSV handler)
- Checks: `(thread->sp <= stack_mem_base) || (*stack_mem_base != osRtxStackMagicWord)`
- On detection: calls `osRtxKernelErrorNotify(osRtxErrorStackOverflow, thread)` — default handler triggers `osRtxErrorNotify()` which you can override to log + reset

**Watermark** (`#ifdef RTX_STACK_WATERMARK` — requires `OS_STACK_WATERMARK=1`):
- At thread creation: stack memory above the magic word is filled with `0xCCCCCCCC`
- `osThreadGetStackSpace(tid)` scans from stack base upward, counts contiguous `0xCCCCCCCC` words, returns free bytes
- Returns 0 if watermark not enabled — do not rely on this value in production polling without enabling the config

```c
// RTX5 stack monitoring equivalent of FreeRTOS HWM pattern
uint32_t free_bytes = osThreadGetStackSpace(tid);
if (free_bytes < 128) {
    // Less than 128 bytes remain — danger zone
    log_warning("Stack low: %u B free", free_bytes);
}
```

---

### Tickless Low-Power (osKernelSuspend / Resume)

RTX5 supports tick-less idle natively. The idle thread calls `osKernelSuspend()`, which:
1. Blocks thread switching (`KernelBlock()`)
2. Calculates the minimum delay across all pending thread timers, RTOS software timers, and watchdog list
3. Returns that value as `sleep_ticks` (0 if cannot sleep)

`osKernelResume(sleep_ticks)` is called after wakeup with the actual ticks elapsed, which updates all delay counters and fires expired timers.

**STM32 idle thread pattern** (place in `os_idle_thread` or override the weak idle hook):

```c
// RTX5 tickless idle — implement in application
// Override osRtxIdleThread or use the idle thread hook
void osRtxIdleThread(void *arg) {
    for (;;) {
        uint32_t sleep_ticks = osKernelSuspend();
        if (sleep_ticks > 0U) {
            // Configure RTC or LPTIM wakeup for sleep_ticks * (1000/OS_TICK_FREQ) ms
            // Enter STM32 low-power mode (e.g., HAL_PWR_EnterSTOPMode)
            uint32_t actual_ticks = GetElapsedTicksFromRTC();
            osKernelResume(actual_ticks);
        }
        // If sleep_ticks == 0: no sleep possible, spin
    }
}
```

**STM32 note:** SysTick is typically stopped in STOP mode. Use LPTIM1 or RTC wakeup timer as the wakeup source. Call `SystemClock_Config()` to restore PLL after wake if needed (clock lost in STOP2 on STM32H7/STM32L4).

---

### Round-Robin Configuration

```c
// RTX_Config.h
#define OS_ROBIN_ENABLE   1   // 1=enable, 0=disable (priority-only scheduling)
#define OS_ROBIN_TIMEOUT  5   // time slice in ticks (5ms at 1kHz tick)
```

Equal-priority threads share CPU in round-robin slices. Thread 3 has higher priority than threads 1 and 2 → threads 1 and 2 only run when 3 is blocked. Within their group, 1 and 2 alternate every `OS_ROBIN_TIMEOUT` ticks. Round-robin does NOT preempt higher-priority threads.

---

### Safety Features (Source Variant Only — RTX_SAFETY_FEATURES)

Requires using the RTX5 source files (not pre-built library). Enable with `#define OS_SAFETY_FEATURES 1`.

| Macro | Default | Effect |
|-------|---------|--------|
| `OS_SAFETY_FEATURES` | 1 | Master enable. Requires source variant. |
| `OS_SAFETY_CLASS` | 1 | Thread safety classes — isolate thread groups. |
| `OS_EXECUTION_ZONE` | 1 | MPU-enforced execution zones per thread. |
| `OS_THREAD_WATCHDOG` | 1 | Per-thread watchdog timers (software, not IWDG). |
| `OS_OBJ_PTR_CHECK` | 0 | Verify object pointer alignment before kernel call. |
| `OS_SVC_PTR_CHECK` | 0 | Verify SVC function pointer before execution. |

**Thread Watchdog — `osThreadFeedWatchdog`:**

Each thread can register a software watchdog timeout. The watchdog list is ticked every SysTick in `osRtxThreadWatchdogTick()`. If a thread's `wdog_tick` reaches zero before it calls `osThreadFeedWatchdog()`, `osWatchdogAlarm_Handler()` fires.

```c
// Register watchdog (call once at thread start)
osStatus_t osThreadFeedWatchdog(uint32_t ticks);  // reset watchdog countdown

// User implements (weak):
void osWatchdogAlarm_Handler(uint32_t safety_class) {
    // Called when any thread misses its feed deadline
    // Typically: log + trigger IWDG / system reset
    NVIC_SystemReset();
}
```

**Safety Class isolation:**
```c
// Assign thread to class 1 (via attr_bits in osThreadAttr_t)
// Suspend/resume entire class atomically:
osThreadSuspendClass(1U, 0U);   // suspend all class-1 threads
osThreadResumeClass(1U, 0U);    // resume all class-1 threads

// Protect kernel from lower-class interference:
osKernelProtect(1U);            // threads below class 1 cannot call kernel
```

---

### Memory Allocation — Three Strategies

```c
// Strategy 1: Global dynamic pool (default) — simple but may fragment
//   OS_DYNAMIC_MEM_SIZE = 32768 (bytes) in RTX_Config.h
//   osObjectNew() draws from this pool; returns NULL if exhausted

// Strategy 2: Object-specific fixed pools — deterministic, no fragmentation
//   OS_THREAD_OBJ_MEM=1, OS_THREAD_NUM=8
//   OS_MUTEX_OBJ_MEM=1,  OS_MUTEX_NUM=4
//   Each object type has its own fixed-size pool

// Strategy 3: Static — zero runtime allocation risk (required for safety)
static uint64_t thread_stack[512];     // 4KB, 8-byte aligned
static osRtxThread_t thread_cb;  // control block storage (canonical type from rtx_os.h)
const osThreadAttr_t attr = {
    .cb_mem     = &thread_cb,
    .cb_size    = sizeof(thread_cb),
    .stack_mem  = thread_stack,
    .stack_size = sizeof(thread_stack),
};
// Strategy 3 cannot exhaust the heap — safe for all OS_DYNAMIC_MEM_SIZE=0 builds
```

---

### RTX5 STM32-Specific Integration Notes

1. **SVC/PendSV/SysTick priority:** RTX5 sets these to the lowest interrupt priority group automatically. Do not assign custom priorities to SVC_Handler, PendSV_Handler, or SysTick_Handler in your NVIC config. Application ISRs should always run at numerically lower (higher-priority) NVIC values.

2. **Keil MDK scatter file:** RTX5 places `isr_queue`, thread stacks, and kernel data in `.bss.os` and `.data.os` sections. Verify your scatter file does not exclude these sections. The default MDK scatter template includes them.

3. **FPU context:** RTX5 detects FPU automatically via `SCB->CPACR`. On STM32F4/H7/L4 with FPU enabled, RTX5 saves/restores the full FP context (S0–S31 + FPSCR) — 136 bytes additional stack per thread. Budget accordingly.

4. **DTCM / ITCM stacks (STM32H7):** Thread stacks placed in DTCM RAM (0x20000000) are fine. Avoid placing stacks in ITCM (0x00000000) — it is not accessible by DMA and may cause issues with stack canary reads at lowest exception priority.

5. **RTX5 library vs source:** The pre-built library (`RTX_CM7.lib`) does not support `OS_SAFETY_FEATURES`. If you need `osThreadFeedWatchdog`, `osKernelProtect`, or MPU zones, you must add the RTX5 source files to your Keil project directly.

6. **`osRtxThread_t` size:** The static CB size must match what RTX uses internally. Use `sizeof(osRtxThread_t)` — do not hardcode a byte count; it varies by RTX5 version and safety feature configuration. (`osStaticThreadDef_t` is NOT a CMSIS-RTOS2 type; use `osRtxThread_t` from `rtx_os.h`.)

7. **Event Recorder integration:** Enable `OS_EVR_INIT 1` and `OS_EVR_START 1` in RTX_Config.h to get RTOS-aware real-time tracing in Keil's Component Viewer. This shows thread state transitions, ISR posts, mutex contention, and stack watermarks without halting the target.
