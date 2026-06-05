# STM32 RAM Maps + Per-Family Scatter / Linker Reference

> Verified RAM region maps (address + size + domain), DMA reachability, cache
> behavior, and ready Keil **armlink scatter** + GCC **`.ld` MEMORY** skeletons
> for **every STM32 family**. Companion to [ref-armlink-scatter.md](ref-armlink-scatter.md)
> (armlink syntax / `.ANY` priorities) and [ref-linker-script.md](ref-linker-script.md) (GCC).
>
> The deep STM32H730 worked example (TCM_AXI_SHARED, `.ANY3/2/1`, MPU non-cacheable
> DMA, UNINIT backup) lives in [ref-armlink-scatter.md](ref-armlink-scatter.md) §"STM32H730".
> This file is the **breadth** reference; that one is the H730 **depth** reference.

All base addresses/sizes verified against ST CMSIS device headers
(`STMicroelectronics/cmsis_device_*`) + reference manuals. Per-density sizes are
representative — confirm against the exact ordering-code datasheet before shipping.

---

## Universal rules (apply the right ones per core — don't copy blindly)

| Rule | Applies to |
|------|-----------|
| **L1 D-cache coherency** (MPU non-cacheable region *or* `SCB_CleanDCache`/`InvalidateDCache` around 32-byte-aligned DMA buffers) | **Cortex-M7 only** (F7, H7, H7RS). M0/M0+/M3/M4/M33 have **no core D-cache** → skip entirely |
| **TCM is peripheral-DMA-blind** (ITCM/DTCM unreachable by DMA1/2/BDMA; only **MDMA** reaches TCM via the M7 AHBS port) | All M7 with TCM |
| **CCM RAM (`0x10000000`)** is CPU-fast but **DMA-blind on F3/F4**; **DMA-reachable on G4 only via its `0x2000xxxx` alias** | F3, F4 (blind), G4 (alias-reachable) |
| **TrustZone secure/non-secure aliases** — secure code uses high aliases (FLASH `0x0C000000`, SRAM `0x30000000`); scatter base **must** match GTZC-MPCBB + SAU | M33: L5, U5, H5 (≥H523), WBA |
| **System DCACHE caches EXTERNAL memory only** (OCTOSPI/FMC @ `0x90000000`), never internal SRAM | U5, H5 (≥H523) |
| **XIP from external flash @ `0x90000000`** (load region = exec region, no copy) | Value lines: H730, H750, H7B0, H7S/H7R; F730/F750 |
| **Radio-shared SRAM** — wireless coprocessor owns part of SRAM2; app linker must stop at the boundary | WB, WBA, WL |

`.ANY` fill/priority mechanics (`.ANY3` fills first, `--any_placement`, `UNINIT`,
`*(STACK)`/`*(HEAP)` vs `ARM_LIB_STACK`) are in [ref-armlink-scatter.md](ref-armlink-scatter.md).

---

# Cortex-M7 — High Performance (D-cache present)

## STM32H7 value line (H730 / H750 / H7B0 / H7S·H7R)
Deep H730 example: see [ref-armlink-scatter.md](ref-armlink-scatter.md) §"STM32H730".
Key value-line trait: tiny internal flash → **XIP from OCTOSPI/XSPI @ 0x90000000**.

| Part | Internal flash | TCM | AXI-SRAM | D2/AHB SRAM | D3/SRD | Notes |
|------|---------------|-----|----------|-------------|--------|-------|
| H730 | 128 KB | ITCM 64K / DTCM 128K | 320 KB (TCM_AXI_SHARED) | 32 KB | SRAM4 16K + BKP 4K | XIP OCTOSPI |
| H750 | 128 KB | ITCM 64K / DTCM 128K | 512 KB | 288 KB | SRAM4 64K + BKP 4K | RAM == H743 |
| H7B0 | 128 KB | ITCM 64K / DTCM 128K | 1024 KB (3 banks) | 128 KB | SRD 32K + BKP 4K | XIP OCTOSPI1/2 |
| H7S3/S7, H7R3/R7 | H7S 64 KB / H7R **none** | ITCM/DTCM cfg 64–192K | ~455K usable (RAMCFG pool) | AHB 32 KB | BKP 4K | XSPI1 @0x90000000, XSPI2 @0x70000000, OTFDEC |

## STM32H743 / H753 — Cortex-M7 (16K I-cache / 16K D-cache)
| Region | Base | Size | Domain | DMA1/2 | MDMA | BDMA | Cacheable |
|---|---|---|---|---|---|---|---|
| ITCM | 0x00000000 | 64 KB | D1/CPU | ❌ | ✅(AHBS) | ❌ | ❌ |
| DTCM | 0x20000000 | 128 KB | D1/CPU | ❌ | ✅(AHBS) | ❌ | ❌ |
| AXI-SRAM | 0x24000000 | **512 KB** | D1 | ✅ | ✅ | ❌ | ✅ |
| SRAM1 | 0x30000000 | 128 KB | D2 | ✅ | ✅ | ❌ | ✅ |
| SRAM2 | 0x30020000 | 128 KB | D2 | ✅ | ✅ | ❌ | ✅ |
| SRAM3 | 0x30040000 | 32 KB | D2 | ✅ | ✅ | ❌ | ✅ |
| SRAM4 | 0x38000000 | 64 KB | D3 | ❌ | ✅ | ✅ | ✅ |
| Backup | 0x38800000 | 4 KB | D3/bkp | ❌ | ✅ | ✅ | ✅ |

**Rule:** M7 D-cache coherency on AXI/SRAM1-4 (MPU non-cacheable or clean/invalidate); TCM peripheral-DMA-blind (MDMA only). AXI = **512 KB** (vs H730's 320).
```c
LR_FLASH 0x08000000 0x00200000 {            ; 2 MB dual-bank
  ER_FLASH 0x08000000 0x00200000 { *.o (RESET, +First) *(InRoot$$Sections) .ANY (+RO) }
  RW_ITCM  0x00000000 0x00010000 { *(STACK) *(HEAP) .ANY3 (+RW +ZI) }   ; 64K ITCM
  RW_DTCM  0x20000000 0x00020000 { *(.dtcm) .ANY (+RW +ZI) }            ; 128K DTCM
  RW_AXI   0x24000000 0x00080000 { .ANY2 (+RW +ZI) }                    ; 512K AXI (cacheable)
  RW_DMA   0x30000000 UNINIT 0x00008000 { *(.dma_buffer) }              ; 32K D2 non-cacheable DMA
  RW_D2    0x30008000 0x00038000 { .ANY1 (+RW +ZI) }                    ; rest of D2 (SRAM1 tail+2+3)
  RW_D3    0x38000000 UNINIT 0x00010000 { *(.d3_sram) }                 ; 64K SRAM4 (BDMA)
  RW_BKP   0x38800000 UNINIT 0x00001000 { *(.backup_sram) }             ; 4K backup
}
```
```ld
MEMORY {
  FLASH(rx):ORIGIN=0x08000000,LENGTH=2048K   ITCMRAM(xrw):ORIGIN=0x00000000,LENGTH=64K
  DTCMRAM(xrw):ORIGIN=0x20000000,LENGTH=128K  RAM_D1(xrw):ORIGIN=0x24000000,LENGTH=512K
  RAM_D2(xrw):ORIGIN=0x30000000,LENGTH=288K   RAM_D3(xrw):ORIGIN=0x38000000,LENGTH=64K
  BKPSRAM(xrw):ORIGIN=0x38800000,LENGTH=4K }
```
**Gotchas:** keep DMA ring/descriptor buffers in D2 + non-cacheable; only BDMA services SRAM4/backup in Stop; D-cache+DMA on AXI is the #1 silent bug. Errata **ES0392**.

## STM32H742 — reduced-RAM H743
Same as H743 but **AXI = 384 KB**, D2 = 48 KB (SRAM1 32K @0x30000000 + SRAM2 16K @0x30008000, no SRAM3), SRAM4 64K, BKP 4K, flash 1 MB single-bank. Same M7 cache/DMA rules. Errata **ES0392**.

## STM32H745/755, H747/757 — dual-core M7 + M4
RAM identical to H743 (AXI 512K, D2 288K, SRAM4 64K). **Domain ownership:** CM7 boots Flash Bank1 @0x08000000; CM4 boots Bank2 @0x08100000, default RAM = **D2 AXISRAM aliased @0x10000000** (same cells as 0x30000000). ITCM/DTCM are **CM7-exclusive** (M4 can't address TCM). Shared inter-core buffers → D2 SRAM, **M7-MPU-non-cacheable** (M4 is cacheless), HSEM-guarded. Errata **ES0393**.
```c
LR_FLASH_CM7 0x08000000 0x00100000 {        ; CM7 = Bank1
  ER_FLASH 0x08000000 0x00100000 { *.o (RESET, +First) *(InRoot$$Sections) .ANY (+RO) }
  RW_ITCM  0x00000000 0x00010000 { *(STACK) *(HEAP) .ANY3 (+RW +ZI) }
  RW_DTCM  0x20000000 0x00020000 { .ANY (+RW +ZI) }
  RW_AXI   0x24000000 0x00080000 { .ANY2 (+RW +ZI) }
  RW_SHARED 0x30000000 UNINIT 0x00010000 { *(.shared_d2) }   ; inter-core, non-cacheable
  RW_D2    0x30010000 0x00030000 { .ANY1 (+RW +ZI) }
}
; CM4 image: separate scatter -> FLASH 0x08100000, RW @ 0x10000000 (D2 alias)
```

## STM32H7A3 / H7B3 / H7B0 — Cortex-M7, ~1.4 MB RAM (RM0455 CD/SRD naming)
| Region | Base | Size | Domain | DMA1/2 | MDMA | BDMA | Cacheable |
|---|---|---|---|---|---|---|---|
| ITCM | 0x00000000 | 64 KB | CD | ❌ | ✅ | ❌ | ❌ |
| DTCM | 0x20000000 | 128 KB | CD | ❌ | ✅ | ❌ | ❌ |
| AXI-SRAM1/2/3 | 0x24000000 / 0x24040000 / 0x240A0000 | 256K + 384K + 384K = **1024 KB** | CD/D1 | ✅ | ✅ | ❌ | ✅ |
| AHB SRAM1/2 | 0x30000000 / 0x30010000 | 64K + 64K | D2 | ✅ | ✅ | ❌ | ✅ |
| SRD SRAM | 0x38000000 | 32 KB | SRD/D3 | ❌ | ✅ | ✅ | ✅ |
| Backup | 0x38800000 | 4 KB | SRD | ❌ | ✅ | ✅ | ✅ |

**Rule:** three AXI banks are contiguous 0x24000000–0x24100000 (1 MB, treat as one cacheable region); two OCTOSPI ports (XIP @0x90000000 and @0x70000000). **H7B0 = value line** (128 KB flash → XIP like H750). SRD replaces D3; only BDMA in low-power. Errata **ES0455**.
```c
LR_FLASH 0x08000000 0x00200000 {            ; H7A3/B3 2 MB; H7B0 128K → use LR_XIP 0x90000000
  ER_FLASH 0x08000000 0x00200000 { *.o (RESET, +First) *(InRoot$$Sections) .ANY (+RO) }
  RW_ITCM  0x00000000 0x00010000 { *(STACK) *(HEAP) .ANY3 (+RW +ZI) }
  RW_DTCM  0x20000000 0x00020000 { .ANY (+RW +ZI) }
  RW_AXI   0x24000000 0x00100000 { .ANY2 (+RW +ZI) }            ; 1024K AXI-SRAM1+2+3
  RW_DMA   0x30000000 UNINIT 0x00010000 { *(.dma_buffer) }      ; 64K AHB SRAM1 non-cacheable
  RW_D2    0x30010000 0x00010000 { .ANY1 (+RW +ZI) }            ; 64K AHB SRAM2
  RW_D3    0x38000000 UNINIT 0x00008000 { *(.srd_sram) }        ; 32K SRD
  RW_BKP   0x38800000 UNINIT 0x00001000 { *(.backup_sram) }     ; 4K backup
}
```

---

# Cortex-M7 — Older (F7) + Cortex-M4/M3 (F4/F2)

## STM32F7 — Cortex-M7 (16K I / 16K D-cache)
| Region | Base | Size | DMA reach | Cacheable |
|---|---|---|---|---|
| ITCM | 0x00000000 | 16 KB | ❌ (MDMA only) | ❌ |
| DTCM | 0x20000000 | 64 KB (F74x/75x) / 128 KB (F76x/77x) | ❌ (MDMA only) | ❌ |
| SRAM1 | 0x20010000 (F74x) / 0x20020000 (F76x) | 240K / 368K | ✅ | ✅ |
| SRAM2 | (after SRAM1) | 16 KB | ✅ | ✅ |
| Backup | 0x40024000 | 4 KB | ✅ (BKP) | ✅ |

**Rule:** identical to H7 — D-cache coherency on SRAM1/2 (MPU non-cacheable or clean/invalidate, 32-byte aligned + 32-byte size); DTCM/ITCM peripheral-DMA-blind. SRAM1+SRAM2 contiguous → 256K (F74x/75x) or 384K (F76x/77x).
```c
; STM32F746 (DTCM 64K, SRAM1+2 = 256K)
LR_FLASH 0x08000000 0x00100000 {
  ER_VEC 0x08000000 { *.o (RESET, +First) }
  ER_ROM 0x08000200 0x000FFE00 { .ANY (+RO) }
  RW_DTCM 0x20000000 0x00010000 { *(.dtcm) .ANY (+RW +ZI) }   ; 64K DTCM (fast, no DMA)
  RW_SRAM 0x20010000 0x00040000 { .ANY (.sram) }              ; 256K SRAM1+2 (DMA-capable, cacheable)
  RW_DMA  0x20030000 UNINIT 0x00002000 { *(.dma_buffer) }     ; back with MPU non-cacheable
}
; F767/F777/F765: DTCM 128K, RAM ORIGIN 0x20020000 LENGTH 384K
```
**Gotchas:** SRAM1 base shifts with DTCM size (0x20010000 @64K vs 0x20020000 @128K); never put UART/SPI/ADC DMA buffers in DTCM. Errata ES0290 (F74x) / ES0334 (F76x).

## STM32F4 — Cortex-M4 (NO cache)
| Region | Base | Size | DMA reach | Note |
|---|---|---|---|---|
| **CCM RAM** | 0x10000000 | 64 KB (F405/7/27/29/37/39); none on F446/F412/F413/F411/F401 | **❌ DMA-BLIND** | CPU-only fast data |
| SRAM1 | 0x20000000 | 112 KB (most) / 256 KB (F412) | ✅ | |
| SRAM2 | 0x2001C000 | 16 KB (most); F413 64K @0x20040000 | ✅ | |
| SRAM3 | 0x20020000 | 64 KB (F427/29/37/39 only) | ✅ | |
| Backup | 0x40024000 | 4 KB | ✅ (BKP) | |

**Rule:** NO cache → never clean/invalidate; SRAM always coherent. The trap is the inverse of F7: **CCM @0x10000000 is invisible to every DMA** — use it for CPU-only data (stacks, DSP scratch), keep ALL DMA buffers in SRAM1/2/3. SRAM1/2(/3) contiguous (128K F40x/446, 192K F42x/43x, 256K F412, 320K F413).
```c
; STM32F407 (SRAM 128K, CCM 64K CPU-only)
LR_FLASH 0x08000000 0x00100000 {
  ER_VEC 0x08000000 { *.o (RESET, +First) }
  ER_ROM 0x08000200 0x000FFE00 { .ANY (+RO) }
  RW_SRAM 0x20000000 0x00020000 { .ANY (+RW +ZI) *(.dma_buffer) }   ; SRAM1+2, DMA-capable
  RW_CCM  0x10000000 0x00010000 { *(.ccmram) }                      ; 64K CPU-only — NO DMA here
}
```
**Gotchas:** CCM-DMA-blindness is the #1 F4 trap; don't port H7/F7 clean/invalidate (no cache). CCM presence varies by part. Errata e.g. ES0182 (F407), ES0206 (F429).

## STM32F2 — Cortex-M3 (NO cache, NO CCM)
SRAM1 112K @0x20000000 + SRAM2 16K @0x2001C000 = **128K flat**, fully DMA-coherent. Backup 4K @0x40024000. Simplest model — place data and DMA buffers anywhere. ART = flash prefetch only (not a data cache). Errata RM0033 / ES0005.
```c
LR_FLASH 0x08000000 0x00100000 {
  ER_VEC 0x08000000 { *.o (RESET, +First) }
  ER_ROM 0x08000200 0x000FFE00 { .ANY (+RO) }
  RW_SRAM 0x20000000 0x00020000 { .ANY (+RW +ZI) }   ; 128K flat
}
```

---

# Mainstream — M4 (CCM) / M0+ / M0 / M3 (no cache)

## STM32G4 — Cortex-M4 (NO cache); CCMSRAM **is** DMA-reachable (via 0x2000xxxx alias)
| Region | Base | Size (G474) | DMA reach |
|---|---|---|---|
| SRAM1 | 0x20000000 | 80 KB | ✅ |
| SRAM2 | 0x20014000 | 16 KB | ✅ |
| CCM (alias) | 0x20018000 (after SRAM2) | 32 KB | ✅ via this alias |
| CCM (CPU view) | 0x10000000 | 32 KB | ❌ at this address |

**Rule:** No cache. **G4 CCMSRAM is DMA-accessible — but ONLY through its `0x2000xxxx` mirror** (contiguous after SRAM2); the `0x10000000` view is CPU-only (opposite of F4). Bases shift per density (G431: SRAM1 16K/SRAM2 6K/CCM 10K; G491: 80K/16K/16K).
```c
; STM32G474xE (96K @0x20000000 + 32K CCM)
LR_IROM1 0x08000000 0x00080000 {
  ER_IROM1 0x08000000 0x00080000 { *.o (RESET, +First) *(InRoot$$Sections) .ANY (+RO) }
  RW_IRAM1 0x20000000 0x00018000 { .ANY (+RW +ZI) }   ; SRAM1+2 (DMA-safe)
  RW_CCM   0x10000000 0x00008000 { *(.ccmram) }       ; CPU-only view; for DMA-into-CCM use 0x20018000
}
```
Errata ES0430 (G431), ES0436 (G473/4), ES0507 (G491). RM0440.

## STM32F3 — Cortex-M4 (NO cache); CCM is **CPU-only, NO DMA** (like F4, unlike G4)
SRAM @0x20000000 (F303xE 64K, F334 12K, F373 32K) DMA-capable; **CCMSRAM @0x10000000** (F303xB/C 8K, xD/E 16K, F334 4K; **F373 has none**) is D-bus/CPU-only — **no DMA path of any kind**. Put DMA buffers only in main SRAM. Errata RM0316/RM0364/RM0313.
```c
; STM32F303xE (64K SRAM + 16K CCM)
LR_IROM1 0x08000000 0x00080000 {
  ER_IROM1 0x08000000 0x00080000 { *.o (RESET, +First) *(InRoot$$Sections) .ANY (+RO) }
  RW_IRAM1 0x20000000 0x00010000 { .ANY (+RW +ZI) }   ; 64K main SRAM (DMA-safe)
  RW_CCM   0x10000000 0x00004000 { *(.ccmram) }       ; 16K CPU-only — NO DMA. (F373: omit)
}
```

## STM32G0 / C0 / F0 / F1 — single linear SRAM, no cache, no CCM
| Family | Core | SRAM @0x20000000 | Flash @0x08000000 |
|---|---|---|---|
| G0 | M0+ | G030/031 8K · G070/071 36K · G0B1 up to 144K | 32K–512K |
| C0 | M0+ | C011 6K · C031 12K · C071 24K | 32K–128K |
| F0 | M0 | F030 4/8K · F051 8K · F072 16K · F091 32K | 16K–256K |
| F1 | M3 | F103 20–96K · F105/107 64K | 64K–1M |

**Rule:** No cache, no CCM, no DMA regioning — single DMA-capable SRAM. Simplest case; place everything in one region. (M3 has a 0x22000000 bit-band alias of the same RAM — not a separate region.)
```c
; e.g. STM32G071RB (36K) / F091 (32K) / F103xB (20K)
LR_IROM1 0x08000000 0x00020000 {
  ER_IROM1 0x08000000 0x00020000 { *.o (RESET, +First) *(InRoot$$Sections) .ANY (+RO) }
  RW_IRAM1 0x20000000 0x00009000 { .ANY (+RW +ZI) }   ; size per part
}
```
Errata: G0 ES0418/0419/0494 · C0 ES0560 · F0 ES0219/0124/0096/0228 · F1 ES0340/0220.

---

# Low Power — L0 / L1 / L4 / L4+ / L5 / U5

## STM32L0 (M0+) / L1 (M3) — single SRAM, no cache, no TrustZone
- **L0:** SRAM @0x20000000, 2–20 KB (L07x/L08x 20K, L05x 8K, L03x 8K); data EEPROM @0x08080000 (separate, not RAM). No MPU on Cat.1/2.
- **L1:** SRAM @0x20000000, 16–80 KB (xB 16K…xE 80K); bit-band @0x22000000; data EEPROM @0x08080000 up to 16K.

**Rule:** no D-cache, single DMA-coherent SRAM, no clean/invalidate, no regions.
```c
; STM32L073RZ (20K) / L152RE (80K)
LR_IROM1 0x08000000 0x00030000 {
  ER_IROM1 0x08000000 0x00030000 { *.o (RESET, +First) *(InRoot$$Sections) .ANY (+RO) }
  RW_IRAM1 0x20000000 0x00005000 { .ANY (+RW +ZI) }   ; size per part
}
```

## STM32L4 — Cortex-M4 (NO cache); SRAM2 parity + retention; no TrustZone
| Region | Base | Size (L476) | Note |
|---|---|---|---|
| SRAM1 | 0x20000000 | 96 KB | DMA-capable |
| SRAM2 (primary) | 0x10000000 | 32 KB | parity-checkable, retained |
| SRAM2 (alias) | 0x20018000 (L476) | 32 KB | contiguous with SRAM1 |

Per-part: L431/432 48K+16K · L452 128K+32K · L476 96K+32K · L496 256K+64K. **SRAM2 alias = SRAM1_BASE+SRAM1_SIZE — never assume 0x20020000.**
**Rule:** no D-cache; DMA coherent. SRAM2 hardware-parity (`SRAM2_PE` option byte → NMI/reset on error) + Standby-retained.
```c
; STM32L476RG (96K SRAM1 + 32K SRAM2)
LR_IROM1 0x08000000 0x00100000 {
  ER_IROM1 0x08000000 0x00100000 { *.o (RESET, +First) *(InRoot$$Sections) .ANY (+RO) }
  RW_IRAM1 0x20000000 0x00018000 { .ANY (+RW +ZI) }   ; 96K SRAM1
  RW_IRAM2 0x10000000 0x00008000 { *(.sram2) }        ; 32K SRAM2 (parity/retained)
}
```

## STM32L4+ (L4R5/L4S5/L4R9/L4S9) — Cortex-M4, large SRAM3
SRAM1 192K @0x20000000 + SRAM2 64K (@0x10000000, alias 0x20030000) + SRAM3 384K @0x20040000 = **640K linear** (0x20000000–0x2009FFFF). No D-cache. SRAM3 per-bank power-down in Stop (PWR SRAM3 bits) — don't keep DMA-active buffers in a powered-down bank. Errata ES0393.

## STM32L5 (L552/L562) — Cortex-M33 + TrustZone (ICACHE only)
| Region | Base NS | Base Secure | Size |
|---|---|---|---|
| SRAM1 | 0x20000000 | 0x30000000 | 192 KB |
| SRAM2 | 0x20030000 | 0x30030000 | 64 KB |
| FLASH | 0x08000000 | 0x0C000000 | up to 512 KB |

**Rule:** no L1 data cache (ICACHE = instruction only) → no SRAM maintenance. **TrustZone:** secure code uses 0x30000000/0x0C000000 aliases, NS uses 0x20000000/0x08000000; scatter base **must** match GTZC-MPCBB + SAU or SecureFault. SRAM1+SRAM2 contiguous (256K). Errata ES0448.
```c
; SECURE image (NS image is a separate project @0x08.../0x20...)
LR_IROM_S 0x0C000000 0x00040000 {
  ER_IROM_S 0x0C000000 0x00040000 { *.o (RESET, +First) *(InRoot$$Sections) .ANY (+RO) }
  RW_IRAM_S 0x30030000 0x00010000 { .ANY (+RW +ZI) }   ; 64K secure SRAM2 @secure alias
}
```

## STM32U5 — Cortex-M33 + TrustZone (ICACHE + DCACHE for EXTERNAL mem only)
| Region | Base NS | Base Secure | Size (U575/585) |
|---|---|---|---|
| SRAM1 | 0x20000000 | 0x30000000 | 192 KB |
| SRAM2 | 0x20030000 | 0x30030000 | 64 KB |
| SRAM3 | 0x20040000 | 0x30040000 | 512 KB |
| SRAM4 | 0x28000000 | 0x38000000 | 16 KB (SmartRun/SRD, low-power) |
| FLASH | 0x08000000 | 0x0C000000 | up to 2 MB |

**Big parts (U595/U5A5/U5F9/U5G9):** SRAM1=768K so offsets shift — SRAM2 0x200C0000, SRAM3 0x200D0000, SRAM5 0x201A0000 (832K), SRAM6 0x20270000 (512K, U5Fx/Gx). Totals: U575/585 784K; U595/5A5 ~2.5MB; U5Fx/Gx ~3MB. **Never hardcode 0x20030000 across the family.**
**Rule:** no core D-cache for SRAM. DCACHE1/2 cache **external memory only** (OCTOSPI/HSPI/FMC) — if you cache external RAM you must clean/invalidate on that region; internal SRAM never. TrustZone aliases as above. ECC on SRAM2/3/5/6 (`SRAMx_ECC` option byte) — ECC SRAM must be word-initialized before read. SRAM4 in SRD stays alive in Stop for autonomous GPDMA. Errata ES0499 (U575/585), ES0511 (U59x/5Ax), ES0561 (U5Fx/Gx), ES0535 (U535/545).
```c
; STM32U575ZI SECURE (784K SRAM1+2+3 contiguous @0x30000000)
LR_IROM_S 0x0C000000 0x00040000 {
  ER_IROM_S 0x0C000000 0x00040000 { *.o (RESET,+First) *(InRoot$$Sections) .ANY (+RO) }
  RW_IRAM_S 0x30000000 0x000C4000 { .ANY (+RW +ZI) }   ; 784K secure SRAM1+2+3
}
; SRAM4 @0x28000000(NS)/0x38000000(S) 16K low-power; ext-mem DCACHE optional.
```

---

# Wireless — H5 / WB / WBA / WL (radio-shared & TrustZone)

## STM32H5 — Cortex-M33 (ICACHE always; DCACHE = external-mem only on ≥H523; TrustZone except H503)
| Region | Base NS | Base Secure | Size (H563) |
|---|---|---|---|
| SRAM1 | 0x20000000 | 0x30000000 | 256 KB |
| SRAM2 | 0x20040000 | 0x30040000 | 64 KB |
| SRAM3 | 0x20050000 | 0x30050000 | 320 KB |
| FLASH | 0x08000000 | 0x0C000000 | up to 2 MB |

Totals: H503 32K · H523/533 272K · H562/563/573 **640K** (SRAM1+2+3 contiguous). BKPSRAM 4K (VBAT). **DCACHE is NOT a core D-cache** — caches OCTOSPI @0x90000000/FMC only; internal SRAM DMA buffers need no maintenance. **H503** = no DCACHE, no TrustZone (`__SAUREGION_PRESENT 0`). **ECC SRAM** (RAMCFG) must be word-initialized before read or NMI on double-error. Errata ES0566 (H563/573), ES0612 (H503). RM0481.
```c
; STM32H563 SECURE (640K SRAM @0x30000000)
LR_FLASH 0x0C000000 0x00200000 {
  ER_ROM 0x0C000000 0x00200000 { *.o (RESET, +First) *(InRoot$$Sections) .ANY (+RO) }
  RW_RAM 0x30000000 0x000A0000 { .ANY (+RW +ZI) }   ; SRAM1+2+3; enable RAMCFG ECC + zero-init first
}
```

## STM32WB — M4 (app CPU1) + M0+ (radio CPU2); SRAM2 SHARED with radio
| Region | Base | Size (WB55) | Owner |
|---|---|---|---|
| SRAM1 | 0x20000000 | 192 KB | CPU1 app (DMA-capable) |
| SRAM2a | 0x20030000 | 32 KB | **CPU2/radio** (IPCC mailbox + BLE stack) |
| SRAM2b | 0x20038000 | 32 KB | **CPU2/radio reserved** |

**Rule:** no cache (M4). **CRITICAL: SRAM2 (from 0x20030000) is owned by the M0+ radio CPU2.** The M4 app linker RAM must end at/below 0x20030000 (within SRAM1); only the agreed IPCC `MAPPING_TABLE`/`MB_MEM1/2` go into SRAM2a. Flash top is reserved for FUS + wireless stack. Errata ES0394. RM0434.
```c
; STM32WB55 CPU1/M4 app — RAM stops before 0x20030000
LR_FLASH 0x08000000 0x000C4000 {
  ER_ROM 0x08000000 0x000C4000 { *.o (RESET, +First) *(InRoot$$Sections) .ANY (+RO) }
  RW_RAM 0x20000008 0x0002FFF8 { .ANY (+RW +ZI) }   ; SRAM1, ends < 0x20030000 (+8 IPCC reserve)
}
RW_SHARED 0x20030000 UNINIT 0x00002800 { *(MAPPING_TABLE) *(MB_MEM1) *(MB_MEM2) }  ; handed to CPU2
```

## STM32WBA — Cortex-M33 single-core BLE/802.15.4; TrustZone; dedicated radio SRAM6
SRAM1 @0x20000000 (WBA52/55 64K, WBA62/65 448K) + SRAM2 @0x20010000/0x20070000 (64K, Standby-retained link-layer context) + **SRAM6 @0x48028000 (16K, 2.4 GHz RADIO TXRX)**. Secure aliases +0x10000000 (FLASH 0x0C000000, FLASH_NSC @ +0x7E000). No internal cache. Don't place app data in SRAM6 or clobber the retained SRAM2 stack slice. Errata ES0571/ES0573. RM0493.

## STM32WL — M4 (CPU1) + M0+ (CPU2 on WL5x); sub-GHz LoRa; SRAM split by option bytes
SRAM1 32K @0x20000000 + SRAM2 32K @0x20008000 = 64K total. **Single-core WLE5/WLE4** = all 64K to M4 (+ SRAM2 ICODE alias @0x10000000 for RAM-exec). **Dual-core WL55/WL54:** default split M4 = SRAM1 (0x20000000) + flash 0x08000000/128K; M0+ radio = **SRAM2 (0x20008000)** + flash 0x08020000/128K. **Boundaries set by option bytes SBRV/SBRSA/SNBRSA** — linker must match or CPU2 won't boot / silent corruption. Errata ES0506 (WL55), ES0500 (WLE5). RM0453/RM0461.
```c
; STM32WL55 CPU1/M4 — RAM stops at 0x20008000 (SRAM2 = CPU2 radio)
LR_FLASH 0x08000000 0x00020000 {
  ER_ROM 0x08000000 0x00020000 { *.o (RESET, +First) *(InRoot$$Sections) .ANY (+RO) }
  RW_RAM 0x20000000 0x00008000 { .ANY (+RW +ZI) }   ; SRAM1 32K — must end at 0x20008000
}
; CPU2/M0+ image: FLASH 0x08020000 / RAM 0x20008000 (per SBRV/SBRSA option bytes)
```

---

## Confidence & sources
All region bases/sizes verified against ST CMSIS device headers
(`cmsis_device_h7`, `_h7rs`, `_f7`, `_f4`, `_f2`, `_g4`, `_g0`, `_c0`, `_f0`,
`_f1`, `_f3`, `_l0`, `_l1`, `_l4`, `_l5`, `_u5`, `_h5`, `_wb`, `_wba`, `_wl`) and
RM0433/0399/0455/0477 (H7), RM0385/0410 (F7), RM0090 (F4), RM0033 (F2), RM0440
(G4), RM0444/0490/0091/0008/0316 (mainstream), RM0351/0432/0438/0456 (L4/L5/U5),
RM0481 (H5), RM0434/0493/0453/0461 (WB/WBA/WL), plus ST CubeIDE/MDK linker DB.
Per-density flash/RAM sizes and errata-sheet revisions are representative —
confirm against the exact ordering-code datasheet before shipping a linker file.
Items needing per-part RM verification: H7RS AXI-SRAM4 (72 KB) and RAMCFG-dependent
H7RS bank totals; U5 big-part offsets; exact silicon-rev errata IDs.
