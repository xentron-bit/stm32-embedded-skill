# Memory Optimization Reference

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
void paint_stack(void) {
    uint32_t sp; __asm("MOV %0, SP" : "=r"(sp));
    for (uint32_t a = sp; a < STACK_TOP; a += 4) *(uint32_t*)a = 0xDEADBEEF;
}
uint32_t stack_used(void) {
    uint32_t a = STACK_TOP - STACK_SIZE;
    while (*(uint32_t*)a == 0xDEADBEEF) a += 4;
    return STACK_TOP - a;
}
```

## Linker Script Essentials

```ld
MEMORY {
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 512K
    DTCM  (rwx) : ORIGIN = 0x20000000, LENGTH = 64K   /* M7: no cache, ISR use */
    AXI   (rwx) : ORIGIN = 0x24000000, LENGTH = 512K  /* M7: cached, DMA use */
}

SECTIONS {
    .dma_buf (NOLOAD) : { *(.dma_buf) } > AXI  /* 32B-aligned DMA buffers */
    .fast    (NOLOAD) : { *(.fast)    } > DTCM  /* ISR hot code */
}
```
