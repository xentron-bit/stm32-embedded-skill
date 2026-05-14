# TrustZone-M & MPU — STM32H5 / U5 / L5

Platform: Cortex-M33 (STM32H5, U5, L5, WBA) — TrustZone-M
MPU bölümü: Cortex-M4/M7 (F4/F7/H7) + Cortex-M33 her ikisini kapsar.

---

## INDEX

| Bölüm | Konu |
|-------|------|
| [I. Temel Kavramlar](#i-temel-kavramlar) | Secure/NS dünya, SAU, IDAU, NSC, CMSE |
| [II. STM32H5 TrustZone Mimarisi](#ii-stm32h5-trustzone-mimarisi) | TZEN option byte, memory map, dual-project |
| [III. GTZC — Global TrustZone Controller](#iii-gtzc--global-trustzone-controller) | Peripheral güvenlik, MPCBB, MPCWM |
| [IV. SAU Konfigürasyonu](#iv-sau-konfigürasyonu) | 8 bölge, NS/NSC atama, CMSIS API |
| [V. CMSE — Non-Secure Callable API](#v-cmse--non-secure-callable-api) | NSC fonksiyon, pointer doğrulama, callback |
| [VI. Güvenli Boot Zinciri](#vi-güvenli-boot-zinciri) | SECWM, option bytes, NS handoff |
| [VII. Shared Memory Pattern](#vii-shared-memory-pattern) | NS↔Secure paylaşımlı bellek, DSB barrier |
| [VIII. MPU — Cortex-M4/M7](#viii-mpu--cortex-m4m7) | Region konfigürasyonu, armv7-m, stack guard |
| [IX. MPU — Cortex-M33 (armv8-m)](#ix-mpu--cortex-m33-armv8-m) | M33 CMSIS API, attribute index, M7 farkları |
| [X. FreeRTOS MPU Port](#x-freertos-mpu-port) | Task isolation, xTaskCreateRestricted |
| [XI. Kontrol Listesi](#xi-kontrol-listesi) | Üretim öncesi güvenlik checklist |
| [XII. Yaygın Hatalar](#xii-yaygın-hatalar) | Hata tablosu + çözümler |

---

## I. Temel Kavramlar

| Kavram | Açıklama |
|--------|----------|
| Secure World | Güvenli işlemci modu — kriptografik anahtarlar, boot doğrulama |
| Non-Secure (NS) | Uygulama kodu, RTOS, iletişim stack'leri |
| SAU | Security Attribution Unit — M33 içi, 8 bölgeye kadar NS/NSC tanımlar |
| IDAU | Implementation Defined Attribution Unit — çip üreticisi ek mantık (STM32H5: GTZC = IDAU) |
| NSC | Non-Secure Callable — NS'den çağrılabilen Secure fonksiyon (SG instruction ile geçiş) |
| CMSE | C Microcontroller Security Extensions — GCC/AC6 derleyici eklentisi |
| GTZC | Global TrustZone Controller — STM32H5/U5/L5'e özgü peripheral+bellek güvenlik birimi |
| MPCBB | Memory Protection Controller Block-Based — SRAM'ı 512-byte blok granülüyle S/NS yap |
| MPCWM | Memory Protection Controller Watermark — flash/FMC/OCTOSPI için watermark |
| SecureFault | NS kodun Secure bölgeye erişiminde oluşan Cortex-M33 exception |

**Kural: SAU VE IDAU/GTZC her ikisi NS derse → NS, biri Secure derse → Secure.**

---

## II. STM32H5 TrustZone Mimarisi

### TZEN Option Byte (Kritik)

```
STM32H5'te TrustZone ZORUNLU DEĞİL ama TZEN=1 yapılınca:
  - Secure + Non-Secure iki ayrı proje gerekir
  - TZEN=1 → TZEN=0 dönüşü: mass erase + option byte reset gerekir
  - Factory default: TZEN=0 (TrustZone devre dışı, tek proje çalışır)

STM32_Programmer_CLI -c port=SWD -ob TZEN=1
```

### STM32H5 Bellek Haritası (TZEN=1)

```
Flash (2MB total — STM32H563):
  0x0800_0000 ─────────────────── Secure Flash başlangıcı
  0x0800_0000 → 0x080F_FFFF       Secure firmware (SECWM ile korunan)
  0x0810_0000 → 0x081F_FFFF       Non-Secure firmware
  0x0C00_0000 → 0x0C00_3FFF       NSC region (veneer table — SAU NSC)

SRAM (640KB total):
  0x2000_0000 → 0x2001_FFFF       SRAM1 — Secure (128KB)
  0x2002_0000 → 0x2004_FFFF       SRAM2/3 — Non-Secure (192KB)
  0x3000_0000 → 0x3000_0FFF       SRAM4 — GTZC2 yönetir (4KB)

Peripheral:
  Secure periph: RNG, PKA, HASH, AES, safeboot bölgesi
  NS periph: UART, SPI, I2C, CAN, USB (GTZC ile yapılandırılır)
```

### CubeIDE Dual-Project Yapısı

```
Workspace/
├── MyProject_S/          ← Secure proje
│   ├── Core/Src/main.c   (Secure main, SAU/GTZC/MPU init)
│   ├── secure_api.c      (NSC fonksiyon implementasyonları)
│   └── Output/
│       └── MyProject_S_CMSE.lib  ← NS projesine link edilecek veneer library
│
└── MyProject_NS/         ← Non-Secure proje
    ├── Core/Src/main.c   (NS main, RTOS başlatma)
    ├── Drivers/           (NS periph sürücüler)
    └── Linker/
        └── MyProject_NS.ld  (veneer bölgesi tanımlı)
```

```
Build sırası: Önce Secure → sonra Non-Secure (veneer .lib bağımlılığı)
Secure FW değişince: NS projeyi de rebuild et (veneer table güncellenir)
```

---

## III. GTZC — Global TrustZone Controller

STM32H5'te iki GTZC instance:
- **GTZC1**: APB1, APB2, AHB1, AHB2 peripheral'ları + SRAM1/2/3 (MPCBB)
- **GTZC2**: APB3, AHB3 peripheral'ları + SRAM4 (MPCBB) + Flash (MPCWM)

### Peripheral Güvenlik Ataması

```c
void gtzc_init(void)
{
    __HAL_RCC_GTZC1_CLK_ENABLE();
    __HAL_RCC_GTZC2_CLK_ENABLE();

    /* Secure-only peripheral'lar — NS erişimi SecureFault üretir */
    HAL_GTZC_TZSC_ConfigPeriphAttributes(GTZC_PERIPH_RNG,
        GTZC_TZSC_PERIPH_SEC | GTZC_TZSC_PERIPH_PRIV);

    HAL_GTZC_TZSC_ConfigPeriphAttributes(GTZC_PERIPH_PKA,
        GTZC_TZSC_PERIPH_SEC | GTZC_TZSC_PERIPH_PRIV);

    HAL_GTZC_TZSC_ConfigPeriphAttributes(GTZC_PERIPH_HASH,
        GTZC_TZSC_PERIPH_SEC | GTZC_TZSC_PERIPH_PRIV);

    HAL_GTZC_TZSC_ConfigPeriphAttributes(GTZC_PERIPH_AES,
        GTZC_TZSC_PERIPH_SEC | GTZC_TZSC_PERIPH_PRIV);

    /* Non-Secure peripheral'lar — NS uygulama kullanabilir */
    HAL_GTZC_TZSC_ConfigPeriphAttributes(GTZC_PERIPH_USART1,
        GTZC_TZSC_PERIPH_NSEC | GTZC_TZSC_PERIPH_NPRIV);

    HAL_GTZC_TZSC_ConfigPeriphAttributes(GTZC_PERIPH_FDCAN1,
        GTZC_TZSC_PERIPH_NSEC | GTZC_TZSC_PERIPH_NPRIV);

    HAL_GTZC_TZSC_ConfigPeriphAttributes(GTZC_PERIPH_USB,
        GTZC_TZSC_PERIPH_NSEC | GTZC_TZSC_PERIPH_NPRIV);
}
```

### MPCBB — SRAM Blok Tabanlı Koruma

```c
/* SRAM1: Tüm bloklar Secure (64 blok × 512 byte = 32KB örnek) */
void gtzc_sram_config(void)
{
    MPCBB_ConfigTypeDef mpcbb = {0};

    /* SecureRWIllegalMode: NS'nin Secure bölgeye erişimi TZIC interrupt üretir */
    mpcbb.SecureRWIllegalMode = GTZC_MPCBB_SRWILADIS_ENABLE;
    mpcbb.InvertSecureState   = GTZC_MPCBB_INVSECSTATE_NOT_INVERTED;

    /* Her uint32_t = 32 blok (her bit 1 blok = 512 byte) */
    /* 0xFFFFFFFF = tüm bloklar Secure */
    for (int i = 0; i < GTZC_MPCBB_NB_VCTR_REG_MAX; i++) {
        mpcbb.AttributeConfig.MPCBB_SecConfig_array[i] = 0xFFFFFFFF;
    }

    HAL_GTZC_MPCBB_ConfigMem(SRAM1, &mpcbb);

    /* SRAM2: Tüm bloklar Non-Secure */
    for (int i = 0; i < GTZC_MPCBB_NB_VCTR_REG_MAX; i++) {
        mpcbb.AttributeConfig.MPCBB_SecConfig_array[i] = 0x00000000;
    }
    HAL_GTZC_MPCBB_ConfigMem(SRAM2, &mpcbb);
}
```

### MPCWM — Flash Watermark (SECWM)

```c
/* Flash Secure Watermark — option bytes ile de yapılabilir */
/* SECWM1_PSTRT / SECWM1_PEND: page granülü (8KB/page STM32H5) */

/* Yazılım yöntemi (runtime): */
FLASH_BBAttributesTypeDef bb_attr = {0};
bb_attr.BBAttributesType = FLASH_BB_SEC;  /* Secure block-based */
/* 1. sayfadan 31. sayfaya Secure (256KB) */
for (uint32_t page = 0; page < 32; page++) {
    FLASH_BBAttr_SetPageAttribute(&bb_attr, page, FLASH_PAGE_SEC);
}
HAL_FLASHEx_ConfigBBAttributes(&bb_attr);
```

### TZIC — TrustZone Interrupt Controller

```c
/* TZIC: NS'nin Secure alana izinsiz erişiminde interrupt üretir */
/* SecureFault exception bu erişimi yakalar */

void GTZC_IRQHandler(void)
{
    HAL_GTZC_IRQHandler();
}

void HAL_GTZC_S_Error_Callback(uint32_t PeriphId)
{
    /* Hangi peripheral ihlal etti? */
    log_security_violation(PeriphId);
    /* Güvenli tepki: NS uygulamayı sıfırla veya sistemik reset */
    NVIC_SystemReset();
}
```

---

## IV. SAU Konfigürasyonu

```c
/* SAU: 8 bölge (Cortex-M33) */
/* CMSIS doğrudan register erişimi — Secure reset handler'da çağır */

void sau_init(void)
{
    SAU->CTRL = 0;  /* SAU'yu devre dışı bırak (yapılandırma sırasında) */

    /* Bölge 0: Non-Secure Flash (NS uygulama kodu) */
    SAU->RNR  = 0U;
    SAU->RBAR = 0x08100000U & SAU_RBAR_BADDR_Msk;  /* NS flash başlangıcı */
    SAU->RLAR = (0x081FFFFFU & SAU_RLAR_LADDR_Msk)
              | SAU_RLAR_ENABLE_Msk;                 /* NS (NSC flag yok) */

    /* Bölge 1: NSC Flash bölgesi (veneer table) */
    SAU->RNR  = 1U;
    SAU->RBAR = 0x0C000000U & SAU_RBAR_BADDR_Msk;
    SAU->RLAR = (0x0C003FFFU & SAU_RLAR_LADDR_Msk)
              | SAU_RLAR_NSC_Msk        /* Non-Secure Callable */
              | SAU_RLAR_ENABLE_Msk;

    /* Bölge 2: Non-Secure SRAM */
    SAU->RNR  = 2U;
    SAU->RBAR = 0x20020000U & SAU_RBAR_BADDR_Msk;
    SAU->RLAR = (0x2004FFFFU & SAU_RLAR_LADDR_Msk)
              | SAU_RLAR_ENABLE_Msk;

    /* Bölge 3: Non-Secure Peripheral (APB/AHB NS peripheral'lar) */
    SAU->RNR  = 3U;
    SAU->RBAR = 0x40000000U & SAU_RBAR_BADDR_Msk;
    SAU->RLAR = (0x4FFFFFFFU & SAU_RLAR_LADDR_Msk)
              | SAU_RLAR_ENABLE_Msk;

    /* Bölge 4: Non-Secure External (OCTOSPI, FMC — proje gerektiriyorsa) */
    SAU->RNR  = 4U;
    SAU->RBAR = 0x90000000U & SAU_RBAR_BADDR_Msk;
    SAU->RLAR = (0x9FFFFFFFU & SAU_RLAR_LADDR_Msk)
              | SAU_RLAR_ENABLE_Msk;

    /* SAU etkinleştir — tanımlanmamış bölgeler Secure kalır */
    SAU->CTRL = SAU_CTRL_ENABLE_Msk;
    __DSB();  /* bellek erişim sıralama — SAU sonrası zorunlu */
    __ISB();  /* pipeline flush — sonraki instruction yeni SAU ile */
}
```

**SAU_CTRL_ALLNS_Msk:** Tüm belleği NS yapar (TZ test modu — production'da kullanma).

---

## V. CMSE — Non-Secure Callable API

### NSC Fonksiyon Tanımı (Secure Proje)

```c
/* secure_api.h — her iki proje tarafından include edilir */
#pragma once
#include <stdint.h>
#include <stdbool.h>

/* NS dünyadan çağrılabilir Secure fonksiyonlar */
int32_t SECURE_Crypto_Sign(const uint8_t *data, uint32_t len, uint8_t *sig_out);
int32_t SECURE_RNG_GetBytes(uint8_t *buf, uint32_t len);
bool    SECURE_KeyExists(uint32_t key_id);
```

```c
/* secure_api.c — Secure projede derlenir */
#include "arm_cmse.h"
#include "secure_api.h"

__attribute__((cmse_nonsecure_entry))
int32_t SECURE_Crypto_Sign(const uint8_t *data_ns, uint32_t len,
                            uint8_t *sig_out_ns)
{
    /* 1. NS pointer doğrulama — Secure heap'e işaret etmemeli */
    if (cmse_check_address_range((void *)data_ns, len,
            CMSE_NONSECURE | CMSE_MPU_READ) == NULL) {
        return -1;  /* Geçersiz NS pointer */
    }
    if (cmse_check_address_range(sig_out_ns, 64U,
            CMSE_NONSECURE | CMSE_MPU_READWRITE) == NULL) {
        return -2;
    }

    /* 2. Güvenli kopyala — NS pointer'ı doğrudan kullanma */
    static uint8_t local_data[256];  /* Secure SRAM'da */
    if (len > sizeof(local_data)) { return -3; }
    memcpy(local_data, data_ns, len);

    /* 3. Secure operasyon */
    uint8_t local_sig[64];
    int32_t ret = crypto_sign_internal(local_data, len, local_sig);

    /* 4. Sonucu NS buffer'a yaz */
    if (ret == 0) {
        memcpy(sig_out_ns, local_sig, 64U);
    }

    /* 5. Hassas veriyi temizle — register sızıntısı önle */
    memset(local_data, 0, len);
    memset(local_sig, 0, sizeof(local_sig));

    return ret;
    /* r0 dışındaki register'lar derleyici tarafından temizlenir (CMSE ABI) */
}

__attribute__((cmse_nonsecure_entry))
int32_t SECURE_RNG_GetBytes(uint8_t *buf_ns, uint32_t len)
{
    if (cmse_check_address_range(buf_ns, len,
            CMSE_NONSECURE | CMSE_MPU_READWRITE) == NULL) {
        return -1;
    }
    /* HAL_RNG — RNG peripheral Secure'a atanmış */
    for (uint32_t i = 0; i < len; i += 4U) {
        uint32_t rnd;
        HAL_RNG_GenerateRandomNumber(&hrng, &rnd);
        uint32_t chunk = (len - i) < 4U ? (len - i) : 4U;
        memcpy(buf_ns + i, &rnd, chunk);
    }
    return 0;
}
```

### cmse_check Fonksiyonları

```c
/* cmse_check_pointed_object: tek nesne pointer doğrulama */
void *result = cmse_check_pointed_object(ptr, CMSE_NONSECURE);
/* result == NULL → ptr Secure alana işaret ediyor → reddet */

/* cmse_check_address_range: belirli uzunlukta aralık doğrulama */
void *result = cmse_check_address_range(ptr, len,
    CMSE_NONSECURE | CMSE_MPU_READ);
/* CMSE_MPU_READ: NS MPU'nun okuma iznine de bak */
/* CMSE_MPU_READWRITE: yazma iznine de bak */

/* Fark:
   check_pointed_object → pointer'ın işaret ettiği nesnenin boyutunu otomatik alır
   check_address_range  → açıkça len verilir (diziler, buffer'lar için) */
```

### NS→Secure Function Pointer (Callback)

```c
/* NS kodu Secure'a callback registrar edebilir */
/* cmse_nsfptr_create: NS function pointer'ı güvenli hale getirir */

typedef void (*ns_callback_t)(uint32_t event) __attribute__((cmse_nonsecure_call));

static ns_callback_t s_ns_callback = NULL;

__attribute__((cmse_nonsecure_entry))
void SECURE_RegisterCallback(void *ns_func_ptr)
{
    /* NS function pointer'ı doğrula */
    if (cmse_check_pointed_object(ns_func_ptr, CMSE_NONSECURE) == NULL) {
        return;
    }
    s_ns_callback = cmse_nsfptr_create(ns_func_ptr);
}

/* Secure'dan NS callback'i çağır */
void secure_notify_ns(uint32_t event)
{
    if (s_ns_callback != NULL) {
        s_ns_callback(event);  /* BLXNS instruction ile NS'ye geçer */
    }
}
```

---

## VI. Güvenli Boot Zinciri

### STM32H5 Option Bytes (TZEN=1)

```
Önemli option bytes:
  TZEN    = 1          TrustZone etkin
  SECWM1_PSTRT = 0     Secure watermark başlangıç sayfası (page 0)
  SECWM1_PEND  = 31    Secure watermark bitiş sayfası (page 31 = 256KB)
  RDP     = 0xB4       RDP Level 1 (Secure flash korumalı)
  BKPWRP  = 0          Backup register write protection

STM32_Programmer_CLI -c port=SWD -ob TZEN=1 SECWM1_PSTRT=0 SECWM1_PEND=31 RDP=0xB4
```

### NS Firmware Doğrulama (Secure'da)

```c
bool secure_verify_ns_firmware(void)
{
    const uint8_t *ns_flash = (const uint8_t *)0x08100000U;
    uint32_t       ns_size  = get_ns_firmware_size();  /* metadata'dan */

    /* SHA-256 hesapla — HASH peripheral (Secure) */
    uint8_t computed_hash[32];
    HAL_HASHEx_SHA256_Start(&hhash, (uint8_t *)ns_flash, ns_size,
                             computed_hash, 1000U);

    /* Güvenilir hash ile karşılaştır (Secure flash'ta saklı) */
    const uint8_t *trusted_hash = (const uint8_t *)SECURE_TRUSTED_HASH_ADDR;
    return (memcmp(computed_hash, trusted_hash, 32U) == 0);
}
```

### NS Dünyaya Geçiş (Handoff)

```c
typedef void (*ns_reset_t)(void) __attribute__((cmse_nonsecure_call));

void secure_handoff_to_ns(void)
{
    uint32_t ns_msp   = *(__IO uint32_t *)NS_APP_FLASH_BASE;
    uint32_t ns_entry = *(__IO uint32_t *)(NS_APP_FLASH_BASE + 4U);

    /* NS stack pointer geçerli mi? */
    if (ns_msp < NS_SRAM_BASE || ns_msp > (NS_SRAM_BASE + NS_SRAM_SIZE)) {
        /* NS firmware geçersiz — secure fault loop */
        while (1) {}
    }

    /* NS MSP'yi set et */
    __TZ_set_MSP_NS(ns_msp);

    /* VTOR_NS — NS vector table */
    SCB_NS->VTOR = NS_APP_FLASH_BASE;

    /* NS'ye geç — geri dönmez */
    ns_reset_t ns_reset = (ns_reset_t)((ns_entry & ~1U) | 1U);
    ns_reset();
}
```

---

## VII. Shared Memory Pattern

```c
/* Paylaşımlı bellek: NS yazar, Secure okur */
/* SAU: bu bölge NS olarak işaretli */
/* GTZC MPCBB: bloklar NS olarak konfigüre */

/* Linker script'te ayrı section */
/* secure_s.ld: */
/* .ns_shared (NOLOAD) : { *(.ns_shared) } > SRAM_NS */

__attribute__((section(".ns_shared")))
static volatile uint8_t shared_ipc_buf[256];
static volatile uint32_t shared_ipc_len;
static volatile uint32_t shared_ipc_ready;  /* flag */

/* NSC: NS kodu bu fonksiyonu çağırarak Secure işlemi tetikler */
__attribute__((cmse_nonsecure_entry))
int32_t SECURE_ProcessIPCData(void)
{
    if (!shared_ipc_ready) { return -1; }

    __DMB();  /* NS'nin tüm yazmaları görünür olsun */

    uint32_t len = shared_ipc_len;
    if (len > sizeof(shared_ipc_buf)) { return -2; }

    /* Güvenli kopyala */
    uint8_t local[256];
    memcpy(local, (const void *)shared_ipc_buf, len);

    shared_ipc_ready = 0U;
    __DMB();  /* flag temizleme görünür olsun */

    return secure_process(local, len);
}

/* NS tarafı */
void ns_send_to_secure(const uint8_t *data, uint32_t len)
{
    memcpy((void *)shared_ipc_buf, data, len);
    shared_ipc_len = len;
    __DMB();                  /* yazma tamamlandı */
    shared_ipc_ready = 1U;
    __DMB();                  /* flag görünür */
    SECURE_ProcessIPCData();  /* NSC çağrısı */
}
```

---

## VIII. MPU — Cortex-M4/M7

armv7-m MPU: 8 veya 16 bölge, her bölge power-of-2 boyut, doğal hizalı.

```c
#include "core_cm7.h"   /* veya core_cm4.h */

typedef enum {
    MPU_REGION_FLASH       = 0,
    MPU_REGION_SRAM        = 1,
    MPU_REGION_PERIPH      = 2,
    MPU_REGION_DMA_BUF     = 3,  /* M7: non-cacheable */
    MPU_REGION_STACK_GUARD = 4,
    MPU_REGION_NULL_TRAP   = 5,
} mpu_region_t;

/* TEX/S/C/B kodlaması (armv7-m):
   0x06 = TEX=0, S=1, C=1, B=0 → Normal, write-through (flash için)
   0x0B = TEX=0, S=1, C=1, B=1 → Normal, write-back (SRAM için)
   0x00 = TEX=0, S=1, C=0, B=1 → Device (peripheral)
   0x08 = TEX=1, S=0, C=0, B=0 → Strongly-ordered / non-cacheable (DMA buf M7)
*/

static void mpu_region(uint8_t region, uint32_t base,
                        uint32_t size_enc, uint8_t ap,
                        uint8_t tex_scb, bool xn)
{
    MPU->RNR  = region;
    MPU->RBAR = base & MPU_RBAR_ADDR_Msk;
    MPU->RASR = ((uint32_t)xn      << MPU_RASR_XN_Pos)
              | ((uint32_t)ap      << MPU_RASR_AP_Pos)
              | ((uint32_t)tex_scb << MPU_RASR_TEX_Pos)
              | (size_enc          << MPU_RASR_SIZE_Pos)
              | MPU_RASR_ENABLE_Msk;
}

void mpu_setup_m7(void)
{
    ARM_MPU_Disable();

    /* Flash: RO, executable, write-through cache */
    mpu_region(MPU_REGION_FLASH,   FLASH_BASE,  MPU_REGION_SIZE_2MB,
               MPU_REGION_PRIV_RO_URO, 0x06, false);

    /* SRAM: RW, XN, write-back cache */
    mpu_region(MPU_REGION_SRAM,    SRAM_BASE,   MPU_REGION_SIZE_512KB,
               MPU_REGION_FULL_ACCESS, 0x0B, true);

    /* Peripheral: RW, XN, device (strongly ordered) */
    mpu_region(MPU_REGION_PERIPH,  0x40000000U, MPU_REGION_SIZE_512MB,
               MPU_REGION_FULL_ACCESS, 0x00, true);

    /* DMA buffer: RW, XN, non-cacheable (M7 cache bypass) */
    extern uint32_t _dma_buf_start[];
    mpu_region(MPU_REGION_DMA_BUF, (uint32_t)_dma_buf_start,
               MPU_REGION_SIZE_4KB, MPU_REGION_FULL_ACCESS, 0x08, true);

    /* Stack guard: 32B below stack → MemManage fault on overflow */
    extern uint32_t _estack[];
    mpu_region(MPU_REGION_STACK_GUARD,
               (uint32_t)_estack - 32U, MPU_REGION_SIZE_32B,
               MPU_REGION_NO_ACCESS, 0x00, true);

    /* Null pointer trap: 0x0–0x1FF → no access */
    mpu_region(MPU_REGION_NULL_TRAP, 0x00000000U, MPU_REGION_SIZE_512B,
               MPU_REGION_NO_ACCESS, 0x00, true);

    /* PRIVDEFENA: tanımlı olmayan bölgelerde privileged default map geçerli */
    ARM_MPU_Enable(MPU_CTRL_PRIVDEFENA_Msk);
}
```

**Size encoding:** `size_enc = log2(size_bytes) - 1`
Örnek: 4KB = 4096 = 2^12 → `size_enc = 11 = 0x0B = MPU_REGION_SIZE_4KB`

---

## IX. MPU — Cortex-M33 (armv8-m)

armv8-m MPU: doğal hizalama zorunluluğu yok, granül = 32 byte, CMSIS yeni API.

```c
#include "mpu_armv8.h"

/* Attribute index 0: Write-Back, Write-Allocate (SRAM) */
/* Attribute index 1: Non-cacheable (DMA buffer)         */
/* Attribute index 2: Device-nGnRnE (peripheral)         */

void mpu_setup_m33(void)
{
    ARM_MPU_Disable();

    /* Attribute tanımları (8 adet, MPU_MAIR0/1 register'larına yüklenir) */
    ARM_MPU_SetMemAttr(0UL, ARM_MPU_ATTR(
        ARM_MPU_ATTR_MEMORY_(1,1,1,1),   /* Outer: WB, WA */
        ARM_MPU_ATTR_MEMORY_(1,1,1,1))); /* Inner: WB, WA */

    ARM_MPU_SetMemAttr(1UL, ARM_MPU_ATTR(
        ARM_MPU_ATTR_NON_CACHEABLE,      /* Outer: non-cacheable */
        ARM_MPU_ATTR_NON_CACHEABLE));    /* Inner: non-cacheable */

    ARM_MPU_SetMemAttr(2UL, ARM_MPU_ATTR(
        ARM_MPU_ATTR_DEVICE,             /* Device */
        ARM_MPU_ATTR_DEVICE_nGnRnE));    /* Strongly ordered */

    /* Bölge 0: Flash — RO (AP=0b10), executable */
    ARM_MPU_SetRegion(0UL,
        ARM_MPU_RBAR(FLASH_BASE,
            ARM_MPU_SH_NON,  /* non-shareable */
            1U,              /* RO */
            1U,              /* non-privileged accessible */
            0U),             /* XN=0 — executable */
        ARM_MPU_RLAR(FLASH_BASE + FLASH_SIZE - 1U,
            0UL));           /* AttrIdx=0 (WB cacheable) */

    /* Bölge 1: SRAM — RW, XN */
    ARM_MPU_SetRegion(1UL,
        ARM_MPU_RBAR(SRAM_BASE, ARM_MPU_SH_INNER, 0U, 1U, 1U),
        ARM_MPU_RLAR(SRAM_BASE + SRAM_SIZE - 1U, 0UL));

    /* Bölge 2: DMA buffer — non-cacheable, XN */
    extern uint32_t _dma_buf_start[], _dma_buf_end[];
    ARM_MPU_SetRegion(2UL,
        ARM_MPU_RBAR((uint32_t)_dma_buf_start, ARM_MPU_SH_NON, 0U, 0U, 1U),
        ARM_MPU_RLAR((uint32_t)_dma_buf_end - 1U, 1UL));  /* AttrIdx=1 */

    /* Bölge 3: Peripheral — device, XN */
    ARM_MPU_SetRegion(3UL,
        ARM_MPU_RBAR(0x40000000U, ARM_MPU_SH_NON, 0U, 0U, 1U),
        ARM_MPU_RLAR(0x5FFFFFFFU, 2UL));  /* AttrIdx=2 */

    /* Bölge 4: Stack guard (32 byte) */
    extern uint32_t _estack[];
    ARM_MPU_SetRegion(4UL,
        ARM_MPU_RBAR(((uint32_t)_estack - 32U),
            ARM_MPU_SH_NON, 1U, 0U, 1U),  /* RO = trap on write */
        ARM_MPU_RLAR(((uint32_t)_estack - 1U), 0UL));

    ARM_MPU_Enable(MPU_CTRL_PRIVDEFENA_Msk);
    __DSB();
    __ISB();
}
```

**M7 vs M33 MPU Farkları:**

| Özellik | M4/M7 (armv7-m) | M33 (armv8-m) |
|---------|-----------------|---------------|
| Header | `mpu_armv7.h` | `mpu_armv8.h` |
| Granül | Power-of-2 zorunlu | 32-byte granül |
| Hizalama | Base = N×size | Keyfi (32B hizalı) |
| Cache attr | TEX/S/C/B field | AttrIdx → MAIR |
| API | `MPU->RASR` | `ARM_MPU_SetRegion()` |
| TrustZone | Yok | Secure/NS ayrı MPU |

---

## X. FreeRTOS MPU Port

```c
/* FreeRTOSConfig.h: */
/* #define portUSING_MPU_WRAPPERS  1 */
/* #define configENABLE_MPU        1  (M33) */

/* Task-private bellek bölgeleri */
static StackType_t  sensor_stack[512];
static StaticTask_t sensor_tcb;

/* Sensor task: sadece SPI1 + DMA buffer erişebilir */
static const MemoryRegion_t sensor_regions[] = {
    { (void *)SPI1_BASE,     0x400U,  portMPU_REGION_READ_WRITE | portMPU_REGION_DEVICE },
    { (void *)sensor_dma_buf, 256U,   portMPU_REGION_READ_WRITE | portMPU_REGION_EXECUTE_NEVER },
    { NULL, 0U, 0U }  /* sentinel */
};

static const TaskParameters_t sensor_params = {
    .pvTaskCode     = sensor_task_fn,
    .pcName         = "sensor",
    .usStackDepth   = 512U,
    .pvParameters   = NULL,
    .uxPriority     = 3U,   /* portPRIVILEGE_BIT eklenirse privileged */
    .puxStackBuffer = sensor_stack,
    .xRegions       = sensor_regions,
};

/* Task oluşturma */
xTaskCreateRestricted(&sensor_params, &sensor_handle);

/* ⚠ Unprivileged task (portPRIVILEGE_BIT olmadan):
   - Sadece kendi stack + xRegions alanlarına erişebilir
   - Diğer peripheral'lara erişim → MemManage fault
   - RTOS API'leri: MPU wrapper ile privileged moda geçer (otomatik) */
```

---

## XI. Kontrol Listesi

```
TrustZone Option Bytes:
□ TZEN=1 ayarlandı (gerekiyorsa)
□ SECWM1_PSTRT / SECWM1_PEND doğru sayfa aralığını kapsıyor
□ RDP ≥ Level 1 (production build)
□ Debug portuna TZEN=1 sonrası erişilebildi mi? (test et)

GTZC Peripheral Atamaları:
□ RNG, PKA, HASH, AES → Secure olarak işaretli
□ NS uygulamanın ihtiyacı olan peripheral'lar NS olarak işaretli
□ TZIC (GTZC IRQ) aktif, ihlalleri loglayacak handler yazıldı

SAU:
□ SAU bölgeleri NS flash, NSC flash, NS SRAM, NS peripheral kapsıyor
□ __DSB() + __ISB() SAU aktifleştirmesinden sonra var
□ Tanımlanmamış bölgeler Secure (varsayılan) — beklendiği gibi mi?

NSC API:
□ Tüm NSC fonksiyonlar cmse_check_address_range() ile pointer doğruluyor
□ Hassas veriler NSC dönüşünden önce temizleniyor (memset)
□ Veneer table NS projesine doğru link ediliyor (.lib/.a)
□ Secure proje rebuild sonrası NS proje de rebuild edildi

Shared Memory:
□ DSB barrier NS→Secure yön için var (flag set'ten önce)
□ DMB barrier Secure→NS yön için var (flag clear'dan sonra)
□ Paylaşımlı bölge SAU'da NS, MPCBB'de NS olarak işaretli

MPU:
□ Stack guard bölgesi tanımlı (32 byte stack altında)
□ NULL pointer trap aktif (0x0–0x1FF no-access)
□ DMA buffer bölgesi non-cacheable (M7 için zorunlu)
□ ARM_MPU_Enable(MPU_CTRL_PRIVDEFENA_Msk) — privileged default map açık
□ __DSB() + __ISB() MPU aktifleştirmesinden sonra var

Boot:
□ NS firmware hash doğrulaması Secure'da yapılıyor
□ NS MSP aralığı doğrulanıyor (NS SRAM içinde mi?)
□ SCB_NS->VTOR NS flash base adresine set edildi
```

---

## XII. Yaygın Hatalar

| Hata | Neden | Çözüm |
|------|-------|-------|
| SecureFault exception | NS kodu Secure bölgeye erişti | SAU + GTZC sınırlarını kontrol et |
| TZEN=0'da SAU config çalışmıyor | TrustZone devre dışı | Option byte'ta TZEN=1 yap |
| NSC çağrı fault üretiyor | Veneer NSC bölgesi dışında | SAU_RLAR_NSC_Msk ile NSC bölgeyi işaretle |
| NS pointer Secure alana işaret | cmse_check eksik | NSC fonksiyonlarda tüm pointer'ları doğrula |
| Shared buffer bozuluyor | DSB/DMB eksik | Her iki tarafta __DMB() / __DSB() ekle |
| Debug bağlanamıyor | RDP2 aktif | RDP1 kullan; RDP2 → geri alınamaz |
| Secure peripheral NS'den görünüyor | GTZC yanlış | HAL_GTZC_TZSC_ConfigPeriphAttributes() düzelt |
| Veneer table stale | Secure build, NS build yok | Her iki projeyi rebuild et |
| SECWM sınırı SAU'yla uyumsuz | Farklı boundary | SECWM sayfaları = SAU NS region başlangıcı |
| MPU MemManage: DMA transferi | DMA buffer cacheable | MPU bölgesini non-cacheable yap (AttrIdx=1) |
| NS hand-off sonrası SecureFault | SCB_NS->VTOR set edilmedi | Handoff'tan önce NS VTOR'u yaz |
| MPCBB granülü uyumsuz | Bölge 512B'den küçük | MPCBB minimum 512B blok — sınırı hizala |
