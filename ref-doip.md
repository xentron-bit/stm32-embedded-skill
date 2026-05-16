# DoIP — Diagnostics over Internet Protocol (ISO 13400)

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, errata workarounds, protocol-spec content** here is authoritative — that is why this file exists.
> - **Inline HAL/CMSIS/peripheral code snippets** are illustrative. The HAL drifts between versions and parts. For the canonical version of any HAL symbol at your HAL release: `gh search code <SymbolName> --owner=STMicroelectronics --extension=c` — see [ref-st-github-map.md](ref-st-github-map.md) §8 for the full lookup procedure.
> - **CRITICAL bugs identified in the 2026-05-16 audit have been corrected** in this file, but verify against your own HAL version before copy-pasting.
> - **For bootloader / IAP / OTA topics** the canonical checklist + ARM KA001193 + AN5188/2606/3155/3156 references are in [ref-bootloader.md](ref-bootloader.md).


Kaynak: ISO 13400-2:2019 (Transport protocol and network layer services)

DoIP, araç dış ağ bağlantısı (Ethernet, Wi-Fi) üzerinden UDS (ISO 14229) mesajlarını
iletmek için tanımlanmış bir uygulama katmanı protokolüdür. CAN-tabanlı K-Line/ISO-TP
yerine Ethernet kullanılır. Bant genişliği: teorik ~100 Mbit/s.

```
Dış Test Cihazı (PC / EOL Tester)
        │
    Ethernet
        │
  DoIP Gateway (STM32H7 — bu referans)
        │
    CAN / FDCAN (ISO-TP)
        │
  Hedef ECU (UDS sunucu)
```

---

## 1. Protokol Katmanı

```
Uygulama     │ UDS (ISO 14229) mesajı
             │ DoIP payload (0x8001 Diagnostic Message)
─────────────┼──────────────────────────────────────────
Transport    │ TCP (bağlantılı, güvenilir) — tanı mesajları
             │ UDP (bağlantısız) — araç keşfi ve duyuru
─────────────┼──────────────────────────────────────────
Network      │ IPv4 / IPv6
─────────────┼──────────────────────────────────────────
Link         │ Ethernet IEEE 802.3 (STM32 ETH + PHY)
```

**Portlar:**
- UDP 13400: Araç duyurusu, keşif
- TCP 13400: Tanı oturumu (routing activation + diagnostic message)
- Multicast: 224.0.0.51 (IPv4 "AllDoIPNodes", per ISO 13400-2 §7.1.1) — vehicle announcement

---

## 2. DoIP Header Yapısı (8 Byte, Big-Endian)

```
Offset  Boyut  Alan
──────  ─────  ────
  0       1    Protocol Version   (0xFE = ISO 13400-2:2019, 0xFD = 2012)
  1       1    Inverse Version    (~byte0 — bütünlük kontrolü)
  2-3     2    Payload Type       (uint16_t)
  4-7     4    Payload Length     (uint32_t — sadece payload baytları)
```

```c
#define DOIP_PROTO_VER          0xFEU   /* ISO 13400-2:2019 */
#define DOIP_HEADER_LEN         8U

typedef struct __attribute__((packed)) {
    uint8_t  proto_ver;
    uint8_t  proto_ver_inv;   /* = ~proto_ver */
    uint16_t payload_type;    /* big-endian */
    uint32_t payload_len;     /* big-endian */
} doip_hdr_t;

/* Header doğrulama */
static bool doip_hdr_valid(const doip_hdr_t *hdr)
{
    return (hdr->proto_ver == DOIP_PROTO_VER) &&
           (hdr->proto_ver_inv == (uint8_t)(~DOIP_PROTO_VER));
}

/* Big-endian alanları host byte order'a çevir */
static inline uint16_t doip_get_type(const doip_hdr_t *hdr) {
    return __builtin_bswap16(hdr->payload_type);
}
static inline uint32_t doip_get_len(const doip_hdr_t *hdr) {
    return __builtin_bswap32(hdr->payload_len);
}
```

---

## 3. Payload Tipleri

```
Değer   Kullanım  Ad
──────  ────────  ──
0x0000  UDP/TCP   Generic DoIP header negative ACK
0x0001  UDP       Vehicle identification request
0x0002  UDP       Vehicle identification request with EID
0x0003  UDP       Vehicle identification request with VIN
0x0004  UDP       Vehicle announcement / identification response
0x0005  TCP       Routing activation request
0x0006  TCP       Routing activation response
0x0007  TCP       Alive check request
0x0008  TCP       Alive check response
0x4001  UDP/TCP   DoIP entity status request
0x4002  UDP/TCP   DoIP entity status response
0x4003  UDP/TCP   Diagnostic power mode information request
0x4004  UDP/TCP   Diagnostic power mode information response
0x8001  TCP       Diagnostic message
0x8002  TCP       Diagnostic message positive ACK
0x8003  TCP       Diagnostic message negative ACK
```

```c
/* Payload tipi sabitleri */
#define DOIP_TYPE_HDR_NACK              0x0000U
#define DOIP_TYPE_VEHICLE_ID_REQ        0x0001U
#define DOIP_TYPE_VEHICLE_ID_REQ_EID    0x0002U
#define DOIP_TYPE_VEHICLE_ID_REQ_VIN    0x0003U
#define DOIP_TYPE_VEHICLE_ANNOUNCEMENT  0x0004U
#define DOIP_TYPE_ROUTING_ACT_REQ       0x0005U
#define DOIP_TYPE_ROUTING_ACT_RESP      0x0006U
#define DOIP_TYPE_ALIVE_REQ             0x0007U
#define DOIP_TYPE_ALIVE_RESP            0x0008U
#define DOIP_TYPE_ENTITY_STATUS_REQ     0x4001U
#define DOIP_TYPE_ENTITY_STATUS_RESP    0x4002U
#define DOIP_TYPE_POWER_MODE_REQ        0x4003U
#define DOIP_TYPE_POWER_MODE_RESP       0x4004U
#define DOIP_TYPE_DIAG_MSG              0x8001U
#define DOIP_TYPE_DIAG_MSG_POS_ACK      0x8002U
#define DOIP_TYPE_DIAG_MSG_NEG_ACK      0x8003U
```

---

## 4. Araç Keşfi — UDP Faz

### Vehicle Announcement (Gateway → Test Cihazı)

DoIP gateway güç açılışında ve istek üzerine UDP multicast gönderir.

```c
/* Vehicle identification response payload (49 veya 50 byte) */
typedef struct __attribute__((packed)) {
    uint8_t  vin[17];           /* ASCII VIN, doldurulmazsa 0x00 */
    uint16_t logical_address;   /* Bu DoIP entity'nin lokal adresi */
    uint8_t  eid[6];            /* Entity ID — tipik olarak MAC adresi */
    uint8_t  gid[6];            /* Group ID — varsayılan: 0xFF ile dolu */
    uint8_t  further_action;    /* 0x00: no action, 0x10: routing activation needed */
    /* Opsiyonel: uint8_t vin_gid_sync; */
} doip_vehicle_id_resp_t;

/* further_action değerleri */
#define DOIP_FURTHER_ACTION_NONE            0x00U
#define DOIP_FURTHER_ACTION_NODE_REQUIRED   0x10U   /* central security needed */
```

### Duyuru Zamanlama Parametreleri (ISO 13400-2 §7.2)

```c
#define A_DOIP_ANNOUNCE_WAIT_MS     500U    /* ilk duyurudan önce bekleme */
#define A_DOIP_ANNOUNCE_INTERVAL_MS 500U    /* duyurular arası aralık */
#define A_DOIP_ANNOUNCE_NUM         3U      /* toplam duyuru sayısı */
```

---

## 5. TCP Bağlantı Faz — Routing Activation

Test cihazı TCP 13400'e bağlanır → Routing Activation Request gönderir → Gateway onaylar.

### Routing Activation Request (payload = 7 byte minimum)

```c
typedef struct __attribute__((packed)) {
    uint16_t source_address;      /* Test cihazının lokal adresi */
    uint8_t  activation_type;     /* 0x00=default, 0x01=WWH-OBD, 0xE0-FF=OEM */
    uint32_t reserved;            /* 0x00000000 — zorunlu */
    /* Opsiyonel: uint32_t oem_specific; */
} doip_routing_act_req_t;
```

### Routing Activation Response (payload = 9 byte minimum)

```c
typedef struct __attribute__((packed)) {
    uint16_t client_address;      /* Test cihazının kaynak adresi (echo) */
    uint16_t entity_address;      /* Bu gateway'in lokal adresi */
    uint8_t  response_code;       /* Sonuç kodu */
    uint32_t reserved;            /* 0x00000000 */
    /* Opsiyonel: uint32_t oem_specific; */
} doip_routing_act_resp_t;

/* Response kod değerleri */
#define DOIP_ROUTING_ACK_DENIED_UNKNOWN_SA      0x00U
#define DOIP_ROUTING_ACK_DENIED_UNSUPPORTED_ACT 0x01U
#define DOIP_ROUTING_ACK_DENIED_MEMORY_FULL     0x02U
#define DOIP_ROUTING_ACK_DENIED_TA_NOTFOUND     0x03U
#define DOIP_ROUTING_ACK_DENIED_SA_CONFLICT     0x04U
#define DOIP_ROUTING_ACK_DENIED_ALREADY_ACTIVE  0x05U
#define DOIP_ROUTING_ACK_DENIED_MISSING_AUTH    0x06U
#define DOIP_ROUTING_ACK_DENIED_REJECTED_CONF   0x07U
#define DOIP_ROUTING_ACK_DENIED_UNSUPPORTED_VER 0x08U
#define DOIP_ROUTING_ACK_OK_CONFIRMATION_REQ    0x10U  /* aktivasyon tamam, onay bekleniyor */
#define DOIP_ROUTING_ACK_OK                     0x11U  /* aktivasyon tamam */
```

---

## 6. Tanı Mesajı Alışverişi (TCP)

### Diagnostic Message (0x8001)

```c
typedef struct __attribute__((packed)) {
    uint16_t source_address;    /* Test cihazı — routing activation'daki SA */
    uint16_t target_address;    /* Hedef ECU'nun lokal adresi */
    /* uint8_t user_data[]; */ /* UDS mesajı (örn: 0x22 0xF1 0x90) */
} doip_diag_msg_t;
```

### Diagnostic Message Positive ACK (0x8002)

```c
typedef struct __attribute__((packed)) {
    uint16_t source_address;    /* Hedef ECU'nun adresi (echo) */
    uint16_t target_address;    /* Test cihazının adresi (echo) */
    uint8_t  ack_code;          /* 0x00 = routing confirmed */
    /* Opsiyonel: uint8_t previous_msg[]; */ /* İlk byte'lar echo edilebilir */
} doip_diag_pos_ack_t;
```

### Diagnostic Message Negative ACK (0x8003)

```c
typedef struct __attribute__((packed)) {
    uint16_t source_address;
    uint16_t target_address;
    uint8_t  nack_code;
} doip_diag_neg_ack_t;

/* NAK kod değerleri */
#define DOIP_DIAG_NACK_INVALID_SA       0x02U
#define DOIP_DIAG_NACK_UNKNOWN_TA       0x03U
#define DOIP_DIAG_NACK_MSG_TOO_LARGE    0x04U
#define DOIP_DIAG_NACK_OUT_OF_MEMORY    0x05U
#define DOIP_DIAG_NACK_TARGET_DEAD      0x06U  /* ECU ulaşılamaz */
#define DOIP_DIAG_NACK_UNKNOWN_NETWORK  0x07U
#define DOIP_DIAG_NACK_TRANSPORT_ERROR  0x08U
```

---

## 7. TCP Bağlantı Zamanlama Parametreleri (ISO 13400-2 §7.6)

```c
#define T_TCP_GENERAL_INACTIVITY_MS  5000U  /* aktivite yoksa bağlantı kapat */
#define T_TCP_INITIAL_INACTIVITY_MS  2000U  /* routing activation gelmezse kapat */
#define T_TCP_ALIVE_CHECK_MS          500U  /* alive check yanıt timeout */
#define A_PROCESSING_TIME_MS         2000U  /* ECU işleme süresi (UDS P2_server_max) */
```

---

## 8. Bağlantı Durum Makinesi (Gateway TCP Bağlantısı)

```c
typedef enum {
    DOIP_CONN_INIT,              /* bağlantı yeni kuruldu */
    DOIP_CONN_ROUTING_PENDING,   /* routing activation bekleniyor */
    DOIP_CONN_ROUTING_ACTIVE,    /* tanı mesajları yönlendirilebilir */
    DOIP_CONN_FINALIZED,         /* bağlantı kapatılıyor */
} doip_conn_state_t;

typedef struct {
    int                 sock;
    doip_conn_state_t   state;
    uint16_t            client_sa;      /* Test cihazının kaynak adresi */
    uint32_t            last_activity;  /* ms timestamp */
    uint8_t             rx_buf[1500];
    uint16_t            rx_len;
} doip_conn_t;
```

```
Bağlantı açıldı → INIT
INIT → ROUTING_PENDING  : T_TCP_Initial_Inactivity sayacı başladı
ROUTING_PENDING → ROUTING_ACTIVE : RoutingActivationRequest geldi, 0x11 gönderildi
ROUTING_PENDING → FINALIZED      : T_TCP_Initial_Inactivity doldu
ROUTING_ACTIVE → FINALIZED       : T_TCP_General_Inactivity doldu
                                 : TCP RST/FIN alındı
ROUTING_ACTIVE → ROUTING_ACTIVE  : DiagnosticMessage alındı, CAN'e iletildi
ROUTING_ACTIVE → ROUTING_ACTIVE  : AliveCheckRequest/Response
```

---

## 9. Alive Check

Gateway uzun süre veri almadığında bağlantının canlı olduğunu doğrulamak için kullanır.

```c
/* Gateway → Test cihazı: Alive Check Request (payload yok) */
/* Test cihazı → Gateway: Alive Check Response (payload yok) */

void doip_send_alive_check(doip_conn_t *conn)
{
    doip_hdr_t hdr = {
        .proto_ver     = DOIP_PROTO_VER,
        .proto_ver_inv = (uint8_t)(~DOIP_PROTO_VER),
        .payload_type  = __builtin_bswap16(DOIP_TYPE_ALIVE_REQ),
        .payload_len   = 0,
    };
    send(conn->sock, &hdr, sizeof(hdr), 0);
    /* T_TCP_Alive_Check sonrası yanıt gelmezse bağlantıyı kapat */
}
```

---

## 10. STM32H7 — LwIP ile DoIP Gateway Kurulumu

### Bellek Yerleşimi

```c
/* ETH DMA: AXI SRAM (0x24000000) ve D2 SRAM (0x30000000) erişebilir */
/* DTCM (0x20000000): ETH DMA ERİŞEMEZ — oraya buffer koyma */

/* ETH descriptor ve buffer: non-cacheable olmalı */
/* Yöntem 1: MPU ile non-cacheable bölge yarat */
/* Yöntem 2: D2 SRAM (0x30000000) kullan — cache H7'de orada etkisiz */

/* Linker script */
/* .lwip_sec (NOLOAD) : { *(.lwip_sec) } >RAM_D2 */

__attribute__((section(".lwip_sec"), aligned(4)))
static uint8_t eth_rx_buf[ETH_RX_DESC_CNT][ETH_MAX_PACKET_SIZE];

__attribute__((section(".lwip_sec"), aligned(4)))
static uint8_t eth_tx_buf[ETH_TX_DESC_CNT][ETH_MAX_PACKET_SIZE];
```

### LwIP Socket Modu (barebone, FreeRTOS)

```c
/* DoIP gateway task */
#define DOIP_UDP_PORT   13400
#define DOIP_TCP_PORT   13400
#define DOIP_MULTICAST  "224.0.0.51"   /* ISO 13400-2 §7.1.1 "AllDoIPNodes" */

static void doip_gateway_task(void *arg)
{
    /* UDP socket — vehicle announcement + discovery */
    int udp_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    struct sockaddr_in udp_addr = {
        .sin_family      = AF_INET,
        .sin_port        = htons(DOIP_UDP_PORT),
        .sin_addr.s_addr = INADDR_ANY,
    };
    bind(udp_sock, (struct sockaddr *)&udp_addr, sizeof(udp_addr));

    /* Multicast grubuna katıl */
    struct ip_mreq mreq;
    mreq.imr_multiaddr.s_addr = inet_addr(DOIP_MULTICAST);
    mreq.imr_interface.s_addr = INADDR_ANY;
    setsockopt(udp_sock, IPPROTO_IP, IP_ADD_MEMBERSHIP, &mreq, sizeof(mreq));

    /* TCP socket — diagnostic connection */
    int tcp_server = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    int opt = 1;
    setsockopt(tcp_server, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    struct sockaddr_in tcp_addr = {
        .sin_family      = AF_INET,
        .sin_port        = htons(DOIP_TCP_PORT),
        .sin_addr.s_addr = INADDR_ANY,
    };
    bind(tcp_server, (struct sockaddr *)&tcp_addr, sizeof(tcp_addr));
    listen(tcp_server, 1);

    /* Vehicle announcement gönder */
    osDelay(A_DOIP_ANNOUNCE_WAIT_MS);
    for (uint32_t i = 0; i < A_DOIP_ANNOUNCE_NUM; ++i) {
        doip_send_vehicle_announcement(udp_sock);
        osDelay(A_DOIP_ANNOUNCE_INTERVAL_MS);
    }

    /* Ana döngü */
    for (;;) {
        fd_set fds;
        FD_ZERO(&fds);
        FD_SET(udp_sock, &fds);
        FD_SET(tcp_server, &fds);
        /* ... select ile UDP ve TCP aynı anda izle */
    }
}
```

### Vehicle Announcement Gönder

```c
static void doip_send_vehicle_announcement(int sock)
{
    uint8_t buf[DOIP_HEADER_LEN + sizeof(doip_vehicle_id_resp_t)];
    doip_hdr_t *hdr = (doip_hdr_t *)buf;
    doip_vehicle_id_resp_t *resp = (doip_vehicle_id_resp_t *)(buf + DOIP_HEADER_LEN);

    hdr->proto_ver     = DOIP_PROTO_VER;
    hdr->proto_ver_inv = (uint8_t)(~DOIP_PROTO_VER);
    hdr->payload_type  = __builtin_bswap16(DOIP_TYPE_VEHICLE_ANNOUNCEMENT);
    hdr->payload_len   = __builtin_bswap32(sizeof(doip_vehicle_id_resp_t));

    memset(resp->vin, 0x00, 17);               /* VIN henüz programlanmamışsa 0x00 */
    memcpy(resp->vin, "1HGBH41JXMN109186", 17);  /* Gerçek projede OTP'den oku */
    resp->logical_address  = __builtin_bswap16(0x0E80);  /* Bu gateway'in adresi */
    memset(resp->eid, 0, 6);
    /* EID = MAC adresi. HAL_ETH_GetMACAddr() bir ST HAL fonksiyonu DEĞİL.
     * MAC adresi heth.Init.MACAddr alanından (HAL_ETH_Init öncesi set edilir)
     * veya doğrudan MAC kayıt yazmaçlarından okunur. */
    memcpy(resp->eid, heth.Init.MACAddr, 6);
    /* Alternatif: registerlardan oku (STM32H7 RM0433 §62.5)
     *   uint32_t hi = ETH->MACA0HR;
     *   uint32_t lo = ETH->MACA0LR;
     *   resp->eid[0] = lo & 0xFF;        resp->eid[1] = (lo >> 8)  & 0xFF;
     *   resp->eid[2] = (lo >> 16) & 0xFF; resp->eid[3] = (lo >> 24) & 0xFF;
     *   resp->eid[4] = hi & 0xFF;        resp->eid[5] = (hi >> 8)  & 0xFF;
     */
    memset(resp->gid, 0xFF, 6);
    resp->further_action   = DOIP_FURTHER_ACTION_NONE;

    struct sockaddr_in dest = {
        .sin_family      = AF_INET,
        .sin_port        = htons(DOIP_UDP_PORT),
        .sin_addr.s_addr = inet_addr(DOIP_MULTICAST),
    };
    sendto(sock, buf, sizeof(buf), 0, (struct sockaddr *)&dest, sizeof(dest));
}
```

---

## 11. DoIP → CAN/ISO-TP Köprüsü

```c
/* Lokal adres → CAN ID tablosu */
typedef struct {
    uint16_t doip_addr;
    uint32_t isotp_tx_id;   /* CAN ID — test cihazı → ECU */
    uint32_t isotp_rx_id;   /* CAN ID — ECU → test cihazı */
} doip_routing_entry_t;

static const doip_routing_entry_t routing_table[] = {
    { 0x0001, 0x7DF, 0x7E8 },   /* OBD broadcast → engine ECU */
    { 0x0010, 0x700, 0x708 },   /* ECU-A */
    { 0x0011, 0x710, 0x718 },   /* ECU-B */
};

/* Tanı mesajı al → ISO-TP CAN'e ilet */
static void doip_route_to_can(doip_conn_t *conn,
                               uint16_t sa, uint16_t ta,
                               const uint8_t *uds_msg, uint16_t uds_len)
{
    /* Routing tablosunda TA'yı bul */
    const doip_routing_entry_t *entry = NULL;
    for (size_t i = 0; i < ARRAY_SIZE(routing_table); ++i) {
        if (routing_table[i].doip_addr == ta) {
            entry = &routing_table[i];
            break;
        }
    }

    if (entry == NULL) {
        doip_send_diag_nack(conn, ta, sa, DOIP_DIAG_NACK_UNKNOWN_TA);
        return;
    }

    /* Önce pozitif ACK gönder — mesaj kabul edildi */
    doip_send_diag_pos_ack(conn, ta, sa);

    /* ISO-TP ile CAN'e ilet (bloklayıcı, A_Processing_Time timeout ile) */
    int32_t ret = isotp_send(entry->isotp_tx_id, uds_msg, uds_len,
                              A_PROCESSING_TIME_MS);
    if (ret < 0) {
        doip_send_diag_nack(conn, ta, sa, DOIP_DIAG_NACK_TARGET_DEAD);
        return;
    }

    /* ECU yanıtını bekle */
    uint8_t resp_buf[4096];
    int32_t resp_len = isotp_recv(entry->isotp_rx_id, resp_buf,
                                   sizeof(resp_buf), A_PROCESSING_TIME_MS);
    if (resp_len < 0) {
        doip_send_diag_nack(conn, ta, sa, DOIP_DIAG_NACK_TARGET_DEAD);
        return;
    }

    /* Yanıtı DoIP ile test cihazına gönder */
    doip_send_diag_msg(conn, ta, sa, resp_buf, (uint16_t)resp_len);
}
```

---

## 12. Header Negative ACK

Geçersiz veya desteklenmeyen bir mesaj alındığında gönderilir.

```c
/* Payload: 1 byte NAK code */
#define DOIP_HDR_NACK_INCORRECT_PATTERN     0x00U  /* proto_ver/inv hatalı */
#define DOIP_HDR_NACK_UNKNOWN_PAYLOAD_TYPE  0x01U
#define DOIP_HDR_NACK_MSG_TOO_LARGE         0x02U  /* payload_len > max_buf */
#define DOIP_HDR_NACK_OUT_OF_MEMORY         0x03U
#define DOIP_HDR_NACK_INVALID_PAYLOAD_LEN   0x04U  /* tip için yanlış uzunluk */

static void doip_send_hdr_nack(int sock, uint8_t nack_code)
{
    uint8_t buf[DOIP_HEADER_LEN + 1];
    doip_hdr_t *hdr = (doip_hdr_t *)buf;
    hdr->proto_ver     = DOIP_PROTO_VER;
    hdr->proto_ver_inv = (uint8_t)(~DOIP_PROTO_VER);
    hdr->payload_type  = __builtin_bswap16(DOIP_TYPE_HDR_NACK);
    hdr->payload_len   = __builtin_bswap32(1U);
    buf[DOIP_HEADER_LEN] = nack_code;
    send(sock, buf, sizeof(buf), 0);
}
```

---

## 13. Entity Status Response

```c
typedef struct __attribute__((packed)) {
    uint8_t  node_type;             /* 0x00=DoIP gateway, 0x01=DoIP node */
    uint8_t  max_open_sockets;      /* Desteklenen maks. TCP bağlantı sayısı */
    uint8_t  currently_open_sockets;
    uint32_t max_data_size;         /* Maks. mesaj boyutu (byte) — opsiyonel */
} doip_entity_status_resp_t;

#define DOIP_NODE_TYPE_GATEWAY  0x00U
#define DOIP_NODE_TYPE_NODE     0x01U   /* ECU'nun kendisi DoIP sunuyor */
```

---

## 14. Lokal Adres Atama

```
Standart aralıklar (ISO 13400-2 Tablo 3):
  Per ISO 13400-2 Table 13 (Logical Address Assignment):
  0x0000          : Reserved
  0x0001–0x0DFF   : VM-specific tester/external addresses
  0x0E00–0x0FFF   : DoIP entity / gateway addresses
  0x1000–0x7FFF   : VM-specific (ECU node addresses)
  0x8000–0xCFFF   : Reserved by ISO
  0xD000–0xDFFF   : Reserved for SAE
  0xE000–0xE3FF   : Functional addresses (legislated)  e.g. 0xE000 ISO OBD
                                                            0xE400 SAE WWH-OBD
  0xE400–0xEFFF   : Functional addresses (OEM-defined)
  0xF000–0xFFFF   : Reserved by ISO

Örnek:
  DoIP Gateway   → 0x0E80
  EOL Tester     → 0x0E00
  Engine ECU     → 0x1000
  Gearbox ECU    → 0x1001
  ISO OBD funct  → 0xE000 (ISO 27145 legislated OBD)
  WWH-OBD funct  → 0xE400
```

---

## 15. Sık Yapılan Hatalar

| Hata | Sonuç | Önlem |
|------|-------|-------|
| ETH buffer DTCM'de | DMA transfer sıfır byte — sessiz hata | AXI SRAM veya D2 SRAM kullan |
| proto_ver_inv kontrolü yok | Sahte paket parse edilir | `~proto_ver` eşit değilse NACK gönder |
| Routing activation olmadan diagnostic mesaj kabul | Güvenlik ihlali | State machine: ROUTING_PENDING'de 0x8001 gelirse NACK |
| T_TCP_Initial_Inactivity uygulanmaz | Zombi TCP bağlantıları | Sayaç yoksa bellek dolar |
| Payload length'i doğrulamama | Heap overflow | `payload_len > MAX_BUF_SIZE` → 0x02 HDR NACK |
| Big-endian dönüşümü unutma | Adres/uzunluk hatalı decode | Her uint16/uint32 alanında `__builtin_bswap` kullan |
| ISO-TP timeout çok kısa | Test takımı yanıt alamıyor | `A_Processing_Time` = 2000ms (P2*_server = 5s bile olabilir) |
| Multicast join yapılmıyor | Vehicle announcement çalışmıyor | `IP_ADD_MEMBERSHIP` setsockopt zorunlu |
| SA çakışması kontrolü yok | İki test cihazı aynı SA: routing karışır | Active bağlantılarda SA tablosu tut |
| EID (MAC) sabit hardcode | Üretim firmwaresinde ağ çakışması | `heth.Init.MACAddr`'dan veya `ETH->MACA0HR/LR` registerlarından oku |

---

## 16. Bağlantı Akışı Özeti

```
Test Cihazı                    DoIP Gateway                  Hedef ECU (CAN)
     │                              │                              │
     │── UDP Broadcast ────────────▶│ (Vehicle ID Request)         │
     │◀─ UDP Unicast/Multicast ─────│ (Vehicle Announcement)       │
     │                              │                              │
     │── TCP connect :13400 ────────▶│                              │
     │                              │ (TCP kabul, T_Initial başlar)│
     │── Routing Act. Req (0x0005) ─▶│                              │
     │◀─ Routing Act. Resp 0x11 ────│ (SA tablo kaydı)             │
     │                              │                              │
     │── Diag Msg (0x8001) ─────────▶│ UDS: 22 F1 90               │
     │◀─ Diag Pos ACK (0x8002) ─────│                              │
     │                              │──── ISO-TP TX ──────────────▶│
     │                              │◀─── ISO-TP RX ───────────────│
     │◀─ Diag Msg (0x8001) ─────────│ UDS yanıtı: 62 F1 90 ...    │
     │                              │                              │
     │── TCP close ─────────────────▶│                              │
```
