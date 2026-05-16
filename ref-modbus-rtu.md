# Modbus RTU (RS485)

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, errata workarounds, protocol-spec content** here is authoritative — that is why this file exists.
> - **Inline HAL/CMSIS/peripheral code snippets** are illustrative. The HAL drifts between versions and parts. For the canonical version of any HAL symbol at your HAL release: `gh search code <SymbolName> --owner=STMicroelectronics --extension=c` — see [ref-st-github-map.md](ref-st-github-map.md) §8 for the full lookup procedure.
> - **CRITICAL bugs identified in the 2026-05-16 audit have been corrected** in this file, but verify against your own HAL version before copy-pasting.
> - **For bootloader / IAP / OTA topics** the canonical checklist + ARM KA001193 + AN5188/2606/3155/3156 references are in [ref-bootloader.md](ref-bootloader.md).


## Protocol Essentials

| Parameter | Value |
|-----------|-------|
| Physical | RS485 half-duplex (2-wire) |
| Frame | ADR(1) + FN(1) + DATA(N) + CRC16(2) |
| Silence gap | 3.5 character times between frames |
| Baud common | 9600, 19200, 38400, 115200 |
| Max slaves | 247 (addr 1–247; 0 = broadcast) |
| CRC poly | 0xA001 (reflected 0x8005) |

## Hardware Setup (STM32 UART + RS485 DE/RE pin)

```c
/* CubeMX: UART in Asynchronous mode, RS485 Driver Enable:
   - DE Pin: e.g. PA1
   - DE Polarity: High = transmit
   - DE Assertion/Deassertion time: 2 baud cycles */

/* Or manually toggle DE pin in software */
#define RS485_DE_GPIO   GPIOA
#define RS485_DE_PIN    GPIO_PIN_1

static inline void rs485_tx_enable(void)
{
    HAL_GPIO_WritePin(RS485_DE_GPIO, RS485_DE_PIN, GPIO_PIN_SET);
}

static inline void rs485_rx_enable(void)
{
    HAL_GPIO_WritePin(RS485_DE_GPIO, RS485_DE_PIN, GPIO_PIN_RESET);
}
```

## CRC16 Modbus

```c
uint16_t modbus_crc16(const uint8_t *buf, uint16_t len)
{
    uint16_t crc = 0xFFFF;
    for (uint16_t i = 0; i < len; i++) {
        crc ^= (uint16_t)buf[i];
        for (int b = 0; b < 8; b++) {
            if (crc & 1)
                crc = (crc >> 1) ^ 0xA001;
            else
                crc >>= 1;
        }
    }
    return crc; /* low byte first in frame */
}

bool modbus_crc_valid(const uint8_t *frame, uint16_t len)
{
    if (len < 4) return false;
    uint16_t calc    = modbus_crc16(frame, len - 2);
    uint16_t rx_crc  = (uint16_t)frame[len-2] | ((uint16_t)frame[len-1] << 8);
    return calc == rx_crc;
}
```

## Register Map (slave implementation)

```c
/* Holding registers (FC03/FC06/FC16) — 16-bit, read/write */
#define REG_SETPOINT_TEMP   0x0000  /* 0.1°C units */
#define REG_ACTUAL_TEMP     0x0001  /* read-only (enforce in write handler) */
#define REG_CONTROL_WORD    0x0002  /* bit 0=enable, bit 1=alarm_reset */
#define REG_STATUS_WORD     0x0003  /* bit 0=running, bit 1=alarm, bit 2=fault */
#define REG_FAULT_CODE      0x0004  /* last fault reason */
#define REG_FW_VERSION      0x000F  /* BCD: 0x0123 = v1.23 */
#define HOLDING_REG_COUNT   16

static uint16_t holding_regs[HOLDING_REG_COUNT];

/* Input registers (FC04) — read-only process values */
#define INPUT_REG_COUNT 8
static uint16_t input_regs[INPUT_REG_COUNT];
```

## Frame Buffer and Timing

```c
#define MODBUS_BUF_SIZE  256
#define MODBUS_ADDR      1        /* this slave address */
#define MODBUS_TIMEOUT_MS 5       /* inter-frame gap timeout */

static uint8_t  rx_buf[MODBUS_BUF_SIZE];
static uint16_t rx_len = 0;
static uint32_t last_rx_tick = 0;
static bool     frame_complete = false;

/* Called from UART RX ISR.
 *
 * NOTE: HAL_GetTick() resolution is 1 ms. Modbus over Serial V1.02 §2.5.1.1:
 *   - baud ≤ 19200: gap = 3.5 char time (~2 ms @ 19200, ~4 ms @ 9600)
 *   - baud  > 19200: gap is FIXED at 1.750 ms
 * 1 ms tick is too coarse above 19200 baud. For those use either:
 *   (a) hardware idle-line detect (USART IDLE flag)  -- recommended
 *   (b) a basic timer running at 10 kHz for sub-ms resolution
 *   (c) USART RTOR (Receiver Timeout Register, F0/F4/F7/H7/L4) — built-in
 *       silent-interval interrupt; the cleanest STM32-specific solution.
 * The example below is correct only for ≤ 19200 baud.
 */
void modbus_uart_rx_byte(uint8_t byte)
{
    uint32_t now = HAL_GetTick();

    /* 3.5 char silence detected — frame boundary */
    /* For 9600 baud: 3.5 * (1/9600) * 11 bits ≈ 4 ms; use 5 ms with HAL_GetTick. */
    if ((now - last_rx_tick) > MODBUS_TIMEOUT_MS && rx_len > 0) {
        frame_complete = true; /* previous frame done, will be processed in main */
        rx_len = 0;
    }

    last_rx_tick = now;
    if (rx_len < MODBUS_BUF_SIZE)
        rx_buf[rx_len++] = byte;
}
```

## Function Code Handlers (Slave)

```c
/* Returns response length, 0 = no response (broadcast or error) */
uint16_t modbus_process_frame(const uint8_t *req, uint16_t req_len,
                               uint8_t *resp, uint16_t resp_max)
{
    if (req_len < 4) return 0;
    if (!modbus_crc_valid(req, req_len)) return 0;

    uint8_t  addr = req[0];
    uint8_t  fn   = req[1];

    /* Ignore frames not addressed to us (allow broadcast addr=0 for writes only) */
    if (addr != MODBUS_ADDR && addr != 0) return 0;

    uint16_t start, count, value;
    uint16_t resp_len = 0;

    switch (fn) {
    case 0x03: /* Read Holding Registers */
        start = ((uint16_t)req[2] << 8) | req[3];
        count = ((uint16_t)req[4] << 8) | req[5];
        if (start + count > HOLDING_REG_COUNT) goto exception;

        resp[0] = addr; resp[1] = fn;
        resp[2] = (uint8_t)(count * 2);
        for (uint16_t i = 0; i < count; i++) {
            resp[3 + i*2]     = (uint8_t)(holding_regs[start+i] >> 8);
            resp[3 + i*2 + 1] = (uint8_t)(holding_regs[start+i]);
        }
        resp_len = 3 + count * 2;
        break;

    case 0x04: /* Read Input Registers */
        start = ((uint16_t)req[2] << 8) | req[3];
        count = ((uint16_t)req[4] << 8) | req[5];
        if (start + count > INPUT_REG_COUNT) goto exception;

        resp[0] = addr; resp[1] = fn;
        resp[2] = (uint8_t)(count * 2);
        for (uint16_t i = 0; i < count; i++) {
            resp[3 + i*2]     = (uint8_t)(input_regs[start+i] >> 8);
            resp[3 + i*2 + 1] = (uint8_t)(input_regs[start+i]);
        }
        resp_len = 3 + count * 2;
        break;

    case 0x06: /* Write Single Holding Register */
        start = ((uint16_t)req[2] << 8) | req[3];
        value = ((uint16_t)req[4] << 8) | req[5];
        if (start >= HOLDING_REG_COUNT) goto exception;
        if (start == REG_ACTUAL_TEMP) goto exception; /* read-only */

        holding_regs[start] = value;
        memcpy(resp, req, 6); /* echo request on success */
        resp_len = 6;
        break;

    case 0x10: /* Write Multiple Holding Registers */
        start = ((uint16_t)req[2] << 8) | req[3];
        count = ((uint16_t)req[4] << 8) | req[5];
        if (start + count > HOLDING_REG_COUNT) goto exception;

        for (uint16_t i = 0; i < count; i++) {
            holding_regs[start+i] = ((uint16_t)req[7 + i*2] << 8)
                                  | req[8 + i*2];
        }
        resp[0]=addr; resp[1]=fn;
        resp[2]=req[2]; resp[3]=req[3]; resp[4]=req[4]; resp[5]=req[5];
        resp_len = 6;
        break;

    default:
    exception:
        resp[0] = addr;
        resp[1] = fn | 0x80;            /* exception response */
        resp[2] = (fn == 0x03 || fn == 0x04 || fn == 0x06 || fn == 0x10)
                  ? 0x02  /* Illegal Data Address */
                  : 0x01; /* Illegal Function */
        resp_len = 3;
        break;
    }

    if (resp_len == 0 || addr == 0) return 0; /* no response for broadcast */

    /* Append CRC */
    uint16_t crc = modbus_crc16(resp, resp_len);
    resp[resp_len++] = (uint8_t)(crc);
    resp[resp_len++] = (uint8_t)(crc >> 8);
    return resp_len;
}
```

## Main Loop Integration

```c
static uint8_t resp_buf[MODBUS_BUF_SIZE];

void modbus_poll(void)
{
    if (!frame_complete) return;
    frame_complete = false;

    uint16_t resp_len = modbus_process_frame(rx_buf, rx_len,
                                              resp_buf, sizeof(resp_buf));
    if (resp_len > 0) {
        rs485_tx_enable();
        HAL_UART_Transmit(&huart1, resp_buf, resp_len, 10);
        /* Wait for TX complete before switching to RX */
        while (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_TC) == RESET) {}
        rs485_rx_enable();
    }

    /* Update input registers with fresh sensor data */
    input_regs[0] = (uint16_t)(adc_to_mv(adc_get(0)) / 10); /* temp in 0.1°C */
    input_regs[1] = (uint16_t)system_status_word();
}
```

## Inter-Frame Gap via Timer (precise 3.5 char detection)

```c
/* More robust than HAL_GetTick() for high-baud rates.
   Configure a 1-shot timer with period = 3.5 * char_time_us */

static volatile bool modbus_gap_expired = false;

/* In TIMx update ISR */
void TIM6_DAC_IRQHandler(void)
{
    __HAL_TIM_CLEAR_IT(&htim6, TIM_IT_UPDATE);
    modbus_gap_expired = true;
    HAL_TIM_Base_Stop_IT(&htim6);
}

/* Restart timer on every RX byte */
void modbus_uart_rx_byte_tim(uint8_t byte)
{
    if (modbus_gap_expired && rx_len > 0) {
        frame_complete = true;
        rx_len = 0;
    }
    modbus_gap_expired = false;
    /* Restart one-shot timer */
    __HAL_TIM_SET_COUNTER(&htim6, 0);
    HAL_TIM_Base_Start_IT(&htim6);

    if (rx_len < MODBUS_BUF_SIZE)
        rx_buf[rx_len++] = byte;
}
```

## Rules

- DE pin must go LOW within one character time after last TX byte — use hardware DE mode if available
- Never process Modbus frame in ISR context — flag it and process in main loop
- CRC is little-endian: low byte at `frame[n-2]`, high byte at `frame[n-1]`
- Exception response must keep FC number and OR with 0x80 — not a new FC
- Broadcast (addr=0): execute write, send NO response — ever
- Slave must not respond if CRC fails — silence is the correct behavior
- For baud > 19200: use fixed 1750µs inter-frame gap (Modbus spec allows it)
