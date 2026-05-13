# Ethernet + LwIP — STM32 (F7/H7/H5)

## Hardware Requirements

```
RMII pinout (mandatory, 7 pins):
  REF_CLK (50MHz external oscillator → MCU) — PA1
  MDIO    → PA2
  MDC     → PC1
  CRS_DV  → PA7
  RXD0    → PC4
  RXD1    → PC5
  TXD0    → PB11 (or PG11)
  TXD1    → PB12 (or PG12)
  TX_EN   → PB10 (or PG11)

GPIO speed: VERY_HIGH mandatory for all ETH pins
GPIO pull:  NOPULL (PHY handles termination)
```

## ETH HAL Init Pattern

```c
ETH_HandleTypeDef heth;

void MX_ETH_Init(void)
{
    heth.Instance              = ETH;
    heth.Init.MACAddr[0]       = 0x00;     /* OUI or derived from UID */
    heth.Init.MACAddr[1]       = 0x80;
    heth.Init.MACAddr[2]       = 0xE1;
    heth.Init.MACAddr[3]       = 0x00;
    heth.Init.MACAddr[4]       = 0x00;
    heth.Init.MACAddr[5]       = 0x00;
    heth.Init.MediaInterface   = HAL_ETH_RMII_MODE;
    heth.Init.TxDesc           = DMATxDscrTab;  /* must be in AXI SRAM on H7 */
    heth.Init.RxDesc           = DMARxDscrTab;
    heth.Init.RxBuffLen        = ETH_RX_BUFFER_SIZE;

    if (HAL_ETH_Init(&heth) != HAL_OK) { Error_Handler(); }

    /* Configure ETH MAC — full duplex, 100Mbps after autoneg */
    ETH_MACConfigTypeDef macconf = {0};
    HAL_ETH_GetMACConfig(&heth, &macconf);
    macconf.DuplexMode = ETH_FULLDUPLEX_MODE;
    macconf.Speed      = ETH_SPEED_100M;
    HAL_ETH_SetMACConfig(&heth, &macconf);
}
```

## DMA Descriptor Placement (H7 CRITICAL)

```c
/* STM32H7: DMA descriptors and Rx buffers MUST be in non-cacheable AXI SRAM */
/* DTCM (0x20000000) → ETH DMA cannot access it → HardFault */

/* Place in .lwip_sec section mapped to AXI SRAM with MPU non-cacheable */
ETH_DMADescTypeDef DMATxDscrTab[ETH_TX_DESC_CNT] __attribute__((section(".lwip_sec"), aligned(32)));
ETH_DMADescTypeDef DMARxDscrTab[ETH_RX_DESC_CNT] __attribute__((section(".lwip_sec"), aligned(32)));
uint8_t Rx_Buff[ETH_RX_DESC_CNT][ETH_RX_BUFFER_SIZE]  __attribute__((section(".lwip_sec"), aligned(32)));
```

```c
/* Linker script (GCC): add .lwip_sec region */
/* AXI_RAM (rwx) : ORIGIN = 0x24000000, LENGTH = 512K */
.lwip_sec (NOLOAD) :
{
    . = ALIGN(32);
    *(.lwip_sec)
    . = ALIGN(32);
} >AXI_RAM
```

```c
/* MPU non-cacheable region for ETH DMA area (add in SystemClock_Config or before HAL_ETH_Init) */
MPU_Region_InitTypeDef mpu = {0};
HAL_MPU_Disable();
mpu.Enable           = MPU_REGION_ENABLE;
mpu.BaseAddress      = 0x24000000;
mpu.Size             = MPU_REGION_SIZE_512KB;
mpu.AccessPermission = MPU_REGION_FULL_ACCESS;
mpu.IsBufferable     = MPU_ACCESS_NOT_BUFFERABLE;
mpu.IsCacheable      = MPU_ACCESS_NOT_CACHEABLE;
mpu.IsShareable      = MPU_ACCESS_NOT_SHAREABLE;
mpu.Number           = MPU_REGION_NUMBER0;
mpu.TypeExtField     = MPU_TEX_LEVEL1;
mpu.SubRegionDisable = 0x00;
mpu.DisableExec      = MPU_INSTRUCTION_ACCESS_ENABLE;
HAL_MPU_ConfigRegion(&mpu);
HAL_MPU_Enable(MPU_PRIVILEGED_DEFAULT);
```

## PHY Initialization (LAN8742, DP83848, KSZ8081)

```c
/* LAN8742A — most common on NUCLEO/Discovery boards */
#define LAN8742_PHY_ADDRESS   0x00U
#define LAN8742_BCR_REG       0x00U
#define LAN8742_BSR_REG       0x01U
#define LAN8742_PHYSCSR_REG   0x1FU

/* Reset PHY */
HAL_ETH_WritePHYRegister(&heth, LAN8742_PHY_ADDRESS, LAN8742_BCR_REG, 0x8000);
HAL_Delay(500);  /* LAN8742 needs 500ms after reset */

/* Start autonegotiation */
HAL_ETH_WritePHYRegister(&heth, LAN8742_PHY_ADDRESS, LAN8742_BCR_REG, 0x1200);

/* Wait for link (with timeout) */
uint32_t t0 = HAL_GetTick();
uint32_t bsr;
do {
    HAL_ETH_ReadPHYRegister(&heth, LAN8742_PHY_ADDRESS, LAN8742_BSR_REG, &bsr);
    if ((HAL_GetTick() - t0) > 5000U) { /* link up timeout */ break; }
} while ((bsr & 0x0004) == 0);  /* BSR bit2: Link Status */

/* Read negotiated speed/duplex from PHY-specific register */
uint32_t physcsr;
HAL_ETH_ReadPHYRegister(&heth, LAN8742_PHY_ADDRESS, LAN8742_PHYSCSR_REG, &physcsr);
/* physcsr[3:2]: 01=10M half, 10=100M half, 11=10M full, 10x=100M full */
```

```
PHY Reset Timing (mandatory minimum delays):
  LAN8742A : 500ms after nRST assert, 100ms before any register access
  DP83848  : 100ms after reset
  KSZ8081  : 50ms after reset
  Skipping this causes autoneg failure or stuck link state
```

## LwIP Configuration (lwipopts.h)

```c
/* lwipopts.h — tuned for STM32H7 at 480MHz */

#define NO_SYS                      0       /* use RTOS */
#define LWIP_SOCKET                 1
#define LWIP_NETCONN                1
#define LWIP_NETIF_LINK_CALLBACK    1       /* link up/down events */
#define LWIP_NETIF_STATUS_CALLBACK  1

/* Memory */
#define MEM_SIZE                    (32 * 1024)   /* heap for pbuf/TCP */
#define MEMP_NUM_PBUF               24
#define MEMP_NUM_RAW_PCB            4
#define MEMP_NUM_TCP_PCB            8
#define MEMP_NUM_TCP_PCB_LISTEN     4
#define MEMP_NUM_TCP_SEG            32
#define MEMP_NUM_SYS_TIMEOUT        10
#define PBUF_POOL_SIZE              24
#define PBUF_POOL_BUFSIZE           1536    /* > ETH MTU (1514) + alignment */

/* TCP */
#define TCP_MSS                     1460    /* must match MTU - 40 bytes headers */
#define TCP_SND_BUF                 (4 * TCP_MSS)
#define TCP_WND                     (4 * TCP_MSS)
#define TCP_SND_QUEUELEN            8

/* ICMP, ARP */
#define LWIP_ICMP                   1
#define ARP_TABLE_SIZE              4
#define ARP_QUEUEING                1

/* DHCP */
#define LWIP_DHCP                   1
#define DHCP_DOES_ARP_CHECK         0       /* faster init */

/* Checksum offload to ETH MAC */
#define CHECKSUM_BY_HARDWARE        1       /* requires ETH MAC checksum engine */
#define CHECKSUM_GEN_IP             0
#define CHECKSUM_GEN_UDP            0
#define CHECKSUM_GEN_TCP            0
#define CHECKSUM_CHECK_IP           0
#define CHECKSUM_CHECK_UDP          0
#define CHECKSUM_CHECK_TCP          0

/* RTOS task stack */
#define TCPIP_THREAD_STACKSIZE      4096    /* minimum — never less than 2KB */
#define TCPIP_THREAD_PRIO           osPriorityAboveNormal
#define DEFAULT_THREAD_STACKSIZE    1024
```

## RTOS Integration (sys_arch)

```c
/* sys_arch.c skeleton for RTX5/FreeRTOS */

sys_prot_t sys_arch_protect(void)
{
    /* disable interrupts — used for short critical sections in LwIP */
    sys_prot_t old = __get_PRIMASK();
    __disable_irq();
    return old;
}

void sys_arch_unprotect(sys_prot_t pval)
{
    __set_PRIMASK(pval);
}

u32_t sys_now(void)
{
    return HAL_GetTick();  /* or osKernelGetTickCount() */
}

/* LwIP main task — must call ethernetif_input periodically */
void ethernetif_task(void *arg)
{
    for (;;) {
        /* Wait for ETH RX event (semaphore from HAL_ETH_RxCpltCallback) */
        osSemaphoreAcquire(eth_rx_sem, 50);  /* 50ms timeout for periodic checks */
        ethernetif_input(&gnetif);           /* process all pending RX packets */
        sys_check_timeouts();                /* LwIP timers (DHCP, TCP keepalive) */
    }
}
```

## Network Interface Init

```c
#include "lwip/netif.h"
#include "lwip/dhcp.h"
#include "netif/etharp.h"

struct netif gnetif;

void network_init(void)
{
    ip_addr_t ipaddr, netmask, gw;

#if LWIP_DHCP
    IP_ADDR4(&ipaddr,  0, 0, 0, 0);
    IP_ADDR4(&netmask, 0, 0, 0, 0);
    IP_ADDR4(&gw,      0, 0, 0, 0);
#else
    IP_ADDR4(&ipaddr,  192, 168, 1, 10);
    IP_ADDR4(&netmask, 255, 255, 255, 0);
    IP_ADDR4(&gw,      192, 168, 1,  1);
#endif

    tcpip_init(NULL, NULL);

    netif_add(&gnetif, &ipaddr, &netmask, &gw, NULL,
              ethernetif_init, tcpip_input);
    netif_set_default(&gnetif);

    /* Register link up/down callbacks */
    netif_set_link_callback(&gnetif, link_changed_cb);
    netif_set_status_callback(&gnetif, status_changed_cb);

    if (netif_is_link_up(&gnetif)) {
        netif_set_up(&gnetif);
#if LWIP_DHCP
        dhcp_start(&gnetif);
#endif
    }
}

void HAL_ETH_RxCpltCallback(ETH_HandleTypeDef *heth)
{
    osSemaphoreRelease(eth_rx_sem);  /* signal ethernetif_task */
}
```

## TCP Server (netconn API)

```c
void tcp_server_task(void *arg)
{
    struct netconn *conn, *client;
    struct netbuf *inbuf;
    void *data;
    u16_t len;

    conn = netconn_new(NETCONN_TCP);
    netconn_bind(conn, NULL, 80);   /* port 80 */
    netconn_listen(conn);

    for (;;) {
        if (netconn_accept(conn, &client) != ERR_OK) continue;

        while (netconn_recv(client, &inbuf) == ERR_OK) {
            netbuf_data(inbuf, &data, &len);
            /* process data */
            netconn_write(client, response, resp_len, NETCONN_COPY);
            netbuf_delete(inbuf);
        }
        netconn_close(client);
        netconn_delete(client);
    }
}
```

## UDP (Raw API)

```c
void udp_broadcast_send(const uint8_t *data, uint16_t len)
{
    struct udp_pcb *pcb = udp_new();
    ip_addr_t dst;
    IP_ADDR4(&dst, 255, 255, 255, 255);

    struct pbuf *p = pbuf_alloc(PBUF_TRANSPORT, len, PBUF_RAM);
    memcpy(p->payload, data, len);
    udp_sendto(pcb, p, &dst, 1234);
    pbuf_free(p);
    udp_remove(pcb);
}
```

## DHCP Wait Pattern

```c
void wait_for_dhcp(uint32_t timeout_ms)
{
    uint32_t t0 = HAL_GetTick();
    while (dhcp_supplied_address(&gnetif) == 0) {
        if ((HAL_GetTick() - t0) > timeout_ms) {
            /* Fall back to static IP */
            dhcp_stop(&gnetif);
            IP_ADDR4(&gnetif.ip_addr,  192, 168, 1, 10);
            netif_set_up(&gnetif);
            return;
        }
        osDelay(100);
    }
}
```

## Common Bugs

| Bug | Symptom | Fix |
|-----|---------|-----|
| ETH DMA buffers in DTCM | HardFault on ETH DMA | Move to AXI SRAM (.lwip_sec) |
| MPU not set non-cacheable | Random packet corruption | Add MPU region before ETH init |
| PHY reset too short | Autoneg fails, link never up | 500ms delay for LAN8742 |
| RMII CLK not 50MHz exact | Packet loss at high rate | Use external oscillator, not MCO |
| `sys_check_timeouts` not called | DHCP never completes, TCP retransmit stuck | Call in ethernetif_task loop |
| `PBUF_POOL_BUFSIZE < 1514` | Large packets dropped silently | Set to 1536 |
| `TCP_MSS` > 1460 | Fragmentation, TCP slow | Always 1460 for 100M Ethernet |
| LwIP not thread-safe | Crash in concurrent socket calls | All LwIP calls from tcpip_thread via `tcpip_callback` |
| Missing `netif_set_link_up` | IP address never assigned | Call in PHY link-up detection |
