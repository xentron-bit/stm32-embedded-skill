---
name: stm32-embedded-dev
description: Use when developing, reviewing, or debugging firmware for STM32 microcontrollers (STM32F0/F1/F2/F3/F4/F7/G0/G4/H5/H7/H7RS/L0/L1/L4/L5/U0/U5/WB/WBA/N6) in bare-metal or RTOS environments (FreeRTOS, Keil RTX5/CMSIS-RTOS2, ThreadX, Zephyr). Trigger for peripheral drivers (I2C/SPI/UART/CAN/FDCAN/DMA/ADC/Timer/HRTIM/QSPI/OCTOSPI/FMC/SDMMC), RTOS task design, flash/RAM optimization, XIP/SWD/JTAG debug, compiler pitfall detection (volatile/LTO/aliasing/cache), or industrial firmware for automotive, factory automation, harsh environments. Also: STM32CubeMX/HAL/LL, Keil MDK, STM32CubeIDE, linker scripts (.ld + scatter), startup code, fault handlers, OTA/IAP/dual-bank bootloaders, secure boot/RDP/PCROP/OTFDEC, TrustZone-M (SAU/GTZC/MPCBB/CMSE), power modes/sleep/LPTIM/RTC wakeup, automotive diagnostics (UDS ISO 14229, J1939, OBD-II SAE J1979, WWH-OBD ISO 27145, DoIP ISO 13400, Modbus RTU), BLE (BlueNRG), USB device/host (CDC-ACM/HID/MSC + TinyUSB), Ethernet/LwIP, errata cross-check.
---

# STM32 Embedded Development Skill

## ⚡ Quick Start — Operating Modes (READ FIRST)

When this skill is invoked, **identify the mode first**, then follow the matching procedure.

| Mode | Trigger | Procedure | Output shape | Max length |
|------|---------|-----------|--------------|------------|
| **A. Quick Q&A** | Single-question (≤2 lines), no code attached | Answer directly. No graphify, no checklist. | Plain answer | ≤5 lines |
| **B. Review existing code** | User pastes/points to code | (1) Detect MCU + family (2) Errata cross-check (3) Graphify if ≥3 `.c` files (4) Use Finding Template | Findings list | ≤8 findings inline; use template for ≥1 file |
| **C. Implement new feature** | "Write a driver for...", "Add OTA..." | (1) Context interview if ambiguous (2) 5-phase summary (3) Code with errata notes inline | Code + 5-phase summary | ≤30 lines summary + code |
| **D. Debug** | "Why does X not work?", "HardFault at ..." | (1) Ask for fault dump / debug info (2) Decode CFSR/BFAR (3) Walk root cause | Q&A + decoded fields | Until root cause found |

### Mandatory Finding Template (Mode B + D)

Every issue you flag MUST use this exact shape — never prose paragraphs:

```
[SEVERITY] file.c:LINE — CATEGORY
  what:  one sentence describing the bug
  why:   one sentence explaining failure mode (what breaks at runtime / on which silicon)
  fix:   one sentence — concrete change, with RM/spec citation if applicable
  errata: [ES0480 §2.3.1] if applicable, else omit
```

Severity codes: `CRITICAL` (data loss / silent corruption / compile fail), `HIGH` (functional bug), `MEDIUM` (maintainability / latent), `LOW` (style).

### Decision Tree on Invocation

```
User request
   │
   ▼
1. Mode = A (quick Q)?         ──► Answer in ≤5 lines. STOP.
   │
   ▼
2. Mode = B (review)?
     │
     ▼
   2a. Detect MCU + silicon rev (ask if unknown)
   2b. Open ref-stm32-errata.md, list relevant errata IDs (≤3 lines)
   2c. Scope ≥3 .c files?  YES → bash: [ -f graphify-out/GRAPH_REPORT.md ] || Skill(graphify, <dir>)
                            NO  → skip graphify
   2d. Apply Code Review Checklist filtered by triage rules (see §Code Review)
   2e. Emit findings via template (above)
   │
   ▼
3. Mode = C (implement)?
     │
     ▼
   3a. If ambiguous: 1-2 Context Interview questions (see §Context Interview)
   3b. Otherwise: code first, 5-phase summary after
   │
   ▼
4. Mode = D (debug)?  ──► Walk fault dump / CFSR. Ask for missing data.
```

### Response language

Respond in the user's language. Reference files may mix Turkish/English — translate quoted terms inline if needed. Never code-switch within a single sentence.

---

## Overview

Systematic workflow for production-grade STM32 firmware: constraints → architecture → drivers → optimization → verification. Applies to bare-metal, FreeRTOS, and Keil RTX5/CMSIS-RTOS2 targets. Covers the full chain from HAL/LL driver authoring to XIP debug and compiler optimization traps.

---

## 5-Phase Development Workflow

```
[1. Analyze Constraints] → [2. Design Architecture] → [3. Implement Drivers]
         ↓                          ↓                          ↓
   MCU specs, flash/RAM      Task/ISR/peripheral          HAL + LL drivers
   limits, timing budget     memory layout                RTOS integration
         ↓                          ↓                          ↓
                    [4. Optimize Resources] → [5. Test & Verify]
                    Code size, RAM, power      Timing, edge cases,
                                               performance measurement
```

---

## Phase 1: Analyze Constraints

**Document before writing a single line:**

| Constraint | Questions to answer |
|---|---|
| MCU specs | Part number + silicon rev? Flash/RAM split? Core speed? FPU present? |
| Memory budget | Flash target (KiB left for future), RAM headroom, stack per task |
| Timing | Worst-case ISR latency allowed? Scheduler tick? DMA transfer deadlines? |
| Power budget | Average mA target? Sleep mode? Wakeup latency budget? |
| Communication | Bus speeds, frame rates, error budgets, master/slave roles |
| Industrial | Operating temp range, EMC class, ESD requirements, vibration |

**Memory map template (document in linker script comments):**
```
Flash:  0x08000000 - Bootloader (48KB) / App (remainder)
RAM:    0x20000000 - .data + .bss / Heap (if used) / Task stacks
DTCM:   0x20000000 (H7) - ISR handlers, critical data — CPU ONLY, DMA CANNOT ACCESS
AXI:    0x24000000 (H7) - DMA buffers (32B aligned), FatFS work area, large arrays
D2SRAM: 0x30000000 (H7) - DMA1/DMA2 accessible (128KB D2S1 + 32KB D2S2)
CCMRAM: 0x10000000 (F4/F7) - ISR code, fast data — NO DMA capable
```

---

## Phase 2: Design Architecture

### RTOS Task Design (FreeRTOS & Keil RTX5)

**Priority ladder (highest → lowest):**
```
Priority 7 (highest): Safety/watchdog monitor
Priority 6: Real-time control (motor, actuator)
Priority 5: Protocol RX (CAN/UART time-critical)
Priority 4: Protocol TX
Priority 3: Application logic
Priority 2: Communication (non-RT)
Priority 1: Background processing
Priority 0: Idle + watchdog pet
```

**Task sizing rules:**
- Stack = max call depth × frame size × 1.5 safety margin
- Measure stack HWM in debug; never skip in production-bound code
- One task per peripheral domain (not one mega-task)

**Keil RTX5 / CMSIS-RTOS2 specifics:**
```c
// Thread definition — prefer static allocation
static uint64_t task_stack[256];              // 64-bit aligned
static osStaticThreadDef_t task_cb;
const osThreadAttr_t task_attr = {
    .name       = "ctrl",
    .stack_mem  = task_stack,
    .stack_size = sizeof(task_stack),
    .cb_mem     = &task_cb,
    .cb_size    = sizeof(task_cb),
    .priority   = osPriorityHigh,
};
tid = osThreadNew(ctrl_task, NULL, &task_attr);

// Event flags instead of semaphores for ISR→task signaling
osEventFlagsSet(evt_id, FLAG_CAN_RX);  // safe from ISR
```

**FreeRTOS specifics:**
```c
// Static allocation — avoid heap in hard-RT code
static StaticTask_t task_tcb;
static StackType_t  task_stack[256];
xTaskCreateStatic(ctrl_task, "ctrl", 256, NULL,
                  PRIORITY_CTRL, task_stack, &task_tcb);

// ISR → task notification (faster than queue for single events)
BaseType_t woken = pdFALSE;
vTaskNotifyGiveFromISR(ctrl_task_handle, &woken);
portYIELD_FROM_ISR(woken);
```

### Interrupt Architecture

```
ISR responsibilities (< 2µs each):
  ✓ Set flag / give semaphore / send notification
  ✓ Read hardware status register (clear-on-read flags)
  ✓ Increment counter
  ✓ Arm DMA for next transfer

ISR forbidden:
  ✗ malloc / new
  ✗ printf / semihosting
  ✗ Blocking RTOS calls (use FromISR variants)
  ✗ Floating point (unless lazy stacking enabled AND registers saved)
  ✗ Long computation
```

**NVIC priority mapping (FreeRTOS + Cortex-M4/M7):**
```c
// configMAX_SYSCALL_INTERRUPT_PRIORITY = 5 (numerical value)
// ISRs using FromISR APIs: priority 5..15 (lower urgency = higher number)
// ISRs NOT using RTOS: priority 0..4 (true real-time, cannot call RTOS)
HAL_NVIC_SetPriority(CAN1_RX0_IRQn, 5, 0);   // uses FromISR → OK
HAL_NVIC_SetPriority(TIM1_UP_IRQn,  2, 0);   // pure HW ISR, no RTOS
```

---

## Phase 3: Implement Drivers

### Peripheral Driver Pattern (LL preferred over HAL for RT code)

```c
// GOOD: LL driver — zero overhead, direct register access
static inline HAL_StatusTypeDef spi_xfer_byte(uint8_t tx, uint8_t *rx)
{
    while (!LL_SPI_IsActiveFlag_TXE(SPI1));
    LL_SPI_TransmitData8(SPI1, tx);
    while (!LL_SPI_IsActiveFlag_RXNE(SPI1));
    *rx = LL_SPI_ReceiveData8(SPI1);
    return HAL_OK;
}

// BAD: HAL polling in tight loop — overhead + blocking
HAL_SPI_TransmitReceive(&hspi1, &tx, rx, 1, HAL_MAX_DELAY);
```

### DMA Driver Pattern (cache-safe, M7)

```c
// DMA buffer: 32-byte aligned, placed in AXI SRAM (NOT DTCM on H7)
// DTCM (0x20000000) is CPU-only — DMA1/DMA2 cannot access it!
__attribute__((section(".dma_buffer"), aligned(32)))
static uint8_t rx_buf[DMA_BUF_SIZE];

// Size formula: round up to 32-byte boundary — NEVER use (len + 32)
#define DMA_CACHE_SIZE(n)  ((int32_t)(((n) + 31U) & ~31U))

void dma_rx_complete_cb(DMA_HandleTypeDef *hdma)
{
    // Invalidate cache BEFORE reading buffer (M7 D-cache)
    // Wrong formula overshoots buffer → dirty adjacent data discarded → corruption at -O1+
    SCB_InvalidateDCache_by_Addr((uint32_t *)rx_buf, DMA_CACHE_SIZE(DMA_BUF_SIZE));
    process_rx_data(rx_buf, DMA_BUF_SIZE);
}

void dma_tx_start(const uint8_t *data, size_t len)
{
    // Clean cache BEFORE DMA reads buffer (M7 D-cache)
    SCB_CleanDCache_by_Addr((uint32_t *)data, DMA_CACHE_SIZE(len));
    HAL_UART_Transmit_DMA(&huart2, data, len);
}
```

### UART / USART

```c
// Ring buffer for UART RX — IDLE line interrupt + DMA
void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *huart, uint16_t size)
{
    // size = bytes received since last callback (IDLE or HT or TC)
    ring_buf_write(&uart_rx_ring, dma_rx_buf, size);
    osEventFlagsSet(uart_evt, UART_RX_FLAG);
    // Restart DMA in circular mode — no explicit restart needed
}
```

### I2C (with timeout protection)

```c
// Never use HAL_MAX_DELAY on I2C — bus can hang forever
#define I2C_TIMEOUT_MS  10

HAL_StatusTypeDef i2c_write_reg(uint8_t addr, uint8_t reg, uint8_t val)
{
    uint8_t buf[2] = { reg, val };
    HAL_StatusTypeDef r = HAL_I2C_Master_Transmit(&hi2c1, addr << 1,
                                                   buf, 2, I2C_TIMEOUT_MS);
    if (r != HAL_OK) {
        // Reset I2C on bus error — critical for industrial reliability
        __HAL_RCC_I2C1_FORCE_RESET();
        HAL_Delay(1);
        __HAL_RCC_I2C1_RELEASE_RESET();
        MX_I2C1_Init();
    }
    return r;
}
```

### CAN / FDCAN (industrial)

```c
// FDCAN filter: whitelist by range — reject all others
FDCAN_FilterTypeDef filter = {
    .IdType       = FDCAN_STANDARD_ID,
    .FilterIndex  = 0,
    .FilterType   = FDCAN_FILTER_RANGE,
    .FilterConfig = FDCAN_FILTER_TO_RXFIFO0,
    .FilterID1    = 0x100,   // accept 0x100..0x1FF only
    .FilterID2    = 0x1FF,
};
HAL_FDCAN_ConfigFilter(&hfdcan1, &filter);
HAL_FDCAN_ConfigGlobalFilter(&hfdcan1,
    FDCAN_REJECT, FDCAN_REJECT,          // non-matching frames rejected
    FDCAN_FILTER_REMOTE, FDCAN_FILTER_REMOTE);

// Bus-off recovery: MANUAL — never automatic in safety-critical apps
HAL_FDCAN_Start(&hfdcan1);
// In error ISR:
if (HAL_FDCAN_GetProtocolStatus(&hfdcan1, &status) == HAL_OK)
    if (status.BusOff) log_error(ERR_CAN_BUSOFF);  // app decides when to recover
```

### Watchdog Pattern (multi-task)

```c
// Checklist bitmap — every task must kick its own bit
static volatile uint32_t wdg_checklist;
#define WDG_TASK_CTRL   BIT(0)
#define WDG_TASK_COMMS  BIT(1)
#define WDG_TASK_SENSOR BIT(2)
#define WDG_ALL_TASKS   (WDG_TASK_CTRL | WDG_TASK_COMMS | WDG_TASK_SENSOR)

// Each task periodically sets its bit
void ctrl_task(void *arg) {
    for (;;) {
        wdg_checklist |= WDG_TASK_CTRL;
        // ... work ...
        osDelay(10);
    }
}

// Watchdog monitor task (highest priority)
void wdg_task(void *arg) {
    for (;;) {
        if ((wdg_checklist & WDG_ALL_TASKS) == WDG_ALL_TASKS) {
            wdg_checklist = 0;
            HAL_IWDG_Refresh(&hiwdg);   // pet only when ALL tasks alive
        }
        osDelay(IWDG_FEED_PERIOD_MS);
    }
}
```

---

## Phase 4: Optimize Resources

### Flash / Code Size

```
Compiler flags (GCC arm-none-eabi):
  -Os          → optimize for size (prefer over -O2 for flash-constrained)
  -flto        → link-time optimization (can save 10-20% flash)
  -ffunction-sections -fdata-sections → enable linker GC
  -Wl,--gc-sections                   → remove dead code/data
  -fno-exceptions -fno-rtti           → C++ projects: saves 10-30KB
  -fshort-enums                       → pack enums to smallest type

Check size:
  arm-none-eabi-size build/firmware.elf
  arm-none-eabi-nm --size-sort --print-size build/firmware.elf | tail -20
```

### RAM Optimization

```c
// Put large read-only tables in flash
const uint16_t sine_lut[1024] __attribute__((section(".rodata"))) = { ... };

// Zero-init large buffers in .bss (not .data) — only matters for link size
static uint8_t frame_buf[4096];   // .bss — no flash image cost

// Use bitfields for flag clusters
typedef struct {
    uint8_t sensor_ok  : 1;
    uint8_t can_ok     : 1;
    uint8_t ota_active : 1;
    uint8_t reserved   : 5;
} sys_flags_t;
```

### Compiler Optimization — Silent Bug Prevention

**Tanı:** Kod -O0'da çalışıyor, -O1/-O2/-Os'ta sessizce bozuluyor. Hata mesajı yok.

#### Cat 1: `volatile` Eksikliği (En Yaygın)

```c
/* YANLIŞ — -O2'de sonsuz döngü */
uint8_t dma_done = 0;
void DMA_IRQHandler(void) { dma_done = 1; }
void wait(void)           { while (!dma_done) {} }

/* DOĞRU */
volatile uint8_t dma_done = 0;
```

| Kural | Açıklama |
|-------|----------|
| ISR ile paylaşılan değişken | `volatile` zorunlu |
| Hardware register pointer | CMSIS `__IO` (= `volatile`) — zaten tanımlı |
| DMA buffer | `volatile` değil — cache/barrier gerekli (Cat 3) |
| Multi-byte struct | `volatile` yetmez — critical section şart |

```c
/* Multi-byte atomic okuma */
uint32_t primask = __get_PRIMASK();
__disable_irq();
MyStruct_t snap = shared_struct;  /* atomik blok */
__set_PRIMASK(primask);
```

#### Cat 2: Memory Barrier Eksikliği

```c
/* DMA TX — eksik barrier → eski veri gönderilir */
memcpy(tx_buf, data, len);
__DSB();                              /* CPU write buffer flush */
SCB_CleanDCache_by_Addr((uint32_t *)tx_buf, len);  /* M7 */
HAL_SPI_Transmit_DMA(&hspi, tx_buf, len);

/* Peripheral enable sonrası */
RCC->APB1ENR |= RCC_APB1ENR_TIM2EN;
__DSB();                              /* clock enable etkili olsun */
TIM2->CR1 |= TIM_CR1_CEN;

/* MPU/VTOR değişikliği sonrası — pipeline flush şart */
SCB->VTOR = new_vt;
__DSB();
__ISB();

/* Compiler reorder engelle */
#define COMPILER_BARRIER() __asm__ volatile("" ::: "memory")
prepare_data(buf);
COMPILER_BARRIER();     /* compiler buf'ı flag sonrasına taşımasın */
volatile bool ready = true;
```

| Barrier | Ne Yapar |
|---------|----------|
| `__DSB()` | Tüm bellek yazmaları tamamla (DMA, peripheral sonrası) |
| `__DMB()` | Sıralama garantisi (tamamlamayı beklemez) |
| `__ISB()` | Pipeline flush (MPU/VTOR/CPACR sonrası şart) |

#### Cat 3: DMA Cache Coherency (M7: F7, H7, H7RS)

```c
/* TX: CPU yazar → DMA okur → peripheral */
void dma_tx_start(uint8_t *data, uint32_t len) {
    SCB_CleanDCache_by_Addr((uint32_t *)data, len);  /* cache → SRAM */
    __DSB();
    HAL_SPI_Transmit_DMA(&hspi, data, len);
}

/* RX: peripheral → DMA yazar → CPU okur */
void HAL_SPI_RxCpltCallback(SPI_HandleTypeDef *hspi) {
    SCB_InvalidateDCache_by_Addr((uint32_t *)rx_buf, sizeof(rx_buf));
    process(rx_buf);  /* artık SRAM'dan güncel veri gelir */
}

/* Zorunlu: 32-byte hizalama ve 32'nin katı boyut */
ALIGN_32BYTES(uint8_t tx_buf[TX_SIZE]) __attribute__((section(".dma_buf")));
ALIGN_32BYTES(uint8_t rx_buf[RX_SIZE]) __attribute__((section(".dma_buf")));

/* Alternatif: MPU ile non-cacheable — Clean/Invalidate gerekmez */
/* MPU Region: TEX=001, S=0, C=0, B=0 */
```

#### Cat 4: LTO — ISR / Callback Silme

```c
/* ISR ve weak callback override'ları LTO tarafından silinebilir */
__attribute__((used, interrupt("IRQ")))
void USART1_IRQHandler(void) { /* ... */ }

__attribute__((used))
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) { /* ... */ }

/* CMakeLists.txt / Makefile */
/* -Wl,--undefined=USART1_IRQHandler */
/* -Wl,--undefined=HardFault_Handler  */

/* noinline: LTO inline etmesin — naked ISR'lar için zorunlu */
__attribute__((noinline)) void hard_fault_handler_c(uint32_t *sp) { }
```

#### Cat 5: Strict Aliasing İhlali

```c
/* YANLIŞ — -O2'de undefined behavior */
float f = 3.14f;
uint32_t bits = *(uint32_t *)(&f);

/* DOĞRU — memcpy (compiler optimize eder, UB yok) */
uint32_t bits;
memcpy(&bits, &f, 4);

/* DOĞRU — C99 union */
union { float f; uint32_t u; } cv;
cv.f = 3.14f;
uint32_t bits2 = cv.u;

/* Modbus / protocol byte extract — doğru yol */
uint32_t from_be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16)
         | ((uint32_t)p[2] <<  8) |  (uint32_t)p[3];
}
```

#### Cat 6: Struct Padding / Alignment

```c
/* YANLIŞ — padding nedeniyle sizeof != beklenen */
typedef struct { uint8_t cmd; uint32_t addr; uint16_t len; } Packet_t;
/* sizeof = 12, istenen = 7 */

/* DOĞRU */
typedef struct __attribute__((packed)) {
    uint8_t  cmd;   /* +0 */
    uint32_t addr;  /* +1 unaligned — erişimde memcpy */
    uint16_t len;   /* +5 */
} Packet_t;         /* sizeof = 7 */

_Static_assert(sizeof(Packet_t) == 7, "Packet layout mismatch");

uint32_t get_addr(const Packet_t *p) {
    uint32_t v; memcpy(&v, &p->addr, 4); return v;
}
```

#### Cat 7: Optimizasyon Seviyesi Farkı Tablosu

| Durum | -O0 | -O2/-Os | Çözüm |
|-------|-----|---------|-------|
| ISR shared, volatile yok | Çalışır (şans) | **Bozulur** | `volatile` ekle |
| DMA buf, volatile var | Yavaş | Yavaş | Volatile değil — barrier |
| HAL weak callback | Çalışır | **Silinebilir** | `__attribute__((used))` |
| Float↔uint aliasing | Çalışır | **Bozulur** | `memcpy` veya union |
| Empty delay loop | Bekler | **Silinir** | DWT cycle counter |
| ISR, LTO açık | Çalışır | **Kaybolur** | `--undefined=XYZ` |
| Struct padding | Çalışır | **Layout yanlış** | `__attribute__((packed))` |
| DMA cache boyut `n+32` | Çalışır | **Komşu veri bozulur** | `(n+31U)&~31U` kullan |
| ISR flag/veri sırası | Çalışır | **Task boş veri okur** | `COMPILER_BARRIER()` ekle |

#### Tanı Diagnostic Flags

```makefile
CFLAGS += -Wall -Wextra -Werror
CFLAGS += -Wcast-align       # unaligned cast uyarısı
CFLAGS += -Wstrict-aliasing=2 # aliasing ihlali
CFLAGS += -Wshadow           # değişken gölgeleme
CFLAGS += -fstack-usage      # .su dosyası — stack analizi
```

#### Hızlı Kontrol: "-O0 çalışıyor, -Os bozuluyor"

```
□ ISR ile paylaşılan değişken → volatile var mı? (ISR ring buffer index, flag, counter)
□ M7 DMA → SCB_CleanDCache / SCB_InvalidateDCache çağrılıyor mu?
□ DMA cache boyut formülü → (n+31U)&~31U mı, yoksa n+32 mi? ← FatFS killer bug
□ Peripheral enable sonrası → __DSB() var mı?
□ ISR/callback → __attribute__((used)) var mı? (Keil AC6 LTO tehlikesi)
□ Type-pun (float↔uint) → memcpy veya union kullanılıyor mu?
□ Struct protocol → __attribute__((packed)) + _Static_assert var mı?
□ ISR'da veri yaz → flag=1 → COMPILER_BARRIER() aralarında var mı?
□ DMA buffer DTCM'de mi? → H7'de DMA erişemez, AXI SRAM'a taşı
```

Detaylı örnekler: [ref-compiler-hardening.md](ref-compiler-hardening.md) | Keil özellikleri: [ref-keil-armclang.md](ref-keil-armclang.md)

### Power Optimization

```c
// Enter STOP2 (deepest with RAM retention, STM32L4/U5)
HAL_SuspendTick();           // stop SysTick before sleep
__HAL_PWR_CLEAR_FLAG(PWR_FLAG_WU);
HAL_PWREx_EnterSTOP2Mode(PWR_STOPENTRY_WFI);
// ... woken by RTC or EXTI ...
SystemClock_Config();        // restore clocks (PLL stopped in STOP)
HAL_ResumeTick();

// Peripheral clock gating — disable unused peripherals
__HAL_RCC_SPI2_CLK_DISABLE();
__HAL_RCC_ADC_CLK_DISABLE();

// Run mode: reduce core voltage + frequency when load is light
HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE2);
// Reconfigure PLL to lower target frequency
```

---

## Phase 5: Test and Verify

### XIP Debug Setup (SWD + Keil MDK / STM32CubeIDE)

```
XIP (Execute-in-Place) debug — code runs from flash, debugger attaches live:

Keil MDK:
  Options → Debug → ST-Link Debugger
  Settings → Download: "Erase Full Chip" for first flash
  Settings → Flash Download: verify after program
  Trace: SWO pin → ITM stimulus for printf without UART
  Watchpoints on peripheral registers (hardware breakpoints, limited to 4 on M4)

STM32CubeIDE:
  Debug Configuration → Debugger → ST-LINK (OpenOCD)
  .cfg: "reset_config srst_nogate"  ← prevents reset asserts during attach
  Live Expressions for real-time variable watch (no halt needed)
  SWV (Serial Wire Viewer) → ITM Data Console for trace

Common XIP issues:
  - Cache enabled but debug area not marked non-cacheable → stale values in watch
    Fix: mark debug watch variables as volatile, or disable D-cache during debug
  - JTAG/SWD pins remapped → cannot connect
    Fix: ensure SWD GPIO init runs before any GPIO reconfiguration
  - WFI loop prevents halt → add __NOP() in idle
  - Option byte RDP=1 → debug port locked → must mass-erase
```

### Timing Validation

```c
// Cycle-accurate measurement using DWT (no timer needed)
static inline void dwt_enable(void) {
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0;
    DWT->CTRL  |= DWT_CTRL_CYCCNTENA_Msk;
}
#define DWT_CYCLES_NOW()  (DWT->CYCCNT)
#define DWT_CYCLES_TO_US(c) ((c) / (SystemCoreClock / 1000000U))

// Usage: measure ISR execution time
uint32_t t0 = DWT_CYCLES_NOW();
// ... ISR body ...
uint32_t dt = DWT_CYCLES_NOW() - t0;
if (dt > ISR_MAX_CYCLES) log_timing_violation(dt);
```

### Stack High-Water Mark (FreeRTOS)

```c
// Call periodically from a low-priority monitor task
void stack_monitor_task(void *arg) {
    for (;;) {
        for (int i = 0; i < TASK_COUNT; i++) {
            UBaseType_t hwm = uxTaskGetStackHighWaterMark(task_handles[i]);
            if (hwm < STACK_DANGER_WORDS)
                log_warning(WARN_STACK_LOW, i, hwm);
        }
        osDelay(1000);
    }
}
```

### Communication Protocol Verification

```
I2C: Logic analyzer capture → verify ACK/NACK, clock stretching, repeated START
SPI: Verify CPOL/CPHA match between master and slave; check CS setup/hold time
CAN: Use Vector CANalyzer or open-source Cangaroo; verify bitrate, arbitration, bus load %
UART: Check framing errors (FE flag in SR), overrun errors (ORE), baud rate accuracy
DMA: Toggle GPIO at DMA complete ISR entry/exit → measure transfer duration on scope
```

---

## MUST DO — Embedded Iron Rules

- **`volatile` on all ISR-shared and hardware-mapped variables** — optimizer will silently break otherwise
- **Short ISRs** — set flag, give semaphore, return; task does the work
- **Watchdog on all release builds** — IWDG only, not WWDG alone; IWDG uses LSI (survives HSE failure)
- **Validate all external data** — CAN frames, UART packets, I2C sensor values before use
- **Document flash and RAM usage** in every PR (arm-none-eabi-size output)
- **DMA buffers 32-byte aligned on M7** — cache line boundary; always clean/invalidate
- **Timeout on every peripheral** — I2C, SPI, UART HAL calls: never `HAL_MAX_DELAY`
- **Critical sections minimal** — `__disable_irq()` / `__enable_irq()` spans must be < 1µs
- **Test all error paths** — HAL_ERROR, bus-off, sensor saturation, timeout
- **Use LL drivers for time-critical code** — HAL has per-call overhead (60-200 cycles on M4)
- **Enable MPU for stack overflow detection** (guard region below each task stack)

---

## MUST NOT DO

- **Blocking operations in ISRs** — no `HAL_Delay`, no mutex wait, no queue receive
- **Dynamic allocation in hard-RT tasks** — `malloc`/`new` in control loops
- **Floating point in ISRs without lazy stacking enabled** — silent register corruption
- **Skip critical section protection on shared state** — even single 32-bit read-modify-write on M0 is non-atomic
- **Kick watchdog from ISR or single task only** — defeats multi-task health checking
- **Use `HAL_Delay` in RTOS context** — busy-waits, blocks scheduler; use `osDelay` / `vTaskDelay`
- **Ignore hardware errata** — always check silicon errata PDF for your exact MCU revision
- **`printf` to UART in ISR or real-time task** — UART TX blocks for milliseconds
- **Access shared peripheral registers without mutex** — DMA controller, I2C CR1, etc.
- **Ship with SWD/JTAG pins accessible and RDP=0** — reflash attack vector
- **Use soft timers for hard deadlines** — FreeRTOS software timers run in daemon task, jitter up to one tick

---

## Industrial Best Practices Checklist

Before declaring firmware "done for production":

**Stability & Safety**
- [ ] Watchdog enabled and multi-task checklist implemented
- [ ] All ISRs under 2µs worst-case (measured with DWT)
- [ ] Stack HWM < 70% for all tasks (measured, not estimated)
- [ ] Startup self-test: RAM, Flash CRC, peripheral ping
- [ ] Brown-out detection configured (BOR level matches VDD min)
- [ ] HardFault / MemManage handlers log stack frame before halting (not silent `while(1)`)

**Memory & DMA (M7 specific)**
- [ ] DMA buffers in AXI SRAM (0x24000000) — NOT DTCM on H7
- [ ] DMA cache size formula: `(n+31U)&~31U` — NOT `n+32`
- [ ] All DMA buffers 32-byte aligned; section in scatter/linker script
- [ ] `SCB_CleanDCache_by_Addr` before TX DMA; `SCB_InvalidateDCache_by_Addr` after RX DMA
- [ ] `volatile` audit: every `static` modified in ISR reviewed
- [ ] ISR-to-task flag pattern: `COMPILER_BARRIER()` between data write and flag=1

**Keil AC6 Specific**
- [ ] All HAL callback overrides have `__attribute__((used))` — LTO protection
- [ ] FDCAN Init.Mode checked: `BUS_MONITORING` vs `NORMAL` — OBD/UDS needs NORMAL
- [ ] Every ISR handler: peripheral name in function matches peripheral in LL/HAL calls
- [ ] RTX5 mutexes: `osMutexPrioInherit` attribute set
- [ ] RTX5 threads: static stack (`stack_mem` not NULL)
- [ ] `osMutexAcquire` timeout value intentional: `0U` = non-blocking, not "forever"
- [ ] NVIC priority grouping: `NVIC_PRIORITYGROUP_4` set before RTOS start

**Protocol & Communication**
- [ ] CAN message whitelist / filter enforced
- [ ] All peripheral timeouts set (never `HAL_MAX_DELAY` on I2C/SPI/UART)
- [ ] FDCAN bus-off recovery: manual decision, not automatic
- [ ] USART overrun errors (ORE) handled — uncleared ORE causes interrupt storm

**Build & Release**
- [ ] `arm-none-eabi-size` output documented; flash < 80% for OTA headroom
- [ ] Compiler flags: `-Wall -Wextra -Werror -Wcast-align` enabled in CI
- [ ] RDP level set appropriately for production
- [ ] Bootloader / OTA: dual-bank or A/B with rollback

**Debug & Verification**
- [ ] XIP debug verified: attach/detach cycle does not corrupt state
- [ ] EMC: all GPIOs with appropriate slew rate and pull configuration
- [ ] Power: measured average current in all operating modes
- [ ] All peripheral error paths tested (timeout, bus error, sensor disconnect)

---

## Quick Reference: HAL vs LL vs Register

| Use case | Recommended API | Reason |
|---|---|---|
| Init / one-time config | HAL | Readability, CubeMX generated |
| Time-critical data path | LL | No overhead |
| ISR data read/write | LL or direct register | Speed |
| DMA start/stop | HAL (callbacks) or LL | HAL handles error states |
| Clock / power config | HAL + CMSIS | Complex sequencing, errata |
| Custom peripheral not in HAL | Direct register | Only option |

---

## Pre-Review: Code Map + Context Interview

**Do this before opening the Code Review Checklist.** Skipping this step produces false positives — flagging intentional embedded optimizations as bugs.

### Step 1 — Generate the Code Map (when scope ≥3 .c files)

**Skip rule:** For single-file snippets or inline code (<200 LOC), DO NOT run graphify — go straight to review.

**Trigger conditions:** ≥3 `.c` files in scope, OR user asks for call-graph / dependency analysis.

**Procedure:**

```
1. Check: [ -f graphify-out/GRAPH_REPORT.md ]
   - EXISTS → Read it, jump to Step 2
   - MISSING → run graphify:
       Bash: graphify . --no-viz   (run from project root)
     If `graphify` command is missing, install:
       macOS  : brew install python@3.12 && /opt/homebrew/opt/python@3.12/bin/pip3 install graphifyy
       Linux  : pip3 install --user graphifyy
       Windows: py -m pip install graphifyy
     If install also fails, SKIP graphify and tell the user — do not block review.

2. After graphify completes:
   - Read graphify-out/GRAPH_REPORT.md — God Nodes + Surprising Connections
   - Targeted queries: graphify query "<question>" --graph graphify-out/graph.json
   - Path: graphify path "fnA" "fnB" --graph graphify-out/graph.json
```

**Vendor filter (CRITICAL for signal-to-noise):** Before reading the graph,
mentally filter out HAL_*, LL_*, __HAL_*, CMSIS *, FreeRTOS internal, RTX_*
nodes. Focus on application symbols. The graph is noisy by default; the
useful signal is in the application's own call chains.

**Çıktılar (`graphify-out/` klasörü):**
- `GRAPH_REPORT.md` — God nodes, call chains, paylaşılan değişkenler
- `graph.html` — İnteraktif görselleştirme
- `graph.json` — Sorgulanabilir JSON

> Graph, çağrı derinliği ve include zincirlerini ortaya çıkarır. Birçok "eksik null check" aslında çağrı grafı göz önüne alındığında hiç çalışmayan ölü kod yollarıdır — önce graph'ı oku.

### Obsidian Integration (İsteğe Bağlı — Büyük Projeler İçin)

Graphify, Obsidian vault'una doğrudan export yapabilir. Her fonksiyon/dosya ayrı bir `.md` notu olur, wiki-link ve frontmatter ile bağlanır.

**Kurulum:**
```bash
# Obsidian'ı indir: https://obsidian.md (macOS/Windows/Linux — ücretsiz)
# Yeni vault oluştur veya mevcut vault dizinini kullan
```

**Export Komutu:**
```bash
# STM32 projesini Obsidian vault'una export et
graphify export obsidian ./Core \
  --obsidian-dir ~/vaults/stm32-proje \
  --watch

# --watch: C/header değişikliklerinde AST otomatik güncellenir
# LLM maliyeti yok — sadece parser yeniden çalışır
# Not: Obsidian vault'u manuel yenile (Ctrl+R) her export sonrası
```

**Önerilen Obsidian Eklentileri:**
| Eklenti | Amaç | Öncelik |
|---------|------|---------|
| **Graph Analysis** | Call graph → Obsidian graph view entegrasyonu | Zorunlu |
| **Dataview** | `dataview` sorguları ile fonksiyon/dosya filtreleme | Zorunlu |
| **Kanban** | Bug/review kartları oluştur, graph node'larına bağla | İsteğe bağlı |
| **Breadcrumbs** | Hiyerarşik navigasyon (driver → HAL → peripheral) | İsteğe bağlı |

**STM32 Projesi İçin Best Practice Komutu:**
```bash
# Derin analiz modu — HAL + LL + uygulama katmanını birlikte haritalandırır
/graphify ./Core --obsidian --watch --mode deep
```

**Dataview Sorgu Örneği (Obsidian notu içinde):**
```dataview
TABLE file.size, file.mtime FROM "stm32-proje/Core/Src"
WHERE contains(tags, "dma") OR contains(tags, "isr")
SORT file.size DESC
```

**Ne Zaman Kullan:**
- 10+ kaynak dosyası olan projeler
- Birden fazla geliştirici (graph → ortak referans noktası)
- Uzun vadeli bakım (hangi fonksiyon nerede kullanılıyor?)
- ISR → Task → Protocol zincirini görselleştirmek istiyorsan

**Obsidian kurulu değilse:** `graphify-out/graph.html` dosyasını tarayıcıda aç — interaktif görselleştirme Obsidian gerekmeden çalışır.

### Step 2 — Context Interview (ask before flagging anything)

Embedded code that looks wrong is often intentionally simplified because the developer owns both sides of the system. Ask these questions **before** raising any finding:

#### Communication / Protocol
- **"Bu iki uç arasındaki protokolü sen mi yazıyorsun?"** (Do you own both sides of this protocol?)  
  → If yes: fixed packet sizes, known baud rate, zero invalid frames → buffer overflow guards may be intentionally omitted.
- **"Alıcı taraf paketin max boyutunu biliyor mu?"** (Does the receiver know the max packet size?)  
  → If yes: `rx_len < BUF_SIZE` checks may be intentional omissions, not bugs.
- **"Paket formatı değişebilir mi ileride?"** (Can the packet format change later?)  
  → If no: no need for length-field validation — flag as NOTE only.

#### Buffer Sizing
- **"Bu buffer boyutu nasıl hesaplandı?"** (How was this buffer size calculated?)  
  → Owner-controlled protocols: buffer = max packet × 1 (no margin needed if protocol is fixed)  
  → Third-party protocol (Modbus, CANopen, USB): buffer must handle all legal frames + error recovery.

#### Timing / Polling
- **"Bu polling döngüsü başka bir iş parçacığıyla yarışıyor mu?"** (Does this polling loop race with another thread?)  
  → Single-threaded bare-metal: `volatile` flags without critical section may be fine.  
  → RTOS: same pattern is a bug.

#### Error Handling
- **"Bu HAL_ERROR durumu gerçekte hiç olabilir mi bu donanımda?"** (Can this HAL_ERROR actually occur on this hardware?)  
  → If the bus is on-board and cannot be disconnected: ignoring HAL_ERROR may be intentional cost reduction.  
  → If the bus reaches a connector exposed to the field: ignoring is always a bug.

#### Watchdog / Resets
- **"Bu sistem field'da kesintisiz çalışacak mı?"** (Will this system run unattended in the field?)  
  → Lab/bench prototype: watchdog omission is acceptable.  
  → Production/field: watchdog is mandatory regardless of developer confidence.

### Step 3 — Classify Findings

After the context interview, classify every finding into one of three buckets:

| Bucket | Meaning | Action |
|--------|---------|--------|
| **Bug** | Would fail in the stated operating conditions | Raise as CRITICAL/HIGH |
| **Intentional simplification** | Developer owns both ends, conditions are controlled | Document assumption, raise as NOTE only |
| **Latent risk** | Correct now, breaks if system evolves | Raise as MEDIUM with specific trigger condition |

**Never flag an intentional simplification as a bug.** Ask first.

### Intentional Simplification Examples

```c
// LOOKS LIKE: missing overflow check
void uart_rx_callback(uint8_t byte) {
    rx_buf[rx_idx++] = byte;   // no bounds check
}
// IS ACTUALLY FINE IF: developer controls transmitter, packet is fixed 8 bytes,
// buffer is 64 bytes, and rx_idx is reset after each packet.
// RAISE AS: NOTE — "Add assert(rx_idx < sizeof(rx_buf)) for defensive coding"

// LOOKS LIKE: HAL_ERROR ignored
HAL_SPI_Transmit(&hspi1, buf, len, 1);
// IS ACTUALLY FINE IF: SPI slave is on the same PCB (no connector, no unplug).
// RAISE AS: MEDIUM — "Add error counter for production telemetry"

// LOOKS LIKE: missing CRC validation
void process_frame(uint8_t *frame, uint16_t len) {
    uint8_t cmd = frame[0];
    // no CRC check
}
// IS ACTUALLY FINE IF: UART hardware CRC is enabled in peripheral config,
// or the two MCUs share the same ground plane and EMI is controlled.
// RAISE AS: MEDIUM — "Document that hardware CRC is relied upon"
```

---

## Code Review Checklist (MANDATORY after every implementation)

Apply to every `.c`/`.h` file written or modified. Complete the Pre-Review context interview first. Check each category — do not skip any.

### 1. Volatile / Memory Visibility

- [ ] Every `static` variable modified inside an ISR is declared `volatile`
- [ ] Every `static` variable shared between tasks is protected by mutex or critical section (not just `volatile` — `volatile` alone is not thread-safe on M4/M7)
- [ ] Hardware register structs use `__IO` (CMSIS) or `volatile` — never plain pointer cast
- [ ] Compiler barriers `__DSB()` / `__DMB()` present after register write sequences that must not be reordered

### 2. ISR Discipline

- [ ] No `HAL_Delay` / `osDelay` / blocking wait in any ISR
- [ ] No `malloc` / `pvPortMalloc` in any ISR
- [ ] No `printf` / `sprintf` in any ISR
- [ ] No floating-point operations in ISRs (unless lazy stacking explicitly enabled and registers saved)
- [ ] RTOS calls use ISR-safe variants: FreeRTOS `xXxxFromISR()`, RTX5 `osXxx()` (RTX auto-detects ISR)
- [ ] ISR execution time measured with DWT and within budget (< 2µs typical)
- [ ] All interrupt flags cleared inside ISR (no accidental tail-chain)

### 3. DMA / Cache Coherency (M7: F7, H7, H7RS)

- [ ] Every DMA RX buffer has `SCB_InvalidateDCache_by_Addr()` before first read
- [ ] Every DMA TX buffer has `SCB_CleanDCache_by_Addr()` before DMA starts
- [ ] DMA buffers are 32-byte aligned (`ALIGN_32BYTES()` or `__attribute__((aligned(32)))`)
- [ ] DMA buffers NOT crossing a cache line boundary for size < 32 bytes
- [ ] If non-cacheable region used: verify linker section `.noinit` or `.dma_buf` maps to AXI SRAM or DTCMRAM correctly

### 4. RTOS Usage

- [ ] All tasks use static allocation (no `pvPortMalloc` for TCB/stack)
- [ ] Task stack sizes estimated from worst-case call depth, not guessed
- [ ] Stack HWM measurement call present (in debug/monitor task)
- [ ] Priority assignments documented and justified; no priority inversion risk
- [ ] RTX5: `OS_DYNAMIC_MEM_SIZE 0` for industrial (no heap)
- [ ] RTX5: `OS_ROBIN_ENABLE 0` for strict-priority systems
- [ ] RTX5 safety features: `OS_THREAD_WATCHDOG 1` + `osThreadFeedWatchdog()` in every RT task
- [ ] FreeRTOS: `configUSE_MALLOC_FAILED_HOOK 1` + hook implemented

### 5. Peripheral / HAL Errors

- [ ] Every HAL call return value checked — no silently ignored `HAL_ERROR`
- [ ] I2C / SPI / UART calls use bounded timeout (not `HAL_MAX_DELAY`)
- [ ] I2C recovery sequence on `HAL_ERROR` (force-reset + re-init)
- [ ] FDCAN: reject-on-mismatch global filter configured; whitelist enforced
- [ ] All peripheral error callbacks implemented (not left as weak empty stubs)

### 6. Watchdog

- [ ] IWDG enabled in release build (`MX_IWDG_Init()` present in `main()`)
- [ ] Watchdog fed from multi-task checklist (not from single task or ISR)
- [ ] IWDG timeout > worst-case task period × safety margin (≥ 2×)
- [ ] Debug freeze bit (`DBGMCU_APB1FZR_DBG_IWDG_STOP`) documented if used in debug

### 7. Memory and Resources

- [ ] No `malloc` / `new` in hard-RT tasks (control loop, ISR)
- [ ] `arm-none-eabi-size` output: flash < 80% (OTA headroom), RAM < 85%
- [ ] Stack overflow detection: MPU guard region configured below each task stack
- [ ] No global arrays on stack (large buffers as `static`)

### 8. Compiler / Linker / Optimization

- [ ] `-Wall -Wextra -Werror -Wcast-align -Wstrict-aliasing=2` enabled
- [ ] No implicit function declarations (all headers included)
- [ ] ISR handlers not removed by LTO: `__attribute__((used))` or `-Wl,--undefined=XYZ`
- [ ] Linker map inspected for unexpected symbol sizes
- [ ] Release build: `NDEBUG` defined; `assert()` compile away or replaced with telemetry
- [ ] **[volatile]** Every ISR-shared variable is `volatile`; hardware registers use CMSIS `__IO`
- [ ] **[barrier]** `__DSB()` present after peripheral enable and before DMA start
- [ ] **[barrier]** `__ISB()` present after MPU/VTOR modification
- [ ] **[DMA M7]** `SCB_CleanDCache_by_Addr` before TX DMA; `SCB_InvalidateDCache_by_Addr` in RX callback
- [ ] **[aliasing]** No `*(T*)(&other_type)` — use `memcpy` or `union`
- [ ] **[struct]** Protocol structs are `__attribute__((packed))` + `_Static_assert` on size
- [ ] **[LTO]** `HAL_XxxCallback` overrides marked `__attribute__((used))`
- [ ] **[-O0 vs -Os test]** Critical ISR and DMA paths verified at release optimization level, not just -O0

### 9. Timing Constraints

- [ ] All timing requirements documented in code comments (deadline, period)
- [ ] DWT measurement or oscilloscope capture confirms actual vs. required timing
- [ ] No `HAL_Delay()` in RTOS context (use `osDelay` / `vTaskDelay`)

### 10. Security / Industrial Hardening

- [ ] No hardcoded keys, passwords, or calibration secrets in source
- [ ] CAN/UART/SPI input validated before use (length, range, CRC)
- [ ] Stack canaries or MPU guard enabled for all tasks
- [ ] RDP level documented; not `RDP=0` in production builds
- [ ] Startup self-test: RAM pattern, flash CRC, peripheral ping

---

**Code Review Severity Levels:**

| Level | Meaning | Action |
|---|---|---|
| CRITICAL | ISR blocking call, missing volatile on ISR-shared var, watchdog disabled in release, DMA cache bug | **Block — must fix before merge** |
| HIGH | HAL_ERROR ignored, timeout=HAL_MAX_DELAY, malloc in task, stack not measured | **Warn — should fix before merge** |
| MEDIUM | Missing error callback, HAL used in tight loop (LL preferred), no DWT timing | **Info — fix in follow-up** |
| LOW | Style, naming, comment | **Note — optional** |

---

## Diagnostic Session — Problem Solving Q&A

When the user reports a firmware bug or unexpected behavior, follow this structured diagnostic workflow. Ask clarifying questions before proposing solutions. Never guess the cause without data.

### Step 1: Establish the symptom precisely

Ask:
- "What exactly is the observed behavior?" (crash, wrong value, hang, corrupt data, missing interrupt?)
- "When does it happen?" (always, intermittently, after N hours, only at high load?)
- "What changed before it appeared?" (new peripheral, optimization level, RTOS, clock config?)
- "Does it reproduce at -O0 but not -Os, or vice versa?"

### Step 2: Narrow by category

Based on symptom, immediately classify and ask targeted follow-up:

| Symptom | Ask |
|---------|-----|
| Crash → HardFault | "Do you have a HardFault handler that dumps CFSR/SP? What are the values?" |
| Wrong data from peripheral | "Are you on M7? Is the DMA buffer cache-cleaned/invalidated?" |
| Code works at -O0, breaks at -Os | "Is there a `volatile` missing on the ISR-shared variable?" |
| Peripheral freezes after first error | "Is there a recovery / re-init on HAL_ERROR return?" |
| ISR never fires | "Is NVIC priority set? Is the interrupt globally enabled? Is the IRQ flag cleared?" |
| Task never unblocks | "Is the semaphore/event given from ISR using FromISR variant and portYIELD_FROM_ISR?" |
| CAN frames lost | "What is FIFO fill level? Is there an ORE/overrun flag set? Is bus load > 75%?" |
| Watchdog reset in field | "Which task is blocking? Is IWDG fed from multi-task checklist or single task?" |
| Random corruption | "Are DMA and CPU sharing the same buffer? Is there cache coherency (M7)?" |
| USB disconnect/reconnect | "Is the VBUS detection correct? Is USB enumeration completing (CDC gets port)?" |

### Step 3: Request evidence

Never diagnose blind. Ask for:
- `arm-none-eabi-objdump -d build/firmware.elf | grep <function>` — assembly check
- CFSR + SP dump from HardFault handler
- Logic analyzer capture (I2C/SPI/CAN/UART)
- DWT cycle count from ISR timing check
- `uxTaskGetStackHighWaterMark()` for all tasks
- FreeRTOS tracealyzer / RTX5 event recorder if available

### Step 4: Apply fix methodology

```
1. Reproduce reliably → add instrumentation (GPIO toggle, ITM trace)
2. Isolate scope → comment out unrelated code, test peripheral alone
3. Verify hypothesis with measurement (scope, logic analyzer, DWT)
4. Apply minimal fix
5. Verify fix doesn't break other paths
6. Add regression test or assertion
```

### Common root causes by frequency

1. **Missing `volatile`** — ISR-shared variable optimized away at -O1+
2. **DMA cache coherency** — M7: forgot `SCB_CleanDCache` before TX or `SCB_InvalidateDCache` before RX read
3. **I2C bus lockup** — no recovery after HAL_ERROR; BUSY bit stuck
4. **HAL_MAX_DELAY** — peripheral call hangs forever when hardware fails
5. **Priority inversion** — low-prio task holds mutex needed by high-prio task; no priority inheritance
6. **Stack overflow** — task stack too small; corrupts adjacent memory silently
7. **LTO removes ISR/callback** — missing `__attribute__((used))` on `HAL_XxxCallback`
8. **FDCAN no global filter** — accept-all floods RX FIFO with noise
9. **RS485 DE timing** — switching to RX before TC fires cuts last byte
10. **Clock source after Stop mode** — PLL stopped; forgot `SystemClock_Config()` after wake

---

## STM32 Family Reference

See [stm32-families.md](stm32-families.md) for:
- Complete family catalog (Mainstream / High-Performance / Ultra-Low-Power / Wireless)
- Core architecture table (FPU, DSP, TrustZone, D-cache by family)
- All HAL driver and CMSIS device repos
- Middleware repos (FreeRTOS, ThreadX, FatFS, LwIP, USBPD...)
- Keil RTX5 / CMSIS-RTX configuration reference
- RTX5 safety features (thread watchdog, MPU zones, safety classes)
- MEMS sensor PID driver list
- X-CUBE expansion packages

---

## Reference Files

> **Tek kaynak (canonical):** Bu tablo SKILL.md içinde. README.md ve CLAUDE.md
> sadece bu dosyaya işaret etmeli — referans listesini kopyalamayın.

### Drivers & Protocols
| File | Contents |
|------|----------|
| [stm32-families.md](stm32-families.md) | Family catalog, HAL repos, CMSIS, RTX5 config |
| [ref-communication-protocols.md](ref-communication-protocols.md) | I2C, SPI DMA, UART ring buffer, FDCAN |
| [ref-qspi-octospi-highspeed.md](ref-qspi-octospi-highspeed.md) | QSPI/OCTOSPI high-speed: sample shift, DLYB, dummy cycles |
| [ref-adc-timer.md](ref-adc-timer.md) | ADC calibration, DMA circular, oversampling, PWM, encoder, HRTIM |
| [ref-modbus-rtu.md](ref-modbus-rtu.md) | Modbus RTU slave/master, CRC16, framing, exception codes |
| [ref-fdcan-multi.md](ref-fdcan-multi.md) | FDCAN multi-instance, 8Mbps bit timing, filter, bus-off |
| [ref-external-memory-fmc.md](ref-external-memory-fmc.md) | FMC SDRAM/NOR/SRAM, OCTOSPI PSRAM init + timing |

### USB & Networking
| File | Contents |
|------|----------|
| [ref-usb-device.md](ref-usb-device.md) | USB device stack: CDC-ACM, HID, MSC, descriptors, endpoints |
| [ref-usb-host-filesystem.md](ref-usb-host-filesystem.md) | USB host (TinyUSB MSC) + FatFS/LittleFS, RTOS-safe file I/O |
| [ref-ethernet-lwip.md](ref-ethernet-lwip.md) | STM32H5/H7 ETH, LwIP raw/netconn/socket, DHCP, TCP patterns |
| [ref-ble-bluenrg355.md](ref-ble-bluenrg355.md) | BlueNRG-355 BLE: PHY, MTU, throughput, security, OTA |

### Automotive / Diagnostic Stack
| File | Contents |
|------|----------|
| [ref-j1939.md](ref-j1939.md) | SAE J1939 AC state machine, CMDT TP, DM1/DM11, FDCAN bit timing |
| [ref-uds-iso14229.md](ref-uds-iso14229.md) | ISO 14229 UDS: P2/P2*/S3 timing, Security Access, dual-bank OTA |
| [ref-obd2.md](ref-obd2.md) | OBD-II (SAE J1979): Modes 0x01–0x0A, Permanent DTC, readiness |
| [ref-wwh-obd.md](ref-wwh-obd.md) | WWH-OBD (ISO 27145): Euro VI, J1939 29-bit IDs, IUMPR |
| [ref-doip.md](ref-doip.md) | DoIP (ISO 13400): UDP discovery 224.0.0.51, routing activation, TCP |
| [ref-diagnostic-stack.md](ref-diagnostic-stack.md) | Unified DTC, CAN dispatch, NVM, freeze frame, OBD+J1939+UDS+WWH |
| [ref-dtc-mapping.md](ref-dtc-mapping.md) | J1939 SPN/FMI ↔ OBD-II P-code ↔ WWH wire format conversion |

### RTOS / Compiler / C
| File | Contents |
|------|----------|
| [ref-rtos-patterns.md](ref-rtos-patterns.md) | FreeRTOS periodic, ISR→task, mutex, event groups, RTX5 patterns |
| [ref-keil-armclang.md](ref-keil-armclang.md) | Keil MDK / AC6: LTO traps, scatter, RTX5 pitfalls |
| [ref-compiler-hardening.md](ref-compiler-hardening.md) | volatile, barriers, DMA cache, ISR reorder, LTO |
| [ref-c-code-style.md](ref-c-code-style.md) | BARR-C:2018 / QuantumLeaps / NASA style — solid index |
| [ref-arm-asm.md](ref-arm-asm.md) | Cortex-M assembly: AAPCS, intrinsics, DSP/SIMD, Thumb-2, naked ISR |

### Memory / Clock / Boot / Linker
| File | Contents |
|------|----------|
| [ref-memory-optimization.md](ref-memory-optimization.md) | Compiler flags, memory pools, packed structs, ring buffer |
| [ref-power-optimization.md](ref-power-optimization.md) | Sleep/Stop/Standby, RTC/LPTIM wakeup, VOS, domain power |
| [ref-fault-handlers.md](ref-fault-handlers.md) | HardFault decode, CFSR/BFAR/MMFAR, reset cause, noinit persist |
| [ref-boot-clock.md](ref-boot-clock.md) | PLL (F4/H7/H5), flash wait states, CSS, backup domain |
| [ref-linker-script.md](ref-linker-script.md) | GCC linker (.ld): MEMORY, SECTIONS, .data/.bss/.noinit |
| [ref-armlink-scatter.md](ref-armlink-scatter.md) | armlink scatter complete syntax: regions, attributes, .ANY |
| [ref-iap-ota.md](ref-iap-ota.md) | IAP bootloader, jump, dual-bank swap, CRC verify, DFU |

### Safety / Security / Errata
| File | Contents |
|------|----------|
| [ref-stm32-errata.md](ref-stm32-errata.md) | Real-world errata: HAL bugs, GPIO speed, USB, DMA-DTCM, I2C hang |
| [ref-trustzone.md](ref-trustzone.md) | TrustZone-M (H5/U5/L5): SAU, GTZC, MPCBB, CMSE, MPU stack guard |
| [ref-secure-boot.md](ref-secure-boot.md) | RDP levels, option bytes, PCROP, ECDSA, PKA, OTFDEC, anti-rollback |

---

## Companion Skills

- **CortexM-software-fmea** — systematic failure mode analysis before coding
- **CortexM-fault-tree-analysis** — safety case for actuation paths
- **CortexM-fuzz-testing** — adversarial testing of protocol parsers
- **CortexM-hil-chaos** — hardware fault injection to validate watchdog/recovery

Pipeline:
```
CortexM-software-fmea → stm32-embedded-dev (implement + code review) → CortexM-hil-chaos (validate)
```
