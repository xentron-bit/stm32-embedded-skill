# Memory Optimization Reference

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, errata workarounds, protocol-spec content** here is authoritative — that is why this file exists.
> - **Inline HAL/CMSIS/peripheral code snippets** are illustrative. The HAL drifts between versions and parts. For the canonical version of any HAL symbol at your HAL release: `gh search code <SymbolName> --owner=STMicroelectronics --extension=c` — see [ref-st-github-map.md](ref-st-github-map.md) §8 for the full lookup procedure.
> - **CRITICAL bugs identified in the 2026-05-16 audit have been corrected** in this file, but verify against your own HAL version before copy-pasting.
> - **For bootloader / IAP / OTA topics** the canonical checklist + ARM KA001193 + AN5188/2606/3155/3156 references are in [ref-bootloader.md](ref-bootloader.md).


## Compiler Flags

```makefile
CFLAGS += -Os -ffunction-sections -fdata-sections -flto
LDFLAGS += -Wl,--gc-sections
# Check result:
# arm-none-eabi-size build/firmware.elf
# arm-none-eabi-nm --size-sort --print-size build/firmware.elf | tail -20
```

## Flash vs RAM Placement

```c
const uint16_t sine_lut[360] = { ... };       // → .rodata (flash)
static uint8_t dma_buf[1024];                 // → .bss (RAM, no flash cost)
static uint8_t init_buf[64] = { 1, 2, 3 };   // → .data (flash + RAM both)
```

## Memory Pool (no-malloc fixed allocator)

```c
#define POOL_SIZE 10
typedef struct { uint8_t buf[64]; bool in_use; } MemBlock_t;
static MemBlock_t pool[POOL_SIZE];

MemBlock_t *AllocBlock(void) {
    for (int i = 0; i < POOL_SIZE; i++)
        if (!pool[i].in_use) { pool[i].in_use = true; return &pool[i]; }
    return NULL;
}
void FreeBlock(MemBlock_t *b) {
    if (b >= pool && b < pool + POOL_SIZE) b->in_use = false;
}
```

## Packed Structures

```c
typedef struct {
    uint32_t timestamp;
    uint16_t value;
    uint8_t  status;
    uint8_t  checksum;
} __attribute__((packed)) Record_t;  // 8B not 12B
_Static_assert(sizeof(Record_t) == 8, "check packing");
```

## Ring Buffer (power-of-2, no modulo)

```c
typedef struct { uint8_t buf[256]; uint8_t head, tail; } Ring_t;
void ring_put(Ring_t *r, uint8_t d) { r->buf[r->head++] = d; }  // wraps at 256
uint8_t ring_get(Ring_t *r)         { return r->buf[r->tail++]; }
```

## Stack Painting (HWM detection without RTOS)

```c
/* Cortex-M stack grows DOWNWARD. Paint the UNUSED portion (from STACK_BOTTOM
 * up to a safe margin below current SP) — NEVER paint from SP upward toward
 * STACK_TOP, which would overwrite live frames (return addresses!) and
 * crash on the next instruction.
 *
 * Call once from main() before tasks/ISRs use the stack significantly. */
extern uint32_t _estack;          /* linker symbol: STACK_TOP */
#define STACK_TOP    ((uint32_t)&_estack)
#define STACK_SIZE   0x4000U      /* must match linker */
#define STACK_BOTTOM (STACK_TOP - STACK_SIZE)

void paint_stack(void) {
    uint32_t sp; __asm volatile("MOV %0, SP" : "=r"(sp));
    /* Leave a 64-byte safety margin below current SP */
    for (uint32_t a = STACK_BOTTOM; a + 64U < sp; a += 4U) {
        *(volatile uint32_t *)a = 0xDEADBEEFU;
    }
}
uint32_t stack_used(void) {
    uint32_t a = STACK_BOTTOM;
    while (a < STACK_TOP && *(volatile uint32_t *)a == 0xDEADBEEFU) a += 4U;
    return STACK_TOP - a;
}
```

## Linker Script Essentials

```ld
/* Sizes below are STM32H7x3 (H743/H753/H750). Verify per part — H730 has
 * smaller AXI (320K), H7A3 has different layout. DTCM is 128K on the entire
 * H7 family; ITCM is 64K. DTCM is CPU-only — DMA1/DMA2 CANNOT access it
 * (only MDMA can). Put DMA buffers in AXI or D2 SRAM. */
MEMORY {
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 2048K
    ITCM  (rx)  : ORIGIN = 0x00000000, LENGTH = 64K   /* M7 ITCM */
    DTCM  (rwx) : ORIGIN = 0x20000000, LENGTH = 128K  /* M7 DTCM, CPU-only */
    AXI   (rwx) : ORIGIN = 0x24000000, LENGTH = 512K  /* cached, DMA OK via MDMA */
    D2_S1 (rwx) : ORIGIN = 0x30000000, LENGTH = 128K  /* DMA1/DMA2 accessible */
}

SECTIONS {
    .dma_buf (NOLOAD) : { *(.dma_buf) } > AXI  /* 32B-aligned DMA buffers */
    .fast    (NOLOAD) : { *(.fast)    } > DTCM  /* ISR hot code */
}
```

---

## Dynamic Memory — Ne Zaman Uygun?

### Genel Kural

```
Hard-RT görevler (ISR, kontrol döngüsü, watchdog):    malloc YOK
Init/startup aşaması (bir kez, boot sırasında):       GÜVENLİ
Büyük + ara sıra kullanılan buffer'lar:               DÜŞÜN
FreeRTOS/RTX5 RTOS task'ları:                         osMemoryPool tercih et
```

### Bellek Baskısı Durumunda Dynamic Allocation Öneri Kriterleri

```
RAM azalıyor (statik allocate > %80 RAM doldu) VE
  ↓
Aşağıdakilerden biri varsa dynamic allocation DÜŞÜNÜLEBİLİR:

1. Büyük ama sürekli kullanılmayan buffer'lar:
   - FatFS work area (4-8 KB) — sadece dosya işlemi süresince
   - JPEG/PNG decode buffer — sadece decode sırasında
   - USB host enum buffer — sadece enum sırasında
   - Protocol TX packet buffer — sadece TX sırasında

2. Sayısı çalışma zamanında belli olan struct'lar:
   - CAN filter table — filtre sayısı config dosyasından geliyorsa
   - Log record buffer — derinlik yapılandırılabilirse

3. Opsiyonel/koşullu özellikler:
   - Debug/trace buffer — yalnızca debug modda alloc et
```

### Güvenli Dynamic Allocation Örüntüleri

```c
/* ÖRÜNTÜ 1: Startup'ta bir kez alloc — asla free etme (statik gibi davran) */
static uint8_t *fatfs_work;

void storage_init(void)
{
    fatfs_work = malloc(FF_MAX_SS * 4);   /* 4 sektor buffer */
    if (fatfs_work == NULL) {
        /* Başlangıçta bile alloc başarısız → sistem kritik hata */
        Error_Handler();
    }
    /* fatfs_work artık uygulama boyunca geçerli, asla free edilmez */
}

/* ÖRÜNTÜ 2: Kısa ömürlü büyük buffer — göreve özel */
int32_t jpeg_decode_and_save(const uint8_t *jpeg, uint32_t jpeg_len)
{
    uint8_t *decode_buf = malloc(LCD_WIDTH * LCD_HEIGHT * 2);  /* 2 byte/pixel */
    if (decode_buf == NULL) {
        return -1;   /* hata — statik RAM yetmedi */
    }

    int32_t ret = jpeg_decode(jpeg, jpeg_len, decode_buf);
    if (ret == 0) {
        lcd_blit(decode_buf);
    }

    free(decode_buf);   /* decode bitti, geri ver */
    return ret;
}

/* ÖRÜNTÜ 3: RTX5 / FreeRTOS memory pool — heap yerine tercih et */
/* Sabit boyutlu bloklar → fragmentation yok */
static osMemoryPoolId_t packet_pool;

void comms_init(void)
{
    packet_pool = osMemoryPoolNew(8, sizeof(Packet_t), NULL);
}

Packet_t *comms_alloc_packet(void)
{
    return (Packet_t *)osMemoryPoolAlloc(packet_pool, 10U);  /* 10ms timeout */
}

void comms_free_packet(Packet_t *p)
{
    osMemoryPoolFree(packet_pool, p);
}
```

### Dynamic Allocation — Tehlikeler ve Önlemler

| Risk | Neden | Önlem |
|------|-------|-------|
| Fragmentation | Farklı boyutlarda alloc/free | Sabit boyutlu pool veya startup-only alloc |
| malloc NULL kontrolü atlanır | Hafıza dolu → dereference crash | MUTLAKA NULL kontrolü — `if (!ptr) Error_Handler()` |
| ISR içinde malloc | Heap mutex interrupt güvenli değil | ISR'da asla malloc |
| RTOS task'ta malloc + FreeRTOS heap | configSUPPORT_DYNAMIC_ALLOCATION = 0 ise çalışmaz | RTX5: OS_DYNAMIC_MEM_SIZE = 0 → statik zorla |
| free sonrası erişim (UAF) | Pointer sıfırlanmaz | `free(p); p = NULL;` |
| Double free | Aynı pointer iki kez free | `p = NULL` sonrası; pool allocator ile imkansız |

### Embedded Heap Alternatifleri

```c
/* 1. tlsf (Two-Level Segregated Fit) — O(1) malloc/free, az fragmentation */
/* Kaynak: https://github.com/mattconte/tlsf */
#include "tlsf.h"
tlsf_t heap = tlsf_create_with_pool(heap_buf, sizeof(heap_buf));
void *p = tlsf_malloc(heap, 256);
tlsf_free(heap, p);

/* 2. umm_malloc — küçük gömülü sistemler için */
/* Kaynak: https://github.com/rhempel/umm_malloc */

/* 3. FreeRTOS heap_4 — birleştiren (coallescing) heap */
/* pvPortMalloc / vPortFree kullan, NOT malloc/free */
void *p = pvPortMalloc(256);
vPortFree(p);

/* 4. STM32 HAL'de heap boyutu — startup_stm32xxx.s veya linker */
/* _Min_Heap_Size = 0x400; → linker script'te arttır */
```

### Ne Zaman Static Zorla Kalın?

```
□ Hard real-time garanti (motor kontrol, güvenlik watchdog)
□ < 32 KB RAM (statik profil her zaman deterministic)
□ Endüstriyel sertifikasyon (IEC 61508, ISO 26262 — malloc yasaklı)
□ RTOS_DYNAMIC_MEM_SIZE = 0 ile RTX5 heap'i kapalı ise
□ Fragmentation analizi yapılamıyorsa (uzun süreli çalışma)
```
