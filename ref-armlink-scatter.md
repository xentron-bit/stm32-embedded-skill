# ARM Linker (armlink) Scatter File — Complete Reference

Source: ARM Compiler armlink User Guide Version 5.06 (dui0474m) + Keil µVision Linker Dialog (uv4_dg_adsld)

---

## Overview

Scatter-loading gives you complete control over the grouping and placement of image components. Use it whenever the simple `--ro_base`/`--rw_base` command-line options are insufficient — e.g. multiple RAM regions, non-contiguous flash, TCM placement, DMA buffers, XIP external flash, overlays.

The linker requires two pieces of information:
1. **Grouping**: which code/data goes together into a region
2. **Placement**: where each group is placed in memory

Region-related linker-defined symbols (e.g. `Image$$RW_DMA$$Base`) are only generated when code references them.

---

## Keil µVision Linker Dialog Options (uv4_dg_adsld)

| Dialog field | armlink flag | Description |
|---|---|---|
| Use Memory Layout from Target Dialog | *(auto)* | When enabled, µVision generates the scatter file automatically from Target dialog. Disable to use a hand-written `.sct` file. |
| Make RW Sections Position Independent | `--rwpi` | Makes RW/ZI sections position-independent |
| Make RO Sections Position Independent | `--ropi` | Makes RO section position-independent |
| Don't Search Standard Libraries | `--noscanlib` | Same as `--no_scanlib` |
| Report 'might fail' Conditions as Errors | `--strict` | Promotes linker warnings to errors |
| X/O Base | `--xo_base=address` | Base address for execute-only (XO) execution region. Must be word-aligned. If not specified, no ER_XO is created. If XO sections exist without X/O Base, ER_XO is placed at R/O Base and ER_RO follows immediately. |
| R/O Base | `--ro_base=address` | Address for RO output section. Default: 0x8000. Also sets program entry address. |
| R/W Base | `--rw_base=address` | Address for RW/ZI sections. Does not affect XO section placement. |
| disable Warnings | `--diag_suppress=n,n,...` | Comma-separated warning numbers to suppress |
| Scatter File | *(path)* | Name of `.sct` file. Active only when "Use Memory Layout" is disabled. |
| Edit... | *(button)* | Opens scatter file in µVision editor |
| Misc Controls | *(text field)* | Additional linker commands without individual dialog controls |
| Linker control string | *(display)* | Shows current linker command-line constructed from dialog |

---

## BNF Notation (Table 8-1)

| Symbol | Meaning |
|---|---|
| `"x"` | Literal character (e.g. `"+"` means literal `+`) |
| `A ::= B` | A is defined as B |
| `[A]` | A is optional |
| `A+` | One or more occurrences of A |
| `A*` | Zero or more occurrences of A |
| `A \| B` | Either A or B, not both |
| `(A B)` | A and B grouped together |

---

## Scatter File Structure

```
scatter_file ::= load_region_description+
```

A scatter file contains **one or more load regions**. Each load region contains **one or more execution regions**.

```
LOAD_REGION_NAME  base_address  [attributes]  [max_size]
{
    EXEC_REGION_NAME  base_address  [attributes]  [max_size]
    {
        input_section_description*
    }
    ...
}
```

---

## Load Region Description

### Syntax (BNF)

```
load_region_description ::=
    load_region_name (base_address | ("+" offset)) [attribute_list] [max_size]
    "{"
        execution_region_description+
    "}"
```

### Parameters

| Parameter | Description |
|---|---|
| `load_region_name` | Names the load region. Quoted names allowed. Case-sensitive only if region-related linker symbols are used. |
| `base_address` | Address where objects are linked. Must satisfy alignment constraints. |
| `+offset` | Base address is `offset` bytes beyond end of preceding load region. `offset` must be zero mod 4. If first load region, base = `offset` from zero. May inherit attributes from previous region. |
| `attribute_list` | Controls properties of load region contents (see below) |
| `max_size` | Maximum size before decompression/ZI. armlink errors if region exceeds this. |

### Load Region Attributes

| Attribute | Description |
|---|---|
| `ABSOLUTE` | Content placed at fixed address. Default unless PI or RELOC. |
| `ALIGN alignment` | Increase alignment from 4 to `alignment` (positive power of 2). With `base_address`: address must be aligned. With `+offset`: linker aligns calculated base to boundary. Also affects offset in ELF file. Example: `FOO +4 ALIGN 4096` causes data to be written at 4K offset in ELF. |
| `NOCOMPRESS` | RW data compression is on by default. NOCOMPRESS prevents compression for this region. |
| `OVERLAY` | Multiple load regions at same address. ARM tools provide no overlay manager — you must supply your own. Content placed at fixed address. May overlap OVERLAY-designated regions. |
| `PI` | Position independent. Content does not depend on fixed address; can be moved post-link with no extra processing. Not supported if image contains execute-only sections. |
| `PROTECTED` | Prevents: (1) overlapping with other regions, (2) veneer sharing, (3) string sharing with `--merge`. |
| `RELOC` | Relocatable. Content depends on fixed addresses. Relocation info output to allow another tool to move it. |

---

## Execution Region Description

### Syntax (BNF)

```
execution_region_description ::=
    exec_region_name (base_address | "+" offset) [attribute_list] [max_size | [-]length]
    "{"
        input_section_description*
    "}"
```

### Parameters

| Parameter | Description |
|---|---|
| `exec_region_name` | Names the execution region. Quoted names allowed. Case-sensitive only if linker symbols used. |
| `base_address` | Address where objects are linked. Must be word-aligned. Note: ALIGN on exec region causes both load and execution address to be aligned. |
| `+offset` | Base = `offset` bytes beyond end of preceding execution region. Must be zero mod 4. First exec region in load region: base = `offset` from load region base. May inherit attributes from parent load region or previous exec region. |
| `attribute_list` | Controls properties (see below) |
| `max_size` | For EMPTY/FILL: interpreted as region length. Otherwise: maximum size — linker errors if exceeded. |
| `[-]length` | Only with EMPTY. Negative value means base_address is the end address (stack grows down). |

### Execution Region Attributes

| Attribute | Description |
|---|---|
| `ABSOLUTE` | Content placed at fixed execution address specified by base designator. |
| `ALIGN alignment` | Increase alignment from 4 to `alignment` (power of 2). Both load and execution address are aligned — can cause ELF padding. To align only execution address, use `AlignExpr()` on the base address instead. |
| `ALIGNALL value` | Increases alignment of all sections within the region. Value must be power of 2, >= 4. |
| `ANY_SIZE max_size` | Max size armlink can fill with unassigned sections (for `.ANY` selector). Cannot use `ImageLimit()` in the expression. Overrides `--any_contingency`. Restrictions: `max_size` <= region size; ignored on regions with no `.ANY` selector. |
| `EMPTY [-]length` | Reserves empty memory block of given size (heap or stack). No sections can be placed in an EMPTY region. Negative length: base_address is the end address (grows down). |
| `FILL value` | Creates a linker-generated region filled with `value`. Example: `FILL 0xFFFFFFFF`. Replaces the combination `EMPTY ZEROPAD PADVALUE`. |
| `FIXED` | Linker attempts to make execution address equal load address (root region). Error if impossible. Linker inserts padding. |
| `NOCOMPRESS` | RW data in this execution region must not be compressed in final image. |
| `OVERLAY` | Use for sections with overlaying address ranges. Consecutive execution regions with same `+offset` get same base address. Fixed address, may overlap other OVERLAY regions. |
| `PADVALUE value` | Value used for padding. Must be word-sized. Example: `EXEC 0x10000 PADVALUE 0xFFFFFFFF EMPTY ZEROPAD 0x2000` creates 0x2000 region filled with 0xFFFFFFFF. PADVALUE on load regions is ignored. |
| `PI` | Region contains only position-independent sections. Not supported with execute-only sections. |
| `SORTTYPE algorithm` | Sorting algorithm for region (e.g. `ER1 +0 SORTTYPE CallTree`). Overrides `--sort` command-line option. |
| `UNINIT` | For execution regions with uninitialized data or memory-mapped I/O. ARM Compiler does not support ECC/parity-protected memory that is not initialized. |
| `ZEROPAD` | ZI sections written as block of zeros in ELF — no runtime zeroing needed. Sets load length of ZI section to `Image$$region_name$$ZI$$Length`. Only root execution regions can use ZEROPAD; non-root: warning, attribute ignored. |

---

## Input Section Description

### Syntax (BNF)

```
input_section_description ::=
    module_select_pattern ["(" input_section_selector ("," input_section_selector)* ")"]

input_section_selector ::=
    "+" input_section_attr
    | input_section_pattern
    | input_symbol_pattern
    | section_properties
```

### module_select_pattern

Matches one of:
- Object file name
- Library member name (without path)
- Full library path name (with path)

Wildcards: `*` = zero or more chars, `?` = any single char. Case-insensitive on all hosts.

| Pattern | Matches |
|---|---|
| `*` | Any module or library (all objects and libraries) |
| `*.o` | Any object module |
| `math.o` | Specific object `math.o` |
| `*armlib*` | All ARM-supplied C libraries |
| `"file 1.o"` | Object with space in name |
| `*math.lib` | Any library path ending with `math.lib` |
| `.ANY` | Module selector — matches unassigned sections (lower precedence than `*`) |

**Rules:**
- Cannot have two `*` selectors in one scatter file
- Can use two modified selectors (e.g. `*A` and `*B`)
- Can combine `.ANY` with a `*` module selector; `*` has higher precedence
- Matching is not case-sensitive

### input_section_attr (after `+`)

Attribute selectors (case-insensitive):

| Selector | Meaning |
|---|---|
| `+RO-CODE` | Read-only code sections |
| `+RO-DATA` | Read-only data sections |
| `+RO` | All RO: both RO-CODE and RO-DATA |
| `+RW-CODE` | Read-write code |
| `+RW-DATA` | Read-write data |
| `+RW` | All RW: both RW-CODE and RW-DATA |
| `+XO` | Execute-only sections |
| `+ZI` | Zero-initialized sections |
| `+ENTRY` | Section containing an ENTRY point |

Synonyms:
| Alias | Equivalent |
|---|---|
| `+CODE` | `+RO-CODE` |
| `+CONST` | `+RO-DATA` |
| `+TEXT` | `+RO` |
| `+DATA` | `+RW` |
| `+BSS` | `+ZI` |

Pseudo-attributes (placement control):
| Pseudo | Meaning |
|---|---|
| `+FIRST` | Place this section first in the execution region |
| `+LAST` | Place this section last in the execution region |

**CAUTION:** FIRST/LAST must not violate basic attribute sorting order. For example, `FIRST RW` is placed after any RO-CODE or RO-DATA.

Only one FIRST or LAST per execution region. FIRST/LAST must follow a single `input_section_selector`:
```
*(section, +FIRST)    ; CORRECT
*(+FIRST, section)    ; INCORRECT — error
```

### input_section_pattern

Pattern matched case-insensitively against ELF section name. Wildcards `*` and `?` supported. Quoted names allowed.

Do not rely on compiler-generated section names — they can change between compilations and compiler versions.

### input_symbol_pattern

Selects input section by a global symbol it defines. Uses `:gdef:` prefix:

```
*(:gdef:mysym1)        ; section that defines global symbol mysym1
*(:gdef:mysym2)
```

Quoted symbol patterns supported; `:gdef:` can be inside or outside quotes.

### section_properties

Additional placement controls:
- `+FIRST` — as above
- `+LAST` — as above
- `OVERALIGN value` — value must be power of 2, >= 4

### Default Selector

If `(+input_section_attr)` and `(input_section_pattern)` are both omitted, the default is `+RO`.

Only sections matching **both** `module_select_pattern` **and** at least one `input_section_attr` or `input_section_pattern` are included.

---

## Module Selector Examples

```
*            ; all objects and libraries
*.o          ; all object files
math.o       ; specific object
*armlib*     ; all ARM C library members
"file 1.o"  ; object name with space
*math.lib   ; library path ending with math.lib
```

## Input Section Selector Examples

```
+RO          ; all RO code and RO data
+RW,+ZI      ; all RW code, RW data, and ZI data
BLOCK_42     ; sections named BLOCK_42 (all attributes)
```

---

## Complete Scatter File Example — Complex Memory Map (Two Load Regions)

From the ARM Compiler armlink User Guide:

```c
LOAD_ROM_1 0x0000              ; Start address for first load region (0x0000)
{
    EXEC_ROM_1 0x0000          ; Start address for first exec region (0x0000)
    {
        program1.o (+RO)       ; Place all code and RO data from program1.o
    }
    DRAM 0x18000 0x8000        ; Start address (0x18000), Max size (0x8000)
    {
        program1.o (+RW, +ZI)  ; Place all RW and ZI data from program1.o
    }
}
LOAD_ROM_2 0x4000              ; Start address for second load region (0x4000)
{
    EXEC_ROM_2 0x4000
    {
        program2.o (+RO)       ; Place all code and RO data from program2.o
    }
    SRAM 0x8000 0x8000
    {
        program2.o (+RW, +ZI)  ; Place all RW and ZI data from program2.o
    }
}
```

**CAUTION:** If you link an additional module not listed (e.g. `program3.o`), its placement is unspecified. Use `*` or `.ANY` to catch leftover sections.

---

## STM32 Scatter File Patterns

### STM32H7 — Multi-RAM with DMA Buffer Placement

```c
; STM32H743xI: 2MB Flash, 128KB DTCM, 512KB AXI SRAM, 128KB D2 SRAM1
LR_IROM1 0x08000000 0x00200000
{
    ; Flash: code and RO data
    ER_IROM1 0x08000000 0x00200000
    {
        *.o (RESET, +First)          ; vector table — always first
        *(InRoot$$Sections)          ; ARM runtime root sections
        .ANY (+RO)                   ; all remaining RO
    }

    ; DTCM (0x20000000, 128KB) — CPU-only, no DMA
    RW_IRAM1 0x20000000 0x00020000
    {
        .ANY (+RW +ZI)               ; default RW/ZI placement
    }

    ; AXI SRAM (0x24000000, 512KB) — accessible by DMA1/2 and MDMA
    RW_DMA 0x24000000 0x00080000
    {
        *(.dma_buffer)               ; __attribute__((section(".dma_buffer")))
    }

    ; D2 SRAM1 (0x30000000, 128KB) — DMA1/2 accessible
    RW_IRAM2 0x30000000 0x00020000
    {
        *(.d2_buffer)
    }
}
```

C side:
```c
/* DMA buffer — placed in AXI SRAM, 32-byte aligned for cache line */
__attribute__((section(".dma_buffer"), aligned(32)))
static uint8_t SPI_RxBuffer[4096];

__attribute__((section(".dma_buffer"), aligned(32)))
static uint8_t SPI_TxBuffer[4096];
```

### STM32H730/H750 — OCTOSPI XIP External Flash

```c
; STM32H730VBH6: 128KB internal flash (bootloader), OCTOSPI XIP at 0x90000000
LR_IROM1 0x08000000 0x00020000      ; internal flash (128KB)
{
    ER_IROM1 0x08000000 0x00020000
    {
        *.o (RESET, +First)
        *(InRoot$$Sections)
        bootloader.o (+RO)
        .ANY (+RO)
    }
    RW_IRAM1 0x20000000 0x00010000   ; 64KB DTCM
    {
        .ANY (+RW +ZI)
    }
}

LR_OSPI 0x90000000 0x01000000       ; OCTOSPI bank 1 (16MB XIP)
{
    ER_OSPI 0x90000000 0x01000000
    {
        application.o (+RO)
        .ANY (+RO)
    }
    RW_IRAM2 0x24000000 0x00050000   ; 320KB AXI SRAM
    {
        .ANY (+RW +ZI)
    }
}
```

### STM32F4/F7 — Basic Single Flash Layout

```c
LR_IROM1 0x08000000 0x00100000      ; 1MB flash
{
    ER_IROM1 0x08000000 0x00100000
    {
        *.o (RESET, +First)
        *(InRoot$$Sections)
        .ANY (+RO)
    }
    RW_IRAM1 0x20000000 0x00020000   ; 128KB SRAM
    {
        .ANY (+RW +ZI)
    }
}
```

### STM32G4 — CCM + SRAM

```c
; STM32G474RE: 512KB flash, 32KB CCM SRAM, 96KB SRAM
LR_IROM1 0x08000000 0x00080000
{
    ER_IROM1 0x08000000 0x00080000
    {
        *.o (RESET, +First)
        *(InRoot$$Sections)
        .ANY (+RO)
    }

    ; CCM SRAM — single-cycle access, no DMA
    RW_CCM 0x10000000 0x00008000
    {
        *(.ccmram)                   ; __attribute__((section(".ccmram")))
    }

    ; Main SRAM
    RW_IRAM1 0x20000000 0x00018000
    {
        .ANY (+RW +ZI)
    }
}
```

### Stack and Heap Regions (EMPTY)

```c
; Stack and heap defined as EMPTY regions
; Heap grows up, stack grows down

RW_IRAM1 0x20000000 0x00020000
{
    .ANY (+RW +ZI)
}

ARM_LIB_HEAP  0x20018000 EMPTY 0x4000   ; heap: 16KB
{
}

ARM_LIB_STACK 0x20020000 EMPTY -0x2000  ; stack: 8KB, grows down
{                                         ; base_address = end of stack
}
```

### Vector Table Keep Pattern

```c
ER_IROM1 0x08000000 0x00200000
{
    *.o (RESET, +First)     ; vector table first
    *(InRoot$$Sections)
    .ANY (+RO)
}
```

With linker misc control to prevent DCE removal:
```
--keep=*.o(RESET)
```

### XO (Execute-Only) Region Pattern

```c
; Execute-only regions: code can be fetched but data reads produce fault
; Used for security-sensitive code on ARMv8-M / Cortex-M33 targets

LR_IROM1 0x08000000 0x00200000
{
    ER_XO 0x08000000 0x00010000     ; execute-only code
    {
        secure_boot.o (+XO)
    }
    ER_RO 0x08010000 0x001F0000     ; normal RO
    {
        *(InRoot$$Sections)
        .ANY (+RO)
    }
    RW_IRAM1 0x20000000 0x00020000
    {
        .ANY (+RW +ZI)
    }
}
```

From dialog: set X/O Base to `--xo_base=0x08000000` and R/O Base to `--ro_base=0x08010000`.

---

## Linker-Defined Region Symbols

armlink generates these symbols when they are referenced. Pattern: `Image$$region_name$$qualifier`.

| Symbol | Value |
|---|---|
| `Image$$region$$Base` | Start address of execution region |
| `Image$$region$$Limit` | One past end of execution region |
| `Image$$region$$Length` | Byte length of execution region |
| `Image$$region$$ZI$$Base` | Start of ZI section in region |
| `Image$$region$$ZI$$Limit` | End of ZI section in region |
| `Image$$region$$ZI$$Length` | Length of ZI section |
| `Load$$region$$Base` | Start of region in load view |
| `Load$$LR$$load_region_name$$Base` | Load region start |
| `Load$$LR$$load_region_name$$Length` | Load region byte length |
| `Load$$LR$$load_region_name$$Limit` | One past end of load region |

Usage in C:
```c
extern uint32_t Image$$RW_DMA$$Base;
extern uint32_t Image$$RW_DMA$$Length;

/* Example: zero-init a region manually */
void init_dma_region(void)
{
    uint32_t *start = &Image$$RW_DMA$$Base;
    uint32_t len    = (uint32_t)&Image$$RW_DMA$$Length;
    memset(start, 0, len);
}
```

---

## .ANY Selector — Automatic Overflow Fill

`.ANY` is a special module selector that assigns unplaced sections. Priority is lower than `*`.

```c
; Two RAM regions — .ANY distributes overflow automatically
RW_IRAM1 0x20000000 0x00010000
{
    .ANY (+RW +ZI)                   ; fills IRAM1, overflows to IRAM2
}

RW_IRAM2 0x10000000 0x00008000
{
    .ANY (+RW +ZI)                   ; receives overflow from IRAM1
}
```

Control overflow limit with `ANY_SIZE`:
```c
RW_IRAM1 0x20000000 ANY_SIZE 0x8000 0x00010000
{
    .ANY (+RW +ZI)                   ; .ANY can use at most 0x8000 bytes here
}
```

---

## InRoot$$Sections

`InRoot$$Sections` is an ARM library section name that must be placed in a root execution region (a region where load address = execution address). Required for the runtime startup code that copies RW data and zeros ZI. Always place in the same load region as flash.

```c
ER_IROM1 0x08000000 0x00200000
{
    *.o (RESET, +First)
    *(InRoot$$Sections)          ; MUST be in root region (LMA = VMA)
    .ANY (+RO)
}
```

---

## Expression Evaluation in Scatter Files

Scatter files support C-style expressions for addresses and sizes.

Constants:
```
0x08000000   ; hex
131072       ; decimal
0200000      ; octal (leading 0)
```

Operators: `+  -  *  /  %  &  |  ^  ~  <<  >>  (  )`

Useful functions:
```
AlignExpr(expr, align)     ; rounds expr up to align boundary
ImageBase(region_name)     ; returns base of named execution region
ImageLimit(region_name)    ; returns limit of named execution region
ImageLength(region_name)   ; returns byte length of named execution region
LoadBase(region_name)      ; load address base
LoadLimit(region_name)     ; load address limit
```

Example — place RW immediately after RO without hardcoding address:
```c
LR_FLASH 0x08000000 0x00200000
{
    ER_RO 0x08000000 0x00200000
    {
        .ANY (+RO)
    }
    ER_RW 0x20000000 0x00020000
    {
        .ANY (+RW +ZI)
    }
}
```

Example — ALIGN to cache line using AlignExpr:
```c
ER_DATA AlignExpr(+0, 32) 0x00010000    ; execution addr aligned to 32B, load addr unaffected
{
    .ANY (+RW +ZI)
}
```

---

## Scatter File Preprocessing

armlink supports C preprocessor directives in scatter files when invoked with `--predefine` or by passing through the C preprocessor first.

```c
#define FLASH_BASE    0x08000000
#define FLASH_SIZE    0x00200000
#define SRAM_BASE     0x20000000
#define SRAM_SIZE     0x00020000

LR_IROM1 FLASH_BASE FLASH_SIZE
{
    ER_IROM1 FLASH_BASE FLASH_SIZE
    {
        *.o (RESET, +First)
        *(InRoot$$Sections)
        .ANY (+RO)
    }
    RW_IRAM1 SRAM_BASE SRAM_SIZE
    {
        .ANY (+RW +ZI)
    }
}
```

---

## Common Pitfalls

### 1. DTCM DMA Prohibition (STM32H7)

```
STM32H7 memory buses:
  DTCM  0x20000000  128KB  — CPU only (TCM bus). DMA CANNOT access this.
  AXI   0x24000000  512KB  — CPU + DMA1/2 + MDMA
  D2S1  0x30000000  128KB  — DMA1/2
  D2S2  0x30020000   32KB  — DMA1/2
  D3    0x38000000   16KB  — BDMA only (not DMA1/2)
```

If a DMA buffer is placed in DTCM, the DMA transaction silently fails or causes a bus fault HardFault. No compiler error.

### 2. InRoot$$Sections Not in Root Region

If `*(InRoot$$Sections)` is placed in a non-root execution region (where LMA != VMA), the C runtime copy-down code itself cannot be copied — the system hangs at startup before `main()`.

### 3. Missing +First for Vector Table

The vector table must be at offset 0 of the flash image. Without `(RESET, +First)`, the linker may place other sections before it. Result: invalid initial SP and PC — system faults before `main()`.

```c
*.o (RESET, +First)    ; mandatory — places startup_stm32xxxx.o RESET section first
```

### 4. Duplicate * Selectors

Two `*` selectors in one scatter file produce a linker error. Use `.ANY` for the secondary region, or use specific object/pattern selectors.

### 5. ZEROPAD on Non-Root Region

`ZEROPAD` is silently ignored on non-root execution regions. Only root regions (LMA = VMA) can use ZEROPAD.

### 6. ALIGN on Exec Region Pads ELF

`ALIGN` on an execution region aligns both load and execution addresses, inserting padding bytes into the ELF file. To align only the execution address (VMA), use `AlignExpr()` on the base address instead.

### 7. EMPTY Region Cannot Contain Sections

A region with `EMPTY` attribute cannot accept any input sections. It reserves memory only for heap/stack management by the C runtime.

---

## Quick Reference — Section Attribute Cheat Sheet

| C attribute | Scatter selector | Use case |
|---|---|---|
| No attribute (code) | `+RO-CODE` / `+RO` | Normal functions |
| `const` global | `+RO-DATA` / `+RO` | Read-only constants |
| `static`/global init | `+RW-DATA` / `+RW` | Initialized globals |
| Uninit global | `+ZI` / `+BSS` | Zero-initialized globals |
| `__attribute__((section(".dma_buffer")))` | `*(.dma_buffer)` | DMA buffers in specific RAM |
| `__attribute__((section(".ccmram")))` | `*(.ccmram)` | STM32 CCM fast RAM |
| `__attribute__((section(".dtcm")))` | `*(.dtcm)` | STM32H7 DTCM critical data |
| `__attribute__((section(".d3_buffer")))` | `*(.d3_buffer)` | BDMA-accessible D3 SRAM |

---

## Linker Misc Controls — Common Options

Entered in Keil Options → Linker → Misc controls field:

```
--keep=*.o(RESET)                  ; prevent DCE of vector table
--keep=*(.ARM.exidx)               ; keep exception index (if using exceptions)
--any_contingency                   ; reserve space for .ANY overflow
--sort=binding                      ; sort sections by binding (default)
--sort=callgraph                    ; sort by call graph for ICODE locality
--diag_suppress=L6314W             ; suppress "no section matches" warning
--diag_suppress=L6329W             ; suppress PI attribute mismatch
--list=image.map                   ; generate memory map file
--info=sizes,totals,unused         ; linker info output
--map                              ; generate full map in .map file
--symbols                          ; include symbol table in .map
```

---

## .map File Key Sections

The `.map` file (generated by `--map`) is essential for diagnosing placement issues:

```
Image component sizes     — per-object RO/RW/ZI breakdown
Memory Map of the image   — final load/exec address of every section
Image Symbol Table        — all symbols with addresses
```

Critical things to verify in the map:
1. `RESET` section at flash base (0x08000000 for most STM32)
2. `InRoot$$Sections` in the same load region as `RESET`
3. DMA buffers in correct RAM (AXI, not DTCM, for STM32H7)
4. No unexpected sections in wrong regions
5. Region sizes within `max_size` limits
