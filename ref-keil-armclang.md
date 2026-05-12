# Keil MDK / Arm Compiler 6 (armclang) — STM32 Specific Reference

Bu dosya: Keil MDK + AC6 (armclang) kombinasyonuna özgü tuzakları, scatter file yapısını, RTX5 hatalarını ve LTO davranışını kapsar.

---

## AC5 (ARMCC) vs AC6 (armclang) — Kritik Farklar

| Özellik | AC5 (ARMCC) | AC6 (armclang / LLVM) |
|---------|------------|----------------------|
| Base | Proprietary | LLVM/Clang |
| LTO | Yoktu | `--lto` ile aktif — varsayılan kapalı, proje ayarından açılır |
| Optimizasyon | `-O0..O3` | `-O0..O3, -Oz` |
| Weak symbol | Çoğunlukla korunur | LTO açıkken silinebilir — `__attribute__((used))` şart |
| `volatile` | Daha hoşgörülü | Daha agresif — eksik `volatile` -O1'de bozulur |
| Inline asm | ARM syntax | GNU inline asm (`__asm volatile`) + Clang quirks |
| Diagnostics | `--diag_warning` | `-W` flags (Clang standard) |

**Geçiş notu:** AC5'ten AC6'ya geçişte mevcut kod `-O0`'da çalışsa bile `-O1`'de bozulabilir — özellikle volatile eksiklikleri ve ISR flag'leri için.

---

## Optimizasyon Seviyeleri — AC6 Davranışı

```
-O0  : Hiç optimizasyon yok. Debug için. volatile eksikliği çoğunlukla saklanır.
-O1  : Temel dead code / register alloc. volatile eksikliği görünmeye başlar.
-O2  : Tam optimizasyon. ISR flag, DMA cache, aliasing hataları ortaya çıkar.
-O3  : Agresif. Loop unrolling, inlining. -O2 hatalarına ek yeniler üretebilir.
-Oz  : Boyut odaklı. En agresif dead code elim — LTO yoksa bile callback'ler silinebilir.
```

**Proje ayarı:** Options → C/C++(AC6) → Optimization Level

**Öneri:** Development → `-O1`, Release → `-O2` veya `-Oz` (flash sınırlıysa)  
LTO varsa `-O2 --lto` kombinasyonu; `-Oz --lto` FatFS/lwIP gibi büyük kütüphanelerde ciddi space kazanımı sağlar.

---

## LTO (--lto) — HAL Callback Silme Tehlikesi

### Problem

LTO açıkken armclang tüm TU'ları (Translation Unit) birleştirip anonim bir CU oluşturur. Bu süreçte:
- `__weak` semboller referanssız görünürse → **silinir**
- HAL, zaten `__weak` olarak tanımlar tüm callback'leri
- Kullanıcı override'ı LTO'dan sonra "unused" çıkarsa → yok olur

### Etkilenen callback'ler (örnekler)

```c
/* Bu fonksiyonlar LTO ile silinebilir — MUTLAKA __attribute__((used)) ekle */
__attribute__((used))
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart) { ... }

__attribute__((used))
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) { ... }

__attribute__((used))
void HAL_SPI_TxRxCpltCallback(SPI_HandleTypeDef *hspi) { ... }

__attribute__((used))
void HAL_SPI_RxCpltCallback(SPI_HandleTypeDef *hspi) { ... }

__attribute__((used))
void HAL_FDCAN_RxFifo0MsgPendingCallback(FDCAN_HandleTypeDef *hfdcan) { ... }

__attribute__((used))
void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart) { ... }

__attribute__((used))
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim) { ... }
```

### ISR handler'lar

```c
/* Naked/noinline ISR'lar LTO ile yanlış inline edilebilir */
__attribute__((used, noinline))
void HardFault_Handler(void) { while (1) {} }

__attribute__((used, noinline))
void MemManage_Handler(void) { while (1) {} }

__attribute__((used, noinline))
void BusFault_Handler(void) { while (1) {} }
```

### Scatter / linker: vector table koru

```
; Keil scatter file — vector tablosunu keep et
LR_IROM1 0x08000000 0x00200000 {
  ER_IROM1 0x08000000 0x00200000 {
    *.o (RESET, +First)     ; vector table — her zaman ilk
    *(InRoot$$Sections)
    .ANY (+RO)
  }
  ...
}
```

Linker option (Options → Linker → Misc controls):
```
--keep=*.o(RESET)
```

---

## STM32H7 Scatter File — DMA Buffer Yerleşimi

### ⚠️ DTCM DMA Erişemez

```
STM32H7 bellek mimarisi:
  DTCM  0x20000000  128KB  — Yalnızca CPU (TCM bus) erişebilir. DMA YASAK.
  AXI   0x24000000  512KB  — CPU + DMA1/2 + MDMA erişebilir. ← DMA buffer buraya
  D2S1  0x30000000  128KB  — DMA1/2 erişebilir
  D2S2  0x30020000   32KB  — DMA1/2 erişebilir
  D3    0x38000000   16KB  — BDMA erişebilir (DMA1/2 değil)
```

**Yaygın hata:** DTCM'yi DMA buffer olarak kullanmak — buffer oluşturulur, DMA transaction başlar, transfer "başarılı" görünür ama veri hiç gitmez (DMA bus fault → HardFault veya sessiz veri kaybı).

### Doğru Scatter File

```
; STM32H743xI — 2MB Flash, 128KB DTCM, 512KB AXI, 128KB D2S1
LR_IROM1 0x08000000 0x00200000 {

  ER_IROM1 0x08000000 0x00200000 {
    *.o (RESET, +First)
    *(InRoot$$Sections)
    .ANY (+RO)
  }

  ; DTCM — task stack, ISR handler, kritik veri (DMA YOK)
  RW_IRAM1 0x20000000 0x00020000 {
    .ANY (+RW +ZI)
  }

  ; AXI SRAM — DMA buffer'ları buraya (32-byte aligned section)
  RW_DMA 0x24000000 0x00080000 {
    *(.dma_buffer)           ; __attribute__((section(".dma_buffer")))
  }

  ; D2 SRAM1 — FatFS work area, büyük geçici buffer'lar
  RW_IRAM2 0x30000000 0x00020000 {
    *(.d2_buffer)
  }
}
```

### C tarafında buffer tanımı

```c
/* DMA buffer — AXI SRAM'a yerleştirilecek, 32-byte aligned */
__attribute__((section(".dma_buffer"), aligned(32)))
static uint8_t SPI_TxBuffer[4096 + 32];

__attribute__((section(".dma_buffer"), aligned(32)))
static uint8_t SPI_RxBuffer[4096 + 32];
```

---

## RTX5 / CMSIS-RTOS2 Tuzakları

### 1. Dinamik Stack (Heap Tehlikesi)

```c
/* YANLIŞ — stack_mem = NULL → osRtxMemoryAlloc heap'ten alır */
const osThreadAttr_t task_attr = {
    .name       = "rx_task",
    .stack_mem  = NULL,      /* ← heap! fragmentation riski */
    .stack_size = 1024,
    .priority   = osPriorityNormal,
};

/* DOĞRU — statik stack, heap yok */
static uint64_t rx_task_stack[256];   /* 64-bit aligned — RTX5 zorunluluğu */
static osStaticThreadDef_t rx_task_cb;
const osThreadAttr_t rx_task_attr = {
    .name       = "rx_task",
    .stack_mem  = rx_task_stack,
    .stack_size = sizeof(rx_task_stack),
    .cb_mem     = &rx_task_cb,
    .cb_size    = sizeof(rx_task_cb),
    .priority   = osPriorityNormal,
};
osThreadNew(rx_task_func, NULL, &rx_task_attr);
```

### 2. osMutexAcquire Timeout Hatası

```c
/* YAYGIN HATA — timeout=0 → non-blocking, osErrorTimeout döner, mutex alınamaz */
osMutexAcquire(hMutex, 0U);   /* NON-BLOCKING! */
/* ... kritik bölge ... */
osMutexRelease(hMutex);

/* DOĞRU — timeout=osWaitForever veya belirli bir süre */
if (osMutexAcquire(hMutex, 100U) == osOK) {   /* 100ms timeout */
    /* ... kritik bölge ... */
    osMutexRelease(hMutex);
} else {
    /* timeout hatası — logla */
}
```

**Not:** RTX5'te `osMutexAcquire(mutex, 0U)` **sıfır timeout** demektir; osWaitForever değil. Bu C0 yerine 0U yazan kodlarda sık karşılaşılan hatadır.

### 3. osMutexPrioInherit Eksikliği

```c
/* YANLIŞ — priority inversion riski */
hMutex = osMutexNew(NULL);   /* NULL attr → osMutexPrioInherit yok */

/* DOĞRU — osMutexPrioInherit zorunlu */
static const osMutexAttr_t spi_mutex_attr = {
    "SpiMutex",                        /* name */
    osMutexPrioInherit | osMutexRobust, /* attr_bits */
    NULL,                               /* cb_mem (static için tanımla) */
    0U                                  /* cb_size */
};
hMutex = osMutexNew(&spi_mutex_attr);
```

**Neden önemli:** osMutexPrioInherit olmadan, düşük öncelikli task mutex'i tutarken yüksek öncelikli task bekler — araya giren orta öncelikli task preempt eder → **priority inversion → deadline kaçırma**.

### 4. Semaphore Double-Release (DMA IRQ)

```c
/* SORUN: iki DMA stream'i de aynı handler'ı çağırıyorsa */
void DMA2_Stream0_IRQHandler(void) { SPI1_DmaIrqHandler(); }  /* RX complete */
void DMA2_Stream1_IRQHandler(void) { SPI1_DmaIrqHandler(); }  /* TX complete */

void SPI1_DmaIrqHandler(void) {
    osSemaphoreRelease(sem_SPI1);   /* ← iki kez çağrılır! */
    /* ikinci çağrıda: osErrorResource döner (sessizce) */
    /* ama sem count 1'den 2'ye çıkarsa task iki kez wake olabilir */
}

/* DOĞRU — yalnızca RX complete'ten release et */
void DMA2_Stream0_IRQHandler(void) {    /* RX */
    LL_DMA_ClearFlag_TC0(DMA2);
    LL_DMA_DisableStream(DMA2, LL_DMA_STREAM_0);
    osSemaphoreRelease(sem_SPI1);       /* ← sadece burada */
}

void DMA2_Stream1_IRQHandler(void) {    /* TX */
    LL_DMA_ClearFlag_TC1(DMA2);
    LL_DMA_DisableStream(DMA2, LL_DMA_STREAM_1);
    /* release YOK — RX complete yeterli */
}
```

### 5. Event Flags vs Semaphore — ISR→Task

```c
/* Tercih: Event flags — hem ISR'dan güvenli hem çoklu event destekler */
static osEventFlagsId_t spi_events;

/* Init */
spi_events = osEventFlagsNew(NULL);

/* ISR */
osEventFlagsSet(spi_events, 0x01U);   /* ISR'dan güvenli */

/* Task */
uint32_t flags = osEventFlagsWait(spi_events, 0x01U, osFlagsWaitAny, osWaitForever);
```

### 6. Joinable Thread — Geçici İşçi Task

```c
/* Joinable thread: başka bir task onun bitmesini bekleyebilir */
static const osThreadAttr_t worker_attr = {
    .attr_bits  = osThreadJoinable,
    .stack_mem  = worker_stack,
    .stack_size = sizeof(worker_stack),
    .cb_mem     = &worker_cb,
    .cb_size    = sizeof(worker_cb),
    .priority   = osPriorityBelowNormal,
};

osThreadId_t worker_id = osThreadNew(worker_task, NULL, &worker_attr);
osThreadJoin(worker_id);   /* caller burada bloke olur, worker bitince devam eder */
```

### 7. Memory Pool — Zero-Copy Veri Transferi

```c
/* Queue üzerinden pointer taşı — büyük veri için kopyasız yöntem */
typedef struct {
    uint8_t data[256];
    uint16_t len;
} CanFrame_t;

static osMemoryPoolId_t frame_pool;
static osMessageQueueId_t frame_queue;

/* Init */
frame_pool  = osMemoryPoolNew(8, sizeof(CanFrame_t), NULL);
frame_queue = osMessageQueueNew(8, sizeof(CanFrame_t *), NULL);

/* Producer (ISR veya task) */
CanFrame_t *f = osMemoryPoolAlloc(frame_pool, 0U);  /* timeout=0 = non-blocking */
if (f) {
    memcpy(f->data, dma_rx_buf, len);
    f->len = len;
    osMessageQueuePut(frame_queue, &f, 0, 0U);
}

/* Consumer task */
CanFrame_t *f;
if (osMessageQueueGet(frame_queue, &f, NULL, osWaitForever) == osOK) {
    process_frame(f);
    osMemoryPoolFree(frame_pool, f);   /* geri bırak */
}
```

### 8. osDelayUntil — Kesin Periyodik Task

```c
/* osDelay(10): her çalışma sonrası 10ms bekler — drift birikir */
/* osDelayUntil: mutlak tick'e kadar bekler — drift birikmez */

void periodic_ctrl_task(void *arg)
{
    uint32_t tick = osKernelGetTickCount();
    for (;;) {
        do_control_cycle();
        tick += 10U;                    /* 10ms period */
        osDelayUntil(tick);             /* absolute deadline */
    }
}
```

### 9. Virtual Timer — Callback Tabanlı Zamanlama

```c
/* Timer callback ISR context'inde çalışır — BLOCKING çağrı YASAK */
static void led_timer_cb(void *arg)
{
    (void)arg;
    osEventFlagsSet(led_events, FLAG_BLINK);  /* sadece flag set — iş task'ta */
}

static osTimerId_t led_timer;

/* Init */
led_timer = osTimerNew(led_timer_cb, osTimerPeriodic, NULL, NULL);
osTimerStart(led_timer, 500U);   /* 500ms period */

/* Stop/restart */
osTimerStop(led_timer);
osTimerStart(led_timer, 250U);   /* periyodu değiştir */
```

### 10. Mutex Kullanırken osThreadTerminate Tehlikesi

```c
/*
 * KRITIK: osMutexAcquire yapmış bir thread'i osThreadTerminate ile silersen
 * mutex token YOK OLUR — başka hiçbir thread o mutex'i bir daha alamaz.
 * Peripheral erişimi sonsuza kadar kilitlenir.
 *
 * Çözüm: mutex tutan thread'i hiçbir zaman dışarıdan terminate etme.
 * Bunun yerine task flag veya event ile sinyal ver, task kendisi çıksın.
 */
osThreadFlagsSet(spi_task_id, FLAG_TERMINATE);   /* DOĞRU: task kendisi çıkar */
/* osThreadTerminate(spi_task_id);              YANLIŞ: mutex kaybolabilir */
```

### 11. RTX_Config.h — Kritik Parametreler

```c
/* Stack overflow koruması — MUTLAKA açık olsun */
#define OS_STACK_CHECKING          1    /* stack overflow → osRtxErrorNotify */
#define OS_THREAD_STACK_WATERMARK  1    /* HWM tracking — osThreadGetStackSpace */

/* Heap tamamen kapat — statik allocation zorla */
#define OS_DYNAMIC_MEM_SIZE        0

/* Tick frekansı — FreeRTOS configTICK_RATE_HZ eşdeğeri */
#define OS_TICK_FREQ            1000    /* 1ms tick */

/* Round-robin time slice */
#define OS_ROUND_ROBIN_ENABLED     1
#define OS_ROUND_ROBIN_TIMEOUT    50    /* ms, aynı öncelikli task'lar arası */

/* ISR'dan gelen event queue boyutu */
#define OS_ISR_FIFO_QUEUE         16    /* arttır: çok ISR event üretiyorsa */

/* Privilege mode — unprivileged = MPU ile user task koruması */
#define OS_PRIVILEGE_MODE          0    /* 0 = unprivileged user tasks */
```

### 12. Error Notification Override

```c
/* osRtxErrorNotify override — stack overflow ve ISR queue taşması yakala */
__WEAK uint32_t osRtxErrorNotify(uint32_t code, void *object_id)
{
    switch (code) {
    case osRtxErrorStackOverflow:
        /* object_id = thread handle — hangi task taştı */
        fault_log(FAULT_STACK_OVF, (uint32_t)object_id);
        /* production'da watchdog sıfırlasın */
        while (1) {}
        break;

    case osRtxErrorISRQueueOverflow:
        /* ISR'dan çok fazla flag/semaphore gönderildi — OS_ISR_FIFO_QUEUE arttır */
        fault_log(FAULT_ISR_QUEUE, 0);
        break;

    case osRtxErrorTimerQueueOverflow:
        fault_log(FAULT_TIMER_Q, 0);
        break;

    case osRtxErrorSVC:
        /* Geçersiz SVC çağrısı — genellikle context dışı RTOS çağrısı */
        fault_log(FAULT_SVC, (uint32_t)object_id);
        while (1) {}
        break;

    default:
        while (1) {}
    }
    return 0U;
}
```

### 13. Idle Thread — Low Power Override

```c
/* RTX5 idle thread override — WFI/WFE ile enerji tasarrufu */
__NO_RETURN __WEAK void osRtxIdleThread(void *argument)
{
    (void)argument;
    for (;;) {
        /* HAL_SuspendTick() buraya eklenebilir — stop moduna girmeden önce */
        __WFE();   /* wait for event: interrupt veya event gelene kadar CPU halt */
        /* veya __WFI() — wait for interrupt only */
    }
}
```

### Thread Flag vs Event Flag — Hangisini Kullan?

| Durum | Kullan |
|-------|--------|
| ISR → belirli bir task sinyal | `osThreadFlagsSet` (hedef thread ID gerekli) |
| Task → başka task sinyal | `osEventFlagsSet` (global, herkes bekleyebilir) |
| Çok sayıda waiter | `osEventFlagsSet` |
| ISR içinde basit wake-up | `osEventFlagsSet` (daha güvenli) |

---

## USART / Peripheral Copy-Paste Bug Pattern

Keil projelerinde en sık görülen ISR bug'ı: IRQ handler doğru peripheral'ı hedeflemiyor.

```c
/* HATA — USART2_IRQHandler içinde USART1'i temizliyor */
void USART2_IRQHandler(void)
{
    if (LL_USART_IsActiveFlag_ORE(USART2))
        LL_USART_ClearFlag_ORE(USART1);  /* ← YANLIŞ! USART2 olmalı */
    /* Sonuç: USART2 ORE flag'i hiç temizlenmez → interrupt storm */
    /* CPU sonsuza kadar USART2_IRQHandler'a girer → sistem donar */
}

/* DOĞRU */
void USART2_IRQHandler(void)
{
    if (LL_USART_IsActiveFlag_ORE(USART2))
        LL_USART_ClearFlag_ORE(USART2);  /* peripheral eşleşmeli */
}

/* Kontrol listesi — her ISR'da sor: */
/* □ Tüm LL_XXX çağrıları doğru periferali kullanıyor mu? */
/* □ Handler adı (USART2_IRQHandler) ile içindeki periferallar eşleşiyor mu? */
/* □ NVIC SetPriority'deki IRQn doğru periferale ait mi? */
```

---

## FDCAN Mod Seçimi — Passive vs Active

```c
/* BUS_MONITORING modu: sadece dinler, TX yapamaz */
/* CubeMX "passive sniffing" için bu modu üretir — geliştirme sırasında kalabilir */
hfdcan.Init.Mode = FDCAN_MODE_BUS_MONITORING;  /* ← OBD/UDS için YANLIŞ */

/* NORMAL mod: TX + RX — OBD, UDS, aktif haberleşme için şart */
hfdcan.Init.Mode = FDCAN_MODE_NORMAL;           /* ← DOĞRU */

/* Diğer modlar */
/* FDCAN_MODE_INTERNAL_LOOPBACK  — only for self-test */
/* FDCAN_MODE_EXTERNAL_LOOPBACK  — TX→RX loopback on pin */
/* FDCAN_MODE_RESTRICTED_OPERATION — RX only, limited TX (error frames) */

/* Runtime mod değişikliği — bus recover sonrası */
HAL_FDCAN_Stop(&hfdcan);
hfdcan.Init.Mode = FDCAN_MODE_NORMAL;
HAL_FDCAN_Init(&hfdcan);
HAL_FDCAN_Start(&hfdcan);
```

---

## NVIC Priority — FreeRTOS / RTX5 ile Doğru Yapılandırma

```c
/* SystemInit veya MX_Init öncesinde — PRE-EMPTION BITS ayarla */
HAL_NVIC_SetPriorityGrouping(NVIC_PRIORITYGROUP_4);
/* 4 bit preemption, 0 bit subpriority — FreeRTOS ve RTX5 için standart */

/* STM32H7: 16 preemption seviyesi (0=en yüksek, 15=en düşük) */
/* FreeRTOS: configMAX_SYSCALL_INTERRUPT_PRIORITY ile ISR sınırı */

/* RTOS API çağıran ISR'lar: priority >= configMAX_SYSCALL_INTERRUPT_PRIORITY */
HAL_NVIC_SetPriority(DMA2_Stream0_IRQn, 5, 0);  /* osSemaphoreRelease → ≥5 */
HAL_NVIC_SetPriority(FDCAN1_IT0_IRQn,   5, 0);  /* osEventFlagsSet → ≥5 */
HAL_NVIC_SetPriority(USART6_IRQn,       5, 0);  /* osSemaphoreRelease → ≥5 */

/* RTOS API çağırmayan ISR'lar: her priority kullanılabilir */
HAL_NVIC_SetPriority(TIM1_UP_IRQn, 2, 0);        /* pure HW timing, no RTOS */

/* YANLIŞ: RTOS API çağıran ISR'a 0..4 priority vermek → HardFault */
HAL_NVIC_SetPriority(DMA2_Stream0_IRQn, 3, 0);   /* configMAX_SYSCALL=5 → illegal */
```

---

## Debug: Stack / Heap Overflow Tespiti

```c
/* RTX5: OS_Dynamic_Mem_Size = 0 ile heap'i tamamen kapat */
/* RTX_Config.h veya RTE_Components.h */
#define OS_DYNAMIC_MEM_SIZE  0   /* Heap yok — statik allocation zorunlu */

/* Stack canary — RTX5 zaten doldurur, osThreadGetStackSpace ile oku */
void stack_monitor_task(void *arg)
{
    for (;;) {
        /* Tüm thread'lerin stack kullanımını izle */
        uint32_t free_stack = osThreadGetStackSpace(osThreadGetId());
        if (free_stack < 64) {
            /* Kritik — logla ve sistemi yeniden başlat */
        }
        osDelay(1000);
    }
}

/* MPU ile stack guard — DTCM altında 32-byte no-access region */
/* Keil: Options → Utilities → MPU veya scatter file'da MPU region tanımı */
```

---

## Compiler Warning Flags — AC6

```
; Keil Options → C/C++(AC6) → Warnings veya Misc controls alanı

-Wall                    ; temel uyarılar
-Wextra                  ; ek uyarılar
-Wcast-align             ; unaligned pointer cast (DMA buffer için kritik)
-Wshadow                 ; değişken gölgeleme
-Wundef                  ; tanımsız makro kullanımı
-Wdouble-promotion       ; float'ın double'a promote edilmesi (FPU olmayan MCU'da yavaş)
-Wformat=2               ; printf format string güvenliği (hprintf gibi wrapperlar için)
-fstack-usage            ; her fonksiyon için .su dosyası üretir — stack analizi

; Keil diagnostics (armclang stil)
; --diag_warning=111     ; unreachable code
; --diag_error=9931      ; implicit function declaration
```

---

## Hızlı Kontrol Listesi — Keil AC6 Proje Audit

```
□ LTO açık mı? → Tüm HAL callback override'larında __attribute__((used)) var mı?
□ Scatter file'da DMA buffer AXI SRAM'a (0x24000000) mı yerleştirilmiş?
□ DTCM'de DMA buffer var mı? → Bus fault / sessiz veri kaybı riski
□ osMutexNew'de osMutexPrioInherit var mı?
□ osMutexAcquire timeout=0 mı? → Non-blocking — intentional mi?
□ osThreadAttr_t stack_mem = NULL mı? → Heap kullanıyor — statik yap
□ FDCAN Init.Mode = BUS_MONITORING mı? → OBD/UDS için NORMAL olmalı
□ Her ISR: peripheral adı handler adıyla eşleşiyor mu?
□ ISR → RTOS API: priority ≥ configMAX_SYSCALL_INTERRUPT_PRIORITY mı?
□ DMA cache boyut formülü: (n+31)&~31 mi, yoksa n+32 mi?
□ ISR'da flag set: COMPILER_BARRIER() veri yazma ile flag arasında mı?
□ NVIC priority grouping: NVIC_PRIORITYGROUP_4 set mi?
□ HAL_Delay RTOS context'te kullanılıyor mu? → osDelay kullan
□ HardFault/MemManage handler: __attribute__((used, noinline)) var mı?
```
