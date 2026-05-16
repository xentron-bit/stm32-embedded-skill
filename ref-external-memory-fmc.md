# External Memory — FMC (SDRAM, SRAM) and OCTOSPI PSRAM

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, errata workarounds, protocol-spec content** here is authoritative — that is why this file exists.
> - **Inline HAL/CMSIS/peripheral code snippets** are illustrative. The HAL drifts between versions and parts. For the canonical version of any HAL symbol at your HAL release: `gh search code <SymbolName> --owner=STMicroelectronics --extension=c` — see [ref-st-github-map.md](ref-st-github-map.md) §8 for the full lookup procedure.
> - **CRITICAL bugs identified in the 2026-05-16 audit have been corrected** in this file, but verify against your own HAL version before copy-pasting.
> - **For bootloader / IAP / OTA topics** the canonical checklist + ARM KA001193 + AN5188/2606/3155/3156 references are in [ref-bootloader.md](ref-bootloader.md).


## FMC SDRAM Overview

```
STM32 FMC SDRAM banks:
  Bank 5: 0xC000_0000 (NE1/NE2)
  Bank 6: 0xD000_0000 (NE3/NE4)

Common SDRAM chips:
  W9825G6KH-6   — 32MB (256Mbit), x16, 166MHz
  MT48LC16M16A2 — 32MB (256Mbit), x16, 166MHz
  IS42S16400J   — 8MB  (64Mbit),  x16, 166MHz

FMC clock = HCLK/2 or HCLK/3 (via FMC_SDCR.SDCLK)
SDRAM timing parameters must be calculated from chip datasheet at operating clock.
```

## FMC SDRAM Init Sequence

```c
SDRAM_HandleTypeDef hsdram1;
FMC_SDRAM_TimingTypeDef SdramTiming = {0};

void MX_FMC_Init(void)
{
    /* W9825G6KH-6 at 100MHz FMC clock (HCLK=200MHz, SDCLK=HCLK/2) */
    hsdram1.Instance = FMC_SDRAM_DEVICE;
    hsdram1.Init.SDBank             = FMC_SDRAM_BANK1;
    hsdram1.Init.ColumnBitsNumber   = FMC_SDRAM_COLUMN_BITS_NUM_9;
    hsdram1.Init.RowBitsNumber      = FMC_SDRAM_ROW_BITS_NUM_13;
    hsdram1.Init.MemoryDataWidth    = FMC_SDRAM_MEM_BUS_WIDTH_16;
    hsdram1.Init.InternalBankNumber = FMC_SDRAM_INTERN_BANKS_NUM_4;
    hsdram1.Init.CASLatency         = FMC_SDRAM_CAS_LATENCY_3;
    hsdram1.Init.WriteProtection    = FMC_SDRAM_WRITE_PROTECTION_DISABLE;
    hsdram1.Init.SDClockPeriod      = FMC_SDRAM_CLOCK_PERIOD_2;   /* HCLK/2 */
    hsdram1.Init.ReadBurst          = FMC_SDRAM_RBURST_ENABLE;
    hsdram1.Init.ReadPipeDelay      = FMC_SDRAM_RPIPE_DELAY_0;

    /* Timing in FMC clock cycles (100MHz → 10ns per cycle) */
    SdramTiming.LoadToActiveDelay    = 2;   /* TMRD: 2 cycles */
    SdramTiming.ExitSelfRefreshDelay = 7;   /* TXSR: 70ns / 10 = 7 */
    SdramTiming.SelfRefreshTime      = 4;   /* TRAS: 42ns / 10 = 5 → 4 min */
    SdramTiming.RowCycleDelay        = 7;   /* TRC: 63ns / 10 = 7 */
    SdramTiming.WriteRecoveryTime    = 3;   /* TWR: 2 cycles min → 3 */
    SdramTiming.RPDelay              = 3;   /* TRP: 21ns / 10 = 3 */
    SdramTiming.RCDDelay             = 3;   /* TRCD: 21ns / 10 = 3 */

    HAL_SDRAM_Init(&hsdram1, &SdramTiming);

    /* SDRAM initialization sequence */
    sdram_init_sequence();
}
```

## SDRAM Initialization Sequence

```c
void sdram_init_sequence(void)
{
    FMC_SDRAM_CommandTypeDef cmd = {0};
    uint32_t tmpmrd;

    /* Step 1: Clock Configuration Enable */
    cmd.CommandMode            = FMC_SDRAM_CMD_CLK_ENABLE;
    cmd.CommandTarget          = FMC_SDRAM_CMD_TARGET_BANK1;
    cmd.AutoRefreshNumber      = 1;
    cmd.ModeRegisterDefinition = 0;
    HAL_SDRAM_SendCommand(&hsdram1, &cmd, 0xFFFF);
    HAL_Delay(1);  /* wait ≥ 100µs for power-up */

    /* Step 2: Precharge All */
    cmd.CommandMode = FMC_SDRAM_CMD_PALL;
    HAL_SDRAM_SendCommand(&hsdram1, &cmd, 0xFFFF);

    /* Step 3: Auto-Refresh (8 times) */
    cmd.CommandMode       = FMC_SDRAM_CMD_AUTOREFRESH_MODE;
    cmd.AutoRefreshNumber = 8;
    HAL_SDRAM_SendCommand(&hsdram1, &cmd, 0xFFFF);

    /* Step 4: Load Mode Register */
    /* Burst=1, Sequential, CAS Latency=3, Write Burst=Single */
    tmpmrd = (uint32_t)SDRAM_MODEREG_BURST_LENGTH_1
           | SDRAM_MODEREG_BURST_TYPE_SEQUENTIAL
           | SDRAM_MODEREG_CAS_LATENCY_3
           | SDRAM_MODEREG_OPERATING_MODE_STANDARD
           | SDRAM_MODEREG_WRITEBURST_MODE_SINGLE;

    cmd.CommandMode            = FMC_SDRAM_CMD_LOAD_MODE;
    cmd.AutoRefreshNumber      = 1;
    cmd.ModeRegisterDefinition = tmpmrd;
    HAL_SDRAM_SendCommand(&hsdram1, &cmd, 0xFFFF);

    /* Step 5: Set Refresh Rate */
    /* RefreshCount = ((RefreshPeriod_ms × FMC_clock_Hz) / (1000 × NumRows)) - 20 */
    /* W9825G6KH-6: 64ms refresh for 8192 rows at 100MHz:
       (64 × 100000000) / (1000 × 8192) - 20 = 781 - 20 = 761 */
    HAL_SDRAM_ProgramRefreshRate(&hsdram1, 761);
}
```

## Refresh Rate Formula

```
RefreshCount = (tREF_ms × FMC_CLK_MHz × 1000 / NUM_ROWS) - 20

Examples at 100MHz FMC clock:
  W9825G6KH-6  (tREF=64ms, 8192 rows):  (64×100000/8192) - 20 = 761
  MT48LC16M16  (tREF=64ms, 8192 rows):  (64×100000/8192) - 20 = 761
  IS42S16400J  (tREF=64ms, 4096 rows):  (64×100000/4096) - 20 = 1542

CRITICAL: Too slow refresh → data corruption (silent, intermittent, temperature-dependent)
```

## SDRAM Linker Section

```c
/* Linker script (GCC): */
MEMORY
{
    FLASH  (rx)  : ORIGIN = 0x08000000, LENGTH = 128K
    RAM    (rwx) : ORIGIN = 0x20000000, LENGTH = 512K
    SDRAM  (rwx) : ORIGIN = 0xC0000000, LENGTH = 32M
}

SECTIONS
{
    /* Normal sections in RAM/FLASH */

    .sdram (NOLOAD) :
    {
        . = ALIGN(4);
        _sdram_start = .;
        *(.sdram)
        *(.sdram*)
        . = ALIGN(4);
        _sdram_end = .;
    } >SDRAM
}
```

```c
/* Startup: zero-init SDRAM section after SDRAM init sequence */
/* In main() AFTER sdram_init_sequence() */
extern uint32_t _sdram_start;
extern uint32_t _sdram_end;
memset(&_sdram_start, 0, (uint8_t*)&_sdram_end - (uint8_t*)&_sdram_start);

/* Declare SDRAM variable */
uint8_t frame_buffer[800 * 480 * 2] __attribute__((section(".sdram")));
```

## MPU for SDRAM Cache Policy

```c
/* Option 1: Cached SDRAM (good performance, need clean/invalidate for DMA) */
MPU_Region_InitTypeDef mpu = {0};
HAL_MPU_Disable();
mpu.Enable           = MPU_REGION_ENABLE;
mpu.BaseAddress      = 0xC0000000;
mpu.Size             = MPU_REGION_SIZE_32MB;
mpu.AccessPermission = MPU_REGION_FULL_ACCESS;
mpu.IsBufferable     = MPU_ACCESS_BUFFERABLE;
mpu.IsCacheable      = MPU_ACCESS_CACHEABLE;
mpu.IsShareable      = MPU_ACCESS_NOT_SHAREABLE;
mpu.Number           = MPU_REGION_NUMBER1;
mpu.TypeExtField     = MPU_TEX_LEVEL1;     /* Normal, WB-WA */
mpu.SubRegionDisable = 0x00;
mpu.DisableExec      = MPU_INSTRUCTION_ACCESS_DISABLE;
HAL_MPU_ConfigRegion(&mpu);
HAL_MPU_Enable(MPU_PRIVILEGED_DEFAULT);

/* Option 2: Non-cached SDRAM (for DMA buffers, LTDC frame buffer) */
/* Same but: IsCacheable = MPU_ACCESS_NOT_CACHEABLE, TypeExtField = MPU_TEX_LEVEL1 */
/* No SCB_Clean/Invalidate needed, but slower CPU access */
```

## OCTOSPI PSRAM (APS6404L / LY68L6400)

```c
/* 64Mbit (8MB) PSRAM, Quad SPI, 84MHz max, memory-mapped mode */

OSPI_HandleTypeDef hospi1;

void psram_init(void)
{
    hospi1.Instance = OCTOSPI1;
    hospi1.Init.FifoThreshold      = 4;
    hospi1.Init.DualQuad            = HAL_OSPI_DUALQUAD_DISABLE;
    hospi1.Init.MemoryType          = HAL_OSPI_MEMTYPE_APMEMORY;  /* AP Memory (PSRAM) */
    hospi1.Init.DeviceSize          = 23;     /* 2^(23+1) = 16MB address space */
    hospi1.Init.ChipSelectHighTime  = 2;
    hospi1.Init.FreeRunningClock    = HAL_OSPI_FREERUNCLK_DISABLE;
    hospi1.Init.ClockMode           = HAL_OSPI_CLOCK_MODE_0;
    hospi1.Init.ClockPrescaler      = 4;      /* 120MHz/4 = 30MHz (conservative) */
    hospi1.Init.SampleShifting      = HAL_OSPI_SAMPLE_SHIFTING_NONE;
    hospi1.Init.DelayHoldQuarterCycle = HAL_OSPI_DHQC_DISABLE;
    HAL_OSPI_Init(&hospi1);

    /* Enter QPI mode (APS6404L: write 0x35 to Mode Register) */
    psram_enter_qpi();

    /* Configure memory-mapped mode */
    psram_enable_memmap();
}

void psram_enter_qpi(void)
{
    OSPI_RegularCmdTypeDef cmd = {0};
    cmd.OperationType     = HAL_OSPI_OPTYPE_COMMON_CFG;
    cmd.Instruction       = 0x35;   /* Enter QPI command */
    cmd.InstructionMode   = HAL_OSPI_INSTRUCTION_1_LINE;
    cmd.InstructionSize   = HAL_OSPI_INSTRUCTION_8_BITS;
    cmd.AddressMode       = HAL_OSPI_ADDRESS_NONE;
    cmd.DataMode          = HAL_OSPI_DATA_NONE;
    cmd.NbData            = 0;
    cmd.DummyCycles       = 0;
    HAL_OSPI_Command(&hospi1, &cmd, 100);
}

void psram_enable_memmap(void)
{
    OSPI_RegularCmdTypeDef cmd = {0};
    OSPI_MemoryMappedTypeDef memmap = {0};

    /* Read command in QPI mode */
    cmd.OperationType       = HAL_OSPI_OPTYPE_READ_CFG;
    cmd.Instruction         = 0xEB;   /* Fast Read Quad I/O */
    cmd.InstructionMode     = HAL_OSPI_INSTRUCTION_4_LINES;
    cmd.InstructionSize     = HAL_OSPI_INSTRUCTION_8_BITS;
    cmd.AddressMode         = HAL_OSPI_ADDRESS_4_LINES;
    cmd.AddressSize         = HAL_OSPI_ADDRESS_24_BITS;
    cmd.AlternateBytesMode  = HAL_OSPI_ALTERNATE_BYTES_4_LINES;
    cmd.AlternateBytes      = 0x00;
    cmd.AlternateBytesSize  = HAL_OSPI_ALTERNATE_BYTES_8_BITS;
    cmd.DummyCycles         = 6;
    cmd.DataMode            = HAL_OSPI_DATA_4_LINES;
    HAL_OSPI_Command(&hospi1, &cmd, 100);

    /* Write command in QPI mode */
    cmd.OperationType = HAL_OSPI_OPTYPE_WRITE_CFG;
    cmd.Instruction   = 0x38;   /* Quad Write */
    cmd.DummyCycles   = 0;
    HAL_OSPI_Command(&hospi1, &cmd, 100);

    memmap.TimeOutActivation = HAL_OSPI_TIMEOUT_COUNTER_DISABLE;
    HAL_OSPI_MemoryMapped(&hospi1, &memmap);
}
/* PSRAM now accessible at 0x90000000 (OCTOSPI1 base) */
```

## PSRAM vs SDRAM Comparison

| Feature | FMC SDRAM | OCTOSPI PSRAM |
|---------|-----------|----------------|
| Interface | Parallel (x16/x32) | Quad/Octal SPI |
| Typical size | 32–128 MB | 4–64 MB |
| Max speed (H7) | 100 MHz | 120 MHz |
| Refresh | Application must manage | Self-refreshing |
| Address pins | Many (A0–A12, BA0–BA1) | None (serial) |
| DMA access | Yes (AXI) | Yes (AXI via OCTOSPI) |
| XIP code | No | Yes |
| Power | Higher | Lower |
| PCB complexity | High | Low |

## Common Bugs

| Bug | Symptom | Fix |
|-----|---------|-----|
| Wrong RefreshCount | Intermittent data loss, especially at high temp | Recalculate formula, verify FMC clock |
| SDRAM in DTCM section | HardFault (SDRAM not in CPU address space) | Use `>SDRAM` in linker, 0xC0000000 |
| Missing MPU for cached SDRAM | DMA reads stale data | Add MPU non-cacheable or clean/invalidate |
| PSRAM DeviceSize wrong | Only partial memory accessible | DeviceSize = log2(total_bytes) - 1 |
| Address pin A10/BA0 swap | Half memory corrupted | Verify schematic pin mapping |
| CAS latency mismatch | Reads return wrong data | Match CASLatency in FMC init to Mode Register |
| SDRAM not zero-initialized | LTDC shows garbage on boot | memset SDRAM section after init sequence |
| FMC clock too high | Random errors, fails at temperature | Reduce FMC clock, check SDRAM speed grade |
