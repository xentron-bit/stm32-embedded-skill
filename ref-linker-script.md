# Linker Script and Scatter File — STM32

## GCC Linker Script Structure

```ld
/* STM32H730 — full memory map example */
MEMORY
{
    FLASH     (rx)  : ORIGIN = 0x08000000, LENGTH = 128K
    ITCMRAM   (rwx) : ORIGIN = 0x00000000, LENGTH = 64K    /* CPU-only, no DMA */
    DTCMRAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 128K   /* CPU-only, no DMA on H7 */
    RAM       (rwx) : ORIGIN = 0x24000000, LENGTH = 512K   /* AXI SRAM — DMA safe */
    RAM_D2    (rwx) : ORIGIN = 0x30000000, LENGTH = 288K   /* DMA1/DMA2/ETH accessible */
    RAM_D3    (rwx) : ORIGIN = 0x38000000, LENGTH = 64K    /* BDMA accessible */
    SDRAM     (rwx) : ORIGIN = 0xC0000000, LENGTH = 32M    /* FMC SDRAM Bank1 */
    OCTOSPI   (rx)  : ORIGIN = 0x90000000, LENGTH = 16M    /* XIP external flash */
}
```

## Standard Sections

```ld
SECTIONS
{
    /* Vector table — first in flash, KEEP prevents GC */
    .isr_vector :
    {
        . = ALIGN(4);
        KEEP(*(.isr_vector))
        . = ALIGN(4);
    } >FLASH

    /* Code + read-only data */
    .text :
    {
        . = ALIGN(4);
        *(.text)
        *(.text*)
        *(.glue_7)
        *(.glue_7t)
        KEEP(*(.init))
        KEEP(*(.fini))
        . = ALIGN(4);
        _etext = .;
    } >FLASH

    /* Read-only data in flash */
    .rodata :
    {
        . = ALIGN(4);
        *(.rodata)
        *(.rodata*)
        . = ALIGN(4);
    } >FLASH

    /* Initialized data — LMA=FLASH, VMA=RAM */
    /* _sidata = load address, _sdata/_edata = run address */
    .data :
    {
        . = ALIGN(4);
        _sdata = .;
        *(.data)
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } >RAM AT> FLASH   /* stored in FLASH, copied to RAM at startup */

    _sidata = LOADADDR(.data);   /* startup.s uses this to copy */

    /* Zero-initialized data — not stored in flash image */
    .bss :
    {
        . = ALIGN(4);
        _sbss = .;
        __bss_start__ = _sbss;
        *(.bss)
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
        __bss_end__ = _ebss;
    } >RAM

    /* Heap */
    ._user_heap_stack :
    {
        . = ALIGN(8);
        PROVIDE(end = .);
        PROVIDE(_end = .);
        . = . + _Min_Heap_Size;
        . = . + _Min_Stack_Size;
        . = ALIGN(8);
    } >RAM
}
```

## Custom STM32 Sections

```ld
    /* DTCM — fastest CPU access (F7/H7), NO DMA */
    .dtcm (NOLOAD) :
    {
        . = ALIGN(4);
        *(.dtcm)
        *(.dtcm*)
        . = ALIGN(4);
    } >DTCMRAM

    /* DMA-safe buffers — AXI SRAM, 32-byte aligned */
    .dma_buf (NOLOAD) :
    {
        . = ALIGN(32);
        *(.dma_buf)
        *(.dma_buf*)
        . = ALIGN(32);
    } >RAM

    /* ETH/LwIP non-cacheable region */
    .lwip_sec (NOLOAD) :
    {
        . = ALIGN(32);
        *(.lwip_sec)
        *(.lwip_sec*)
        . = ALIGN(32);
    } >RAM

    /* External SDRAM — large buffers, LTDC frame buffer */
    .sdram (NOLOAD) :
    {
        . = ALIGN(4);
        _sdram_start = .;
        *(.sdram)
        *(.sdram*)
        . = ALIGN(4);
        _sdram_end = .;
    } >SDRAM

    /* OCTOSPI PSRAM */
    .psram (NOLOAD) :
    {
        . = ALIGN(4);
        *(.psram)
        *(.psram*)
        . = ALIGN(4);
    } >OCTOSPI

    /* Backup SRAM — survives VBAT-only power, reset */
    .backup_sram (NOLOAD) :
    {
        . = ALIGN(4);
        *(.backup_sram)
        . = ALIGN(4);
    } >RAM_D3   /* BDMA-accessible on H7 */

    /* noinit — NOT zero-initialized, survives reset */
    /* Use for: boot counter, crash log, warm-reboot flags */
    .noinit (NOLOAD) :
    {
        . = ALIGN(4);
        *(.noinit)
        *(.noinit*)
        . = ALIGN(4);
    } >RAM
```

## Bootloader + Application Shared RAM

```ld
/* Fixed address for boot→app parameter passing */
/* Must be in NOLOAD section in BOTH bootloader and app linker scripts */

    .shared_ram (NOLOAD) :
    {
        . = ALIGN(4);
        KEEP(*(.shared_ram))
        . = ALIGN(4);
    } >DTCMRAM  /* or fixed address in RAM */

/* In C: */
```

```c
/* shared memory layout (same struct in bootloader AND app) */
typedef struct __attribute__((packed)) {
    uint32_t magic;           /* 0xB007C0DE = valid */
    uint32_t update_pending;  /* 1 = new firmware pending */
    uint32_t app_crc32;
    uint32_t boot_count;
    char     fw_version[16];
} shared_boot_t;

__attribute__((section(".shared_ram")))
volatile shared_boot_t shared_boot;

/* Bootloader sets: shared_boot.magic = 0xB007C0DE before jumping to app */
/* App reads:  if (shared_boot.magic == 0xB007C0DE) { use parameters } */
```

## Symbol Export to C

```ld
/* Linker exports symbols, C code uses extern declarations */
_sdram_start = ORIGIN(SDRAM);
_sdram_end   = ORIGIN(SDRAM) + LENGTH(SDRAM);
```

```c
/* In C: */
extern uint32_t _sdram_start;
extern uint32_t _sdram_end;
uint32_t sdram_size = (uint32_t)&_sdram_end - (uint32_t)&_sdram_start;
```

## Keil Scatter File (Keil MDK / AC6)

```
; STM32H730 scatter file
LR_FLASH 0x08000000 0x00020000  ; Load Region: 128KB flash
{
    ER_FLASH 0x08000000 0x00020000
    {
        *.o (RESET, +First)     ; ISR vector first
        *(InRoot$$Sections)
        .ANY (+RO)              ; all read-only
    }

    ; AXI SRAM — DMA safe, main RAM
    RW_RAM 0x24000000 0x00080000    ; 512KB
    {
        .ANY (+RW +ZI)
    }

    ; DMA buffers — AXI SRAM, 32-byte aligned
    RW_DMA 0x24070000 UNINIT 0x00010000
    {
        *(.dma_buf)
    }

    ; DTCM — fast, CPU-only, no DMA on H7
    RW_DTCM 0x20000000 UNINIT 0x00020000   ; 128KB
    {
        *(.dtcm)
    }

    ; noinit — survives reset
    RW_NOINIT 0x24060000 UNINIT 0x00010000
    {
        *(.noinit)
    }

    ; External SDRAM
    RW_SDRAM 0xC0000000 UNINIT 0x02000000  ; 32MB
    {
        *(.sdram)
    }
}
```

```c
/* Keil: place variable in scatter region */
uint8_t dma_buf[4096] __attribute__((section(".dma_buf"), aligned(32)));
uint8_t frame_buf[800*480*2] __attribute__((section(".sdram")));
```

## Map File Analysis

```bash
# After build, inspect .map file:

# Largest symbols (RAM usage)
grep " 0x" firmware.map | awk '{print $2, $1}' | sort -rn | head -20

# Unexpected large functions
grep "\.text\." firmware.map | sort -k2 -rn | head -20

# Dead code that survived (should be empty with --gc-sections)
arm-none-eabi-nm --size-sort build/firmware.elf | tail -30

# Linker GC report — see what was removed
# Add to CMakeLists.txt or Makefile:
# target_link_options(... PRIVATE -Wl,--print-gc-sections)
```

## Common Linker Mistakes

| Bug | Symptom | Fix |
|-----|---------|-----|
| `.data` without `AT> FLASH` | Initialized vars = 0 at startup | Add `AT> FLASH`, copy in startup.s |
| DMA buffer in DTCM | DMA transfer fails (H7) | Move to `.dma_buf` in AXI SRAM |
| Missing `KEEP` on ISR vector | Vector table GC'd with `-Wl,--gc-sections` | `KEEP(*(.isr_vector))` |
| Heap below stack (stack grows down) | Heap/stack collision | Place heap before stack in memory |
| `.noinit` in `.bss` section | Boot counter reset on every boot | Separate `.noinit` section with `NOLOAD` |
| Missing `ALIGN(32)` on DMA buffer | Cache line straddles → partial clean/invalidate corrupts adjacent | `__attribute__((aligned(32)))` AND linker align |
| SDRAM section has LMA | Binary too large (32MB in hex file) | Use `(NOLOAD)` for uninit external memory |
| App linker overlaps bootloader | Partial overwrite of bootloader on first flash | Set `ORIGIN(FLASH) = 0x08000000 + BOOT_SIZE` in app linker |
