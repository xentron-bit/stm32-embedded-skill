# Secure Boot, Option Bytes and Firmware Signing — STM32

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, errata workarounds, protocol-spec content** here is authoritative — that is why this file exists.
> - **Inline HAL/CMSIS/peripheral code snippets** are illustrative. The HAL drifts between versions and parts. For the canonical version of any HAL symbol at your HAL release: `gh search code <SymbolName> --owner=STMicroelectronics --extension=c` — see [ref-st-github-map.md](ref-st-github-map.md) §8 for the full lookup procedure.
> - **CRITICAL bugs identified in the 2026-05-16 audit have been corrected** in this file, but verify against your own HAL version before copy-pasting.
> - **For bootloader / IAP / OTA topics** the canonical checklist + ARM KA001193 + AN5188/2606/3155/3156 references are in [ref-bootloader.md](ref-bootloader.md).


## RDP (Readout Protection) Levels

```
RDP Level 0 (default): Open — debug port fully functional, flash readable
RDP Level 1: Readout protected — SWD debugging limited, flash unreadable via debugger
             Mass erase required to go back to RDP0 (erases all user flash)
RDP Level 2: Fully locked — debug port permanently disabled, irreversible on most parts
             H7/L5/U5: RDP2 disables JTAG/SWD permanently. Cannot undo.

⚠ RDP2 WARNING: Some STM32 parts (H7, G4) allow RDP2 → RDP1 via mass erase.
                Others (L5/U5 with TrustZone) do NOT. Read datasheet carefully.
```

## Option Byte Programming

```c
void set_option_bytes(void)
{
    FLASH_OBProgramInitTypeDef ob = {0};

    HAL_FLASH_Unlock();
    HAL_FLASH_OB_Unlock();

    /* Read current option bytes first */
    HAL_FLASHEx_OBGetConfig(&ob);

    /* Set RDP level 1 */
    ob.OptionType = OPTIONBYTE_RDP;
    ob.RDPLevel   = OB_RDP_LEVEL_1;
    HAL_FLASHEx_OBProgram(&ob);

    /* Write protect bootloader sectors (Bank1, Sector 0-1) */
    ob.OptionType    = OPTIONBYTE_WRP;
    ob.WRPState      = OB_WRPSTATE_ENABLE;
    ob.WRPSector     = OB_WRP_SECTOR_0 | OB_WRP_SECTOR_1;
    ob.Banks         = FLASH_BANK_1;
    HAL_FLASHEx_OBProgram(&ob);

    /* Set BOR level (Brown-Out Reset) */
    ob.OptionType = OPTIONBYTE_BOR;
    ob.BORLevel   = OB_BOR_LEVEL3;   /* ~2.7V reset threshold */
    HAL_FLASHEx_OBProgram(&ob);

    /* Launch: apply option bytes — causes system reset */
    HAL_FLASH_OB_Launch();  /* never returns — MCU resets */
    /* DO NOT call HAL_FLASH_OB_Lock() before Launch */
}
```

## Read Current Option Bytes

```c
void read_option_bytes(void)
{
    FLASH_OBProgramInitTypeDef ob = {0};
    HAL_FLASHEx_OBGetConfig(&ob);

    /* Check RDP level */
    if (ob.RDPLevel == OB_RDP_LEVEL_0) { /* open */ }
    if (ob.RDPLevel == OB_RDP_LEVEL_1) { /* protected */ }
    if (ob.RDPLevel == OB_RDP_LEVEL_2) { /* locked */ }

    /* Check write protection */
    uint32_t wrp = ob.WRPSector;  /* bitmask of protected sectors */

    /* H7: separate read for Bank2 */
    ob.Banks = FLASH_BANK_2;
    HAL_FLASHEx_OBGetConfig(&ob);
}
```

## PCROP (Proprietary Code Read Out Protection)

```c
/* Execute-only region — code cannot be read back, only executed */
/* Available on: F4 Revision Z+, F7, L4, G4 (page or sector granularity varies by family).
 * NOT available on STM32H7 — H7 uses Secure-Only Flash + RDP + WRP instead of PCROP. */

FLASH_OBProgramInitTypeDef ob = {0};
HAL_FLASH_Unlock();
HAL_FLASH_OB_Unlock();

ob.OptionType    = OPTIONBYTE_PCROP;
ob.PCROPConfig   = OB_PCROP_ZONE_ENABLE;  /* H7: zone A */
ob.PCROPStartAddr = 0x08010000;  /* start of PCROP zone */
ob.PCROPEndAddr   = 0x0801FFFF;  /* end of PCROP zone */
HAL_FLASHEx_OBProgram(&ob);
HAL_FLASH_OB_Launch();  /* reset to apply */
```

## Firmware Image Signing (SHA-256 + ECDSA P-256)

```c
/* Signing is done at build time (PC side), verification at boot time (MCU) */

/* Build pipeline (PC): */
/*   1. Compile firmware → .bin */
/*   2. Compute SHA-256 of .bin */
/*   3. Sign SHA-256 with ECDSA private key → signature (64 bytes) */
/*   4. Append metadata + signature to .bin → signed_firmware.bin */

/* Firmware image structure: */
typedef struct __attribute__((packed)) {
    uint32_t magic;           /* 0x5354_4D46 "STMF" */
    uint32_t version;         /* anti-rollback version */
    uint32_t image_size;      /* bytes of firmware (after header) */
    uint8_t  sha256[32];      /* SHA-256 of firmware bytes */
    uint8_t  ecdsa_sig[64];   /* ECDSA P-256 signature of sha256 */
    uint8_t  public_key[64];  /* optional: embedded public key */
    uint32_t crc32;           /* CRC32 of this header */
} fw_image_header_t;
```

```c
/* Boot-time verification using PKA (H7/L5/U5) */
#include "stm32h7xx_hal_pka.h"

PKA_HandleTypeDef hpka;
PKA_ECDSAVerifInTypeDef verify_in;

bool verify_firmware_signature(const fw_image_header_t *hdr, const uint8_t *fw_data)
{
    /* 1. Verify CRC32 of header */
    uint32_t crc = crc32_compute((uint8_t*)hdr, offsetof(fw_image_header_t, crc32));
    if (crc != hdr->crc32) return false;

    /* 2. Compute SHA-256 of firmware */
    uint8_t computed_hash[32];
    sha256_compute(fw_data, hdr->image_size, computed_hash);

    /* 3. Verify hash matches header */
    if (memcmp(computed_hash, hdr->sha256, 32) != 0) return false;

    /* 4. Verify ECDSA signature using PKA.
     *
     * CRITICAL — both size fields are in BITS, not bytes (UM2178 / PKA HAL).
     * For NIST P-256, primeOrderSize = modulusSize = 256.
     *
     * For curve coefficient `a` (= -3 for P-256):
     *   coefSign = 1, coef points to value |a| = 3
     *      OR
     *   coefSign = 0, coef points to (p - 3) — i.e. supply a in unsigned form
     *
     * The previous code used coefSign=0 while pointing to a literal "-3" or
     * to a constant labeled p256_a — verification would silently fail
     * (signature always invalid) and the secure-boot chain would reject all
     * firmware including legitimate releases. */
    verify_in.primeOrderSize = 256;
    verify_in.modulusSize    = 256;
    verify_in.coefSign       = 1;
    verify_in.coef           = (uint8_t*)p256_a_abs;   /* the value 3 */
    verify_in.modulus        = (uint8_t*)p256_p;
    verify_in.basePointX     = (uint8_t*)p256_Gx;
    verify_in.basePointY     = (uint8_t*)p256_Gy;
    verify_in.primeOrder     = (uint8_t*)p256_n;
    verify_in.pPubKeyX       = (uint8_t*)trusted_pub_key;       /* stored in flash */
    verify_in.pPubKeyY       = (uint8_t*)trusted_pub_key + 32;
    verify_in.RSign          = hdr->ecdsa_sig;
    verify_in.SSign          = hdr->ecdsa_sig + 32;
    verify_in.hash           = hdr->sha256;

    HAL_PKA_ECDSAVerif(&hpka, &verify_in, 1000);
    uint32_t result = HAL_PKA_ECDSAVerif_IsValidSignature(&hpka);
    return (result == 1);
}
```

## OTFDEC (On-The-Fly Decryption for OCTOSPI XIP)

```c
/* Firmware stored encrypted in external flash, decrypted transparently on read */
/* Key stays in OTFDEC registers (write-only, cannot be read back) */

OTFDEC_HandleTypeDef hotfdec;
OTFDEC_RegionConfigTypeDef region = {0};

void otfdec_init(void)
{
    hotfdec.Instance = OTFDEC1;
    HAL_OTFDEC_Init(&hotfdec);

    region.Nonce[0] = 0x12345678;   /* IV for AES-CTR */
    region.Nonce[1] = 0x9ABCDEF0;
    region.StartAddress = 0x90000000;   /* OCTOSPI start */
    region.EndAddress   = 0x90FFFFFF;   /* 16MB region */
    region.Mode         = OTFDEC_REG_MODE_INSTRUCTION_OR_DATA_ACCESSES;

    uint32_t key[4] = { 0x... };   /* provisioned at factory, never in source */
    HAL_OTFDEC_RegionSetKey(&hotfdec, OTFDEC_REGION1, key);
    HAL_OTFDEC_RegionConfig(&hotfdec, OTFDEC_REGION1, &region, OTFDEC_REG_CONFIGR_LOCK_ENABLE);
}
/* After this: reads from 0x90000000 are transparently decrypted */
/* Key cannot be read back (write-only registers) */
```

## Anti-Rollback

```c
/* Version stored in OTP fuses (one-time programmable).
 * Each version increment CLEARS one more fuse bit (1 → 0 transition).
 * STM32 flash including OTP ships ERASED = 0xFFFFFFFF; programming can
 * only flip bits from 1 → 0. So:
 *   "burned bits" per word = 32 - popcount(word)
 *   "remaining (still-1) bits" per word = popcount(word)
 *
 * The previous code returned popcount(word) — the *inverse* of what it
 * claimed to measure. Anti-rollback was disabled: as more versions burned
 * fewer bits remained set, so the reported "min version" went DOWN.
 *
 * H7 OTP block is at 0x08FFF000 (1 KB), inside the system flash mapping —
 * NOT at 0x1FFx_xxxx (that's system bootloader). RM0433 §4.3.13. */

#define OTP_VERSION_BASE_ADDR  0x08FFF000U  /* STM32H743/H750/H730 OTP */
#define OTP_VERSION_WORDS      8            /* 8 × 32 = 256 burnable bits */

uint32_t get_hw_min_version(void)
{
    /* Count CLEARED bits — each cleared bit = one accepted version level */
    uint32_t burned = 0;
    for (int i = 0; i < OTP_VERSION_WORDS; i++) {
        uint32_t word = *(__IO uint32_t*)(OTP_VERSION_BASE_ADDR + i * 4);
        burned += (32U - (uint32_t)__builtin_popcount(word));
    }
    return burned;
}

void burn_version_bit(void)
{
    /* OTP burn: program a 256-bit (H7) flash word with ONE bit cleared.
     * OTP is permanent — cannot undo. Find the first OTP word that still
     * has set bits and clear the lowest one. */
    HAL_FLASH_Unlock();
    for (uint32_t i = 0; i < OTP_VERSION_WORDS; i++) {
        uint32_t addr = OTP_VERSION_BASE_ADDR + i * 4U;
        uint32_t cur  = *(__IO uint32_t*)addr;
        if (cur == 0U) continue;
        uint32_t lsb_set = cur & (uint32_t)(-(int32_t)cur);  /* lowest set bit */
        uint32_t flash_word[8] = { 0xFFFFFFFFU, 0xFFFFFFFFU, 0xFFFFFFFFU, 0xFFFFFFFFU,
                                   0xFFFFFFFFU, 0xFFFFFFFFU, 0xFFFFFFFFU, 0xFFFFFFFFU };
        /* H7 programs 256 bits at once; clearing one bit in one of the
         * eight 32-bit lanes is the smallest possible burn. */
        flash_word[i & 7U] = ~lsb_set;
        HAL_FLASH_Program(FLASH_TYPEPROGRAM_FLASHWORD,
                          OTP_VERSION_BASE_ADDR + (i & ~7U) * 4U,
                          (uint32_t)flash_word);
        break;
    }
    HAL_FLASH_Lock();
}

bool is_version_allowed(uint32_t fw_version)
{
    return fw_version >= get_hw_min_version();
}
```

## Production Programming Flow

```
Factory programming sequence (order matters):

1. Mass erase (optional, clean start)
   STM32_Programmer_CLI -c port=SWD freq=4000 -e all

2. Program bootloader (sector 0)
   STM32_Programmer_CLI -c port=SWD -d bootloader.hex -v

3. Program application (sector 2+)
   STM32_Programmer_CLI -c port=SWD -d signed_app.hex -v

4. Program calibration data (last sector)
   STM32_Programmer_CLI -c port=SWD -d calibration.bin 0x0803F000

5. Set option bytes LAST (after firmware verified)
   STM32_Programmer_CLI -c port=SWD -ob RDP=1 BOR_LEV=3 WRP_GRP0=1

6. Verify (smoke test)
   Run production test via UART/CAN/USB

7. Lock (if required)
   STM32_Programmer_CLI -c port=SWD -ob RDP=2   ← IRREVERSIBLE on some parts
```

## Common Mistakes

| Mistake | Consequence | Prevention |
|---------|-------------|------------|
| Set RDP2 before testing | Device bricked | Test fully before RDP2 |
| Call `OB_Lock()` before `OB_Launch()` | Option bytes not applied | Launch immediately after Program |
| PCROP without verifying address | Wrong region protected | Verify with read back at RDP0 |
| Skip `OB_Unlock()` | HAL_FLASHEx_OBProgram returns HAL_ERROR silently | Always unlock before programming |
| Public key in `.rodata` without WRP | Attacker can replace key | WRP-protect boot sector containing key |
| Anti-rollback OTP in user flash | Can be erased | Use hardware OTP fuses |
| OTFDEC key in source code | Key exposure | Factory provisioned, never in source |

---

## BL→App Runtime Chain Verification

Static option-byte protections (RDP/WRP/PCROP) protect against **read-back** of
the App image. They do NOT protect against:

- Field-OTA-installed apps that have valid format but malicious payload
- Replay of an older signed app to bypass a security patch
- Bit-flip / aging corruption of the app image between flash writes
- A bootloader compromise that swaps the public key

The **BL→App runtime chain** verifies the app image on every boot, against
keys/manifest that the bootloader holds in regions outside the app's reach.

### Chain Anatomy

```
   ┌──────────────────────────────────────────────────────────────┐
   │  ROOT OF TRUST (ROT)                                         │
   │   - Lives in WRP+PCROP region                                │
   │   - Contains OEM-Pub-Key (ECDSA P-256)                       │
   │   - On H5/U5: lives in OBK area, RSS-managed (immutable)     │
   │   - On H7/F4/L4/G4: lives in flash sector 0, WRP-locked      │
   └──────────────────────────────────┬───────────────────────────┘
                                      │  signs
                                      ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  BOOTLOADER MANIFEST (BLM)                                   │
   │   - {app_address, app_length, app_hash, app_version,         │
   │      signature_over_above_with_OEM_Priv}                     │
   │   - Lives in dedicated flash sector, WRP-locked              │
   │   - On OTA install: BL writes new BLM after verifying        │
   │     candidate signature                                      │
   └──────────────────────────────────┬───────────────────────────┘
                                      │  describes
                                      ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  APPLICATION IMAGE                                           │
   │   - At app_address, length app_length                        │
   │   - On boot: BL computes SHA-256 of image, compares to       │
   │     BLM.app_hash                                             │
   │   - Mismatch → fall back to last-known-good slot, or brick   │
   │     to a fail-safe loop                                      │
   └──────────────────────────────────────────────────────────────┘
```

### Boot-Time Verification — pseudo-code

```c
/* Bootloader entry — runs at every reset, before app */

#include "psa/crypto.h"   /* or mbedtls equivalent */

typedef struct __attribute__((packed)) {
    uint32_t magic;           /* 'BLM1' */
    uint32_t app_address;
    uint32_t app_length;
    uint8_t  app_hash[32];    /* SHA-256 */
    uint32_t app_version;     /* anti-rollback comparison */
    uint8_t  reserved[32];
    uint8_t  signature[64];   /* ECDSA P-256 over above (excluding this field) */
} BLM_t;

extern const BLM_t   __blm;            /* linker-placed in WRP region */
extern const uint8_t __oem_pub_key[];  /* PCROP region */

int verify_app_chain(void)
{
    /* Step 1: Magic check (fast fail) */
    if (__blm.magic != 0x424C4D31) return -1;

    /* Step 2: Verify signature on BLM with OEM-Pub-Key */
    psa_status_t st = psa_verify_message(
        OEM_PUB_KEY_ID,
        PSA_ALG_ECDSA(PSA_ALG_SHA_256),
        (const uint8_t *)&__blm, offsetof(BLM_t, signature),
        __blm.signature, sizeof(__blm.signature));
    if (st != PSA_SUCCESS) return -2;

    /* Step 3: Anti-rollback — app_version must be ≥ last-booted version */
    uint32_t last_version = anti_rollback_read();   /* from OTP or sticky reg */
    if (__blm.app_version < last_version) return -3;

    /* Step 4: Recompute hash of app image, compare */
    uint8_t hash[32];
    sha256_compute((const void *)__blm.app_address, __blm.app_length, hash);
    if (memcmp(hash, __blm.app_hash, 32) != 0) return -4;

    /* Step 5: Anti-rollback latch — record this version as last-booted */
    if (__blm.app_version > last_version) {
        anti_rollback_write(__blm.app_version);
    }

    return 0;  /* OK — proceed to jump */
}

int main(void)
{
    SystemInit_BL();
    int rc = verify_app_chain();
    if (rc != 0) {
        log_failure(rc);
        /* Two strategies — pick one per product policy: */
        /* (A) Fall back to slot B (A/B firmware scheme) — see ref-iap-ota.md */
        /* (B) Enter a "brick" loop that only USB-DFU or signed UART can recover */
        recovery_loop();
    }
    jump_to_app((void (*)(void))__blm.app_address);
}
```

### Anti-Rollback Storage Options

| Storage | Update mechanism | Erasable? | Quantity |
|---------|------------------|-----------|----------|
| **OTP fuses** (option-byte BFB2, USER0/USER1) | One-time bit-set | No | Limited bits |
| **STM32H5/U5 NV-counter (RSS)** | RSS service call | No (monotonic) | 16-32 counter |
| **Backup register + RTC** | Runtime write | Yes (loss on VBAT fail) | Many |
| **Flash sector with monotonic encoding** | Bit-set 1→0 only (physics); encode counter as bit-mask | No (within sector) | ~ 8192 increments per KB |

**Recommended:** OTP fuses on parts that have them (limited but secure); RSS
NV-counter on H5/U5; monotonic-flash-bitmask on parts without either. Backup
register alone is **insufficient** — battery-removal attack defeats it.

### A/B Slot Scheme — Rollback-Safe OTA

Two app slots, BL tracks which slot is "stable" and which is "candidate":

```c
typedef struct __attribute__((packed)) {
    uint32_t magic;
    uint32_t stable_slot;        /* 0 or 1 */
    uint32_t candidate_slot;     /* 0 or 1 (≠ stable normally) */
    uint32_t candidate_boots;    /* incremented each boot of candidate */
    uint32_t candidate_max;      /* if boots ≥ max without "I_AM_OK" confirm,
                                    revert to stable */
} OTA_State_t;

/* Boot decision tree:
 *
 *   if OTA_State.candidate_slot is valid AND boots < max:
 *       try boot candidate, increment boots
 *       app must call ota_confirm() in first N seconds → resets boots, swap stable/candidate
 *   if candidate fails verify OR boots ≥ max:
 *       fall back to stable_slot
 *   if stable_slot also fails verify:
 *       recovery_loop (USB-DFU only)
 */
```

**Why "boots ≥ max":** the new firmware might pass signature verification but
crash before completing init, causing reboot loops. Counter forces revert
after a fixed number of attempts.

See [ref-iap-ota.md](ref-iap-ota.md) for the linker-script and flash-bank-swap
details on parts with dual-bank flash.

### HDP Latch Integration (H5/U5/L5/WBA)

After signature verification succeeds, **before jumping to app**, latch
HDP so the bootloader code (containing the public key and the verification
routine) becomes unreadable from app context:

```c
/* H5/U5/L5/WBA — latch HDP region 1 (covers bootloader flash) */
FLASH->SECHDPCR |= FLASH_SECHDPCR_HDP1_ACCDIS;
__DSB();
__ISB();
jump_to_app(__blm.app_address);
```

This means even if the application has a memory disclosure vulnerability
(e.g., a missing bounds check that leaks flash content over UART), the
attacker reads zeros for the bootloader region. The OEM public key and the
verification code are mathematically present but architecturally invisible.

For families without HDP (H7/F4/L4/G4), the next-best is `WRP+PCROP` on the
bootloader sector — read returns 0 from CPU, but flash is not write-protected
from a re-flash via SWD (so RDP=1 + WRP also needed to block re-flash route).

### Common BL→App Chain Mistakes

1. **Verifying signature against `__oem_pub_key` that lives in App's address
   space.** App can replace the key. Public key MUST live in BL's
   WRP/PCROP/HDP region.

2. **Computing hash over `app_length` from app's own header.** Self-referential —
   malicious app sets `length = 100` so only the first 100 bytes hash. Always
   use length from the BLM (signed structure outside app).

3. **No anti-rollback check.** OTA downgrade is the typical bypass for a
   newly-patched security vulnerability.

4. **Forgetting to update the anti-rollback counter on FIRST successful boot
   of a new version.** Otherwise, rolling back is trivially allowed.

5. **HDP not latched, OR latched in app instead of BL.** App can read public
   key, derive private key from any side-channel, or leak via UART debug print.

6. **Single slot (no A/B), no fail-safe.** Failed OTA = bricked device.
   Recovery requires customer return.

7. **`recovery_loop()` accessible without auth.** If BL's recovery accepts
   any signed firmware, an attacker can re-flash a malicious image. Recovery
   MUST require the same signature chain — only the auth medium differs (USB
   DFU vs OTA).

8. **HDP latched too late** (after some Secure-context library calls back
   into bootloader for crypto routines). The library calls fail post-latch.
   Plan the call-graph: HDP latch comes AFTER everything the app needs to
   call back into.

### Cross-references

- Key storage / OEM-Priv handling → [ref-key-provisioning.md](ref-key-provisioning.md)
- HDP / DBGAUTH state for secure regions → [ref-secure-debug.md](ref-secure-debug.md)
- TrustZone Secure context for RSS calls → [ref-trustzone.md](ref-trustzone.md)
- A/B slot linker layouts and bank-swap → [ref-iap-ota.md](ref-iap-ota.md)
- Boot order, jump pattern → [ref-bootloader.md](ref-bootloader.md)
- Production-line verification of chain → [ref-eol-test-framework.md](ref-eol-test-framework.md)
