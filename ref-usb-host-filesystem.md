# USB Host + File System Reference — STM32

Covers: USB Host MSC (TinyUSB), FatFS (SDMMC + USB MSC), LittleFS (internal flash), RTOS-safe file I/O.  
Targets: H7, H7RS, U5, F7, L4 with USB HS/FS OTG peripheral.

---

## Contents

1. [USB Host — Architecture choices](#1-usb-host-architecture-choices)
2. [TinyUSB Host MSC](#2-tinyusb-host-msc)
3. [STM32 USB Host Library (Cube)](#3-stm32-usb-host-library-cube)
4. [FatFS — SDMMC](#4-fatfs--sdmmc)
5. [FatFS — USB MSC backend](#5-fatfs--usb-msc-backend)
6. [LittleFS — Internal Flash](#6-littlefs--internal-flash)
7. [RTOS-safe file I/O](#7-rtos-safe-file-io)
8. [USB Host + Filesystem Checklist](#8-checklist)

---

## 1. USB Host Architecture Choices

| Stack | Footprint | RTOS req. | Strengths |
|-------|-----------|-----------|-----------|
| TinyUSB (host) | ~30 KB flash | Optional (event-loop or RTOS task) | Modern, portable, well-maintained, BSD license |
| STM32 USB Host Library (Cube) | ~40 KB flash | FreeRTOS required (for HCD thread) | CubeMX integration, official ST support |
| LibUSB on RTOS | Large | Yes | Flexibility, not typical for bare-metal |

**Recommendation:** TinyUSB for new designs; Cube USB Host if already using CubeMX FreeRTOS.

---

## 2. TinyUSB Host MSC

### 2.1 Setup (CMakeLists / Makefile additions)

```cmake
# Add TinyUSB to project
add_subdirectory(tinyusb)
target_include_directories(firmware PRIVATE
    tinyusb/src
    tinyusb/src/class/msc
    tinyusb/src/host
)
target_sources(firmware PRIVATE
    tinyusb/src/tusb.c
    tinyusb/src/host/usbh.c
    tinyusb/src/class/msc/msh_host.c
    # Board port for STM32:
    tinyusb/src/portable/synopsys/dwc2/hcd_dwc2.c
)
```

### 2.2 tusb_config.h (host MSC only)

```c
#ifndef _TUSB_CONFIG_H_
#define _TUSB_CONFIG_H_

/* STM32H7 USB HS OTG — use HS port (480 Mbit/s) */
#define CFG_TUSB_MCU            OPT_MCU_STM32H7
#define CFG_TUSB_OS             OPT_OS_FREERTOS   /* or OPT_OS_NONE for bare-metal */
#define CFG_TUSB_DEBUG          0

/* Host only — no device */
#define CFG_TUH_ENABLED         1
#define CFG_TUD_ENABLED         0

/* USB HS controller index */
#define CFG_TUH_MAX_SPEED       OPT_MODE_HIGH_SPEED

/* MSC: 1 drive supported */
#define CFG_TUH_MSC             1
#define CFG_TUH_MSC_MAXLUN      4     /* max LUNs per device */

/* Hub support (optional — adds flash) */
#define CFG_TUH_HUB             0

/* Transfer buffers — DMA-aligned */
#define CFG_TUH_MEM_SECTION     __attribute__((section(".dma_buf")))
#define CFG_TUH_MEM_ALIGN       __attribute__((aligned(4)))

#endif
```

### 2.3 Board port — STM32H7 USB HS OTG clock + GPIO init

```c
/* Called by TinyUSB before stack init */
void board_init(void)
{
    /* Enable USB HS OTG clock */
    __HAL_RCC_USB_OTG_HS_CLK_ENABLE();
    __HAL_RCC_USB_OTG_HS_ULPI_CLK_ENABLE();

    /* USB FS (internal PHY, PA11/PA12) — for USB FS port */
    /* USB HS with external ULPI PHY: configure ULPI pins as AF */
    /* CubeMX generates this — copy USB_OTG_HS MspInit here */
}
```

### 2.4 Host main loop (bare-metal)

```c
int main(void)
{
    board_init();
    tusb_init();

    for (;;) {
        tuh_task();  /* drive USB host state machine */
        /* Application logic here, or yield to RTOS */
    }
}
```

### 2.5 MSC mount/unmount callbacks

```c
/* Called when USB drive is plugged and enumerated */
void tuh_msc_mount_cb(uint8_t dev_addr)
{
    uint8_t pdrv = 0;  /* FatFS physical drive number */
    /* Associate dev_addr with FatFS drive */
    disk_set_dev_addr(pdrv, dev_addr);

    FATFS fs;
    FRESULT fr = f_mount(&fs, "0:", 1);  /* mount immediately */
    if (fr != FR_OK) {
        log_error(ERR_USB_MOUNT_FAILED, (int)fr);
    } else {
        log_info("USB drive mounted");
        osEventFlagsSet(fs_events, FS_USB_MOUNTED);
    }
}

void tuh_msc_umount_cb(uint8_t dev_addr)
{
    f_unmount("0:");
    osEventFlagsSet(fs_events, FS_USB_UNMOUNTED);
    log_info("USB drive unmounted");
}
```

### 2.6 TinyUSB FatFS diskio backend

```c
/* diskio.c — bridge between FatFS and TinyUSB MSC */
#include "ff.h"
#include "diskio.h"
#include "tusb.h"

static uint8_t usb_dev_addr = 0xFF;
void disk_set_dev_addr(BYTE pdrv, uint8_t addr) { usb_dev_addr = addr; }

DSTATUS disk_status(BYTE pdrv)
{
    return (usb_dev_addr != 0xFF && tuh_msc_ready(usb_dev_addr)) ? 0 : STA_NOINIT;
}

DSTATUS disk_initialize(BYTE pdrv) { return disk_status(pdrv); }

DRESULT disk_read(BYTE pdrv, BYTE *buff, LBA_t sector, UINT count)
{
    /* TinyUSB MSC read — blocking */
    return tuh_msc_read10(usb_dev_addr, 0, buff, sector, (uint16_t)count)
           ? RES_OK : RES_ERROR;
}

DRESULT disk_write(BYTE pdrv, const BYTE *buff, LBA_t sector, UINT count)
{
    return tuh_msc_write10(usb_dev_addr, 0, buff, sector, (uint16_t)count)
           ? RES_OK : RES_ERROR;
}

DRESULT disk_ioctl(BYTE pdrv, BYTE cmd, void *buff)
{
    tuh_msc_inquiry_resp_t info;
    switch (cmd) {
        case CTRL_SYNC:   return RES_OK;
        case GET_SECTOR_COUNT: {
            uint32_t cnt = tuh_msc_get_block_count(usb_dev_addr, 0);
            *(LBA_t *)buff = cnt;
            return RES_OK;
        }
        case GET_SECTOR_SIZE: {
            *(WORD *)buff = (WORD)tuh_msc_get_block_size(usb_dev_addr, 0);
            return RES_OK;
        }
        case GET_BLOCK_SIZE: *(DWORD *)buff = 1; return RES_OK;
        default: return RES_PARERR;
    }
}
```

---

## 3. STM32 USB Host Library (Cube)

### 3.1 CubeMX setup

```
Middleware → USB_HOST
  Class: MSC (Mass Storage Class)
  Speed: HS (for H7 USB OTG HS) or FS
  FreeRTOS: enabled (USB Host task created automatically)
```

### 3.2 Application connection point

```c
/* USBH_USER_EventCallback — called by Cube USB Host middleware */
void USBH_UserProcess(USBH_HandleTypeDef *phost, uint8_t id)
{
    switch (id) {
        case HOST_USER_CONNECTION:
            break;
        case HOST_USER_DISCONNECTION:
            f_unmount("0:");
            break;
        case HOST_USER_CLASS_ACTIVE:
            /* MSC enumeration complete — mount FatFS */
            if (FATFS_LinkDriver(&USBH_Driver, USBHPath) == 0) {
                f_mount(&USBHFatFS, USBHPath, 1);
                log_info("USB MSC mounted via Cube");
            }
            break;
        case HOST_USER_CLASS_SELECTED:
            break;
    }
}
```

---

## 4. FatFS — SDMMC

### 4.1 SDMMC DMA-safe FatFS (H7)

```c
/* SD card via SDMMC1 — HAL + DMA + FatFS */
/* CubeMX: SDMMC1, 4-bit wide, DMA2 stream, FatFS middleware */

/* SD_Read/Write DMA buffers: must be in AXI SRAM (not DTCM) on H7 */
/* DTCM is not accessible by MDMA (which SDMMC uses on H7) */
/* Place buffers in .sdmmc_buf section → AXI SRAM (0x24000000 on H7) */

ALIGN_32BYTES(static uint8_t sd_work_buf[4096])
    __attribute__((section(".sdmmc_buf")));

/* linker script addition for H7: */
/*   .sdmmc_buf (NOLOAD) : { *(.sdmmc_buf) } > AXI_SRAM */

/* FatFS diskio.c for SDMMC: */
DRESULT disk_read(BYTE pdrv, BYTE *buff, LBA_t sector, UINT count)
{
    /* HAL_SD_ReadBlocks_DMA requires destination in non-cached or cache-cleaned region */
    HAL_StatusTypeDef r = HAL_SD_ReadBlocks_DMA(&hsd1,
        buff, (uint32_t)sector, (uint32_t)count);
    if (r != HAL_OK) return RES_ERROR;

    /* Wait for DMA completion (semaphore given in HAL callback) */
    if (osSemaphoreAcquire(sd_dma_done, 3000) != osOK) return RES_ERROR;

    /* Invalidate cache after DMA write to SRAM */
    SCB_InvalidateDCache_by_Addr((uint32_t *)buff,
        (int32_t)(count * 512));
    return RES_OK;
}
```

### 4.2 FatFS configuration (ffconf.h key settings)

```c
#define FF_FS_TINY       0    /* 0=normal, 1=tiny (smaller RAM, slower) */
#define FF_USE_LFN       1    /* Long file name support (LFN) */
#define FF_CODE_PAGE     850  /* or 932 for Japanese, 437 for US */
#define FF_VOLUMES       2    /* 0="0:" USB, 1="1:" SDMMC */
#define FF_USE_MKFS      1    /* enable f_mkfs() for formatting */
#define FF_FS_EXFAT      1    /* exFAT support (> 4GB files) */
#define FF_USE_FASTSEEK  1    /* fast seek (clst link map cache) */
#define FF_FS_LOCK       2    /* concurrent file lock entries */
#define FF_FS_REENTRANT  1    /* RTOS re-entrancy (requires ff_mutex) */
#define FF_SYNC_t        osMutexId_t   /* or SemaphoreHandle_t */
```

### 4.3 FatFS re-entrant mutex (RTOS) — ffsystem.c

```c
/* ffsystem.c — required when FF_FS_REENTRANT = 1 */
#include "ff.h"
#include "cmsis_os2.h"

static osMutexId_t ff_mutex[FF_VOLUMES];
static const osMutexAttr_t ff_mutex_attr = { "FatFS", osMutexRobust, NULL, 0 };

int ff_mutex_create(int vol)
{
    ff_mutex[vol] = osMutexNew(&ff_mutex_attr);
    return ff_mutex[vol] != NULL ? 1 : 0;
}

void ff_mutex_delete(int vol) { osMutexDelete(ff_mutex[vol]); }

int ff_mutex_take(int vol)
{
    return osMutexAcquire(ff_mutex[vol], osWaitForever) == osOK ? 1 : 0;
}

void ff_mutex_give(int vol) { osMutexRelease(ff_mutex[vol]); }
```

---

## 5. FatFS — USB MSC Backend

See [Section 2.6](#26-tinyusb-fatfs-diskio-backend) for the diskio.c implementation.

Multi-volume FatFS (USB MSC + SDMMC simultaneously):

```c
/* ffconf.h: FF_VOLUMES = 2 */
/* FATFS_LinkDriver(&USBH_Driver, "0:")   → USB MSC on drive 0 */
/* FATFS_LinkDriver(&SD_Driver,   "1:")   → SDMMC on drive 1 */

FATFS usb_fs, sd_fs;
f_mount(&usb_fs, "0:", 1);   /* mount USB */
f_mount(&sd_fs,  "1:", 1);   /* mount SD */

/* Copy file from USB to SD */
FIL src, dst;
f_open(&src, "0:/data.bin", FA_READ);
f_open(&dst, "1:/backup.bin", FA_WRITE | FA_CREATE_ALWAYS);

uint8_t buf[512];
UINT br, bw;
while (f_read(&src, buf, sizeof(buf), &br) == FR_OK && br > 0)
    f_write(&dst, buf, br, &bw);

f_close(&src);
f_close(&dst);
```

---

## 6. LittleFS — Internal Flash (wear-leveling)

Use LittleFS for storing configuration, logs, or calibration data in internal flash.  
LittleFS handles wear-leveling and power-loss recovery — FatFS does not.

### 6.1 LittleFS flash backend (H7 example — bank 2)

```c
#include "lfs.h"

/* Flash region for LittleFS: 512KB at end of bank 2 */
#define LFS_FLASH_BASE   0x081C0000U
#define LFS_FLASH_SIZE   (512 * 1024U)
#define LFS_BLOCK_SIZE   (128 * 1024U)   /* H7 sector size */
#define LFS_BLOCK_COUNT  (LFS_FLASH_SIZE / LFS_BLOCK_SIZE)

static int lfs_flash_read(const struct lfs_config *c, lfs_block_t block,
                           lfs_off_t off, void *buffer, lfs_size_t size)
{
    uint32_t addr = LFS_FLASH_BASE + block * LFS_BLOCK_SIZE + off;
    memcpy(buffer, (void *)addr, size);
    return LFS_ERR_OK;
}

static int lfs_flash_prog(const struct lfs_config *c, lfs_block_t block,
                           lfs_off_t off, const void *buffer, lfs_size_t size)
{
    uint32_t addr = LFS_FLASH_BASE + block * LFS_BLOCK_SIZE + off;
    HAL_FLASH_Unlock();
    /* H7: write in 32-byte words (flash word size = 256 bits) */
    for (uint32_t i = 0; i < size; i += 32) {
        HAL_FLASH_Program(FLASH_TYPEPROGRAM_FLASHWORD, addr + i,
                          (uint32_t)((uint8_t *)buffer + i));
    }
    HAL_FLASH_Lock();
    return LFS_ERR_OK;
}

static int lfs_flash_erase(const struct lfs_config *c, lfs_block_t block)
{
    FLASH_EraseInitTypeDef erase = {
        .TypeErase = FLASH_TYPEERASE_SECTORS,
        .Banks     = FLASH_BANK_2,
        .Sector    = /* calculate sector from block */ 0,
        .NbSectors = 1,
        .VoltageRange = FLASH_VOLTAGE_RANGE_3,
    };
    uint32_t err;
    HAL_FLASH_Unlock();
    HAL_FLASHEx_Erase(&erase, &err);
    HAL_FLASH_Lock();
    return (err == 0xFFFFFFFFU) ? LFS_ERR_OK : LFS_ERR_IO;
}

static int lfs_flash_sync(const struct lfs_config *c) { return LFS_ERR_OK; }

static const struct lfs_config lfs_cfg = {
    .read  = lfs_flash_read,
    .prog  = lfs_flash_prog,
    .erase = lfs_flash_erase,
    .sync  = lfs_flash_sync,
    .read_size      = 4,
    .prog_size      = 32,          /* H7 flash word = 256-bit */
    .block_size     = LFS_BLOCK_SIZE,
    .block_count    = LFS_BLOCK_COUNT,
    .cache_size     = 256,
    .lookahead_size = 16,
    .block_cycles   = 500,         /* wear-leveling cycles before move */
};
```

### 6.2 LittleFS init + read/write pattern

```c
static lfs_t lfs;
static lfs_file_t lfs_file;

void lfs_storage_init(void)
{
    /* Try mount; format on first boot or corruption */
    int err = lfs_mount(&lfs, &lfs_cfg);
    if (err < 0) {
        lfs_format(&lfs, &lfs_cfg);
        lfs_mount(&lfs, &lfs_cfg);
    }
}

/* Write configuration struct */
void lfs_write_config(const device_config_t *cfg)
{
    lfs_file_open(&lfs, &lfs_file, "config.bin",
                  LFS_O_WRONLY | LFS_O_CREAT | LFS_O_TRUNC);
    lfs_file_write(&lfs, &lfs_file, cfg, sizeof(*cfg));
    lfs_file_close(&lfs, &lfs_file);
}

bool lfs_read_config(device_config_t *cfg)
{
    if (lfs_file_open(&lfs, &lfs_file, "config.bin", LFS_O_RDONLY) < 0)
        return false;
    lfs_ssize_t r = lfs_file_read(&lfs, &lfs_file, cfg, sizeof(*cfg));
    lfs_file_close(&lfs, &lfs_file);
    return r == (lfs_ssize_t)sizeof(*cfg);
}
```

### 6.3 LittleFS for log rotation

```c
/* Append-only log with automatic roll-over at max size */
#define LOG_MAX_BYTES  (64 * 1024U)

void lfs_log_append(const log_entry_t *entry)
{
    lfs_file_open(&lfs, &lfs_file, "log.bin",
                  LFS_O_WRONLY | LFS_O_CREAT | LFS_O_APPEND);
    lfs_soff_t pos = lfs_file_tell(&lfs, &lfs_file);
    if (pos >= LOG_MAX_BYTES) {
        /* Roll over: truncate to last 50% */
        /* Simple strategy: delete and restart */
        lfs_file_close(&lfs, &lfs_file);
        lfs_remove(&lfs, "log.bin");
        lfs_file_open(&lfs, &lfs_file, "log.bin",
                      LFS_O_WRONLY | LFS_O_CREAT);
    }
    lfs_file_write(&lfs, &lfs_file, entry, sizeof(*entry));
    lfs_file_close(&lfs, &lfs_file);
}
```

---

## 7. RTOS-safe file I/O

### 7.1 Single file-system task pattern (recommended)

Never call `f_open`/`f_write`/`f_close` from multiple tasks directly, even with `FF_FS_REENTRANT`.  
Reason: FatFS re-entrancy protects the file system state, but does NOT prevent two tasks writing to the same file simultaneously.

```c
/* File system task: owns all FatFS operations */
typedef enum { FS_CMD_WRITE, FS_CMD_READ, FS_CMD_FLUSH } fs_cmd_type_t;

typedef struct {
    fs_cmd_type_t type;
    char          path[64];
    uint8_t      *buf;
    uint32_t      len;
    uint32_t      result_len;
    osSemaphoreId_t done_sem;  /* caller waits on this */
} fs_cmd_t;

static osMessageQueueId_t fs_queue;

void fs_task(void *arg)
{
    fs_cmd_t cmd;
    for (;;) {
        osMessageQueueGet(fs_queue, &cmd, NULL, osWaitForever);
        FIL fil;
        UINT bw;
        switch (cmd.type) {
            case FS_CMD_WRITE:
                f_open(&fil, cmd.path, FA_WRITE | FA_OPEN_APPEND);
                f_write(&fil, cmd.buf, cmd.len, &bw);
                f_close(&fil);
                cmd.result_len = bw;
                break;
            case FS_CMD_FLUSH:
                /* sync all open files */
                break;
        }
        osSemaphoreRelease(cmd.done_sem);
    }
}

/* Caller API — blocks until write completes */
bool fs_write_sync(const char *path, const uint8_t *data, uint32_t len)
{
    osSemaphoreId_t done = osSemaphoreNew(1, 0, NULL);
    fs_cmd_t cmd = { .type = FS_CMD_WRITE, .buf = data, .len = len, .done_sem = done };
    strncpy(cmd.path, path, sizeof(cmd.path) - 1);
    osMessageQueuePut(fs_queue, &cmd, 0, osWaitForever);
    bool ok = osSemaphoreAcquire(done, 5000) == osOK;
    osSemaphoreDelete(done);
    return ok && cmd.result_len == len;
}
```

### 7.2 Async write (fire-and-forget log)

```c
/* Fire-and-forget: caller doesn't wait — no done_sem */
bool fs_log_async(const log_entry_t *entry)
{
    static log_entry_t entry_copy;
    entry_copy = *entry;  /* copy before returning to caller */
    fs_cmd_t cmd = {
        .type = FS_CMD_WRITE,
        .buf  = (uint8_t *)&entry_copy,
        .len  = sizeof(log_entry_t),
        .done_sem = NULL,
    };
    strncpy(cmd.path, "1:/log.bin", sizeof(cmd.path) - 1);
    return osMessageQueuePut(fs_queue, &cmd, 0, 0) == osOK;
}
```

---

## 8. Checklist

### USB Host

- [ ] USB OTG GPIO configured correctly (AF10 on H7 for USB HS pins)
- [ ] USB HS external ULPI PHY: ULPI clock (60 MHz) stable before USB init
- [ ] VBUS power switch GPIO configured and driven HIGH before enumeration
- [ ] Overcurrent detection GPIO configured with interrupt
- [ ] `tuh_task()` / USB Host process task running continuously (not starved by high-prio tasks)
- [ ] MSC mount callback: FatFS f_mount called after `HOST_USER_CLASS_ACTIVE`
- [ ] MSC unmount callback: f_unmount + invalidate cached file handles

### FatFS

- [ ] `FF_FS_REENTRANT = 1` and `ff_mutex_*` implemented when multiple tasks access filesystem
- [ ] SDMMC DMA buffer in AXI SRAM (not DTCM) on H7 — MDMA cannot access DTCM
- [ ] `SCB_InvalidateDCache_by_Addr` after SDMMC DMA read completes (M7)
- [ ] `SCB_CleanDCache_by_Addr` before SDMMC DMA write (M7)
- [ ] `f_sync()` called periodically for write-heavy workloads (prevent data loss on power-off)
- [ ] `f_unmount()` called before USB unplug or SD removal
- [ ] `FF_USE_EXFAT = 1` for drives > 4GB (Windows default for large drives)
- [ ] `GET_SECTOR_SIZE` ioctl returns actual sector size (SDMMC: 512; some USB drives: 4096)

### LittleFS

- [ ] Flash region mapped to non-executable section (MPU: XN bit)
- [ ] `lfs_format` called only once on blank device — not on every boot
- [ ] `lfs_mount` fallback to format on error (corruption recovery)
- [ ] `block_cycles` set to appropriate value (NOR flash: 100,000+; internal H7 flash: 10,000)
- [ ] `prog_size` matches flash minimum write size (H7: 32 bytes = 256-bit word)
- [ ] LittleFS protected by mutex when accessed from multiple tasks
- [ ] File handles NOT shared between tasks without locking

### General

- [ ] Filesystem task is lowest priority of non-idle tasks (I/O doesn't block control loop)
- [ ] File write queue depth sized for burst writes (USB log upload: ≥ 16 entries)
- [ ] Power-fail safe: critical data written with `f_sync()` after every commit
