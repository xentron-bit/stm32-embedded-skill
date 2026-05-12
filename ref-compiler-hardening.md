# Compiler Optimization — Silent Bug Prevention

Bu dosya: hata mesajı vermeden sessizce bozulan davranışların tüm kategorilerini ve çözümlerini kapsar.

---

## Kategori 1: `volatile` Eksikliği (En Yaygın)

**Semptom:** -O2/-Os ile derleme yapılınca ISR'dan değiştirilen değişken main loop'ta görünmüyor; DMA tamamlanma flag'i hiç gözetlenmiyor.

**Neden:** Compiler değişkeni register'a alır, SRAM'dan tekrar okumaz.

```c
/* YANLIŞ */
uint8_t dma_done = 0;
void DMA_IRQHandler(void) { dma_done = 1; }
void wait(void) { while (!dma_done) {} } /* sonsuz döngü -O2'de */

/* DOĞRU */
volatile uint8_t dma_done = 0;
```

**Kurallar:**
- ISR ile paylaşılan tüm değişkenler: `volatile`
- Hardware register pointer: `volatile uint32_t *` (CMSIS zaten `__IO` = `volatile`)
- DMA buffer'ı: `volatile` değil — bunun için cache/barrier gerekli (Kategori 3)
- `volatile` thread-safe değil — RTOS mutex veya disable-interrupt ile birleştir

```c
/* ISR-shared pattern — doğru */
volatile bool     flag;          /* single-writer ISR, single-reader main */
volatile uint32_t counter;       /* ISR artırıyor */

/* Multi-byte struct — volatile yetmez, critical section şart */
typedef struct { uint32_t a; uint32_t b; } Pair_t;
volatile Pair_t pair; /* a ve b ayrı cycle'da okunabilir — tutarsız! */
/* Çözüm: */
uint32_t primask = __get_PRIMASK();
__disable_irq();
Pair_t snap = pair; /* atomik blok */
__set_PRIMASK(primask);
```

---

## Kategori 2: Memory Barrier Eksikliği

**Semptom:** DMA başlatmadan önce buffer'a yazdım ama DMA eski veriyi gönderiyor; peripheral konfigürasyon yazıldı ama etki etmedi.

**Neden:** Compiler veya out-of-order CPU, yazma sırasını değiştiriyor.

```c
/* Barrier türleri */
__DSB();   /* Data Synchronization Barrier — tüm bellek yazmaları tamamla */
__DMB();   /* Data Memory Barrier — sıralama garantisi, tamamlamayı garantilemez */
__ISB();   /* Instruction Synchronization Barrier — pipeline flush (MPU/VTOR sonrası şart) */

/* DMA TX pattern — eksik barrier gizli hata */
memcpy(tx_buf, data, len);
__DSB();                         /* CPU write buffer flush */
SCB_CleanDCache_by_Addr((uint32_t *)tx_buf, len); /* M7: cache → SRAM */
HAL_UART_Transmit_DMA(&huart, tx_buf, len);

/* Peripheral enable sonrası */
RCC->APB1ENR |= RCC_APB1ENR_TIM2EN;
__DSB();        /* clock enable'ın etkili olması için */
TIM2->CR1 |= TIM_CR1_CEN;

/* MPU/VTOR değişikliği sonrası */
SCB->VTOR = new_vector_table;
__DSB();
__ISB();        /* pipeline flush — yeni VTOR'dan exception vector okusun */
```

### Compiler Reorder Engelleme

```c
/* Compiler'ın sıra değiştirmesini önle — asm volatile ile bellek erişimi işaretle */
#define COMPILER_BARRIER() __asm__ volatile("" ::: "memory")

/* Örnek: flag'den önce veri hazır olmalı */
prepare_data(buf);
COMPILER_BARRIER();   /* compiler buf yazmasını flag sonrasına taşımasın */
volatile bool ready = true;
```

---

## Kategori 3: DMA Cache Coherency (M7: F7, H7, H7RS)

**Semptom:** DMA RX tamamlandı ama buffer'dan okunan veri eski; DMA TX doğru veriyi göndermedi.

**Neden:** Cortex-M7'nin D-cache'i (32-byte write-back) var; CPU cache'ten okur, DMA SRAM'dan okur/yazar — ikisi senkron değil.

```c
/* TX: CPU → DMA → peripheral */
void dma_tx_start(uint8_t *data, uint32_t len)
{
    /* 1. Önce cache'i SRAM'a yaz */
    /* DOĞRU boyut formülü: (len + 31) & ~31 — 32-byte hizalı yukarı yuvarlama */
    SCB_CleanDCache_by_Addr((uint32_t *)data, (int32_t)((len + 31U) & ~31U));
    __DSB();
    /* 2. Sonra DMA başlat — SRAM güncel */
    HAL_SPI_Transmit_DMA(&hspi, data, len);
}

/* RX: peripheral → DMA → SRAM; CPU cache'i geçersiz kıl */
void HAL_SPI_RxCpltCallback(SPI_HandleTypeDef *hspi)
{
    /* Cache'i geçersiz kıl — bir sonraki CPU okuma SRAM'dan gelsin */
    /* DOĞRU boyut formülü — aşağıya bakın */
    SCB_InvalidateDCache_by_Addr((uint32_t *)rx_buf,
                                  (int32_t)((sizeof(rx_buf) + 31U) & ~31U));
    process(rx_buf);
}

/* Buffer alignment zorunlu — 32-byte cache line */
ALIGN_32BYTES(uint8_t tx_buf[TX_SIZE]) __attribute__((section(".dma_buf")));
ALIGN_32BYTES(uint8_t rx_buf[RX_SIZE]) __attribute__((section(".dma_buf")));
/* Boyut da 32'nin katı olmalı — yarım cache line temizleme hatalı sonuç verir */

/* Alternatif: MPU ile buffer'ı non-cacheable yap */
/* Region 3: DMA buffer — TEX=001, C=0, B=0 (strongly ordered) */
/* Bu durumda Clean/Invalidate çağrısı GEREKMEZ */
```

### ⚠️ Cache Boyut Formülü — Kritik Hata Kaynağı

```c
/* YANLIŞ — buffer sınırını 32 byte aşar, komşu veriyi bozar */
SCB_InvalidateDCache_by_Addr((uint32_t *)rx_buf, total + 32);

/* DOĞRU — 32-byte sınırına yukarı yuvarlama */
SCB_InvalidateDCache_by_Addr((uint32_t *)rx_buf, (int32_t)((total + 31U) & ~31U));

/*
 * Neden fark eder?
 * SCB_InvalidateDCache_by_Addr DCIMVAC komutu kullanır.
 * DCIMVAC: dirty (kirli) cache line'ı write-back YAPMADAN atar.
 * Formül hatalıysa komşu dirty cache line da geçersiz kılınır →
 * o line'daki CPU verisi (ör: FatFS iç tabloları) SRAM'a yazılmadan kaybolur.
 *
 * Neden -O0'da çalışır, -O1/-O2'de bozulur?
 * -O0: Optimizasyon yok → az dirty cache line → komşu line büyük olasılıkla clean
 * -O1+: Daha agresif veri yükleme → komşu dirty line → DCIMVAC o veriyi siler
 *
 * Gerçek örnek: AT25SF128A_ReadSector() — total = 4096 + 4 = 4100 byte
 *   Hatalı: total + 32 = 4132 → 130 cache line = 4160 byte → 32 byte taşma
 *   Doğru:  (4100 + 31) & ~31 = 4128 byte → 132 cache line = tam 32-byte sınırı
 */
```

### Linker Script: DMA Buffer Bölümü

```ld
/* STM32H7: DMA erişemez DTCM'ye (0x20000000) — AXI SRAM veya D2 SRAM kullan */
/* DTCM yalnızca CPU tarafından TCM veri yolu üzerinden erişilebilir */
.dma_buf (NOLOAD) :
{
    . = ALIGN(32);
    *(.dma_buf)
    . = ALIGN(32);
} >RAM_D2   /* H7: D2 domain SRAM (0x30000000) — DMA1/2 erişebilir */
/* Keil scatter: RW_DMA 0x24000000 { *(.dma_buffer) }  ← AXI SRAM */
```

---

## Kategori 4: LTO (Link Time Optimization) Tuzakları

**Semptom:** ISR hiç çağrılmıyor; `__attribute__((weak))` callback overriding çalışmıyor; `static` fonksiyon silindi.

**Neden:** LTO referanssız görünen fonksiyonları, ISR'ları veya callback'leri dead code olarak siler.

```c
/* ISR'ları LTO'dan koru */
__attribute__((used, interrupt("IRQ")))
void USART1_IRQHandler(void) { /* ... */ }

/* HAL weak callback override — LTO ile bazen silinir */
__attribute__((used))
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) { /* ... */ }

/* Linker script: ISR vectorlerini tut */
/* Keil MDK: scatter file'da --keep=*.o(RESET) */
/* GCC: -Wl,--undefined=USART1_IRQHandler */
/* veya: linker flag -Wl,--keep-all-symbols */

/* CMakeLists.txt için */
target_link_options(app PRIVATE
    -Wl,--undefined=HardFault_Handler
    -Wl,--undefined=USART1_IRQHandler
    -Wl,--gc-sections   /* dead code elimination açık */
)
```

### LTO + Inline Assembly

```c
/* LTO ile inline asm fonksiyonlar bazen yanlış inline edilir */
/* Çözüm: noinline */
__attribute__((noinline)) void hard_fault_handler_c(uint32_t *sp) { }
__attribute__((noinline, used)) void delay_cycles(uint32_t n) {
    __asm volatile ("1: subs %0, #1 \n bne 1b" : "+r"(n));
}
```

---

## Kategori 5: Strict Aliasing İhlalleri

**Semptom:** Type-pun yapılan kod -O2'de yanlış çalışıyor; byte array'den float okumak bozuk veri döndürüyor.

**Neden:** GCC varsayılan olarak `-fstrict-aliasing` uygular; iki farklı pointer tipinin aynı belleği göstermediğini varsayar.

```c
/* YANLIŞ — undefined behavior, -O2'de yanlış sonuç */
float f = 3.14f;
uint32_t bits = *(uint32_t *)(&f);

/* DOĞRU — memcpy ile type-pun (derleyici optimize eder, UB yok) */
uint32_t bits;
memcpy(&bits, &f, 4);

/* DOĞRU — union ile (C99 izin verir) */
union { float f; uint32_t u; } conv;
conv.f = 3.14f;
uint32_t bits2 = conv.u;

/* Modbus / protocol byte extraction — doğru yol */
uint32_t from_be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16)
         | ((uint32_t)p[2] <<  8) |  (uint32_t)p[3];
}
```

**Compiler flag:** `-fno-strict-aliasing` eklemek yerine kodu düzelt — bu flag diğer optimizasyonları da kısar.

---

## Kategori 6: Struct Padding / Alignment Tuzakları

**Semptom:** Protokol paketi network/hardware ile uyumsuz; sizeof beklentiden büyük; DMA transfer boyutu yanlış.

```c
/* YANLIŞ — padding var, layout unspecified */
typedef struct {
    uint8_t  cmd;    /* +0 */
    /* 3 byte padding! */
    uint32_t addr;   /* +4 */
    uint16_t len;    /* +8 */
    /* 2 byte padding */
} Packet_t; /* sizeof = 12, istenen 7 */

/* DOĞRU */
typedef struct __attribute__((packed)) {
    uint8_t  cmd;    /* +0 */
    uint32_t addr;   /* +1 — unaligned, erişimde __UNALIGNED_UINT32 kullan */
    uint16_t len;    /* +5 */
} Packet_t; /* sizeof = 7 */

_Static_assert(sizeof(Packet_t) == 7, "Packet layout mismatch");

/* packed struct'tan aligned okuma */
uint32_t get_addr(const Packet_t *p)
{
    uint32_t v;
    memcpy(&v, &p->addr, 4); /* alignment-safe */
    return v;
}
/* veya CMSIS: __UNALIGNED_UINT32(ptr) */
```

---

## Kategori 7: Volatile + Optimizasyon Seviyesi Karışıklığı

**Tablo: optimizasyon seviyesine göre davranış farkları**

| Durum | -O0 | -O1 | -O2/-Os | Çözüm |
|-------|-----|-----|---------|-------|
| ISR shared var, volatile yok | Çalışır (şans) | Çalışır (şans) | Bozulur | `volatile` ekle |
| DMA buf, volatile var | Yavaş | Yavaş | Doğru | Volatile değil — barrier kullan |
| HAL callback overridden | Çalışır | Çalışır | Silinebilir | `__attribute__((used))` |
| Struct aliasing | Çalışır | Çalışır | Bozulur | `memcpy` veya `union` |
| Empty delay loop | Bekler | Silinir | Silinir | `__attribute__((optimize("O0")))` |
| ISR pointer, volatile yok | Çalışır | Çalışır | Kaybolur | `volatile` ekle |
| DMA cache boyut `n+32` | Çalışır | **Komşu veri bozulabilir** | **Bozulur** | `(n+31)&~31` formülü |
| ISR'da flag önce yazılır | Çalışır | **Bozulabilir** | **Bozulur** | `COMPILER_BARRIER()` ekle |

---

## Kategori 8: DMA Cache Boyut Formülü Hatası

**Semptom:** Büyük DMA transferlerinde (>~4KB) -O1/-O2'de veri bozulması. -O0'da her şey normal. FatFS, USB, Ethernet gibi protokol katmanlarında "sonraki işlem" bozulur — mevcut transfer başarılı görünür ama sonraki read/write hata verir.

**Neden:** `SCB_InvalidateDCache_by_Addr` / `SCB_CleanDCache_by_Addr` boyut parametresi yanlışsa komşu cache line'ı da etkiler.

```c
/* YANLIŞ — 32 eklemek kavramsal olarak mantıklı görünür ama hatalıdır */
SCB_InvalidateDCache_by_Addr((uint32_t *)rx_buf, total + 32);
/*
 * total = 4100 → total + 32 = 4132
 * 4132 / 32 = 129.125 → ceiling → 130 cache line → 4160 byte taranır
 * Buffer = 4128 byte → 4160 - 4128 = 32 byte aşılır
 * O 32 byte, buffer'ın hemen ardındaki veri — ör. FatFS internal buffer
 * DCIMVAC dirty line'ı write-back yapmadan atar → FatFS verisi kaybolur
 */

/* DOĞRU — 32-byte sınırına kadar yukarı yuvarla */
SCB_InvalidateDCache_by_Addr((uint32_t *)rx_buf, (int32_t)((total + 31U) & ~31U));
/*
 * total = 4100 → (4100 + 31) & ~31 = 4131 & 0xFFFFFFE0 = 4128
 * 4128 / 32 = 129 cache line — buffer sınırına tam oturur
 */

/* Aynı formül Clean için de geçerli */
SCB_CleanDCache_by_Addr((uint32_t *)tx_buf, (int32_t)((total + 31U) & ~31U));
```

**Kural:**
```c
/* Her zaman kullan — hem Clean hem Invalidate için */
#define DMA_CACHE_SIZE(n)  ((int32_t)(((n) + 31U) & ~31U))

SCB_CleanDCache_by_Addr((uint32_t *)tx_buf, DMA_CACHE_SIZE(tx_len));
SCB_InvalidateDCache_by_Addr((uint32_t *)rx_buf, DMA_CACHE_SIZE(rx_len));
```

**-O0 neden çalışır?**
- -O0: Compiler tüm değişkenleri register'a almaz → SRAM'a sık yazar → dirty cache line sayısı az
- Komşu 32-byte slot büyük ihtimalle clean → DCIMVAC etkisiz
- -O1+: Daha agresif register kullanımı → daha fazla dirty line → komşu slot da dirty → DCIMVAC siler → bozulma

---

## Kategori 9: ISR İçinde Veri/Flag Yeniden Sıralama

**Semptom:** ISR'dan task'a veri aktarımı -O2'de bozulmuş veri üretiyor. Flag=1 set ediliyor ama task okuyunca veri henüz hazır değil.

**Neden:** Compiler -O2'de `flag = 1` atamasını `memcpy(buf, data, len)` öncesine taşıyabilir — ikisi arasında bağımlılık görmez.

```c
/* YANLIŞ — ISR'da flag veri yazmadan önce set edilebilir */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    memcpy(shared.data, dma_rx_buf, DMA_LEN);  /* 1 */
    shared.flag = 1;                            /* 2 — compiler 1 ve 2'yi yer değiştirebilir! */
}

void rx_task(void *arg)
{
    if (shared.flag) {
        process(shared.data);   /* veri henüz hazır olmayabilir */
        shared.flag = 0;
    }
}

/* DOĞRU — COMPILER_BARRIER veri yazma ile flag arasına girer */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    memcpy(shared.data, dma_rx_buf, DMA_LEN);
    __asm__ volatile("" ::: "memory");  /* COMPILER_BARRIER: yazmaları tamamla */
    shared.flag = 1;
}

/* Flag da volatile olmalı — aksi halde task okuma optimize edilir */
volatile uint8_t flag;
```

**ISR → Task güvenli aktarım pattern:**

```c
/* En güvenli: RTOS primitive kullan — hem barrier hem volatile hem sinyal */

/* RTX5 / CMSIS-RTOS2 */
void HAL_SPI_RxCpltCallback(SPI_HandleTypeDef *hspi)
{
    /* Cache invalidate ÖNCE — ardından task'a sinyal */
    SCB_InvalidateDCache_by_Addr((uint32_t *)rx_buf, DMA_CACHE_SIZE(rx_len));
    osEventFlagsSet(spi_events, EVENT_RX_DONE);  /* barrier etkisi var */
}

/* FreeRTOS */
void HAL_SPI_RxCpltCallback(SPI_HandleTypeDef *hspi)
{
    SCB_InvalidateDCache_by_Addr((uint32_t *)rx_buf, DMA_CACHE_SIZE(rx_len));
    BaseType_t woken = pdFALSE;
    vTaskNotifyGiveFromISR(rx_task_handle, &woken);
    portYIELD_FROM_ISR(woken);
}
```

**Ring buffer index volatile zorunluluğu:**

```c
/* ISR'da yazılan, task'ta okunan her index/counter volatile olmalı */
static volatile uint8_t rx_head = 0;  /* ISR yazar */
static          uint8_t rx_tail = 0;  /* Task okur/yazar */

/* ISR */
void CAN_RxFifo0MsgPendingCallback(FDCAN_HandleTypeDef *hfdcan)
{
    HAL_FDCAN_GetRxMessage(hfdcan, FDCAN_RX_FIFO0, &hdr, buf);
    can_ring[rx_head] = ...; /* veri yaz */
    __asm__ volatile("" ::: "memory");
    rx_head = (rx_head + 1) % CAN_RING_SIZE;  /* volatile write */
}
```

---

## Diagnostic Flags (Build'e Ekle)

```makefile
# GCC: uyarıları hata olarak ele al
CFLAGS += -Wall -Wextra -Werror
CFLAGS += -Wcast-align          # unaligned cast uyarısı
CFLAGS += -Wstrict-aliasing=2   # aliasing ihlali uyarısı
CFLAGS += -Wshadow              # değişken gölgeleme
CFLAGS += -Wundef               # tanımsız macro kullanımı
CFLAGS += -fstack-usage         # .su dosyası üretir — stack analizi için

# Keil MDK / Arm Compiler 6:
# --diag_warning=111            # unreachable code
# --diag_warning=1296           # extended constant initializer
```

---

## Hızlı Kontrol Listesi — "Kod -O0'da çalışıyor ama -Os'ta bozuluyor"

```
1. ISR ile paylaşılan değişken → volatile ekli mi?
2. M7 DMA buffer → SCB_CleanDCache / SCB_InvalidateDCache var mı?
3. Peripheral enable sonrası → __DSB() var mı?
4. ISR handler → __attribute__((used)) var mı? LTO siliyor mu?
5. Type-pun (float↔uint32 vb.) → memcpy veya union kullanılıyor mu?
6. Struct packed → unaligned field erişimi memcpy ile mi yapılıyor?
7. Boş delay loop → silindi mi? DWT cycle counter kullan.
8. Sıra bağımlı işlemler (buffer doldur → DMA başlat) → COMPILER_BARRIER() var mı?
```
