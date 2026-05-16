# Secure Debug — JTAG/SWD Lockdown & Authenticated Re-Open

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, RDP-state decision tree, and DBGAUTH protocol description** here are authoritative.
> - **Register field names / option-byte addresses** track the current RM/datasheet at time of writing; verify against your part's RM if relying on bit positions in code.
> - **DBGAUTH (M33 parts: H5, U5, WBA, L5)** is family-specific; the OEMuROT debug handler implementation differs between families. Reference the part's `STM32U5xx_RootSecurityServices` examples in STM32Cube before customizing.
> - **`gh search code --owner=STMicroelectronics` for canonical** OEMuROT debug handler symbols when in doubt.

## The debug-vs-security tradeoff

| Debug access | Field-recovery story | Attacker recovery story |
|--------------|---------------------|------------------------|
| **Always open** (RDP=0) | Trivial | Trivial — game over |
| **Locked, no recovery** (RDP=2 on legacy parts) | Mass-erase only | Cannot recover |
| **Locked + auth re-open** (DBGAUTH on M33 parts) | Authorized engineer with OEM key | Strong cryptographic gate |

This file is about getting to row 3 on M33 parts (H5, U5, WBA, L5) and how to
approximate it on legacy parts (H7, F7, F4, L4, G4) where DBGAUTH is not
available.

## Approach 1 — Legacy parts (H7, F7, F4, L4, G4)

These parts have **no on-chip debug authentication**. The choice is binary:

```
                ┌─ RDP = 0 ─ open SWD/JTAG, full readback
                │
   Option Bytes ─ RDP = 1 ─ no readback, but mass-erase resets to RDP=0
                │
                └─ RDP = 2 ─ irreversible, SWD/JTAG dead forever
```

### Recommended production setting for legacy parts

```
RDP = 1                          // readback blocked, debug attach blocked
WRP   = locked Bank1[0..N]       // bootloader region write-protected
PCROP = locked Bank1[X..Y]       // crypto-keys region read+exec-only
BOOT_LOCK = 1                    // BOOT_ADD0 cannot be changed via SWD
nDBOOT0 = 0                      // BOOT0 ignored, hard-wired to internal flash
```

**Why not RDP=2:** field-return diagnostics impossible. Defective units
cannot be analyzed. Use RDP=1 + WRP + PCROP — strong enough for most
threat models, recoverable for field-failure analysis.

### Recovery path (legacy)

When you must debug a returned field unit:

1. Document chain-of-custody (the unit leaves customer site, enters OEM lab)
2. `STM32_Programmer_CLI -ob RDP=AA`  → device mass-erases, RDP→0
3. Flash is gone — debug a **fresh-programmed** binary on this hardware
4. **The original failing firmware state is lost.** This is the cost.

Mitigation: design field telemetry (RAM dump on fault, persistent error log in
backup SRAM/RTC backup registers) so post-mortem doesn't require the original
flash. See [ref-fault-handlers.md](ref-fault-handlers.md) §"Fault Log Readout
on Boot".

### Option-byte programming sequence (one-shot at production)

```bash
# Production tool, after firmware load
STM32_Programmer_CLI \
    -c port=SWD freq=4000 \
    -ob WRP1A_STRT=0 WRP1A_END=15 \      # Bank1 sectors 0-15 write-protected
    -ob PCROP1A_STRT=128 PCROP1A_END=159 \ # crypto region read+exec-only
    -ob nBOOT_SEL=1 nBOOT0=0 \           # BOOT0 ignored
    -ob BOOT_LOCK=1 \                    # boot config locked
    -ob RDP=BB                           # RDP level 1 (LAST — must be last)
```

**Critical order:** RDP=1 LAST. Once RDP=1, the option-byte write protocol
itself requires SWD which is about to lock down. Some option bytes are
unwritable in RDP=1 — set them first.

## Approach 2 — M33 parts (H5, U5, WBA, L5) — DBGAUTH

M33 parts implement **Debug Authentication (DBGAUTH)** — a challenge-response
protocol over SWD that re-opens debug access without erasing flash. The OEM
holds a private key; field debug requires the corresponding signed permission
slip.

### DBGAUTH protocol — high level

```
Debugger                                Device (RDP=1, DBGAUTH-capable)
   │                                        │
   │  1. SWD connect → DAP query            │
   │ ─────────────────────────────────────► │
   │                                        │  (1a) Bootloader/RSS detects
   │                                        │       unauthorized DAP access
   │                                        │
   │  2. CHALLENGE (16-byte nonce)          │
   │ ◄───────────────────────────────────── │
   │                                        │
   │  3. Build permission slip:             │
   │     - nonce                            │
   │     - permitted operations             │
   │       (e.g. SoCDBG, DBG, ERASE)        │
   │     - permission_mask                  │
   │     - sign(SLIP, OEM-DBG-private)      │
   │                                        │
   │  4. AUTHENTICATE(slip)                 │
   │ ─────────────────────────────────────► │
   │                                        │  (4a) Verify signature with
   │                                        │       OBK-stored OEM-DBG public
   │                                        │  (4b) Check permission_mask
   │                                        │       allowed in current
   │                                        │       lifecycle state
   │                                        │
   │  5. ACK / NAK                          │
   │ ◄───────────────────────────────────── │
   │                                        │
   │  6. DAP access granted within mask     │
```

### Permission mask granularity (typical for U5)

| Permission bit | Allows |
|---------------|--------|
| `SoCDBG` | Full Secure + Non-Secure debug (highest) |
| `NSDBG`  | Non-Secure debug only — Secure region remains opaque |
| `ERASE`  | Mass erase via DAP (does not enable SWD halt/step) |
| `INVASIVE_DEBUG_NS` | Halt + step in Non-Secure |
| `INVASIVE_DEBUG_S`  | Halt + step in Secure |
| `NON_INVASIVE_DEBUG_NS/S` | Trace / ITM only |

**OEM strategy:** issue tiered permission slips. Tier-1 (RMA technician):
ERASE + NSDBG. Tier-2 (firmware engineer, signed NDA): SoCDBG + INVASIVE_S.
Different keys, different revocation lists.

### Code path — device side (OEMuROT in Secure context)

```c
/* Simplified — actual OEMuROT does this in the X-CUBE-SBSFU SecureBoot path */
#include "rss_api.h"
#include "psa/crypto.h"

void OEMuROT_DebugAuth_Handler(uint8_t *slip, size_t slip_len)
{
    DAP_Slip_t parsed;
    if (DAP_Slip_Parse(slip, slip_len, &parsed) != 0)
        return;  /* malformed */

    /* 1. Verify slip signature against OBK-stored OEM-DBG public key */
    psa_status_t st = psa_verify_message(
        OBK_KEY_ID_OEM_DBG_PUB,
        PSA_ALG_ECDSA(PSA_ALG_SHA_256),
        parsed.payload, parsed.payload_len,
        parsed.signature, parsed.signature_len);
    if (st != PSA_SUCCESS) return;

    /* 2. Verify nonce matches the challenge we issued */
    if (memcmp(parsed.nonce, g_last_challenge, 16) != 0) return;

    /* 3. Verify lifecycle state allows requested permissions */
    if (!LifeCycle_PermitsMask(parsed.perm_mask)) return;

    /* 4. Apply permissions to DBGMCU + SBS_DBGCR + SAU registers */
    DBGMCU_ApplyPermissions(parsed.perm_mask);

    /* Debugger now has DAP access within parsed.perm_mask. */
}
```

### OEM-side — issuing a permission slip

```python
# Engineer's signing workstation (HSM-backed)
from stm32_dbgauth import build_slip, sign_slip

nonce = receive_nonce_from_target()             # 16 bytes from CubeProgrammer
mask  = 0x0F                                    # ERASE | NSDBG | NS_INV | S_INV
slip  = build_slip(
    nonce=nonce,
    permission_mask=mask,
    valid_until_unix=1735689600,                # expire end-of-year
    target_uid=read_uid_from_target(),          # bind to one device
)
signed = sign_slip(slip, hsm_slot="OEM-DBG-priv")

# Hand signed back to CubeProgrammer
STM32_Programmer_CLI \
    -c port=SWD \
    -dbgauth perm=$mask slip=signed.bin
```

**`target_uid` binding** — slip valid for ONE device. Prevents the field
service tool from being copy-pasted to unlock other units. Strongly recommended.

## HDP (Hide Protection) — bootloader-side flash region hiding

On STM32H5/U5/L5/WBA, **HDP** locks a flash region so that AFTER its
configured boundary instruction executes, the region becomes unreadable
even from Secure code until the next reset.

```c
/* Typical bootloader sequence */

/* 1. Bootloader (in HDP region) verifies app signature */
if (app_signature_valid(&app_image) != 0) reboot();

/* 2. Latch HDP — bootloader code now unreadable for the rest of this boot */
FLASH->SECHDPCR |= FLASH_SECHDPCR_HDP1_ACCDIS;
__DSB();

/* 3. Jump to application */
app_entry();
```

**Why this matters:** even an attacker who later compromises the application
cannot read the bootloader code to extract OEM signing keys, because HDP
latched on the bootloader→app handoff. Only a fresh reset can re-open
the HDP region, and the bootloader latches it again before app runs.

**Use HDP for:** OEM signing public key storage, anti-rollback counters,
critical decrypt keys that the app does not need to re-read mid-runtime.

## DBGMCU register — debug-during-low-power

Independent of RDP/DBGAUTH, the **DBGMCU register** controls whether the
debugger remains attached during low-power modes (Stop, Standby).

```c
/* Keep debug session alive during STOP/STANDBY — DEV ONLY, never in production */
#ifdef DEBUG_BUILD
DBGMCU->CR |= DBGMCU_CR_DBG_STOP | DBGMCU_CR_DBG_STANDBY | DBGMCU_CR_DBG_SLEEP;
DBGMCU->APB1FZR1 |= DBGMCU_APB1FZR1_DBG_IWDG_STOP;  /* IWDG paused at halt */
#endif

/* Production build: leave all DBGMCU bits at reset value (0) */
```

**Critical:** ship production with `DBGMCU_CR = 0`. A device that survives
STANDBY with debug attached leaks an active DAP into low-power state —
an attacker can probe SRAM through DAP while you think the device is asleep.

## Secure Debug Decision Tree

```
START — Will SWD/JTAG access be needed in the field?
   │
   ├── NO (fixed industrial control, sealed)
   │     │
   │     └── RDP=2 if available + nDBOOT0 + BOOT_LOCK
   │         (Strongest — irreversible)
   │
   └── YES (RMA, FOTA recovery, field diagnostics)
         │
         ├── Part is M33-family (H5/U5/WBA/L5)?
         │     │
         │     ├── YES → OEMuROT + DBGAUTH + HDP
         │     │         Strongest revocable strategy
         │     │
         │     └── NO  → RDP=1 + WRP + PCROP + DBGMCU=0
         │               Acceptable for non-safety-critical
         │
         └── Field FOTA recovery via UART/CAN bootloader, not SWD?
               │
               └── Pre-shared key UART/CAN authenticated bootloader
                   (no SWD-side access at all; recovery via app channel)
                   See ref-iap-ota.md
```

## Common secure-debug mistakes

1. **`RDP=2` on legacy parts before validating field-return process.**
   The first time you need to debug a returned unit, you'll wish for RDP=1.

2. **`RDP=1` without `WRP`.** Attacker mass-erases (RDP→0) and writes a
   key-dumping firmware. Read protection is read-only; you also need
   write protection.

3. **`DBGMCU` bits set in production builds.** A surprisingly common leak.
   Search `#ifdef DEBUG` blocks before signing the release image.

4. **Single OEM-DBG key for everyone.** Slip-signing key compromise = all
   fielded devices lose debug-auth gate. Use **per-product-line** keys
   minimum, ideally **per-engineer** keys with revocation list in OBK.

5. **No nonce binding / no UID binding on permission slip.** Slip becomes
   a master key once captured.

6. **HDP not latched before jumping to app.** Bootloader code remains
   readable from app, app vulnerability → key extraction.

7. **Forgetting Secure World debug in TrustZone parts.** SAU_RNR + SBS_DBGCR
   need to be configured to deny S-world debug specifically; `NSDBG=allow`
   does NOT imply `SDBG=deny`, they're separate bits.

## Canonical ST + ARM references

| Doc | Coverage | URL |
|-----|----------|-----|
| AN5347 | TrustZone-M + GTZC + Secure debug on H5/U5/L5/WBA | https://www.st.com/resource/en/application_note/an5347-arm-trustzone-features-for-stm32l5-and-stm32u5-series-stmicroelectronics.pdf |
| AN5439 | STM32H5 Root Security Services (RSS) — DBGAUTH service surface | https://www.st.com/resource/en/application_note/an5439-overview-of-bootloader-related-features-on-stm32h5-microcontrollers-stmicroelectronics.pdf |
| UM2237 | STM32CubeProgrammer DBGAUTH CLI flags | https://www.st.com/resource/en/user_manual/um2237-stm32cubeprogrammer-software-description-stmicroelectronics.pdf |
| ARMv8-M ARM §B11 | Debug authentication architecture (DAPEN, SPIDEN, etc.) | ARM DDI 0553 |
| ARM PSA Authenticated Debug Access Control (ADAC) | Standard protocol that ST DBGAUTH derives from | https://developer.arm.com/documentation/den0101/latest/ |

## Cross-references

- Option byte programming details → [ref-secure-boot.md](ref-secure-boot.md) §"Option Byte Programming"
- TrustZone setup that DBGAUTH operates within → [ref-trustzone.md](ref-trustzone.md)
- HSM key storage for OEM-DBG-private → [ref-key-provisioning.md](ref-key-provisioning.md) §"ST33 HSM Provisioning"
- Production-line verification that debug actually locked → [ref-eol-test-framework.md](ref-eol-test-framework.md)
