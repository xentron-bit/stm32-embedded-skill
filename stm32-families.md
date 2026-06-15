# STM32 Family Reference

> Source: https://github.com/STMicroelectronics — scraped May 2026

## Family Classification (ST Official)

### HAL1-Based — Mainstream
| Family | Core | Key Features | GitHub Cube | HAL Driver |
|---|---|---|---|---|
| STM32C0 | Cortex-M0+ | Entry-level, cost-optimized, 48MHz | [STM32CubeC0](https://github.com/STMicroelectronics/STM32CubeC0) | [stm32c0xx-hal-driver](https://github.com/STMicroelectronics/stm32c0xx-hal-driver) |
| STM32F0 | Cortex-M0  | Legacy mainstream, USB, 48MHz | [STM32CubeF0](https://github.com/STMicroelectronics/STM32CubeF0) | [stm32f0xx-hal-driver](https://github.com/STMicroelectronics/stm32f0xx-hal-driver) |
| STM32F1 | Cortex-M3  | Classic, CAN, USB, 72MHz | [STM32CubeF1](https://github.com/STMicroelectronics/STM32CubeF1) | [stm32f1xx-hal-driver](https://github.com/STMicroelectronics/stm32f1xx-hal-driver) |
| STM32F3 | Cortex-M4F | Mixed-signal, fast ADC, 72MHz | [STM32CubeF3](https://github.com/STMicroelectronics/STM32CubeF3) | [stm32f3xx-hal-driver](https://github.com/STMicroelectronics/stm32f3xx-hal-driver) |
| STM32G0 | Cortex-M0+ | Modern mainstream, UCPD, 64MHz | [STM32CubeG0](https://github.com/STMicroelectronics/STM32CubeG0) | [stm32g0xx-hal-driver](https://github.com/STMicroelectronics/stm32g0xx-hal-driver) |
| STM32G4 | Cortex-M4F | Advanced analog, HRTIM, FDCAN, 170MHz | [STM32CubeG4](https://github.com/STMicroelectronics/STM32CubeG4) | [stm32g4xx-hal-driver](https://github.com/STMicroelectronics/stm32g4xx-hal-driver) |

### HAL1-Based — High Performance
| Family | Core | Key Features | GitHub Cube | HAL Driver |
|---|---|---|---|---|
| STM32F2 | Cortex-M3  | Legacy HP, Ethernet, 120MHz | [STM32CubeF2](https://github.com/STMicroelectronics/STM32CubeF2) | [stm32f2xx-hal-driver](https://github.com/STMicroelectronics/stm32f2xx-hal-driver) |
| STM32F4 | Cortex-M4F | Workhorse, FPU, DSP, ETH (per-part: F401 84MHz; F405/407/415/417 168MHz; F411 100MHz; F412/413 100MHz; F427/429/439/446/469/479 180MHz) | [STM32CubeF4](https://github.com/STMicroelectronics/STM32CubeF4) | [stm32f4xx-hal-driver](https://github.com/STMicroelectronics/stm32f4xx-hal-driver) |
| STM32F7 | Cortex-M7  | D-cache, I-cache, 216MHz | [STM32CubeF7](https://github.com/STMicroelectronics/STM32CubeF7) | [stm32f7xx-hal-driver](https://github.com/STMicroelectronics/stm32f7xx-hal-driver) |
| STM32H5 | Cortex-M33 | TrustZone, FDCAN, ETH, 250MHz | [STM32CubeH5](https://github.com/STMicroelectronics/STM32CubeH5) | [stm32h5xx-hal-driver](https://github.com/STMicroelectronics/stm32h5xx-hal-driver) |
| STM32H7 | Cortex-M7  | Dual-core option (M7+M4), 480MHz, RAM per-part: H743/750/753 1MB; H723/725/733/735 564KB; H730 564KB; H7A3/B0/B3 1.4MB — check datasheet | [STM32CubeH7](https://github.com/STMicroelectronics/STM32CubeH7) | [stm32h7xx-hal-driver](https://github.com/STMicroelectronics/stm32h7xx-hal-driver) |
| STM32H7RS | Cortex-M7  | External PSRAM/Flash via XSPI, 600MHz | [STM32CubeH7RS](https://github.com/STMicroelectronics/STM32CubeH7RS) | [stm32h7rsxx-hal-driver](https://github.com/STMicroelectronics/stm32h7rsxx-hal-driver) |
| STM32N6 | Cortex-M55 | **NPU (NeuroPU 600 GOPS)**, Helium SIMD, 800MHz | [STM32CubeN6](https://github.com/STMicroelectronics/STM32CubeN6) | [stm32n6xx-hal-driver](https://github.com/STMicroelectronics/stm32n6xx-hal-driver) |

### HAL1-Based — Ultra-Low-Power
| Family | Core | Key Features | GitHub Cube | HAL Driver |
|---|---|---|---|---|
| STM32L0 | Cortex-M0+ | 130 nA stop, 32MHz | [STM32CubeL0](https://github.com/STMicroelectronics/STM32CubeL0) | [stm32l0xx-hal-driver](https://github.com/STMicroelectronics/stm32l0xx-hal-driver) |
| STM32L1 | Cortex-M3  | Multi-bank flash, LCD, 32MHz | [STM32CubeL1](https://github.com/STMicroelectronics/STM32CubeL1) | [stm32l1xx-hal-driver](https://github.com/STMicroelectronics/stm32l1xx-hal-driver) |
| STM32L4 | Cortex-M4F | 100 nA stop, FPU, USB, 80MHz | [STM32CubeL4](https://github.com/STMicroelectronics/STM32CubeL4) | [stm32l4xx-hal-driver](https://github.com/STMicroelectronics/stm32l4xx-hal-driver) |
| STM32L5 | Cortex-M33 | TrustZone, 110 nA stop, 110MHz | [STM32CubeL5](https://github.com/STMicroelectronics/STM32CubeL5) | [stm32l5xx-hal-driver](https://github.com/STMicroelectronics/stm32l5xx-hal-driver) |
| STM32U0 | Cortex-M0+ | Entry ULP, 30 nA stop, 56MHz | [STM32CubeU0](https://github.com/STMicroelectronics/STM32CubeU0) | [stm32u0xx-hal-driver](https://github.com/STMicroelectronics/stm32u0xx-hal-driver) |
| STM32U3 | Cortex-M33 | TrustZone ULP, LPBAM, 160MHz | [STM32CubeU3](https://github.com/STMicroelectronics/STM32CubeU3) | [stm32u3xx-hal-driver](https://github.com/STMicroelectronics/stm32u3xx-hal-driver) |
| STM32U5 | Cortex-M33 | TrustZone, LPBAM, 10 nA stop, 160MHz | [STM32CubeU5](https://github.com/STMicroelectronics/STM32CubeU5) | [stm32u5xx-hal-driver](https://github.com/STMicroelectronics/stm32u5xx-hal-driver) |

### HAL1-Based — Wireless (STM32)
| Family | Core | Radio | GitHub Cube | HAL Driver |
|---|---|---|---|---|
| STM32WB  | Cortex-M4 + M0+ | BLE 5.2 + 802.15.4, 64MHz | [STM32CubeWB](https://github.com/STMicroelectronics/STM32CubeWB) | [stm32wbxx-hal-driver](https://github.com/STMicroelectronics/stm32wbxx-hal-driver) |
| STM32WB0 | Cortex-M0+      | BLE 5.4, ultra-low-power | [STM32CubeWB0](https://github.com/STMicroelectronics/STM32CubeWB0) | [stm32wb0x-hal-driver](https://github.com/STMicroelectronics/stm32wb0x-hal-driver) |
| STM32WBA | Cortex-M33      | BLE 5.4, TrustZone, 100MHz | [STM32CubeWBA](https://github.com/STMicroelectronics/STM32CubeWBA) | [stm32wbaxx-hal-driver](https://github.com/STMicroelectronics/stm32wbaxx-hal-driver) |
| STM32WL  | Cortex-M4 + M0+ | Sub-GHz (LoRa/FSK), 48MHz | [STM32CubeWL](https://github.com/STMicroelectronics/STM32CubeWL) | [stm32wlxx-hal-driver](https://github.com/STMicroelectronics/stm32wlxx-hal-driver) |
| STM32WL3 | Cortex-M0+      | Sub-GHz ULP, 64MHz | [STM32CubeWL3](https://github.com/STMicroelectronics/STM32CubeWL3) | [stm32wl3x-hal-driver](https://github.com/STMicroelectronics/stm32wl3x-hal-driver) |

### BlueNRG Series (ST BLE SoC — STM32 değil, ayrı ürün ailesi)

> BlueNRG ailesi STM32 değildir — BLE odaklı bağımsız SoC'lar. Cortex-M0+ tabanlı, entegre RF, düşük güç. BLE stack radio CPU üzerinde koşar, ACI (HCI vendor extension) komutlarıyla kontrol edilir.

| Part | Core | Flash/RAM | BLE | PHY | Özellikler | SDK |
|------|------|-----------|-----|-----|------------|-----|
| **BlueNRG-355** | Cortex-M0+ 64MHz | 512KB / 64KB | 5.4 | 1M, **2M**, Coded | Extended Adv, LE Audio hazır, PKA, AES | [x-cube-blemgr](https://github.com/STMicroelectronics/x-cube-blemgr) |
| BlueNRG-LP | Cortex-M0+ 64MHz | 256KB / 64KB·32KB | **5.2** | 1M, 2M, Coded | Long Range, PKA, AES, ROM bootloader; → STM32WB0 | [STM32CubeWB0](https://github.com/STMicroelectronics/STM32CubeWB0) / legacy STSW-BNRGLP-DK |
| BlueNRG-LPS | Cortex-M0+ **64MHz** | 192KB / 24KB | **5.3** | 1M, 2M, Coded | Küçük paket, **AoA/AoD direction-finding**, ES0576 | [STM32CubeWB0](https://github.com/STMicroelectronics/STM32CubeWB0) / legacy STSW-BNRGLP-DK |
| BlueNRG-2 | Cortex-M0  | 256KB / 24KB | 5.0 | 1M sınırlı | Eski nesil | [x-cube-ble2](https://github.com/STMicroelectronics/x-cube-ble2) |

> **BlueNRG-LP / LPS (SoC katmanı):** part decode, bellek haritası (Flash @0x10040000), güç modları (DeepStop/Shutdown), radio/virtual timer, OTA, secure bootloader (SA0041), errata (ES0576), STM32WB0 eşlemesi → [ref-ble-bluenrg-lp.md](ref-ble-bluenrg-lp.md). BlueNRG-LP/LPS silikonu STM32 portföyüne **STM32WB0x** (WB05≈LPS, WB09≈LP) olarak taşınmıştır; yeni tasarımda `STM32CubeWB0` kullan.

**BlueNRG-355 Temel Farklar:**
- `aci_gap_set_extended_advertising_enable()` — Extended Advertising (BLE 5.0+)
- LE 2M PHY: `aci_le_set_phy()` ile 2 Mbps; teorik ~1.37 Mbps data throughput
- Coded PHY (S=2 veya S=8): uzun menzil, düşük hız
- MTU: HCI `ACI_ATT_EXCHANGE_MTU_REQ` + `aci_gatt_update_char_value_ext()` ile 247 byte payload
- `ACI_L2CAP_CONNECTION_PARAMETER_UPDATE_REQ` — bağlantı parametresi güncelleme
- BLE Manager middleware: `x-cube-blemgr` (referans: [ref-ble-bluenrg355.md](ref-ble-bluenrg355.md))

**HSE Kalibrasyon (BlueNRG-LP/355):**
```c
/* 32.768 kHz dış kristal veya HSE — BLE timing için ±20 ppm şart */
LL_RCC_HSE_SetCapacitorTuning(val);   /* 0-63 arası ayar */
aci_hal_tone_start(0x0, 0x0);         /* RF tone ile RF analyzer doğrulama */
```

---

## Core Architecture Quick Reference

| Core | FPU | DSP/SIMD | TrustZone | D-cache | Families |
|---|---|---|---|---|---|
| Cortex-M0/M0+ | No  | No  | No  | No  | F0, G0, C0, L0, U0, WB0, WL3 |
| Cortex-M3     | No  | No  | No  | No  | F1, F2, L1 |
| Cortex-M4F    | Yes | DSP | No  | No  | F3, F4, G4, L4, WB, WL |
| Cortex-M33    | Yes | DSP | **Yes** | No  | H5, L5, U3, U5, WBA |
| Cortex-M7     | Yes | DSP | No  | **Yes** | F7, H7, H7RS |
| Cortex-M55    | Yes | **Helium MVE** | **Yes** | **Yes** | N6 |

**Cache implications by core:**
- M0/M0+/M3/M4/M33: No D-cache → DMA can directly access SRAM without cache maintenance
- M7 (F7, H7, H7RS): D-cache enabled by default in CubeMX → **all DMA buffers need SCB_CleanDCache/InvalidateDCache**
- M55 (N6): D-cache + Helium → DMA coherency + SIMD-aware data alignment

---

## CMSIS Device Repositories (CMSIS headers, startup, linker)

| Series | CMSIS Device Repo |
|---|---|
| C0 | [cmsis-device-c0](https://github.com/STMicroelectronics/cmsis-device-c0) |
| F0 | [cmsis-device-f0](https://github.com/STMicroelectronics/cmsis-device-f0) |
| F1 | [cmsis-device-f1](https://github.com/STMicroelectronics/cmsis-device-f1) |
| F4 | [cmsis-device-f4](https://github.com/STMicroelectronics/cmsis-device-f4) |
| F7 | [cmsis-device-f7](https://github.com/STMicroelectronics/cmsis-device-f7) |
| G0 | [cmsis-device-g0](https://github.com/STMicroelectronics/cmsis-device-g0) |
| G4 | [cmsis-device-g4](https://github.com/STMicroelectronics/cmsis-device-g4) |
| H5 | [cmsis-device-h5](https://github.com/STMicroelectronics/cmsis-device-h5) |
| H7 | [cmsis-device-h7](https://github.com/STMicroelectronics/cmsis-device-h7) |
| H7RS | [cmsis-device-h7rs](https://github.com/STMicroelectronics/cmsis-device-h7rs) |
| L4 | [cmsis-device-l4](https://github.com/STMicroelectronics/cmsis-device-l4) |
| L5 | [cmsis-device-l5](https://github.com/STMicroelectronics/cmsis-device-l5) |
| N6 | [cmsis-device-n6](https://github.com/STMicroelectronics/cmsis-device-n6) |
| U0 | [cmsis-device-u0](https://github.com/STMicroelectronics/cmsis-device-u0) |
| U3 | [cmsis-device-u3](https://github.com/STMicroelectronics/cmsis-device-u3) |
| U5 | [cmsis-device-u5](https://github.com/STMicroelectronics/cmsis-device-u5) |
| WB | [cmsis-device-wb](https://github.com/STMicroelectronics/cmsis-device-wb) |
| WB0 | [cmsis-device-wb0](https://github.com/STMicroelectronics/cmsis-device-wb0) |
| WBA | [cmsis-device-wba](https://github.com/STMicroelectronics/cmsis-device-wba) |
| WL | [cmsis-device-wl](https://github.com/STMicroelectronics/cmsis-device-wl) |
| WL3 | [cmsis-device-wl3](https://github.com/STMicroelectronics/cmsis-device-wl3) |

---

## Middleware Repositories

| Middleware | GitHub Repo | Notes |
|---|---|---|
| FreeRTOS | [stm32-mw-freertos](https://github.com/STMicroelectronics/stm32-mw-freertos) | ST-maintained fork |
| Azure RTOS ThreadX | [stm32-mw-threadx](https://github.com/STMicroelectronics/stm32-mw-threadx) | CMSIS-RTOS2 via CMSIS-TX wrapper |
| NetX Duo | [stm32-mw-netxduo](https://github.com/STMicroelectronics/stm32-mw-netxduo) | |
| FileX | [stm32-mw-filex](https://github.com/STMicroelectronics/stm32-mw-filex) | Flash-aware FS |
| LevelX | [stm32-mw-levelx](https://github.com/STMicroelectronics/stm32-mw-levelx) | Flash wear leveling |
| USBX | [stm32-mw-usbx](https://github.com/STMicroelectronics/stm32-mw-usbx) | Azure RTOS USB |
| FatFS | [stm32-mw-fatfs](https://github.com/STMicroelectronics/stm32-mw-fatfs) | |
| USB Host | [stm32-mw-usb-host](https://github.com/STMicroelectronics/stm32-mw-usb-host) | |
| USB Device | [stm32-mw-usb-device](https://github.com/STMicroelectronics/stm32-mw-usb-device) | |
| LwIP | [stm32-mw-lwip](https://github.com/STMicroelectronics/stm32-mw-lwip) | |
| USBPD Core | [stm32-mw-usbpd-core](https://github.com/STMicroelectronics/stm32-mw-usbpd-core) | USB Power Delivery |
| CMSIS-RTOS2 TX wrap | [stm32-mw-cmsis-rtos-tx](https://github.com/STMicroelectronics/stm32-mw-cmsis-rtos-tx) | ThreadX CMSIS-RTOS2 API |
| Ext Memory Mgr | [stm32-mw-extmem-mgr](https://github.com/STMicroelectronics/stm32-mw-extmem-mgr) | H7RS/N6 external flash/RAM |
| External Mem Loader | [stm32-mw-extmem-ldr](https://github.com/STMicroelectronics/stm32-mw-extmem-ldr) | XIP loader for external flash |
| Touch Sensing | [stm32-mw-touchsensing](https://github.com/STMicroelectronics/stm32-mw-touchsensing) | |
| ISP | [stm32-mw-isp](https://github.com/STMicroelectronics/stm32-mw-isp) | N6 image signal processor |
| Camera | [stm32-mw-camera](https://github.com/STMicroelectronics/stm32-mw-camera) | |
| WPAN | [stm32-mw-wpan](https://github.com/STMicroelectronics/stm32-mw-wpan) | BLE / 802.15.4 stack |

---

## Keil RTX5 / CMSIS-RTX

- **Repository:** https://github.com/ARM-software/CMSIS-RTX
- **License:** Apache 2.0
- **API:** CMSIS-RTOS2 (native interface)
- **Documentation:** https://arm-software.github.io/CMSIS-RTX

### RTX_Config.h Key Parameters

```c
// RTX_Config.h — critical settings for STM32 projects

// Global heap (set to 0 for fully static allocation)
#define OS_DYNAMIC_MEM_SIZE    0        // RECOMMENDED: 0 for industrial

// Tick frequency (1ms default)
#define OS_TICK_FREQ           1000     // Hz

// Round-robin (disable in strict-priority systems)
#define OS_ROBIN_ENABLE        0        // 0 = strict priority (recommended for RT)
#define OS_ROBIN_TIMEOUT       5        // ticks (if enabled)

// Safety features (RTX Source variant required)
#define OS_SAFETY_FEATURES     1        // Enable for IEC 61508 / ISO 26262
#define OS_SAFETY_CLASS        1        // Class-based thread isolation
#define OS_EXECUTION_ZONE      1        // MPU spatial isolation
#define OS_THREAD_WATCHDOG     1        // Per-thread watchdog (osThreadFeedWatchdog)

// ISP (Idle, SVC, PendSV) stack sizes
#define OS_IDLE_THREAD_STACK_SIZE    256   // bytes
#define OS_TIMER_THREAD_STACK_SIZE   256   // bytes (if timers enabled)

// Thread stack watermark (debug builds only — runtime overhead)
#define OS_STACK_WATERMARK     1        // set 0 in production
```

### RTX5 vs FreeRTOS Differences on STM32

| Feature | Keil RTX5 / CMSIS-RTX | FreeRTOS |
|---|---|---|
| API | CMSIS-RTOS2 | FreeRTOS native + CMSIS wrapper |
| Static allocation | Default (no heap needed) | `configSUPPORT_STATIC_ALLOCATION=1` |
| ISR API naming | `osXxx()` — same API, RTX detects ISR context | `xXxxFromISR()` explicit |
| Strict priority | `OS_ROBIN_ENABLE=0` | Default |
| Per-thread watchdog | `osThreadFeedWatchdog()` (built-in) | Manual / 3rd party |
| MPU integration | `OS_EXECUTION_ZONE` | `configENABLE_MPU=1` (Cortex-M33) |
| Safety classes | `OS_SAFETY_CLASS` | Not built-in |
| Keil debugger | Native RTX Component Viewer | FreeRTOS plugin |
| Licensing | Keil MDK (commercial) or ARM pack | MIT |

### RTX5 ISR Pattern (CMSIS-RTOS2)

```c
// ISR → task: event flags (recommended over queue for single signals)
// osEventFlagsSet IS safe from ISR — RTX auto-detects ISR context
void USART2_IRQHandler(void)
{
    uint32_t sr = USART2->ISR;
    if (sr & USART_ISR_RXNE_RXFNE) {
        rx_byte = (uint8_t)USART2->RDR;
        osEventFlagsSet(uart_flags, FLAG_UART_RX);   // safe from ISR
    }
}

// ISR → task: message queue for data with payload
void FDCAN1_IT0_IRQHandler(void)
{
    if (HAL_FDCAN_GetRxFifoFillLevel(&hfdcan1, FDCAN_RX_FIFO0)) {
        FDCAN_RxHeaderTypeDef hdr;
        uint8_t data[64];
        HAL_FDCAN_GetRxMessage(&hfdcan1, FDCAN_RX_FIFO0, &hdr, data);
        can_msg_t msg = { .id = hdr.Identifier, .dlc = hdr.DataLength };
        memcpy(msg.data, data, msg.dlc);
        osMessageQueuePut(can_rx_queue, &msg, 0, 0);  // 0 timeout = ISR safe
    }
}
```

### RTX5 Thread Watchdog (OS_THREAD_WATCHDOG)

```c
// Per-thread deadline monitoring — built into RTX5 safety features
void ctrl_task(void *arg)
{
    // Set watchdog limit: if task doesn't call FeedWatchdog within 50ms → alarm
    osThreadFeedWatchdog(50);  // milliseconds

    for (;;) {
        // ... task work ...
        osThreadFeedWatchdog(50);  // reset deadline
        osDelay(10);
    }
}

// Application-level watchdog alarm handler (called by RTX kernel)
void osWatchdogAlarm_Handler(osThreadId_t thread_id)
{
    // Called when a thread misses its watchdog deadline
    log_fatal(FAULT_THREAD_DEADLINE, (uint32_t)thread_id);
    NVIC_SystemReset();  // or safe-state entry
}
```

---

## X-CUBE Expansion Packages for Industrial Use

| X-CUBE | Purpose | Supported Families |
|---|---|---|
| [x-cube-azrtos-h7](https://github.com/STMicroelectronics/x-cube-azrtos-h7) | Azure RTOS (ThreadX+FileX+NetX+USBX) | H7 |
| [x-cube-azrtos-g4](https://github.com/STMicroelectronics/x-cube-azrtos-g4) | Azure RTOS | G4 |
| [x-cube-azrtos-l5](https://github.com/STMicroelectronics/x-cube-azrtos-l5) | Azure RTOS | L5 |
| [x-cube-azrtos-f7](https://github.com/STMicroelectronics/x-cube-azrtos-f7) | Azure RTOS | F7 |
| [x-cube-azrtos-h7rs](https://github.com/STMicroelectronics/x-cube-azrtos-h7rs) | Azure RTOS | H7RS |
| [x-cube-freertos](https://github.com/STMicroelectronics/x-cube-freertos) | FreeRTOS expansion | Multiple |
| [x-cube-freertos-mpu](https://github.com/STMicroelectronics/x-cube-freertos-mpu) | FreeRTOS + MPU | M33 families |
| [x-cube-ispu](https://github.com/STMicroelectronics/x-cube-ispu) | Intelligent Sensor Processing Unit | MEMS with ISPU |
| [x-cube-mems1](https://github.com/STMicroelectronics/x-cube-mems1) | MEMS sensor drivers | Multiple |

---

## MEMS Sensor PID (Platform-Independent Drivers)

Full list: https://github.com/STMicroelectronics/STMems_Standard_C_drivers

Key sensors used in industrial applications:

| Sensor | Type | PID Repo |
|---|---|---|
| LSM6DSV | IMU (Accel+Gyro) + ISPU | [lsm6dsv-pid](https://github.com/STMicroelectronics/lsm6dsv-pid) |
| LSM6DSO | IMU | [lsm6dso-pid](not in list, use STMems_Standard_C_drivers) |
| LIS2DW12 | Accelerometer LP | [lis2dw12-pid](https://github.com/STMicroelectronics/lis2dw12-pid) |
| LIS2MDL | Magnetometer | [lis2mdl-pid](https://github.com/STMicroelectronics/lis2mdl-pid) |
| HTS221 | Humidity + Temp | [hts221-pid](https://github.com/STMicroelectronics/hts221-pid) |
| LPS22HH | Pressure | [lps22hh-pid](https://github.com/STMicroelectronics/lps22hh-pid) |
| LPS28DFW | Pressure (water-proof) | [lps28dfw-pid](https://github.com/STMicroelectronics/lps28dfw-pid) |

---

## Rust Drivers (emerging ecosystem)

ST has started publishing Rust embedded drivers:

| Driver | Repo |
|---|---|
| LSM6DSV (Rust) | [lsm6dsv-rs](https://github.com/STMicroelectronics/lsm6dsv-rs) |
| LIS2DUX12 (Rust) | [lis2dux12-rs](https://github.com/STMicroelectronics/lis2dux12-rs) |
| LPS22DF (Rust) | [lps22df-rs](https://github.com/STMicroelectronics/lps22df-rs) |
| st-mems-rust-drivers | [st-mems-rust-drivers](https://github.com/STMicroelectronics/st-mems-rust-drivers) |

---

## Developer Tools

| Tool | Repo |
|---|---|
| GNU Tools for STM32 (arm-none-eabi-gcc) | [gnu-tools-for-stm32](https://github.com/STMicroelectronics/gnu-tools-for-stm32) |
| STM32 Memory Loaders (external flash) | [stm32-memory-loaders](https://github.com/STMicroelectronics/stm32-memory-loaders) |
| stm32wrapper4dbg (debug wrapper) | [stm32wrapper4dbg](https://github.com/STMicroelectronics/stm32wrapper4dbg) |
| Open Pin Data (CubeMX pin DB) | [STM32_open_pin_data](https://github.com/STMicroelectronics/STM32_open_pin_data) |
| AI Model Zoo | [stm32ai-modelzoo](https://github.com/STMicroelectronics/stm32ai-modelzoo) |
