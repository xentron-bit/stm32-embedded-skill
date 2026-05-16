# USB Device — STM32 (CDC-VCP, HID, DFU, Composite)

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, errata workarounds, protocol-spec content** here is authoritative — that is why this file exists.
> - **Inline HAL/CMSIS/peripheral code snippets** are illustrative. The HAL drifts between versions and parts. For the canonical version of any HAL symbol at your HAL release: `gh search code <SymbolName> --owner=STMicroelectronics --extension=c` — see [ref-st-github-map.md](ref-st-github-map.md) §8 for the full lookup procedure.
> - **CRITICAL bugs identified in the 2026-05-16 audit have been corrected** in this file, but verify against your own HAL version before copy-pasting.
> - **For bootloader / IAP / OTA topics** the canonical checklist + ARM KA001193 + AN5188/2606/3155/3156 references are in [ref-bootloader.md](ref-bootloader.md).


## USB Clock Requirements (CRITICAL)

```
USB Full Speed (12 Mbps) requires exact 48 MHz clock.
USB High Speed (480 Mbps) requires 60 MHz ULPI clock from external PHY.

STM32H7:
  FS: PLL3Q → 48 MHz (configure in SystemClock_Config)
  HS: external ULPI PHY (USB3320C) → 60 MHz ref from MCO2 or ULPI_CLK

STM32F4/F7:
  FS/HS: PLL48CLK → must be exactly 48 MHz
  Check: RCC_OscInitStruct.PLL.PLLQ = 48MHz_derivation

STM32G4 / L5 / U5:
  HSI48 + CRS (Clock Recovery System) for USB FS — no PLL needed
  CRS locks HSI48 to SOF packets from USB host
```

```c
/* STM32H7 — PLL3 for USB FS */
RCC_PeriphCLKInitTypeDef periph_clk = {0};
periph_clk.PeriphClockSelection = RCC_PERIPHCLK_USB;
periph_clk.UsbClockSelection    = RCC_USBCLKSOURCE_PLL3;
/* Ensure PLL3Q = 48 MHz */
HAL_RCCEx_PeriphCLKConfig(&periph_clk);
```

## USB OTG Init

```c
/* FS device (OTG_FS, embedded PHY, 12 Mbps) */
USBD_HandleTypeDef hUsbDeviceFS;

void usb_device_init(void)
{
    USBD_Init(&hUsbDeviceFS, &FS_Desc, DEVICE_FS);
    USBD_RegisterClass(&hUsbDeviceFS, &USBD_CDC);
    USBD_CDC_RegisterInterface(&hUsbDeviceFS, &USBD_Interface_fops_FS);
    USBD_Start(&hUsbDeviceFS);
}
```

```c
/* VBUS sensing — two modes: */

/* Mode 1: VBUS pin connected to OTG_FS_VBUS (PA9) */
/* In MspInit: configure PA9 as input, let OTG detect */
/* In Init: USB_OTG_FS->GCCFG |= USB_OTG_GCCFG_VBDEN; */

/* Mode 2: No VBUS sensing (always-on device, USB powered) */
/* Disable VBUS detection */
USB_OTG_FS->GCCFG &= ~USB_OTG_GCCFG_VBDEN;
USB_OTG_FS->GOTGCTL |= USB_OTG_GOTGCTL_BVALOEN | USB_OTG_GOTGCTL_BVALOVAL;
/* Add to HAL_PCD_MspInit after HAL_PCDEx_SetRxFiFo */
```

## CDC-VCP (Virtual COM Port)

```c
/* usbd_cdc_if.c — implement these three callbacks */

static int8_t CDC_Init_FS(void)
{
    USBD_CDC_SetTxBuffer(&hUsbDeviceFS, UserTxBufferFS, 0);
    USBD_CDC_SetRxBuffer(&hUsbDeviceFS, UserRxBufferFS);
    return USBD_OK;
}

static int8_t CDC_Receive_FS(uint8_t *buf, uint32_t *len)
{
    /* Called when host sends data */
    /* MUST call SetRxBuffer + ReceivePacket to re-arm before returning */
    process_rx_data(buf, *len);

    USBD_CDC_SetRxBuffer(&hUsbDeviceFS, UserRxBufferFS);
    USBD_CDC_ReceivePacket(&hUsbDeviceFS);   /* re-arm — MANDATORY */
    return USBD_OK;
}

/* TX — must check previous TX done */
static uint8_t cdc_tx_busy = 0;

HAL_StatusTypeDef CDC_Transmit_FS(uint8_t *buf, uint16_t len)
{
    USBD_CDC_HandleTypeDef *hcdc =
        (USBD_CDC_HandleTypeDef *)hUsbDeviceFS.pClassData;

    if (hcdc->TxState != 0) {
        return HAL_BUSY;  /* previous TX not done */
    }

    USBD_CDC_SetTxBuffer(&hUsbDeviceFS, buf, len);
    USBD_CDC_TransmitPacket(&hUsbDeviceFS);
    return HAL_OK;
}
```

```c
/* CDC TX with retry loop (safe for RTOS task) */
HAL_StatusTypeDef cdc_send(const uint8_t *data, uint16_t len, uint32_t timeout_ms)
{
    uint32_t t0 = HAL_GetTick();
    while (CDC_Transmit_FS((uint8_t *)data, len) == HAL_BUSY) {
        if ((HAL_GetTick() - t0) >= timeout_ms) return HAL_TIMEOUT;
        osDelay(1);
    }
    return HAL_OK;
}
```

```
CDC TX packet > 64 bytes on FS:
  USB FS max packet size = 64 bytes.
  USBD_CDC internally fragments — but if last fragment is exactly 64 bytes,
  host waits for ZLP (zero-length packet) before closing transfer.
  Fix: set CDC_DATA_FS_MAX_PACKET_SIZE = 64, and send ZLP manually
  if (len % 64 == 0) send 0-byte packet after.
```

## HID Device

```c
/* Report descriptor — mouse (3 bytes: buttons, X, Y) */
static const uint8_t HID_MOUSE_ReportDesc[] = {
    0x05, 0x01,  /* Usage Page (Generic Desktop) */
    0x09, 0x02,  /* Usage (Mouse) */
    0xA1, 0x01,  /* Collection (Application) */
    0x09, 0x01,  /* Usage (Pointer) */
    0xA1, 0x00,  /* Collection (Physical) */
    0x05, 0x09,  /* Usage Page (Buttons) */
    0x19, 0x01,  /* Usage Minimum (1) */
    0x29, 0x03,  /* Usage Maximum (3) */
    0x15, 0x00,  /* Logical Minimum (0) */
    0x25, 0x01,  /* Logical Maximum (1) */
    0x95, 0x03,  /* Report Count (3) */
    0x75, 0x01,  /* Report Size (1) */
    0x81, 0x02,  /* Input (Data, Variable, Absolute) */
    0x95, 0x01,  /* Report Count (1) */
    0x75, 0x05,  /* Report Size (5 bits padding) */
    0x81, 0x01,  /* Input (Constant) */
    0x05, 0x01,  /* Usage Page (Generic Desktop) */
    0x09, 0x30,  /* Usage (X) */
    0x09, 0x31,  /* Usage (Y) */
    0x15, 0x81,  /* Logical Minimum (-127) */
    0x25, 0x7F,  /* Logical Maximum (127) */
    0x75, 0x08,  /* Report Size (8) */
    0x95, 0x02,  /* Report Count (2) */
    0x81, 0x06,  /* Input (Data, Variable, Relative) */
    0xC0,        /* End Collection */
    0xC0,        /* End Collection */
};

/* Send HID report */
typedef struct { uint8_t buttons; int8_t x; int8_t y; } mouse_report_t;

void hid_send_mouse(int8_t dx, int8_t dy)
{
    mouse_report_t report = { .buttons = 0, .x = dx, .y = dy };
    USBD_HID_SendReport(&hUsbDeviceFS, (uint8_t *)&report, sizeof(report));
    osDelay(10);  /* HID poll interval — match bInterval in descriptor */
}
```

## DFU Device

```c
/* DFU mode: upload firmware from PC using dfu-util */
/* Trigger DFU from application: */
void jump_to_dfu_bootloader(void)
{
    /* STM32 internal bootloader at 0x1FF00000 (H7) */
    /* or use custom DFU class */
    __disable_irq();
    SysTick->CTRL = 0;
    HAL_DeInit();
    __HAL_RCC_APB1L_FORCE_RESET();
    __HAL_RCC_APB1L_RELEASE_RESET();

    /* Set stack pointer and jump */
    uint32_t dfu_addr = 0x1FF09800;  /* H7 system memory */
    typedef void (*pFunc)(void);
    pFunc jump = (pFunc)(*(__IO uint32_t *)(dfu_addr + 4));
    __set_MSP(*(__IO uint32_t *)dfu_addr);
    jump();
}

/* dfu-util command (from PC): */
/* dfu-util -a 0 -s 0x08000000:leave -D firmware.dfu */
/* Generate .dfu file: dfuse-pack or dfu-suffix */
```

## Composite Device (CDC + HID)

```c
/* Composite requires IAD (Interface Association Descriptor) */
/* usbd_composite.c registers both classes */

USBD_Init(&hUsbDeviceFS, &Composite_Desc, DEVICE_FS);
USBD_RegisterClass(&hUsbDeviceFS, &USBD_COMPOSITE);

/* In USBD_COMPOSITE, register both interfaces:
   Interface 0,1: CDC (control + data) — 2 interfaces
   Interface 2:   HID — 1 interface
   Total: 3 interfaces, requires IAD descriptor for CDC */

/* Pitfall: interface numbers in descriptors must be sequential,
   matching the order registered in class driver */
```

## Software Disconnect / Reconnect

```c
/* Force USB re-enumeration (e.g., after firmware update) */
void usb_reconnect(void)
{
    USBD_Stop(&hUsbDeviceFS);
    HAL_PCD_DevDisconnect(&hpcd_USB_OTG_FS);
    osDelay(100);
    HAL_PCD_DevConnect(&hpcd_USB_OTG_FS);
    USBD_Start(&hUsbDeviceFS);
}
```

## USB HS with External ULPI PHY (USB3320C)

```c
/* OTG_HS in HS mode requires external ULPI PHY */
/* GPIO: ULPI_CK, ULPI_DIR, ULPI_NXT, ULPI_STP, ULPI_D0-D7 */
/* All at GPIO_SPEED_FREQ_VERY_HIGH */

hpcd_HS.Instance                    = USB_OTG_HS;
hpcd_HS.Init.dev_endpoints          = 9;
hpcd_HS.Init.dma_enable             = ENABLE;
hpcd_HS.Init.phy_itface             = USB_OTG_ULPI_PHY;
hpcd_HS.Init.Sof_enable             = DISABLE;
hpcd_HS.Init.low_power_enable       = DISABLE;
hpcd_HS.Init.lpm_enable             = DISABLE;
hpcd_HS.Init.vbus_sensing_enable    = DISABLE;
hpcd_HS.Init.use_dedicated_ep1      = DISABLE;
hpcd_HS.Init.use_external_vbus      = DISABLE;
```

## Common Bugs

| Bug | Symptom | Fix |
|-----|---------|-----|
| `ReceivePacket` not called in `CDC_Receive_FS` | Only first packet received | Always re-arm at end of callback |
| TX without checking `TxState` | Packets dropped silently | Check `hcdc->TxState != 0` before transmit |
| USB clock != 48 MHz | Device not enumerated | Verify PLL48CLK / PLL3Q configuration |
| ZLP not sent after 64-byte multiple | Host hangs waiting | Send 0-byte packet if `len % 64 == 0` |
| `VBUS_SENSING_ENABLE` without PA9 connected | USB not detected | Disable VBUS sensing or wire PA9 |
| `HAL_PCD_MspDeInit` missing GPIO deinit | After disconnect, pins float | Deinit all USB GPIO in MspDeInit |
| Composite IAD missing | Windows shows unknown device | Add IAD descriptor for CDC pair |
| DFU BOOT0 pin not configured | Can't enter DFU mode | Set nBOOT1 option bit or use software jump |
