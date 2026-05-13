# Secure Boot, Option Bytes and Firmware Signing — STM32

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
/* Available on: F4 Revision Z+, L4, G4, H7 */

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

    /* 4. Verify ECDSA signature using PKA */
    verify_in.primeOrderSize = 32;
    verify_in.modulusSize    = 32;
    verify_in.coefSign       = 0;              /* P-256 a = -3 */
    verify_in.coef           = (uint8_t*)p256_a;
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
/* Version stored in OTP fuses (one-time programmable) */
/* Each version increment burns one more fuse bit */
/* Never allow installing firmware older than burned version */

#define OTP_VERSION_BASE_ADDR  0x1FF80000   /* H7 OTP area */
#define OTP_VERSION_WORDS      8            /* 8 words = 256 version bits */

uint32_t get_hw_min_version(void)
{
    /* Count set bits in OTP — each set bit = one version level */
    uint32_t count = 0;
    for (int i = 0; i < OTP_VERSION_WORDS; i++) {
        uint32_t word = *(__IO uint32_t*)(OTP_VERSION_BASE_ADDR + i * 4);
        count += __builtin_popcount(word);
    }
    return count;
}

void burn_version_bit(void)
{
    /* Find first zero bit, burn it */
    /* OTP burn: write 0xFFFFFFFF with one bit cleared */
    /* NOTE: OTP is permanent — cannot undo */
    HAL_FLASH_Unlock();
    /* H7: use HAL_FLASH_Program with FLASH_TYPEPROGRAM_FLASHWORD */
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
