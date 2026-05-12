# ARM TrustZone — Güvenli Donanım Mimarisi (STM32L5/U5/H5)

ARM TrustZone: donanım düzeyinde güvenli (Secure) ve güvensiz (Non-Secure) dünya ayrımı. Cortex-A için TrustZone, Cortex-M için TrustZone-M (M23, M33, M35P, M55 ailelerinde).

---

## Temel Kavramlar

| Kavram | Açıklama |
|--------|----------|
| Secure World | Güvenli işlemci modu — güvenilir kod ve veri |
| Normal World | Non-Secure — işletim sistemi, uygulama kodu |
| TEE | Trusted Execution Environment — güvenli dünya çalışma ortamı |
| REE | Rich Execution Environment — normal dünya |
| NS bit | Transaction'da Non-Secure bit — 0=Secure, 1=Normal |
| SAU | Security Attribution Unit (M33) — bölge tabanlı güvenlik |
| IDAU | Implementation Defined Attribution Unit — çip spesifik ek SAU |
| NSC | Non-Secure Callable — Normal dünyadan çağrılabilen güvenli fonksiyon |
| CMSE | C Microcontroller Security Extensions — ARM Clang/GCC eklentisi |

---

## Cortex-A TrustZone vs Cortex-M TrustZone-M

| | Cortex-A TrustZone | Cortex-M TrustZone-M |
|--|--------------------|---------------------|
| Exception Level | EL0..EL3 | Thread/Handler mode |
| Geçiş | SMC (Secure Monitor Call) | SG (Secure Gateway) instruction |
| Monitor | EL3 (Secure Monitor) | Hardware otomatik |
| Boot chain | ATF (TF-A) → OP-TEE → REE | SecureBoot → Secure FW → NS FW |
| Yaygın STM32 | Yok (Cortex-A değil) | STM32L5, U5, H5, WL5 |

---

## Cortex-A TrustZone Mimarisi (Referans — Embedded Linux)

### Exception Level Hiyerarşisi

```
EL3  — Secure Monitor (ATF BL31, SMC handler)  [Secure world]
EL2  — Hypervisor (optionel, ör. Hafnium)       [Normal world]
EL1  — İşletim Sistemi: OP-TEE (Secure) / Linux (Normal)
EL0  — Uygulama: Trusted App (Secure) / Android/Linux app (Normal)
```

### Dünya Geçişi (Cortex-A)

```asm
; Normal World (EL1) → Secure World için SMC
MOV  x0, #FUNC_ID     ; SMC fonksiyon ID
MOV  x1, #ARG1
SMC  #0               ; Secure Monitor'a yükselt (EL3'e gider)
; Döndüğünde EL1'de devam eder — Secure World işi yaptı
```

### TZASC (TrustZone Address Space Controller)

```
TZASC: DRAM bölgelerini Secure/NS olarak işaretler
  Region 0: NS=0 → sadece Secure world erişebilir (OP-TEE private)
  Region 1: NS=1 → Normal world erişebilir (Linux memory)
  Region 2: NS=0 → Shared memory (Secure'a ait, NS okuyabilir — TZASC yapılandırmasına bağlı)

Peripheral'lar: TZPC (TrustZone Protection Controller) ile S/NS atanır
  Örn: UART0 → Secure, UART1 → Normal
```

---

## Cortex-M TrustZone-M (STM32L5 / U5 / H5)

### SAU (Security Attribution Unit) Yapılandırması

STM32L5/U5 çiplerinde SAU 8 bölgeye kadar tanımlanabilir. Her bölge:

```c
/* SAU bölge yapılandırması — CMSIS */
SAU->RNR  = 0;                           /* Bölge 0 seç */
SAU->RBAR = 0x08000000;                  /* Başlangıç adresi */
SAU->RLAR = 0x0801FFFF                   /* Bitiş adresi */
          | SAU_RLAR_ENABLE_Msk;         /* Etkinleştir */
          /* NS bit = 0 → Secure (varsayılan) */

/* NSC bölgesi — Normal world'den çağrılabilir Secure fonksiyonlar */
SAU->RNR  = 1;
SAU->RBAR = 0x0C000000;                  /* NSC region başlangıcı */
SAU->RLAR = 0x0C00007F
          | SAU_RLAR_ENABLE_Msk
          | SAU_RLAR_NSC_Msk;            /* NSC flag */

/* Tüm SAU etkinleştir */
SAU->CTRL = SAU_CTRL_ENABLE_Msk;
```

### CMSE — NSC (Non-Secure Callable) Fonksiyon

```c
/* Secure taraf: NSC fonksiyon tanımı */
/* cmse_nonsecure_entry → SG instruction önüne yerleştirilir */
#include "arm_cmse.h"

__attribute__((cmse_nonsecure_entry))
int32_t secure_get_sensor_value(void)
{
    /* Güvenli sensör verisi oku */
    return (int32_t)SECURE_SENSOR_REG;
}

/* NSC fonksiyon venom güvenlik kontrolü: Normal world pointer'ı kabul etme */
__attribute__((cmse_nonsecure_entry))
void secure_write_config(const uint8_t *ns_ptr, uint32_t len)
{
    /* MUTLAKA pointer güvenliğini kontrol et */
    if (cmse_check_address_range((void *)ns_ptr, len, CMSE_NONSECURE | CMSE_MPU_READ) == NULL) {
        return;   /* Güvensiz pointer → reddet */
    }
    /* Artık güvenli kopyala */
    memcpy(secure_config_buf, ns_ptr, len);
}
```

### Normal World'den NSC Çağrısı

```c
/* Normal world tarafında — veneer (NSC wrapper) ile çağırılır */
/* Linker otomatik veneer üretir veya elle import table kullanılır */

/* veneer_table.h (toolchain tarafından üretilir) */
extern int32_t secure_get_sensor_value(void);  /* NSC fonksiyon */

void ns_application(void)
{
    int32_t val = secure_get_sensor_value();    /* SG instruction → Secure world */
    /* val döndükten sonra Normal world'deyiz */
}
```

### Güvenli Boot Zinciri (STM32H5 Örneği)

```
Power On
  ↓
ROM Bootloader (Secure)
  — OTP / Option Bytes okur
  — RDP (Readout Protection) kontrol eder
  — Hash doğrulama (HASH peripheral)
  ↓
Secure Firmware (Flash Secure bölge)
  — SAU/IDAU yapılandırır
  — MPU Secure bölgelerini ayarlar
  — TZGTZC (TrustZone-aware GTZC) peripheral güvenliğini ayarlar
  — NS firmware'i doğrular (SHA256, RSA vb.)
  — NS dünyaya geçer
  ↓
Non-Secure Firmware (Flash NS bölge)
  — Uygulama kodu çalışır
  — Güvenli işlemler için NSC çağırır
```

---

## STM32L5/U5/H5 — GTZC (Global TrustZone Controller)

```c
/* GTZC: peripheral erişim güvenliğini tanımlar */
/* Örn: RNG (True RNG) sadece Secure world erişebilir */

/* HAL ile peripheral güvenliği ayarla */
__HAL_RCC_GTZC1_CLK_ENABLE();

MPCBB_ConfigTypeDef mpcbb_config;
mpcbb_config.SecureRWIllegalMode = GTZC_MPCBB_SRWILADIS_ENABLE;
mpcbb_config.InvertSecureState   = GTZC_MPCBB_INVSECSTATE_NOT_INVERTED;
mpcbb_config.AttributeConfig.MPCBB_SecConfig_array[0] = 0xFFFFFFFF; /* Tüm bloklar Secure */
HAL_GTZC_MPCBB_ConfigMem(SRAM1, &mpcbb_config);

/* Peripheral güvenlik ataması */
HAL_GTZC_TZSC_ConfigPeriphAttributes(GTZC_PERIPH_RNG,
    GTZC_TZSC_PERIPH_SEC | GTZC_TZSC_PERIPH_PRIV);  /* Secure + Privileged only */

HAL_GTZC_TZSC_ConfigPeriphAttributes(GTZC_PERIPH_USART1,
    GTZC_TZSC_PERIPH_NSEC);  /* Non-Secure — NS world kullanabilir */
```

---

## Shared Memory — Güvenli/Güvensiz Paylaşım

```c
/* Shared buffer: NS world yazar, Secure world okur */
/* Normal SAU yapılandırması gerekli: region NS olarak işaretli */

/* Secure taraf */
__attribute__((section(".ns_shared")))
volatile uint8_t shared_buf[256];

__attribute__((cmse_nonsecure_entry))
void secure_process_shared(uint32_t len)
{
    /* Shared buffer'ı oku — NS world'den geldi */
    /* DSB ile cache coherency sağla */
    __DSB();
    process_data((const uint8_t *)shared_buf, len);
}

/* NS taraf */
extern volatile uint8_t shared_buf[256];   /* linker export */
void ns_send_data(const uint8_t *data, uint32_t len)
{
    memcpy((void *)shared_buf, data, len);
    __DSB();                                /* write complete */
    secure_process_shared(len);             /* NSC çağrı */
}
```

---

## TrustZone Güvenlik Kontrol Listesi

```
□ SAU bölgeleri doğru yapılandırıldı mı? (Secure/NS/NSC)
□ NSC fonksiyonlar cmse_check_address_range ile NS pointer doğruluyor mu?
□ Secure bölge'den NS pointer dereference yapılıyor mu? → Güvenlik açığı
□ GTZC: hassas peripheral'lar (RNG, crypto) Secure olarak işaretli mi?
□ SRAM bölgeleri Secure/NS doğru ayrıldı mı? (MPCBB)
□ Shared memory bölgelerinde DSB/DMB barrier var mı?
□ Flash RDP (Readout Protection) aktif mi? (production build)
□ Secure firmware debug porta kapandı mı? (RDP2)
□ NSC veneer table güncel mi? (yeniden build sonrası)
□ NS firmware hash doğrulama Secure boot'ta yapılıyor mu?
□ Secure/NS geçişte r0-r3 dışında register temizleniyor mu? (bilgi sızıntısı)
```

---

## Yaygın TrustZone Hataları

| Hata | Neden | Çözüm |
|------|-------|-------|
| SecureFault exception | NS kodu Secure bölgeye erişti | SAU bölge sınırlarını kontrol et |
| NSC çağrı çalışmıyor | SG instruction NSC bölgede değil | NSC region'ı SAU_RLAR_NSC_Msk ile işaretle |
| Shared buffer bozuluyor | DSB/DMB eksik | Her iki tarafta __DSB() ekle |
| NS pointer Secure heap'e erişiyor | cmse_check eksik | NSC fonksiyonlarda tüm pointer'ları doğrula |
| Debug bağlanamıyor | RDP2 aktif | RDP1 kullan (mass erase ile geri alınabilir) |
| Secure peripheral NS'den görünüyor | GTZC yapılandırması yanlış | HAL_GTZC_TZSC_ConfigPeriphAttributes düzelt |
| Veneer table stale | Secure FW güncelendi, NS güncellenmedi | Her iki tarafı aynı anda build et |
