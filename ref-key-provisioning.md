# Secure Key Provisioning & ST HSM/RSS Integration

<!-- @trust-header v1 -->
> **Trust level for this reference**
>
> - **Design patterns, decision trees, supply-chain checklists, and ST procedure references** here are authoritative.
> - **Specific tool option flags and CLI examples** (STM32CubeProgrammer, STM32TrustedPackageCreator, SFI Creator) are illustrative of the v2.x toolchain at time of writing. Tool flags evolve; verify against the current ST UM for your CubeProgrammer version.
> - **Cryptographic algorithm choices** here track current ST-recommended defaults. For long-life programs, layer crypto-agility (see [ref-secure-boot.md](ref-secure-boot.md) §"Anti-Rollback") on top.
> - **HSM / SFI / RSS API surface** changes with ST revision packs (ST33 HSM cards, X-CUBE-SBSFU, X-CUBE-CRYPTOLIB). Confirm via `gh search code --owner=STMicroelectronics` before copy-pasting symbol names.

## Why this matters

Untrusted manufacturing — contract assemblers, JTAG-accessible programmers, and
shared production lines — are the realistic threat model for OEM firmware
deployment. Hard-coded keys, plaintext bootloaders, and unprotected SWD
interfaces leave product-line keys recoverable by anyone with physical access
to one device. Three orthogonal mechanisms close this gap:

| Mechanism | Protects against | ST tool / IP |
|-----------|------------------|--------------|
| **SFI (Secure Firmware Install)** | Plaintext firmware leaking at contract manufacturer | STM32TrustedPackageCreator + STM32CubeProgrammer SFI option |
| **HSM provisioning** | Master-key exposure on the programmer host | ST33-based HSM card (SMI/HSMv2 family) |
| **RSS (Root Security Services, H5/U5)** | Per-device key derivation + life-cycle state | On-chip immutable ROM service called via SVC/SMI |

This file documents the **integration patterns** for these three. For the
underlying option bytes, RDP transitions, and signed-image format, see
[ref-secure-boot.md](ref-secure-boot.md).

## Lifecycle States — the ground truth for any provisioning step

Provisioning is always a transition between two well-defined lifecycle states.
The transitions are one-way (in the secure direction).

```
                ┌───────────────────────────────────────┐
                │            ST Factory                 │
                │   Device leaves: RDP=0, life=OPEN     │
                └────────────────┬──────────────────────┘
                                 │
                    OEM programming station (SFI / HSM)
                                 │
                ┌────────────────▼──────────────────────┐
                │   Production: RDP=1, life=CLOSED      │
                │   Optional: HDP zones locked          │
                │   Optional: BOOT_LOCK = 1             │
                └────────────────┬──────────────────────┘
                                 │
                    Field deploy (no further auth needed)
                                 │
                ┌────────────────▼──────────────────────┐
                │   Field: RDP=1, life=LOCKED           │
                │   Debug: only via DBGAUTH (M33) or    │
                │          full mass-erase (RDP=0 path) │
                └───────────────────────────────────────┘
```

**Critical:** `RDP=2` is **irreversible** on most STM32 parts (H7/F7/F4/L4/G4).
On STM32H5/U5/WB/WL, the lifecycle is **OEM-1 → OEM-2 → CLOSED → LOCKED** with
RSS-managed transitions — see [ST AN5054](https://www.st.com/resource/en/application_note/an5054-secure-firmware-install-sfi-overview-stmicroelectronics.pdf)
for the canonical state diagram.

## Pattern 1 — SFI (Secure Firmware Install)

**When to use:** any time the firmware image leaves the OEM perimeter
(contract assembler, programming-house, automated production line).

**Threat addressed:** the contract manufacturer can see the file they program
into devices. Without SFI, that file IS the firmware. With SFI, it's an
opaque encrypted blob keyed to your OEM master key, which lives **only** in
the HSM card connected to their programmer.

### Build-side procedure (OEM, secure environment)

```bash
# 1. Generate OEM master key pair (one-time per product line)
#    Store private key in HSM. Public key gets baked into device.
STM32TrustedPackageCreator -keygen -alg ECDSAP256 \
    -outpub oem_pub.pem -outpriv oem_priv.p12

# 2. Generate per-product AES-256 firmware encryption key (FEK)
#    OEM Key Wrapping Key (OEM-KWK) provisioned to device during SFI install
#    wraps the FEK. So firmware is encrypted ONCE, can be installed N times.
STM32TrustedPackageCreator -genfek -out fek.bin

# 3. Create SFI package: firmware.bin + FEK + metadata, all signed
STM32TrustedPackageCreator -sfi \
    -bin firmware.bin@0x08000000 \
    -fek fek.bin \
    -nonce nonce.bin \
    -hash SHA256 \
    -privkey oem_priv.p12 \
    -out package.sfi

# Output: package.sfi — opaque, useless without the device's installed OEM-KWK
```

### Programming-station-side procedure (contract manufacturer)

```bash
# Programming station has the SFI package + HSM card with OEM keys.
# Station operator never sees firmware contents — only encrypted blob.
STM32_Programmer_CLI \
    -c port=SWD freq=4000 reset=HWrst \
    -sfi package.sfi hsm=1                 # hsm=1 → use ST33 HSM card
# CubeProgrammer talks SCP03 to the HSM, gets unwrapping material,
# writes encrypted blob to device, device-side RSS or bootloader decrypts.
```

### Device-side decryption (varies by family)

| Family | Decryption mechanism |
|--------|---------------------|
| H7 (any) | ST-provided **SBSFU** bootloader (X-CUBE-SBSFU) → uses on-chip AES via CRYPTO peripheral + RDP-locked OBKey storage |
| H5 / U5 | **RSS Install Service** (immutable ROM) — call via SVC from your OEMiROT bootloader; key material lives in HUK-derived region |
| L4 / G4 | SBSFU bootloader with optional STSAFE-A secure element |
| F4 / F7 | SBSFU bootloader (CRYPTO peripheral, less robust life-cycle than H5/U5) |

**The HSM card never leaves the programming station; the OEM private key
never leaves the HSM. Worst case if the programming station is compromised:
attacker can program more devices that nobody buys.**

## Pattern 2 — ST33 HSM Provisioning

**ST33 HSM card** = USB-connected secure element that stores OEM keys and
performs SCP03 with CubeProgrammer. Used by STM32TrustedPackageCreator and
STM32CubeProgrammer in `hsm=1` mode.

### Key hierarchy stored on HSM

```
HSM-CARD (per OEM product line)
├── OEM-KMK   (Key Master Key, ECDSA P-256)   — root of trust on HSM
├── OEM-KWK   (Key Wrapping Key, AES-256)     — wraps the FEK
├── OEM-AUTH  (Static Symmetric Key for SCP03)— authenticates HSM to CubeProgrammer
└── Counter / Slot quota                       — N installs remaining per slot
```

### Provisioning workflow (one-time, secure facility)

```
STEP 1: HSM-PERSO (HSM Personalization)
  - Tool:  ST33KeysProvisioner (ST internal) OR  Provisioning Service Package
  - Input: empty ST33 card
  - Output: HSM card with OEM-KMK + OEM-KWK + OEM-AUTH + N install slots
  - Location: OEM secure facility, signed-in personnel only

STEP 2: HSM-DISTRIBUTE
  - Ship HSM card via dual-control courier to CM
  - CM operator: connect HSM to programming station, enter PIN

STEP 3: HSM-CONSUME
  - Each device programmed decrements slot counter on HSM
  - When counter = 0: card is depleted, return to OEM for re-personalization
```

**Why slot counters matter:** if a single HSM card is compromised at the CM,
the attacker can only program until the slot counter exhausts. Quantum of
loss = remaining slot count × device cost. Size slot count to the contract
batch, not "10000 forever".

## Pattern 3 — RSS (Root Security Services) on H5 / U5 / WBA

H5 (M33), U5 (M33), and WBA (M33) parts ship with an **immutable ROM service
layer** called RSS. It runs in Secure mode under TrustZone, owns the master
key (HUK — Hardware Unique Key), and exposes a small SVC-based API:

| RSS service | What it does |
|-------------|--------------|
| `OEMiROT_Install` | First-stage install — writes OEM iROT (immutable Root of Trust) to dedicated OBK area |
| `OEMuROT_Install` | Updateable Root of Trust install (signed by OEMiROT) |
| `OBK_Provision` | Burn OEM keys (OEM-DHUK seeds, OBK1/2/3 keys) into one-time-programmable OBK area |
| `Set_LifeCycle_State` | Transition OEM-1 → OEM-2 → CLOSED → LOCKED (one-way per direction) |
| `HUK_Derive` | Application calls this in Secure context to derive per-device keys from HUK without ever seeing HUK itself |

### Typical OEM flow on H5/U5

```
ST factory:  life-cycle = OPEN, RSS active, no OEM material
   │
   ▼
OEM-Step-A: STM32CubeProgrammer + OBKey provisioning script
   - life-cycle = OEM-1
   - Program OEMiROT (signed by ST root key)
   - Burn OBK1 = OEM signing public key (ECDSA P-256)
   - Burn OBK2 = encryption pre-derived key
   │
   ▼
OEM-Step-B: SFI install of application firmware
   - life-cycle = OEM-2
   - OEMuROT verifies & decrypts firmware, writes to flash
   - RDP = 1, BOOT_LOCK = 1
   │
   ▼
OEM-Step-C: Lock for field deployment
   - life-cycle = CLOSED
   - SWD/JTAG = DBGAUTH-only (see ref-secure-debug.md)
   - HDP zones latch on first boot in production
   │
   ▼
Field:  life-cycle = LOCKED (after first boot)
   - All OBK areas read-blocked from non-secure
   - HUK only addressable via HUK_Derive SVC
```

### Application code — deriving a per-device key (Secure context)

```c
#include "stm32u5xx_hal.h"
#include "rss_api.h"   /* provided by X-CUBE-SBSFU for U5 */

/* Derive a 32-byte per-device key from HUK + label.
 * HUK never leaves RSS; only the derived key is returned. */
uint8_t per_device_key[32];
const char *label = "MQTT-CLIENT-CERT-2026";

RSS_Status_t st = RSS_HUK_Derive(
    (const uint8_t *)label, strlen(label),
    per_device_key, sizeof(per_device_key));

if (st != RSS_OK) {
    /* HUK access blocked — life-cycle not in CLOSED, or non-secure context */
    Error_Handler();
}

/* Use per_device_key for whatever per-device crypto. After use:
 * mlock + memset(per_device_key, 0, 32); — do not leave in stack frame. */
```

## Supply-Chain Threat Checklist

Run this before signing off on a production-line key strategy:

| Threat | Mitigation | Verified by |
|--------|-----------|-------------|
| Plaintext firmware on programmer host | SFI package + HSM card | Inspect CM workstation: no `.bin` artifacts post-build, only `.sfi` |
| Master OEM private key on programmer host | Keys live only on ST33 HSM | `STM32TrustedPackageCreator -info hsm` shows slots, never raw key |
| JTAG/SWD readback in field | RDP=1 + DBGAUTH (M33) / RDP=2 (legacy) | Field unit: attempt unauthorized `STM32_Programmer_CLI -ob displ` → expected to fail |
| Programmer station impersonation | SCP03 channel HSM ↔ programmer | Use ST-signed programmer build, verify signature before deploy |
| Per-device key recovery via side-channel | Use RSS-derived key, masking (see [ref-sca-countermeasures.md](ref-sca-countermeasures.md) Phase 3) | DPA assessment on production silicon |
| Replay of an old signed firmware | Anti-rollback monotonic counter | See [ref-secure-boot.md](ref-secure-boot.md) §"Anti-Rollback" |
| Compromised CM operator | Slot-counter on HSM; dual control on card issuance | Slot count ≤ batch size |
| OBK area not actually written | Post-program verify via `STM32_Programmer_CLI -obk read` | Production line test step |
| Life-cycle stuck in OEM-2 (not CLOSED) | Production-line "lock" step at EOL | See [ref-eol-test-framework.md](ref-eol-test-framework.md) §"Life-cycle lock test" |
| Programmer cache leaks SFI material | Per-job HSM session, no log persist | Audit programmer disk after run |

## Canonical ST documents

| Doc | Coverage | URL |
|-----|----------|-----|
| AN5054 | SFI overview, supported families, package format | https://www.st.com/resource/en/application_note/an5054-secure-firmware-install-sfi-overview-stmicroelectronics.pdf |
| AN5156 | SBSFU architecture, key storage, decryption flow | https://www.st.com/resource/en/application_note/an5156-introduction-to-stm32-microcontrollers-security-stmicroelectronics.pdf |
| AN5447 | STM32H5 OEMiROT + RSS programming, OBKey layout | https://www.st.com/resource/en/application_note/an5447-overview-of-bootloader-related-features-on-stm32h5-microcontrollers-stmicroelectronics.pdf |
| UM2237 | STM32CubeProgrammer user manual — SFI / HSM CLI flags | https://www.st.com/resource/en/user_manual/um2237-stm32cubeprogrammer-software-description-stmicroelectronics.pdf |
| UM2238 | STM32TrustedPackageCreator — SFI package creation tool | https://www.st.com/resource/en/user_manual/um2238-stm32-trusted-package-creator-tool-software-description-stmicroelectronics.pdf |
| AN5156 §3.x | OEM key provisioning life-cycle states (life-cycle table) | same as above |

## Common provisioning mistakes

1. **Burning OBK area with debug-build keys.** Once OBK is written it's
   read-blocked from non-secure on next reset. If you wrote a debug key,
   the production unit ships with a debug key. Always re-verify OBK
   content before life-cycle CLOSED.

2. **Forgetting `BOOT_LOCK = 1`.** Without BOOT_LOCK, an attacker with SWD
   can change `BOOT_ADD0` to point at SRAM, dump firmware via DMA.

3. **`RDP = 1` without `WRP`.** RDP=1 prevents read but not erase + reprogram.
   An attacker can mass-erase, write a key-dumping firmware, run it. WRP
   on the OBK/iROT regions prevents this.

4. **HSM card stored at CM site between batches.** Defeats the slot-counter
   logic. Card should travel with the batch, return to OEM after.

5. **Reusing one HSM card across multiple product lines.** Compromise of one
   product compromises all. One HSM card = one product line minimum.

6. **No EOL test verifying RDP / life-cycle / OBK state.** Production line
   silently producing devices in OEM-1 state with debug accessible.
   See [ref-eol-test-framework.md](ref-eol-test-framework.md) for the
   verify-before-ship checklist.

## When NOT to use SFI/HSM

- Engineering prototypes (10-100 units): manual STM32CubeProgrammer
  programming with RDP=1 + WRP is acceptable; HSM overhead not justified.
- Open-source / educational devices: keys aren't proprietary, just sign
  the firmware (ref-secure-boot.md §"Firmware Image Signing").
- Internal-use industrial devices behind your physical perimeter: RDP=1
  enough; SFI overkill.

**Use SFI/HSM when:** product ships to customers, contract assembly, and
firmware-IP value > HSM-card cost (~€1000/card + ST licensing).

## Cross-references

- BL-side decryption flow → [ref-secure-boot.md](ref-secure-boot.md) §"Production Programming Flow"
- BL→App signature chain after install → [ref-secure-boot.md](ref-secure-boot.md) §"BL→App Runtime Chain Verification"
- TrustZone Secure boundary for U5/H5/WBA RSS callers → [ref-trustzone.md](ref-trustzone.md)
- Debug lockout post-provisioning → [ref-secure-debug.md](ref-secure-debug.md)
- EOL verification of provisioned state → [ref-eol-test-framework.md](ref-eol-test-framework.md)
