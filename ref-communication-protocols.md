# Communication Protocol Reference — STM32 (HAL + LL + DMA + RTOS)

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, errata workarounds, protocol-spec content** here is authoritative — that is why this file exists.
> - **Inline HAL/CMSIS/peripheral code snippets** are illustrative. The HAL drifts between versions and parts. For the canonical version of any HAL symbol at your HAL release: `gh search code <SymbolName> --owner=STMicroelectronics --extension=c` — see [ref-st-github-map.md](ref-st-github-map.md) §8 for the full lookup procedure.
> - **CRITICAL bugs identified in the 2026-05-16 audit have been corrected** in this file, but verify against your own HAL version before copy-pasting.
> - **For bootloader / IAP / OTA topics** the canonical checklist + ARM KA001193 + AN5188/2606/3155/3156 references are in [ref-bootloader.md](ref-bootloader.md).


Covers: I2C, SPI, UART/USART/RS485, FDCAN, Classic CAN, QSPI/OSPI, USB CDC, 1-Wire, RTOS integration.  
Targets: F0/F1/F4/F7/G0/G4/H7/H7RS/L4/U5/WB series.  
RTOS: FreeRTOS and Keil RTX5 / CMSIS-RTOS2.

---

## Contents

1. [I2C](#1-i2c)
2. [SPI](#2-spi)
3. [UART / USART / RS485](#3-uart--usart--rs485)
4. [FDCAN (G0/G4/H7/U5)](#4-fdcan)
5. [Classic CAN (F4/F0)](#5-classic-can-f4f0)
6. [QSPI / OSPI — External Flash / XIP](#6-qspi--ospi)
7. [USB CDC (Virtual COM)](#7-usb-cdc)
8. [1-Wire](#8-1-wire)
9. [RTOS Integration — FreeRTOS + RTX5](#9-rtos-integration)
10. [Protocol Verification Checklist](#10-protocol-verification-checklist)

---

## 1. I2C

### 1.1 Hardware version differences

| Series | IP version | Key difference |
|--------|-----------|----------------|
| F1, F0, F3 | I2C v1 | Older SR1/SR2 flag model; BUSY lockup common |
| F4, L1 | I2C v1 | Same as F1; errata: bus lockup after timeout |
| F7, L4, G4, H7, U5, WB | I2C v2 | ISR/ICR flag model; NACK/STOP auto-handling; RELOAD/AUTOEND |

### 1.2 I2C v2 — HAL (F7/H7/G4/L4) — recommended pattern

```c
#define I2C_TIMEOUT_MS  10U

/* Write N bytes to device register */
HAL_StatusTypeDef i2c_write_reg(I2C_HandleTypeDef *hi2c,
                                 uint8_t dev_addr, uint8_t reg_addr,
                                 const uint8_t *data, uint16_t len)
{
    /* Build [reg_addr | data...] in a local buffer to one HAL call */
    uint8_t buf[64];
    if (len + 1U > sizeof(buf)) return HAL_ERROR;
    buf[0] = reg_addr;
    memcpy(&buf[1], data, len);
    return HAL_I2C_Master_Transmit(hi2c, (uint16_t)(dev_addr << 1),
                                    buf, (uint16_t)(len + 1U), I2C_TIMEOUT_MS);
}

/* Read N bytes from device register */
HAL_StatusTypeDef i2c_read_reg(I2C_HandleTypeDef *hi2c,
                                uint8_t dev_addr, uint8_t reg_addr,
                                uint8_t *data, uint16_t len)
{
    HAL_StatusTypeDef r;
    r = HAL_I2C_Master_Transmit(hi2c, (uint16_t)(dev_addr << 1),
                                  &reg_addr, 1, I2C_TIMEOUT_MS);
    if (r != HAL_OK) return r;
    return HAL_I2C_Master_Receive(hi2c, (uint16_t)(dev_addr << 1),
                                   data, len, I2C_TIMEOUT_MS);
}
```

### 1.3 I2C error recovery (BOTH v1 and v2)

I2C lines can get stuck when a transaction aborts mid-byte (slave holds SDA low).
HAL does NOT recover automatically.

```c
/* Call after any HAL_I2C_Master_Transmit/Receive returns HAL_ERROR or HAL_BUSY */
void i2c_recover(I2C_HandleTypeDef *hi2c)
{
    /* Force-reset the peripheral */
    __HAL_RCC_I2C1_FORCE_RESET();
    HAL_Delay(2);
    __HAL_RCC_I2C1_RELEASE_RESET();
    HAL_Delay(2);

    /* Bit-bang up to 9 clocks to release slave-held SDA */
    GPIO_InitTypeDef gpio = {
        .Pin   = I2C1_SCL_PIN,
        .Mode  = GPIO_MODE_OUTPUT_OD,
        .Pull  = GPIO_NOPULL,
        .Speed = GPIO_SPEED_FREQ_LOW,
    };
    HAL_GPIO_Init(I2C1_SCL_GPIO_PORT, &gpio);
    for (int i = 0; i < 9; i++) {
        HAL_GPIO_WritePin(I2C1_SCL_GPIO_PORT, I2C1_SCL_PIN, GPIO_PIN_SET);
        HAL_Delay(1);
        HAL_GPIO_WritePin(I2C1_SCL_GPIO_PORT, I2C1_SCL_PIN, GPIO_PIN_RESET);
        HAL_Delay(1);
    }
    /* Re-init peripheral and restore AF pins */
    MX_I2C1_Init();
}

/* Wrapper: auto-recover and retry once */
HAL_StatusTypeDef i2c_write_safe(I2C_HandleTypeDef *hi2c,
                                  uint8_t dev_addr, uint8_t reg_addr,
                                  const uint8_t *data, uint16_t len)
{
    HAL_StatusTypeDef r = i2c_write_reg(hi2c, dev_addr, reg_addr, data, len);
    if (r != HAL_OK) {
        i2c_recover(hi2c);
        r = i2c_write_reg(hi2c, dev_addr, reg_addr, data, len);
    }
    return r;
}
```

### 1.4 I2C DMA (v2 — HAL, cache-safe M7)

```c
/* DMA buffers: must be 32-byte aligned for M7 D-cache */
ALIGN_32BYTES(static uint8_t i2c_tx_dma_buf[64]);
ALIGN_32BYTES(static uint8_t i2c_rx_dma_buf[64]);

void i2c_start_dma_read(I2C_HandleTypeDef *hi2c, uint8_t dev_addr,
                          uint8_t reg_addr, uint16_t len)
{
    i2c_tx_dma_buf[0] = reg_addr;
    SCB_CleanDCache_by_Addr((uint32_t *)i2c_tx_dma_buf, 32);

    /* Transmit register address, then receive via DMA */
    HAL_I2C_Master_Transmit_DMA(hi2c, (uint16_t)(dev_addr << 1),
                                  i2c_tx_dma_buf, 1);
}

void HAL_I2C_MasterTxCpltCallback(I2C_HandleTypeDef *hi2c)
{
    /* Switch to RX DMA */
    HAL_I2C_Master_Receive_DMA(hi2c, SENSOR_ADDR << 1, i2c_rx_dma_buf, READ_LEN);
}

void HAL_I2C_MasterRxCpltCallback(I2C_HandleTypeDef *hi2c)
{
    /* Invalidate cache before reading buffer */
    SCB_InvalidateDCache_by_Addr((uint32_t *)i2c_rx_dma_buf, 32);
    process_sensor_data(i2c_rx_dma_buf);
}
```

### 1.5 I2C v1 bare-metal (F4) — bus-lockup safe

```c
/* F4 / F1 — v1 register model — IMPORTANT: clear ADDR by reading SR1 then SR2 */
static bool i2c_v1_wait_flag(I2C_TypeDef *i2c, uint32_t sr1_flag, uint32_t timeout_ms)
{
    uint32_t tick = HAL_GetTick();
    while (!(i2c->SR1 & sr1_flag)) {
        if ((HAL_GetTick() - tick) >= timeout_ms) return false;
        if (i2c->SR1 & (I2C_SR1_AF | I2C_SR1_ARLO | I2C_SR1_BERR)) {
            i2c->SR1 = 0;          /* clear error flags */
            i2c->CR1 |= I2C_CR1_STOP;
            return false;
        }
    }
    return true;
}

bool i2c_v1_write(I2C_TypeDef *i2c, uint8_t addr,
                   const uint8_t *data, uint16_t len, uint32_t timeout_ms)
{
    i2c->CR1 |= I2C_CR1_START;
    if (!i2c_v1_wait_flag(i2c, I2C_SR1_SB, timeout_ms)) return false;

    i2c->DR = (uint8_t)(addr << 1);  /* write direction */
    if (!i2c_v1_wait_flag(i2c, I2C_SR1_ADDR, timeout_ms)) return false;
    (void)i2c->SR1; (void)i2c->SR2;  /* clear ADDR */

    for (uint16_t i = 0; i < len; i++) {
        i2c->DR = data[i];
        if (!i2c_v1_wait_flag(i2c, I2C_SR1_TXE, timeout_ms)) return false;
    }
    if (!i2c_v1_wait_flag(i2c, I2C_SR1_BTF, timeout_ms)) return false;
    i2c->CR1 |= I2C_CR1_STOP;
    return true;
}
```

### 1.6 I2C checklist

- [ ] `dev_addr` shifted left 1 bit before passing to HAL (7-bit address)
- [ ] Timeout is **wall-clock** (HAL_GetTick), not a bare decrement counter
- [ ] `HAL_MAX_DELAY` never used — bus can hang indefinitely
- [ ] Error recovery called on every `HAL_ERROR` / `HAL_BUSY` return
- [ ] Pull-up resistor values match bus speed: 4.7kΩ @ 100kHz, 2.2kΩ @ 400kHz, 1kΩ @ 1MHz
- [ ] SCL/SDA GPIO configured as `GPIO_MODE_AF_OD` (open-drain), no push-pull
- [ ] DMA buffers 32-byte aligned and cache-cleaned/invalidated on M7

---

## 2. SPI

### 2.1 CPOL / CPHA quick reference

| Mode | CPOL | CPHA | Clock idle | Capture edge |
|------|------|------|-----------|--------------|
| 0 | 0 | 0 | Low | Rising |
| 1 | 0 | 1 | Low | Falling |
| 2 | 1 | 0 | High | Falling |
| 3 | 1 | 1 | High | Rising |

Always confirm from slave datasheet — mislabeled "SPI mode 0" is common.

### 2.2 LL driver — single-byte (F4/H7, tight loop)

```c
/* Full-duplex: transmit TX, receive RX — wait flags individually */
static inline uint8_t spi_xfer_byte_ll(SPI_TypeDef *spi, uint8_t tx)
{
    while (!LL_SPI_IsActiveFlag_TXE(spi));
    LL_SPI_TransmitData8(spi, tx);
    while (!LL_SPI_IsActiveFlag_RXNE(spi));
    return LL_SPI_ReceiveData8(spi);
}

/* Multi-byte transfer: drive CS manually */
void spi_transfer(SPI_TypeDef *spi, GPIO_TypeDef *cs_port, uint16_t cs_pin,
                   const uint8_t *tx, uint8_t *rx, uint16_t len)
{
    HAL_GPIO_WritePin(cs_port, cs_pin, GPIO_PIN_RESET);
    for (uint16_t i = 0; i < len; i++)
        rx[i] = spi_xfer_byte_ll(spi, tx ? tx[i] : 0xFF);
    HAL_GPIO_WritePin(cs_port, cs_pin, GPIO_PIN_SET);
}
```

### 2.3 HAL polling — simple use (any family)

```c
#define SPI_TIMEOUT_MS  5U

HAL_StatusTypeDef spi_read_reg(SPI_HandleTypeDef *hspi,
                                GPIO_TypeDef *cs_port, uint16_t cs_pin,
                                uint8_t reg_addr, uint8_t *data, uint16_t len)
{
    uint8_t cmd = reg_addr | 0x80U;  /* read bit — device specific */
    HAL_GPIO_WritePin(cs_port, cs_pin, GPIO_PIN_RESET);
    HAL_StatusTypeDef r = HAL_SPI_Transmit(hspi, &cmd, 1, SPI_TIMEOUT_MS);
    if (r == HAL_OK)
        r = HAL_SPI_Receive(hspi, data, len, SPI_TIMEOUT_MS);
    HAL_GPIO_WritePin(cs_port, cs_pin, GPIO_PIN_SET);
    return r;
}
```

### 2.4 DMA full-duplex — M7 cache-safe (H7/F7)

```c
/* Both buffers: 32-byte aligned, size rounded up to next multiple of 32 */
#define SPI_DMA_BUF_SIZE   32U
ALIGN_32BYTES(static uint8_t spi_tx_buf[SPI_DMA_BUF_SIZE]);
ALIGN_32BYTES(static uint8_t spi_rx_buf[SPI_DMA_BUF_SIZE]);

static volatile bool spi_dma_busy = false;

void spi_dma_xfer(SPI_HandleTypeDef *hspi,
                   GPIO_TypeDef *cs_port, uint16_t cs_pin,
                   const uint8_t *tx, uint16_t len)
{
    if (len > SPI_DMA_BUF_SIZE) { /* error */ return; }
    memcpy(spi_tx_buf, tx, len);

    /* Clean TX buffer: CPU → SRAM (DMA will read SRAM, not cache) */
    SCB_CleanDCache_by_Addr((uint32_t *)spi_tx_buf, SPI_DMA_BUF_SIZE);

    /* Invalidate RX buffer: ensure stale cache lines won't be read after DMA */
    SCB_InvalidateDCache_by_Addr((uint32_t *)spi_rx_buf, SPI_DMA_BUF_SIZE);

    spi_dma_busy = true;
    HAL_GPIO_WritePin(cs_port, cs_pin, GPIO_PIN_RESET);
    HAL_SPI_TransmitReceive_DMA(hspi, spi_tx_buf, spi_rx_buf, len);
}

void HAL_SPI_TxRxCpltCallback(SPI_HandleTypeDef *hspi)
{
    HAL_GPIO_WritePin(CS_GPIO_PORT, CS_PIN, GPIO_PIN_SET);
    /* No need to invalidate again — already done before DMA start */
    spi_dma_busy = false;
    process_spi_rx(spi_rx_buf);
}
```

### 2.5 SPI v2 FIFO (F7/H7) — 16-bit data frame

```c
/* H7 / F7: SPIv2 has 4-level FIFO and FRXTH bit for 8-bit threshold */
/* CubeMX: DataSize=8bit, FifoThreshold=QUARTER (FRXTH=1) */
/* For 16-bit: DataSize=16bit, use LL_SPI_TransmitData16 */

static inline uint16_t spi_xfer_16(SPI_TypeDef *spi, uint16_t tx)
{
    while (!LL_SPI_IsActiveFlag_TXE(spi));
    LL_SPI_TransmitData16(spi, tx);
    while (!LL_SPI_IsActiveFlag_RXNE(spi));
    return LL_SPI_ReceiveData16(spi);
}
```

### 2.6 Multi-slave: software NSS

```c
/* NEVER use hardware NSS in multi-slave setup — it goes low on first byte
   and high after last byte automatically, but you lose per-slave control.
   Always: NSS=disabled in CubeMX, drive CS GPIOs manually. */

/* Software NSS timing requirement: */
/* CS_SETUP: CS low → first SCLK edge: min 10–50 ns (check slave datasheet) */
/* CS_HOLD:  last SCLK edge → CS high: min 10–50 ns */
/* At 72 MHz: 1 NOP ≈ 14 ns — often 1–2 NOPs sufficient */
HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_RESET);
__NOP(); __NOP();                 /* setup time */
HAL_SPI_TransmitReceive(hspi, tx, rx, len, SPI_TIMEOUT_MS);
__NOP(); __NOP();                 /* hold time */
HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_SET);
```

### 2.7 SPI checklist

- [ ] CPOL/CPHA matches slave datasheet; verified with scope before software
- [ ] Software NSS used for multi-slave; hardware NSS only for single-slave
- [ ] CS setup/hold timing respected (NOP or timer if > few hundred ns)
- [ ] M7: TX buffer cleaned, RX buffer invalidated before `HAL_SPI_TransmitReceive_DMA`
- [ ] DMA buffers 32-byte aligned, sizes multiple of 32 bytes (or padded)
- [ ] `HAL_SPI_ErrorCallback` implemented — check HSE flag for fault detection
- [ ] F7/H7 FIFO threshold set correctly (FRXTH=1 for 8-bit data)

---

## 3. UART / USART / RS485

### 3.1 DMA + IDLE line interrupt (best pattern for variable-length frames)

This is the **correct** pattern for any protocol where frame length is unknown at RX start
(Modbus RTU, custom binary frames, AT commands).

```c
#define UART_DMA_BUF_SIZE  256U

/* Circular DMA buffer — peripheral writes here continuously */
ALIGN_32BYTES(static uint8_t uart_dma_buf[UART_DMA_BUF_SIZE]);

/* Application ring buffer */
static uint8_t  uart_rx_ring[512];
static uint16_t uart_rx_head = 0;
static uint16_t uart_rx_tail = 0;

static uint16_t uart_dma_prev_pos = 0;

/* Start: enable DMA in circular mode + IDLE interrupt */
void uart_rx_start(UART_HandleTypeDef *huart)
{
    __HAL_UART_ENABLE_IT(huart, UART_IT_IDLE);
    HAL_UARTEx_ReceiveToIdle_DMA(huart, uart_dma_buf, UART_DMA_BUF_SIZE);
    /* Disable HT interrupt — we only want IDLE and TC events */
    __HAL_DMA_DISABLE_IT(huart->hdmarx, DMA_IT_HT);
}

/* Called by HAL on: IDLE line detected, DMA half-complete, DMA complete */
void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *huart, uint16_t size)
{
    /* 'size' = total bytes received into DMA buffer since last call */
    uint16_t pos = size;  /* current write position in DMA circular buffer */

    if (pos != uart_dma_prev_pos) {
        if (pos > uart_dma_prev_pos) {
            /* Linear region: prev_pos → pos */
            uint16_t count = pos - uart_dma_prev_pos;
            /* M7: invalidate before reading */
            SCB_InvalidateDCache_by_Addr(
                (uint32_t *)&uart_dma_buf[uart_dma_prev_pos], count);
            ring_buf_write(uart_rx_ring, &uart_dma_buf[uart_dma_prev_pos],
                           count, &uart_rx_head, sizeof(uart_rx_ring));
        } else {
            /* Wrap: prev_pos → end, 0 → pos */
            uint16_t count1 = UART_DMA_BUF_SIZE - uart_dma_prev_pos;
            uint16_t count2 = pos;
            SCB_InvalidateDCache_by_Addr(
                (uint32_t *)&uart_dma_buf[uart_dma_prev_pos], count1);
            ring_buf_write(uart_rx_ring, &uart_dma_buf[uart_dma_prev_pos],
                           count1, &uart_rx_head, sizeof(uart_rx_ring));
            if (count2) {
                SCB_InvalidateDCache_by_Addr((uint32_t *)uart_dma_buf, count2);
                ring_buf_write(uart_rx_ring, uart_dma_buf,
                               count2, &uart_rx_head, sizeof(uart_rx_ring));
            }
        }
        uart_dma_prev_pos = pos % UART_DMA_BUF_SIZE;
        osEventFlagsSet(uart_evt_flags, UART_RX_FLAG);
    }
}

/* Task: process frames from ring buffer */
void uart_task(void *arg)
{
    for (;;) {
        osEventFlagsWait(uart_evt_flags, UART_RX_FLAG, osFlagsWaitAny, osWaitForever);
        uint8_t frame[128];
        uint16_t len = ring_buf_read(uart_rx_ring, frame, sizeof(frame),
                                      &uart_rx_tail, &uart_rx_head);
        if (len) protocol_parse(frame, len);
    }
}
```

### 3.2 UART TX DMA (non-blocking)

```c
ALIGN_32BYTES(static uint8_t uart_tx_dma_buf[256]);
static volatile bool uart_tx_busy = false;

HAL_StatusTypeDef uart_send(UART_HandleTypeDef *huart,
                              const uint8_t *data, uint16_t len)
{
    if (uart_tx_busy) return HAL_BUSY;
    if (len > sizeof(uart_tx_dma_buf)) return HAL_ERROR;

    memcpy(uart_tx_dma_buf, data, len);
    SCB_CleanDCache_by_Addr((uint32_t *)uart_tx_dma_buf,
                             (len + 31U) & ~31U);  /* round up to 32 */
    uart_tx_busy = true;
    return HAL_UART_Transmit_DMA(huart, uart_tx_dma_buf, len);
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    uart_tx_busy = false;
    osEventFlagsSet(uart_evt_flags, UART_TX_DONE_FLAG);
}
```

### 3.3 RS485 — half-duplex DE/RE control

```c
/* DE (Driver Enable) pin: high = TX active, low = RX active */
/* RE (Receiver Enable) active-low — tie to DE (inverted) or same pin */

#define RS485_DE_PORT   GPIOA
#define RS485_DE_PIN    GPIO_PIN_8

static inline void rs485_tx_enable(void)  { HAL_GPIO_WritePin(RS485_DE_PORT, RS485_DE_PIN, GPIO_PIN_SET); }
static inline void rs485_rx_enable(void)  { HAL_GPIO_WritePin(RS485_DE_PORT, RS485_DE_PIN, GPIO_PIN_RESET); }

/* HAL auto-handles DE via UART RS485 mode (H7/L4/G4) — CubeMX: RS485 Driver Enable */
/* If auto DE not available: manual toggle */

HAL_StatusTypeDef rs485_transmit(UART_HandleTypeDef *huart,
                                   const uint8_t *data, uint16_t len)
{
    rs485_tx_enable();
    /* Wait DE propagation: typ 1 bit period at baud rate */
    /* At 9600 baud: ~104µs; at 115200 baud: ~8.7µs */
    HAL_StatusTypeDef r = HAL_UART_Transmit(huart, data, len, 100U);
    /* Wait for TC (Transmission Complete) — TC fires after last stop bit */
    /* HAL_Transmit already waits for TC internally */
    rs485_rx_enable();
    return r;
}

/* For DMA TX — must switch to RX after TC, not DMA complete */
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    /* TC interrupt already triggered by HAL after last byte */
    rs485_rx_enable();
}
```

### 3.4 UART hardware flow control (CTS/RTS)

```c
/* CubeMX: Hardware Flow Control = RTS/CTS */
/* USART HwFlowCtl = UART_HWCONTROL_RTS_CTS */
/* Ensure RTS/CTS pins configured as AF */

/* RTS: STM32 drives low when ready to receive (flow control output) */
/* CTS: STM32 halts TX when remote drives CTS high (flow control input) */
/* Wire: STM32 RTS → remote CTS; remote RTS → STM32 CTS */
```

### 3.5 Baud rate accuracy

```c
/* USART baud rate error formula: */
/* Error% = (ACTUAL_BAUD - TARGET_BAUD) / TARGET_BAUD * 100 */
/* Max allowed: ±2.5% per UART spec */

/* Example: PCLK1=42MHz, target=115200 */
/* BRR = 42000000 / 115200 = 364.58 → round to 365 */
/* Actual = 42000000 / 365 = 115068 → error = -0.11% — OK */

/* Problematic: PCLK=36MHz, target=115200 */
/* BRR = 36000000 / 115200 = 312.5 → 313 → actual=115015 → -0.16% — OK */
/* BRR = 36000000 / 921600 = 39.06 → ±3% — NOT OK, change PCLK */

/* Always verify with logic analyzer at production baud rate */
```

### 3.6 FIFO mode (H7/H7RS)

```c
/* H7 USART has 8-level TX/RX FIFO — enable in CubeMX */
/* FIFO reduces interrupt rate: set RX FIFO threshold */
/* LL: LL_USART_SetRXFIFOThreshold(USART1, LL_USART_FIFOTHRESHOLD_1_2) */
/* HAL: handled via init structure */

/* FIFO + IDLE: best combination for variable-length DMA reception */
/* IDLE line fires only when bus is silent > 1 frame period */
```

### 3.7 UART error handling

```c
void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
    uint32_t err = HAL_UART_GetError(huart);

    if (err & HAL_UART_ERROR_ORE) {
        /* Overrun: DMA/ISR too slow, data lost */
        uart_stats.overrun_count++;
        /* Recovery: re-enable RX — HAL disables on error */
    }
    if (err & HAL_UART_ERROR_FE) {
        /* Framing: baud rate mismatch or line noise */
        uart_stats.frame_error_count++;
    }
    if (err & HAL_UART_ERROR_NE) {
        /* Noise error */
        uart_stats.noise_error_count++;
    }
    if (err & HAL_UART_ERROR_PE) {
        /* Parity error */
        uart_stats.parity_error_count++;
    }

    /* Restart DMA reception after any error */
    HAL_UART_AbortReceive(huart);
    uart_rx_start(huart);
}
```

### 3.8 UART checklist

- [ ] DMA circular mode + IDLE interrupt used for RX (not byte-by-byte ISR)
- [ ] `HAL_UARTEx_RxEventCallback` handles wrap-around in circular DMA buffer
- [ ] RS485: TX→RX switch after TC (not DMA complete) — TC fires after last stop bit
- [ ] `HAL_UART_ErrorCallback` implemented and restarts DMA on overrun
- [ ] M7: DMA RX buffer invalidated; DMA TX buffer cleaned
- [ ] Baud rate accuracy verified (< ±2.5%)
- [ ] `__HAL_DMA_DISABLE_IT(hdmarx, DMA_IT_HT)` called after starting circular DMA if HT not needed

---

## 4. FDCAN

Applies to: G0, G4, H7, H7RS, U5, WB55 with FDCAN IP.

### 4.1 Bit timing calculation

```
Bit time = 1 / Nominal_Bitrate
Segments: Sync_Seg(1) + Prop_Seg + Phase_Seg1 + Phase_Seg2
Sample point: (1 + Prop + Phase1) / Total_TQ * 100%
Target sample point: 75-87.5% for CAN (CiA 601 recommendation)

Example: FDCAN kernel clock = 40 MHz, target = 500 kbps
Total TQ = 40,000,000 / 500,000 = 80 TQ per bit
Prescaler = 1
NomTimeSeg1 = 63, NomTimeSeg2 = 16 (63+16+1 = 80 TQ)
Sample point = (1 + 63) / 80 = 80% — OK

For CAN FD data phase (e.g., 2 Mbit/s):
Total TQ = 40,000,000 / 2,000,000 = 20 TQ
DataTimeSeg1 = 14, DataTimeSeg2 = 5 → SP = 75%
TDC (transmitter delay compensation): required at > 1 Mbit/s data rate
```

### 4.2 FDCAN init (H7 — CubeMX base + filter + global filter)

```c
/* CubeMX generates MX_FDCAN1_Init() — add filters and global config after */

void fdcan_configure(FDCAN_HandleTypeDef *hfdcan)
{
    /* Accept only frames with IDs 0x100–0x1FF into FIFO0 */
    FDCAN_FilterTypeDef filter = {
        .IdType       = FDCAN_STANDARD_ID,
        .FilterIndex  = 0,
        .FilterType   = FDCAN_FILTER_RANGE,
        .FilterConfig = FDCAN_FILTER_TO_RXFIFO0,
        .FilterID1    = 0x100U,
        .FilterID2    = 0x1FFU,
    };
    HAL_FDCAN_ConfigFilter(hfdcan, &filter);

    /* Reject all non-matching; filter remote frames (industrial: no RTR) */
    HAL_FDCAN_ConfigGlobalFilter(hfdcan,
        FDCAN_REJECT,          /* non-matching standard */
        FDCAN_REJECT,          /* non-matching extended */
        FDCAN_FILTER_REMOTE,   /* remote standard: filtered */
        FDCAN_FILTER_REMOTE);  /* remote extended: filtered */

    /* Activate FIFO0 new message interrupt */
    HAL_FDCAN_ActivateNotification(hfdcan,
        FDCAN_IT_RX_FIFO0_NEW_MESSAGE, 0);

    /* Activate error interrupts */
    HAL_FDCAN_ActivateNotification(hfdcan,
        FDCAN_IT_BUS_OFF       |
        FDCAN_IT_ERROR_PASSIVE |
        FDCAN_IT_ARB_PROTOCOL_ERROR |
        FDCAN_IT_DATA_PROTOCOL_ERROR, 0);

    HAL_FDCAN_Start(hfdcan);
}
```

### 4.3 FDCAN TX — non-blocking

```c
HAL_StatusTypeDef fdcan_transmit(FDCAN_HandleTypeDef *hfdcan,
                                   uint32_t id, const uint8_t *data, uint8_t dlc)
{
    /* CAN-FD DLC encoding is NON-LINEAR for DLC > 8 (9=12B, 10=16B, 11=20B,
     * 12=24B, 13=32B, 14=48B, 15=64B). The HAL macros FDCAN_DLC_BYTES_<N>
     * encode this correctly; do NOT compute as (dlc << 16). */
    static const uint32_t dlc_to_field[16] = {
        FDCAN_DLC_BYTES_0,  FDCAN_DLC_BYTES_1,  FDCAN_DLC_BYTES_2,  FDCAN_DLC_BYTES_3,
        FDCAN_DLC_BYTES_4,  FDCAN_DLC_BYTES_5,  FDCAN_DLC_BYTES_6,  FDCAN_DLC_BYTES_7,
        FDCAN_DLC_BYTES_8,  FDCAN_DLC_BYTES_12, FDCAN_DLC_BYTES_16, FDCAN_DLC_BYTES_20,
        FDCAN_DLC_BYTES_24, FDCAN_DLC_BYTES_32, FDCAN_DLC_BYTES_48, FDCAN_DLC_BYTES_64,
    };
    FDCAN_TxHeaderTypeDef hdr = {
        .Identifier          = id,
        .IdType              = FDCAN_STANDARD_ID,
        .TxFrameType         = FDCAN_DATA_FRAME,
        .DataLength          = dlc_to_field[dlc & 0x0FU],
        .ErrorStateIndicator = FDCAN_ESI_ACTIVE,
        .BitRateSwitch       = FDCAN_BRS_OFF,          /* FDCAN_BRS_ON for FD */
        .FDFormat            = FDCAN_CLASSIC_CAN,      /* FDCAN_FD_CAN for FD */
        .TxEventFifoControl  = FDCAN_NO_TX_EVENTS,
        .MessageMarker       = 0,
    };
    /* Check TX FIFO space */
    if (HAL_FDCAN_GetTxFifoFreeLevel(hfdcan) == 0) return HAL_BUSY;
    /* Correct HAL name is *_AddMessageToTxFifoQ — *_AddMessageToTxFifo does
     * not exist (link error). */
    return HAL_FDCAN_AddMessageToTxFifoQ(hfdcan, &hdr, data);
}
```

### 4.4 FDCAN RX callback + ISR routing

```c
/* Callback fires when new message in FIFO0 */
void HAL_FDCAN_RxFifo0Callback(FDCAN_HandleTypeDef *hfdcan, uint32_t RxFifo0ITs)
{
    FDCAN_RxHeaderTypeDef rx_hdr;
    uint8_t rx_data[64];  /* max CAN FD payload */

    while (HAL_FDCAN_GetRxFifoFillLevel(hfdcan, FDCAN_RX_FIFO0) > 0) {
        if (HAL_FDCAN_GetRxMessage(hfdcan, FDCAN_RX_FIFO0,
                                    &rx_hdr, rx_data) == HAL_OK) {
            uint8_t dlc = (uint8_t)(rx_hdr.DataLength >> 16U);
            can_rx_frame_t frame = {
                .id  = rx_hdr.Identifier,
                .dlc = dlc,
            };
            memcpy(frame.data, rx_data, dlc);
            /* Post to queue — never process in ISR */
            osMessageQueuePut(can_rx_queue, &frame, 0, 0);
        }
    }
}
```

### 4.5 FDCAN error handling — bus-off recovery (industrial)

```c
/* Bus-off = TEC > 255 — node disconnects from bus automatically */
/* NEVER auto-recover in safety-critical systems — application decides */

void HAL_FDCAN_ErrorStatusCallback(FDCAN_HandleTypeDef *hfdcan, uint32_t ErrorStatusITs)
{
    FDCAN_ProtocolStatusTypeDef status;
    HAL_FDCAN_GetProtocolStatus(hfdcan, &status);

    if (ErrorStatusITs & FDCAN_IT_BUS_OFF) {
        log_error(ERR_CAN_BUS_OFF);
        can_state = CAN_STATE_BUS_OFF;
        /* Do NOT call HAL_FDCAN_Stop + HAL_FDCAN_Start here */
        /* Let application task decide after debounce / safety check */
    }
    if (ErrorStatusITs & FDCAN_IT_ERROR_PASSIVE) {
        /* TEC or REC > 127 — error passive state */
        log_warning(WARN_CAN_ERROR_PASSIVE);
        log_debug("TEC=%u REC=%u", status.TxErrorCnt, status.RxErrorCnt);
    }
}

/* Application task — bus-off recovery with delay */
void can_monitor_task(void *arg)
{
    for (;;) {
        if (can_state == CAN_STATE_BUS_OFF) {
            osDelay(500);  /* wait before attempting recovery */
            HAL_FDCAN_Stop(&hfdcan1);
            HAL_FDCAN_Start(&hfdcan1);
            can_state = CAN_STATE_RUNNING;
            log_info("CAN bus-off recovery attempted");
        }
        osDelay(100);
    }
}
```

### 4.6 CAN FD — data phase bit rate switch

```c
/* CAN FD frame with bit rate switch: nominaal phase at 500kbps,
   data phase at 2Mbps */
FDCAN_TxHeaderTypeDef hdr = {
    .BitRateSwitch = FDCAN_BRS_ON,
    .FDFormat      = FDCAN_FD_CAN,
    .DataLength    = FDCAN_DLC_BYTES_64,   /* max 64 bytes */
    /* ... */
};

/* TDC (Transmitter Delay Compensation) — MANDATORY at > 1 Mbit/s data rate */
/* CubeMX: enable TDC, set TDCOffset = DataTimeSeg1 × DataPrescaler */
/* Incorrect TDC → bit errors at high data rate */
```

### 4.7 FDCAN checklist

- [ ] Bit timing verified with CAN bit timing calculator (e.g., Peak PCAN Symbol Editor)
- [ ] Sample point 75–87.5% for nominal; 70–80% for data phase
- [ ] Global filter set to REJECT non-matching (never accept-all in production)
- [ ] Per-message filters whitelisted (only expected IDs accepted)
- [ ] Bus-off recovery handled in application task, NOT in error callback ISR
- [ ] TEC/REC counters logged on error-passive for diagnostics
- [ ] TDC enabled and configured for data rates > 1 Mbit/s
- [ ] TX FIFO free level checked before transmit (HAL_FDCAN_GetTxFifoFreeLevel)
- [ ] Error interrupts enabled: BUS_OFF, ERROR_PASSIVE, ARB_PROTOCOL_ERROR, DATA_PROTOCOL_ERROR

---

## 5. Classic CAN (F4/F0)

### 5.1 Init and filter (F4 — bxCAN)

```c
/* bxCAN (F4/F0/F1/L1): up to 28 filter banks, list or mask mode */

void can_configure_filters(CAN_HandleTypeDef *hcan)
{
    CAN_FilterTypeDef filter = {
        .FilterBank           = 0,
        .FilterMode           = CAN_FILTERMODE_IDMASK,
        .FilterScale          = CAN_FILTERSCALE_32BIT,
        /* Accept IDs 0x100–0x1FF: mask = 0x700 */
        .FilterIdHigh         = (0x100U << 5),
        .FilterIdLow          = 0,
        .FilterMaskIdHigh     = (0x700U << 5),
        .FilterMaskIdLow      = 0x0006U,  /* bit0=RTR=0, bit1=IDE=0 (standard) */
        .FilterFIFOAssignment = CAN_RX_FIFO0,
        .FilterActivation     = ENABLE,
    };
    HAL_CAN_ConfigFilter(hcan, &filter);
    HAL_CAN_ActivateNotification(hcan,
        CAN_IT_RX_FIFO0_MSG_PENDING | CAN_IT_BUSOFF | CAN_IT_ERROR_PASSIVE);
    HAL_CAN_Start(hcan);
}
```

### 5.2 TX (F4 — select mailbox)

```c
HAL_StatusTypeDef can_transmit(CAN_HandleTypeDef *hcan,
                                 uint32_t id, const uint8_t *data, uint8_t dlc)
{
    uint32_t mailbox;
    CAN_TxHeaderTypeDef hdr = {
        .StdId = id,
        .IDE   = CAN_ID_STD,
        .RTR   = CAN_RTR_DATA,
        .DLC   = dlc,
    };
    if (HAL_CAN_GetTxMailboxesFreeLevel(hcan) == 0) return HAL_BUSY;
    return HAL_CAN_AddTxMessage(hcan, &hdr, data, &mailbox);
}
```

### 5.3 RX callback (F4)

```c
void HAL_CAN_RxFifo0MsgPendingCallback(CAN_HandleTypeDef *hcan)
{
    CAN_RxHeaderTypeDef rx_hdr;
    uint8_t rx_data[8];

    if (HAL_CAN_GetRxMessage(hcan, CAN_RX_FIFO0,
                               &rx_hdr, rx_data) == HAL_OK) {
        can_rx_frame_t frame = {
            .id  = rx_hdr.StdId,
            .dlc = (uint8_t)rx_hdr.DLC,
        };
        memcpy(frame.data, rx_data, rx_hdr.DLC);
        osMessageQueuePut(can_rx_queue, &frame, 0, 0);
    }
}
```

---

## 6. QSPI / OSPI — External Flash / XIP

### 6.1 QSPI single command (H7/F7/L4 — Quad-SPI)

```c
/* Send command + address + data in Quad mode */
HAL_StatusTypeDef qspi_write_page(QSPI_HandleTypeDef *hqspi,
                                    uint32_t addr, const uint8_t *data, uint32_t len)
{
    QSPI_CommandTypeDef cmd = {
        .InstructionMode   = QSPI_INSTRUCTION_1_LINE,
        .Instruction       = FLASH_CMD_PAGE_PROGRAM_QUAD,
        .AddressMode       = QSPI_ADDRESS_4_LINES,
        .AddressSize       = QSPI_ADDRESS_24_BITS,
        .Address           = addr,
        .AlternateByteMode = QSPI_ALTERNATE_BYTES_NONE,
        .DataMode          = QSPI_DATA_4_LINES,
        .NbData            = len,
        .DummyCycles       = 0,
        .DdrMode           = QSPI_DDR_MODE_DISABLE,
        .SIOOMode          = QSPI_SIOO_INST_EVERY_CMD,
    };
    /* Send Write Enable first */
    qspi_write_enable(hqspi);
    if (HAL_QSPI_Command(hqspi, &cmd, QSPI_TIMEOUT_MS) != HAL_OK) return HAL_ERROR;
    if (HAL_QSPI_Transmit(hqspi, data, QSPI_TIMEOUT_MS) != HAL_OK) return HAL_ERROR;
    /* Wait for WIP (Write In Progress) bit to clear */
    return qspi_wait_not_busy(hqspi, 5000U);
}

/* Memory-mapped mode for XIP (Execute In Place) */
void qspi_enable_memory_mapped(QSPI_HandleTypeDef *hqspi)
{
    QSPI_CommandTypeDef     cmd  = { /* fast read quad I/O command */ };
    QSPI_MemoryMappedTypeDef cfg = {
        .TimeOutActivation = QSPI_TIMEOUT_COUNTER_DISABLE,
    };
    HAL_QSPI_MemoryMapped(hqspi, &cmd, &cfg);
    /* Flash now visible at 0x90000000 (H7) */
    /* __attribute__((section(".qspi_text"))) for code in flash */
}
```

### 6.2 OSPI (H7RS / U5 — OctoSPI)

```c
/* OctoSPI: same pattern, different handle type (OSPI_HandleTypeDef) */
/* Supports: STR (Single Transfer Rate) and DTR (Double Transfer Rate) */
/* Hyperflash / OctoFlash: 8-bit data, optional DTR */

OSPI_RegularCmdTypeDef cmd = {
    .OperationType      = HAL_OSPI_OPTYPE_COMMON_CFG,
    .Instruction        = FLASH_CMD_READ,
    .InstructionMode    = HAL_OSPI_INSTRUCTION_8_LINES,
    .InstructionSize    = HAL_OSPI_INSTRUCTION_8_BITS,
    .InstructionDtrMode = HAL_OSPI_INSTRUCTION_DTR_DISABLE,
    .Address            = addr,
    .AddressMode        = HAL_OSPI_ADDRESS_8_LINES,
    .AddressSize        = HAL_OSPI_ADDRESS_32_BITS,
    .AddressDtrMode     = HAL_OSPI_ADDRESS_DTR_DISABLE,
    .DataMode           = HAL_OSPI_DATA_8_LINES,
    .DataDtrMode        = HAL_OSPI_DATA_DTR_DISABLE,
    .DummyCycles        = 20,
    .NbData             = len,
};
HAL_OSPI_Command(&hospi1, &cmd, OSPI_TIMEOUT_MS);
HAL_OSPI_Receive(&hospi1, data, OSPI_TIMEOUT_MS);
```

### 6.3 QSPI/OSPI XIP checklist

- [ ] Flash device timing verified (CS high time, dummy cycles) from datasheet
- [ ] Write Enable sent before every Page Program and Erase command
- [ ] WIP bit polled after write/erase (flash not ready until WIP=0)
- [ ] Sector/block erase time budgeted (typ 50–200ms) — never in ISR
- [ ] Memory-mapped mode: cache policy set in MPU (writeback or write-through depending on flash spec)
- [ ] XIP code in `.qspi_text` section with proper linker placement
- [ ] `SCB_EnableICache()` and `SCB_EnableDCache()` with MPU configured before enabling mapped mode

---

## 7. USB CDC (Virtual COM Port)

### 7.1 TX non-blocking (TinyUSB or STM32 USB Device Library)

```c
/* STM32 USB Device Library (Cube middleware) */
/* CDC_Transmit_FS blocks if previous TX not complete — check state first */

#include "usbd_cdc_if.h"

HAL_StatusTypeDef usb_cdc_send(const uint8_t *data, uint16_t len)
{
    /* CDC_Transmit_FS returns USBD_OK(0), USBD_BUSY(1), USBD_FAIL(2) */
    uint8_t result = CDC_Transmit_FS(data, len);
    if (result == USBD_BUSY) return HAL_BUSY;
    if (result != USBD_OK)   return HAL_ERROR;
    return HAL_OK;
}

/* In CDC_Receive_FS (called by USB ISR) — copy data and signal task */
int8_t CDC_Receive_FS(uint8_t *buf, uint32_t *len)
{
    /* Copy to application buffer */
    ring_buf_write_from_isr(usb_rx_ring, buf, (uint16_t)*len);
    /* Re-arm USB RX endpoint */
    USBD_CDC_SetRxBuffer(&hUsbDeviceFS, &Buf[0]);
    USBD_CDC_ReceivePacket(&hUsbDeviceFS);
    osEventFlagsSet(usb_evt_flags, USB_RX_FLAG);
    return USBD_OK;
}
```

### 7.2 USB CDC checklist

- [ ] `CDC_Transmit_FS` called only when previous TX complete (USBD_BUSY handled)
- [ ] USB ISR priority below `configMAX_SYSCALL_INTERRUPT_PRIORITY` (FreeRTOS)
- [ ] `USBD_CDC_SetRxBuffer` + `USBD_CDC_ReceivePacket` called in `CDC_Receive_FS` to re-arm endpoint
- [ ] USB enumeration: verify `VID/PID` in `usbd_desc.c` matches INF driver on host
- [ ] Disconnect/reconnect: `HAL_GPIO_WritePin(USB_DP_PORT, USB_DP_PIN, RESET)` for bus reset if DP pullup controlled externally

---

## 8. 1-Wire

### 8.1 Bit-bang 1-Wire (any GPIO, DWT timing)

```c
/* Uses DWT cycle counter for microsecond timing — no timer needed */

static inline void ow_delay_us(uint32_t us)
{
    uint32_t end = DWT->CYCCNT + us * (SystemCoreClock / 1000000U);
    while ((int32_t)(end - DWT->CYCCNT) > 0);
}

static inline void ow_pin_low(void)   { OW_GPIO->BSRR = OW_PIN << 16U; }
static inline void ow_pin_high(void)  { OW_GPIO->BSRR = OW_PIN; }
static inline uint8_t ow_pin_read(void) { return (OW_GPIO->IDR & OW_PIN) ? 1U : 0U; }

/* Reset pulse — returns 1 if device present */
bool ow_reset(void)
{
    ow_pin_low();
    ow_delay_us(480);   /* reset pulse: ≥ 480µs */
    ow_pin_high();
    ow_delay_us(70);    /* sample window for presence pulse */
    bool present = (ow_pin_read() == 0);
    ow_delay_us(410);   /* wait for end of presence period */
    return present;
}

void ow_write_bit(uint8_t bit)
{
    ow_pin_low();
    ow_delay_us(bit ? 6U : 60U);    /* write-1: 6µs low; write-0: 60µs low */
    ow_pin_high();
    ow_delay_us(bit ? 64U : 10U);   /* recovery */
}

uint8_t ow_read_bit(void)
{
    uint8_t bit;
    ow_pin_low();
    ow_delay_us(6);                  /* initiate read slot */
    ow_pin_high();
    ow_delay_us(9);                  /* sample at < 15µs */
    bit = ow_pin_read();
    ow_delay_us(55);                 /* rest of slot */
    return bit;
}

void ow_write_byte(uint8_t byte)
{
    for (int i = 0; i < 8; i++) {
        ow_write_bit(byte & 0x01U);
        byte >>= 1;
    }
}

uint8_t ow_read_byte(void)
{
    uint8_t byte = 0;
    for (int i = 0; i < 8; i++) {
        byte |= (uint8_t)(ow_read_bit() << i);
    }
    return byte;
}

/* DS18B20 temperature read — full sequence */
bool ds18b20_read_temp(float *temp_c)
{
    if (!ow_reset()) return false;
    ow_write_byte(0xCC);   /* Skip ROM (single device on bus) */
    ow_write_byte(0x44);   /* Convert T */
    HAL_Delay(750);         /* Wait for 12-bit conversion (max 750ms) */
    if (!ow_reset()) return false;
    ow_write_byte(0xCC);
    ow_write_byte(0xBE);   /* Read Scratchpad */
    uint8_t lsb = ow_read_byte();
    uint8_t msb = ow_read_byte();
    int16_t raw = (int16_t)((msb << 8) | lsb);
    *temp_c = (float)raw / 16.0f;
    return true;
}
```

### 8.2 1-Wire checklist

- [ ] DWT enabled before first call (`CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk; DWT->CTRL |= 1;`)
- [ ] GPIO configured as open-drain output with external 4.7kΩ pull-up to VCC
- [ ] RTOS context: `ow_delay_us` must NOT be called from task with scheduler running (blocks CPU) — use dedicated bare-metal timing slot or UART trick (UART 1-wire mode on supported devices)
- [ ] CRC8 (Dallas/Maxim) verified on scratchpad data before using temperature
- [ ] Multi-drop bus: use ROM Search (0xF0) algorithm to enumerate devices

---

## 9. Protocol Verification Checklist

### Logic Analyzer / Oscilloscope verification

| Protocol | What to verify |
|----------|---------------|
| I2C | ACK bit after every byte, clock stretching by slave, STOP/START timing, SCL frequency |
| SPI | CPOL/CPHA alignment, CS setup/hold time, correct data on capture edge |
| UART | Baud rate accuracy (measure bit width), start/stop bits, no framing errors |
| RS485 | DE/RE switching delay, no bus collision (both drivers active simultaneously) |
| CAN | Arbitration (multi-node test), ACK slot, bit stuffing, bus-off recovery |
| FDCAN | Bit rate switch correct, TDC offset matches measured propagation delay |
| 1-Wire | Reset pulse width ≥ 480µs, presence pulse < 15µs, slot timing |

### Fault injection test matrix

| Protocol | Fault to inject | Expected behavior |
|----------|----------------|-------------------|
| I2C | Pull SDA low during TX | Bus lockup detected, recovery executed |
| I2C | Remove pull-up resistor | HAL_BUSY or timeout, recovery called |
| SPI | Float MISO | Data validated by CRC/checksum layer |
| UART | Disconnect TX | ORE error flagged, DMA restarted |
| CAN | Short CAN-H to GND | Bus-off detected, logged, recovery debounced |
| CAN | Remove termination | Increased error frames, TEC rises, passive state |
| FDCAN | Inject error frame | Error counter increments, passive state if persistent |

### Common mistakes (by protocol)

**I2C:**
- Forgetting to shift device address left 1 bit before HAL call
- Using `HAL_MAX_DELAY` → bus hangs forever on stuck slave
- Not calling recovery after timeout on v1 peripheral (BUSY flag stays set)

**SPI:**
- Using hardware NSS in multi-slave — NSS goes high between bytes incorrectly
- Not accounting for CS setup/hold time at high clock speeds
- F7/H7 SPIv2: FIFO threshold mismatch (FRXTH bit) causes RXNE to never fire

**UART:**
- Byte-by-byte ISR at high baud rates → ISR overrun, data loss
- RS485: switching DE to RX before TC fires → last byte cut off
- Not re-enabling DMA after `HAL_UART_ErrorCallback`

**CAN/FDCAN:**
- No global filter reject → accept-all in production (security risk + noise)
- Recovering from bus-off in error ISR → possible re-entry, log overflow
- Missing TDC at high data rates → intermittent bit errors

**QSPI:**
- Not waiting for WIP=0 after write → next command corrupts flash
- Wrong dummy cycles → read returns garbage (must match flash datasheet)
- XIP code in cached region without MPU write-back policy → stale instruction fetch

---

## 9. RTOS Integration

### 9.1 Core principle: peripheral ownership model

Every shared peripheral needs one owner. Don't scatter SPI calls across tasks.

```
Correct:           Wrong:
SPI task           Task A ──→ SPI directly
  ↑ queue          Task B ──→ SPI directly   ← race condition
Task A             Task C ──→ SPI directly
Task B
```

**Two valid patterns:**
1. **Dedicated peripheral task** — only one task ever touches the peripheral registers
2. **Mutex-guarded access** — any task can access, but must acquire mutex first

Use pattern 1 for high-throughput or complex state machines (CAN, UART DMA).  
Use pattern 2 for infrequent, blocking access (I2C sensor reads, SPI config writes).

---

### 9.2 I2C with mutex — FreeRTOS + RTX5

```c
/* One mutex per I2C bus — created at startup */
#if defined(FREERTOS_FLAVOR)
static SemaphoreHandle_t i2c1_mutex;
void bus_init(void) { i2c1_mutex = xSemaphoreCreateMutex(); }

HAL_StatusTypeDef i2c_write_task_safe(uint8_t dev, uint8_t reg,
                                        const uint8_t *data, uint16_t len)
{
    if (xSemaphoreTake(i2c1_mutex, pdMS_TO_TICKS(50)) != pdTRUE)
        return HAL_TIMEOUT;
    HAL_StatusTypeDef r = i2c_write_safe(&hi2c1, dev, reg, data, len);
    xSemaphoreGive(i2c1_mutex);
    return r;
}

#elif defined(RTX5_FLAVOR)
static osMutexId_t i2c1_mutex;
static const osMutexAttr_t i2c1_mutex_attr = { "I2C1", osMutexRobust, NULL, 0 };
void bus_init(void) { i2c1_mutex = osMutexNew(&i2c1_mutex_attr); }

HAL_StatusTypeDef i2c_write_task_safe(uint8_t dev, uint8_t reg,
                                        const uint8_t *data, uint16_t len)
{
    if (osMutexAcquire(i2c1_mutex, 50) != osOK)   /* 50ms timeout */
        return HAL_TIMEOUT;
    HAL_StatusTypeDef r = i2c_write_safe(&hi2c1, dev, reg, data, len);
    osMutexRelease(i2c1_mutex);
    return r;
}
#endif
```

**Mutex rules:**
- Use `osMutexRobust` (RTX5) or `configUSE_MUTEXES=1` (FreeRTOS) — enables priority inheritance, prevents priority inversion
- Never call from ISR — mutexes are task-only; use binary semaphores for ISR signaling
- Set timeout, never infinite — a hung peripheral shouldn't hang the system

---

### 9.3 SPI with DMA completion semaphore

```c
/* DMA SPI: ISR gives semaphore → task unblocks after transfer */

#if defined(FREERTOS_FLAVOR)
static SemaphoreHandle_t spi_dma_done;
void spi_rtos_init(void) { spi_dma_done = xSemaphoreCreateBinary(); }

void spi_transfer_blocking_rtos(const uint8_t *tx, uint8_t *rx, uint16_t len)
{
    /* Prepare DMA as usual (cache clean/invalidate) */
    SCB_CleanDCache_by_Addr((uint32_t *)tx, (len + 31U) & ~31U);
    SCB_InvalidateDCache_by_Addr((uint32_t *)rx, (len + 31U) & ~31U);
    HAL_SPI_TransmitReceive_DMA(&hspi1, tx, rx, len);
    /* Block task until ISR gives semaphore */
    xSemaphoreTake(spi_dma_done, pdMS_TO_TICKS(100));
}

void HAL_SPI_TxRxCpltCallback(SPI_HandleTypeDef *hspi)
{
    BaseType_t woken = pdFALSE;
    xSemaphoreGiveFromISR(spi_dma_done, &woken);
    portYIELD_FROM_ISR(woken);
}

#elif defined(RTX5_FLAVOR)
static osSemaphoreId_t spi_dma_done;
void spi_rtos_init(void) {
    spi_dma_done = osSemaphoreNew(1, 0, NULL);  /* initial count = 0 */
}

void spi_transfer_blocking_rtos(const uint8_t *tx, uint8_t *rx, uint16_t len)
{
    SCB_CleanDCache_by_Addr((uint32_t *)tx, (len + 31U) & ~31U);
    SCB_InvalidateDCache_by_Addr((uint32_t *)rx, (len + 31U) & ~31U);
    HAL_SPI_TransmitReceive_DMA(&hspi1, tx, rx, len);
    osSemaphoreAcquire(spi_dma_done, 100);  /* 100ms */
}

void HAL_SPI_TxRxCpltCallback(SPI_HandleTypeDef *hspi)
{
    osSemaphoreRelease(spi_dma_done);  /* RTX5: safe from ISR */
}
#endif
```

---

### 9.4 UART RX — ISR/DMA → task via queue

```c
/* CAN RX pattern works for UART too: ISR populates queue, task consumes */

typedef struct { uint8_t data[128]; uint16_t len; } uart_frame_t;

#if defined(FREERTOS_FLAVOR)
static QueueHandle_t uart_rx_queue;
void uart_rtos_init(void) {
    uart_rx_queue = xQueueCreate(8, sizeof(uart_frame_t));
}

/* Called from HAL UART callback (in ISR context) */
void uart_enqueue_frame_from_isr(const uint8_t *data, uint16_t len)
{
    uart_frame_t frame;
    frame.len = (len > sizeof(frame.data)) ? sizeof(frame.data) : len;
    memcpy(frame.data, data, frame.len);
    BaseType_t woken = pdFALSE;
    xQueueSendFromISR(uart_rx_queue, &frame, &woken);
    portYIELD_FROM_ISR(woken);
}

void uart_task(void *arg) {
    uart_frame_t frame;
    for (;;) {
        if (xQueueReceive(uart_rx_queue, &frame, portMAX_DELAY) == pdTRUE)
            protocol_parse(frame.data, frame.len);
    }
}

#elif defined(RTX5_FLAVOR)
static osMessageQueueId_t uart_rx_queue;
void uart_rtos_init(void) {
    uart_rx_queue = osMessageQueueNew(8, sizeof(uart_frame_t), NULL);
}

void uart_enqueue_frame_from_isr(const uint8_t *data, uint16_t len)
{
    uart_frame_t frame;
    frame.len = (len > sizeof(frame.data)) ? sizeof(frame.data) : len;
    memcpy(frame.data, data, frame.len);
    osMessageQueuePut(uart_rx_queue, &frame, 0, 0); /* RTX5 auto-detects ISR context */
}

void uart_task(void *arg) {
    uart_frame_t frame;
    for (;;) {
        if (osMessageQueueGet(uart_rx_queue, &frame, NULL, osWaitForever) == osOK)
            protocol_parse(frame.data, frame.len);
    }
}
#endif
```

---

### 9.5 CAN RX — event flags for priority signaling

Event flags are faster than queues for single-event signaling (new frame available):

```c
/* Pattern: ISR sets flag → high-priority task unblocks → reads from FIFO */

#if defined(FREERTOS_FLAVOR)
static EventGroupHandle_t can_events;
#define CAN_RX_FLAG  (1 << 0)
#define CAN_ERR_FLAG (1 << 1)

void can_rtos_init(void) { can_events = xEventGroupCreate(); }

void HAL_FDCAN_RxFifo0Callback(FDCAN_HandleTypeDef *h, uint32_t ITs)
{
    BaseType_t woken = pdFALSE;
    xEventGroupSetBitsFromISR(can_events, CAN_RX_FLAG, &woken);
    portYIELD_FROM_ISR(woken);
}

void can_rx_task(void *arg) {
    for (;;) {
        xEventGroupWaitBits(can_events, CAN_RX_FLAG, pdTRUE, pdFALSE, portMAX_DELAY);
        /* Drain FIFO — may have multiple frames */
        FDCAN_RxHeaderTypeDef hdr; uint8_t data[64];
        while (HAL_FDCAN_GetRxFifoFillLevel(&hfdcan1, FDCAN_RX_FIFO0) > 0) {
            HAL_FDCAN_GetRxMessage(&hfdcan1, FDCAN_RX_FIFO0, &hdr, data);
            can_dispatch(&hdr, data);
        }
    }
}

#elif defined(RTX5_FLAVOR)
static osEventFlagsId_t can_events;
#define CAN_RX_FLAG  (1U << 0)

void can_rtos_init(void) { can_events = osEventFlagsNew(NULL); }

void HAL_FDCAN_RxFifo0Callback(FDCAN_HandleTypeDef *h, uint32_t ITs)
{
    osEventFlagsSet(can_events, CAN_RX_FLAG);  /* safe from ISR */
}

void can_rx_task(void *arg) {
    for (;;) {
        osEventFlagsWait(can_events, CAN_RX_FLAG, osFlagsWaitAny, osWaitForever);
        FDCAN_RxHeaderTypeDef hdr; uint8_t data[64];
        while (HAL_FDCAN_GetRxFifoFillLevel(&hfdcan1, FDCAN_RX_FIFO0) > 0) {
            HAL_FDCAN_GetRxMessage(&hfdcan1, FDCAN_RX_FIFO0, &hdr, data);
            can_dispatch(&hdr, data);
        }
    }
}
#endif
```

---

### 9.6 FDCAN dual FIFO + Tx Buffer / Queue management

FDCAN has 3 distinct RX paths and 3 TX paths — use them to separate priorities:

```
RX paths:
  FIFO 0  → high-priority frames (control, safety) — interrupt-driven
  FIFO 1  → low-priority frames (diagnostics, telemetry) — polled
  Rx Buffer → dedicated buffer for specific IDs (filter config required)

TX paths:
  Tx Buffer → dedicated slot, explicit transmission request
  Tx FIFO   → FIFO queue, HW sends in submission order
  Tx Queue  → priority queue, HW sends highest-priority frame first (sorted by CAN ID)
```

```c
/* Filter: split traffic between FIFO0 and FIFO1 */
FDCAN_FilterTypeDef f0 = {
    .FilterIndex  = 0,
    .FilterType   = FDCAN_FILTER_RANGE,
    .FilterConfig = FDCAN_FILTER_TO_RXFIFO0,  /* safety/control IDs */
    .FilterID1    = 0x100U, .FilterID2 = 0x1FFU,
};
FDCAN_FilterTypeDef f1 = {
    .FilterIndex  = 1,
    .FilterType   = FDCAN_FILTER_RANGE,
    .FilterConfig = FDCAN_FILTER_TO_RXFIFO1,  /* diagnostic/telemetry IDs */
    .FilterID1    = 0x400U, .FilterID2 = 0x4FFU,
};
HAL_FDCAN_ConfigFilter(&hfdcan1, &f0);
HAL_FDCAN_ConfigFilter(&hfdcan1, &f1);

/* Activate interrupts for both FIFOs */
HAL_FDCAN_ActivateNotification(&hfdcan1,
    FDCAN_IT_RX_FIFO0_NEW_MESSAGE | FDCAN_IT_RX_FIFO1_NEW_MESSAGE, 0);

/* TX Queue mode (CubeMX: TxFifoQueueMode = TX_QUEUE_OPERATION) */
/* HAL routes through Tx Queue when configured — H7 supports up to 32 Tx buffers */
/* Check free level before sending: */
if (HAL_FDCAN_GetTxFifoFreeLevel(&hfdcan1) == 0) {
    /* TX queue full: log and drop or retry */
}

/* FIFO0 overflow protection: watermark interrupt */
HAL_FDCAN_ActivateNotification(&hfdcan1, FDCAN_IT_RX_FIFO0_WATERMARK, 0);
/* Set watermark at 75% of FIFO depth (CubeMX: Rx Fifo0 Watermark) */
```

```c
/* Rx FIFO fill level monitoring — call from low-priority monitor task */
void can_fifo_monitor(void)
{
    uint32_t f0_fill = HAL_FDCAN_GetRxFifoFillLevel(&hfdcan1, FDCAN_RX_FIFO0);
    uint32_t f1_fill = HAL_FDCAN_GetRxFifoFillLevel(&hfdcan1, FDCAN_RX_FIFO1);
    if (f0_fill >= 3) log_warning(WARN_CAN_FIFO0_NEAR_FULL, f0_fill);
    if (f1_fill >= 3) log_warning(WARN_CAN_FIFO1_NEAR_FULL, f1_fill);

    FDCAN_ProtocolStatusTypeDef ps;
    HAL_FDCAN_GetProtocolStatus(&hfdcan1, &ps);
    if (ps.RxBRSCount > 0)   log_debug("FD frames received: BRS active");
    if (ps.TxBRSCount > 0)   log_debug("FD frames sent: BRS active");
    log_debug("TEC=%u REC=%u", ps.TxErrorCnt, ps.RxErrorCnt);
}
```

---

### 9.7 RTOS integration checklist

- [ ] Every shared peripheral (I2C bus, SPI bus) protected by one mutex
- [ ] Mutex has `osMutexRobust` / priority inheritance enabled (prevents priority inversion)
- [ ] No mutex acquire/release in ISR — use binary semaphore or event flags
- [ ] DMA completion uses semaphore (not busy-wait) in RTOS tasks
- [ ] CAN RX: event flags for high-priority, queue for buffered frames
- [ ] Queue depth ≥ burst frame count (CAN: ≥ 8; UART: ≥ 4 frames)
- [ ] `portYIELD_FROM_ISR(woken)` called after every `xXxxxFromISR` in FreeRTOS
- [ ] RTX5: `osMessageQueuePut` / `osEventFlagsSet` used from ISR (RTX5 auto-detects)
- [ ] FDCAN FIFO0 ↔ FIFO1 split: control traffic in FIFO0, diagnostics in FIFO1
- [ ] FDCAN Tx Queue mode for automatic priority arbitration on multi-frame bursts
- [ ] FIFO watermark interrupt enabled to catch near-overflow before loss

---

## 10. Protocol Verification Checklist

### Logic Analyzer / Oscilloscope verification

| Protocol | What to verify |
|----------|---------------|
| I2C | ACK bit after every byte, clock stretching by slave, STOP/START timing, SCL frequency |
