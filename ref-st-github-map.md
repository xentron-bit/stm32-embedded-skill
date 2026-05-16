# ST Microelectronics GitHub Map

> **Amaç:** HAL/CMSIS/örnek koda hızlı erişim. Ezberden HAL adı çağırmak yerine
> önce buradan repo/yol bul, gerekirse WebFetch ile doğrula.
>
> **Kullanım:**
> 1. Sol sütundan konuyu/MCU'yu bul
> 2. Orta sütundaki repo'yu aç
> 3. Sağ sütundaki dosyaya git (path master branch'ten geçerli)
> 4. Şüpheliyse: `https://github.com/STMicroelectronics/<repo>/blob/main/<path>`

---

## 1. Family → Core Repos (en sık kullanılan)

Her aile için **üç** kanonik repo vardır:

| Family | HAL driver | CMSIS device (SVD + startup) | Cube (örnekler + middleware) |
|--------|------------|------------------------------|------------------------------|
| C0  | stm32c0xx-hal-driver  | cmsis-device-c0  | STM32CubeC0 |
| F0  | stm32f0xx-hal-driver  | cmsis-device-f0  | STM32CubeF0 |
| F1  | stm32f1xx-hal-driver  | cmsis-device-f1  | STM32CubeF1 |
| F2  | stm32f2xx-hal-driver  | cmsis-device-f2  | STM32CubeF2 |
| F3  | stm32f3xx-hal-driver  | cmsis-device-f3  | STM32CubeF3 |
| F4  | stm32f4xx-hal-driver  | cmsis-device-f4  | STM32CubeF4 |
| F7  | stm32f7xx-hal-driver  | cmsis-device-f7  | STM32CubeF7 |
| G0  | stm32g0xx-hal-driver  | cmsis-device-g0  | STM32CubeG0 |
| G4  | stm32g4xx-hal-driver  | cmsis-device-g4  | STM32CubeG4 |
| H5  | stm32h5xx-hal-driver  | cmsis-device-h5  | STM32CubeH5 |
| H7  | stm32h7xx-hal-driver  | cmsis-device-h7  | STM32CubeH7 |
| H7RS| stm32h7rsxx-hal-driver| cmsis-device-h7rs| STM32CubeH7RS |
| L0  | stm32l0xx-hal-driver  | cmsis-device-l0  | STM32CubeL0 |
| L1  | stm32l1xx-hal-driver  | cmsis-device-l1  | STM32CubeL1 |
| L4  | stm32l4xx-hal-driver  | cmsis-device-l4  | STM32CubeL4 |
| L5  | stm32l5xx-hal-driver  | cmsis-device-l5  | STM32CubeL5 |
| N6  | stm32n6xx-hal-driver  | cmsis-device-n6  | STM32CubeN6 |
| U0  | stm32u0xx-hal-driver  | cmsis-device-u0  | STM32CubeU0 |
| U5  | stm32u5xx-hal-driver  | cmsis-device-u5  | STM32CubeU5 |
| WB  | stm32wbxx-hal-driver  | cmsis-device-wb  | STM32CubeWB |
| WBA | stm32wbaxx-hal-driver | cmsis-device-wba | STM32CubeWBA |
| WL  | stm32wlxx-hal-driver  | cmsis-device-wl  | STM32CubeWL |

URL pattern: `https://github.com/STMicroelectronics/<repo>`

---

## 2. Peripheral → HAL File (any family)

Standart HAL dosya isimlendirmesi: `Src/stm32<f>xx_hal_<periph>.c` ve `Inc/stm32<f>xx_hal_<periph>.h`. Aşağıdaki tablo bir peripheral'in **en güncel HAL sürümünün** hangi ailede olduğunu söyler — başka aileler genelde aynı API'yi takip eder.

| Peripheral | Authoritative file (örnek aile) | Notlar |
|------------|--------------------------------|--------|
| ADC        | stm32h7xx-hal-driver / Src/stm32h7xx_hal_adc.c + adc_ex.c | H7 = en yeni multi-mode + cal |
| DMA (std)  | stm32h7xx-hal-driver / Src/stm32h7xx_hal_dma.c | H7'de DMAMUX + MDMA + BDMA ayrı |
| MDMA       | stm32h7xx-hal-driver / Src/stm32h7xx_hal_mdma.c | sadece H7 |
| BDMA       | stm32h7xx-hal-driver / Src/stm32h7xx_hal_bdma.c | sadece H7 (D3 domain) |
| GPDMA      | stm32h5xx-hal-driver / Src/stm32h5xx_hal_gpdma.c | yeni H5/U5/WBA |
| FDCAN      | stm32h7xx-hal-driver / Src/stm32h7xx_hal_fdcan.c | `AddMessageToTxFifoQ` (Q sonek!) |
| HRTIM      | stm32g4xx-hal-driver / Src/stm32g4xx_hal_hrtim.c | G4 daha güncel, H7 de aynı API |
| ETH (yeni) | stm32h7xx-hal-driver / Src/stm32h7xx_hal_eth.c | RxAllocateCallback + RxLinkCallback pattern |
| ETH (legacy)| stm32f4xx-hal-driver / Src/stm32f4xx_hal_eth.c | F4/F7 RxCpltCallback pattern |
| OTFDEC     | stm32h7xx-hal-driver / Src/stm32h7xx_hal_otfdec.c | sadece H7/L5/U5 |
| PKA        | stm32h7xx-hal-driver / Src/stm32h7xx_hal_pka.c | ECDSA/RSA, alanlar BIT cinsinden |
| RNG        | stm32h7xx-hal-driver / Src/stm32h7xx_hal_rng.c | |
| QUADSPI    | stm32f7xx-hal-driver / Src/stm32f7xx_hal_qspi.c | F4/F7/H7 legacy |
| OCTOSPI    | stm32h7xx-hal-driver / Src/stm32h7xx_hal_ospi.c | H7/L5/U5 yeni |
| DLYB       | stm32h7xx-hal-driver / Src/stm32h7xx_hal_dlyb.c | ayrı dosya — `HAL_DLYB_*` API |
| FMC SDRAM  | stm32h7xx-hal-driver / Src/stm32h7xx_hal_sdram.c | |
| SDMMC      | stm32h7xx-hal-driver / Src/stm32h7xx_hal_sd.c + sdmmc.c | |
| USB device | stm32-mw-usb-device (middleware repo) | Class/CDC, HID, MSC alt-klasörlerde |
| USB host   | stm32-mw-usb-host (middleware repo) | |
| LPTIM      | stm32h7xx-hal-driver / Src/stm32h7xx_hal_lptim.c | RTC backup wakeup için |
| PWR        | stm32h7xx-hal-driver / Src/stm32h7xx_hal_pwr_ex.c | VOS/STOP/Standby family-spesifik |
| GTZC       | stm32h5xx-hal-driver / Src/stm32h5xx_hal_gtzc.c | TrustZone-M peripheral |
| MPCBB      | stm32h5xx-hal-driver / Src/stm32h5xx_hal_gtzc.c | GTZC içinde |
| ICACHE     | stm32h5xx-hal-driver / Src/stm32h5xx_hal_icache.c | H5/U5 (H7'de yok) |

---

## 3. Konu Bazlı Örnekler (Cube package içinde)

Cube paketlerinin yapısı: `STM32CubeXX/Projects/<board>/<Examples|Applications|Demonstrations>/<topic>/`.

| Konu | Repo | Tipik path |
|------|------|-----------|
| FDCAN classic + FD | STM32CubeH7 | Projects/STM32H743I-EVAL/Examples/FDCAN/ |
| HRTIM dead-time PWM | STM32CubeG4 | Projects/STM32G474E-EVAL/Examples/HRTIM/ |
| OCTOSPI NOR + DLYB | STM32CubeH7 | Projects/NUCLEO-H743ZI/Examples/OSPI/ |
| OCTOSPI PSRAM | STM32CubeH7 | Projects/STM32H7B3I-EVAL/Examples/OSPI/OSPI_HyperRAM_MemoryMapped/ |
| Dual-bank flash + OTA | STM32CubeH7 | Projects/STM32H743I-EVAL/Applications/FLASH/FLASH_DualBoot/ |
| Ethernet + LwIP | STM32CubeH7 | Projects/STM32H743I-EVAL/Applications/LwIP/ |
| LwIP TCP echo server | STM32CubeH7 | Projects/STM32H743I-EVAL/Applications/LwIP/LwIP_TCP_Echo_Server/ |
| USB CDC device | STM32CubeH7 | Projects/STM32H743I-EVAL/Applications/USB_Device/CDC_Standalone/ |
| USB HID device | STM32CubeH7 | Projects/STM32H743I-EVAL/Applications/USB_Device/HID_Standalone/ |
| USB MSC host | STM32CubeH7 | Projects/STM32H743I-EVAL/Applications/USB_Host/MSC_Standalone/ |
| FreeRTOS port (CM7) | STM32CubeH7 | Middlewares/Third_Party/FreeRTOS/Source/portable/GCC/ARM_CM7/r0p1/ |
| FreeRTOS + TCP | STM32CubeH7 | Projects/STM32H743I-EVAL/Applications/LwIP/LwIP_HTTP_Server_Netconn_RTOS/ |
| FatFS + SDMMC | STM32CubeH7 | Projects/STM32H743I-EVAL/Applications/FatFs/FatFs_uSD/ |
| FatFS + USB MSC | STM32CubeH7 | Projects/STM32H743I-EVAL/Applications/FatFs/FatFs_USBDisk/ |
| AES + crypto | STM32CubeH7 | Projects/STM32H743I-EVAL/Examples/CRYP/ |
| PKA ECDSA verify | STM32CubeH7 | Projects/STM32H743I-EVAL/Examples/PKA/PKA_ECDSA_Verify/ |
| OTFDEC + OSPI XIP | STM32CubeH7 | Projects/STM32H7B3I-EVAL/Examples/OTFDEC/ |
| TrustZone-M (H5) | STM32CubeH5 | Projects/NUCLEO-H563ZI/Templates/Trustzone/ |
| Secure boot + FUOTA | x-cube-sbsfu | Projects/<board>/Applications/2_Images/ |
| LPTIM + Stop mode | STM32CubeL4 | Projects/NUCLEO-L476RG/Examples/LPTIM/LPTIM_PulseCounter/ |
| RTC wakeup | STM32CubeH7 | Projects/STM32H743I-EVAL/Examples/RTC/RTC_Wakeup/ |
| ADC + DMA | STM32CubeH7 | Projects/STM32H743I-EVAL/Examples/ADC/ADC_DMA_Transfer/ |
| Encoder mode | STM32CubeG4 | Projects/NUCLEO-G474RE/Examples/TIM/TIM_Encoder/ |

---

## 4. Middleware (X-CUBE ve Standalone)

ST'nin reuse-friendly middleware paketleri Cube'dan **ayrı** maintain edilir. Cube paketleri bunları submodule olarak alır; standalone versiyon her zaman daha güncel.

| Konu | Repo |
|------|------|
| USB device library (CDC/HID/MSC/DFU/HID) | stm32-mw-usb-device |
| USB host library (MSC/HID/CDC/Audio) | stm32-mw-usb-host |
| FatFS (R0.14b+ port) | stm32-mw-fatfs |
| LwIP integration | stm32-mw-lwip |
| FreeRTOS (ST'nin portu) | stm32-mw-freertos |
| OpenBootloader (IAP + DFU) | stm32-mw-openbootloader |
| BLE Manager (BlueNRG abstraction) | x-cube-blemgr |
| Bluetooth LE host stack (BlueNRG-LP/355) | bluenrg-x-ble-stack |
| Secure Boot + Secure FW Update | x-cube-sbsfu |
| Safety Library (IEC 61508 Class B) | x-cube-classb (kapalı, ama indirilebilir) / x-cube-stl |
| Sensors (MEMS) | x-cube-mems1 |
| AI inference (X-CUBE-AI runtime) | (commercial; HAL eklemez) |
| Crypto (TLS + COSE + PKCS) | mbedtls fork dahili Cube'da |
| Azure RTOS port (ThreadX/FileX/NetX/USBX) | x-cube-azrtos-<family> |

---

## 5. SVD Dosyaları (peripheral register decode)

SVD'ler **iki yerde** bulunur — biri CMSIS-device repo'su (sadece SVD), diğeri Keil DFP pack (Lab + IDE).

| Aile | CMSIS-device repo | Path |
|------|-------------------|------|
| H7 | cmsis-device-h7 | `Source/SVD/STM32H743x.svd` (örnek; aileye göre değişir) |
| H5 | cmsis-device-h5 | `Source/SVD/STM32H563x.svd` |
| G4 | cmsis-device-g4 | `Source/SVD/STM32G474xx.svd` |
| F4 | cmsis-device-f4 | `Source/SVD/STM32F407.svd` |
| U5 | cmsis-device-u5 | `Source/SVD/STM32U585xx.svd` |

`keil-mcp-server/tools/svd.py` SVD'yi Keil DFP'den alır; CMSIS-device repo'sundaki sürüm çoğu zaman daha güncel.

---

## 6. Tooling & Programmer

| İş | Repo |
|------|------|
| ST-LINK util / CubeProgrammer CLI | (closed source — st.com'dan indir) |
| OpenOCD STM32 desteği | (upstream OpenOCD) |
| stlink-tools (3rd party CLI) | stlink-org/stlink |
| stm32cubemonitor scripts | STM32CubeMonitor-* |

---

## 7. Errata + AN (App Notes)

Errata ST github'da yok — `www.st.com/resource/en/errata_sheet/<es-number>.pdf` adresinden çekilir (örn. ES0480 H7). Application Note'lar da PDF olarak `www.st.com/resource/en/application_note/<an-number>.pdf`.

| Konu | AN |
|------|----|
| HW CRC + flash | AN4187 |
| QSPI/OCTOSPI yüksek hız + DLYB | AN5050 |
| Dual-bank flash + OTA | AN4767 (F4/F7), AN4861 (H7) |
| Secure boot referans | AN5156 (TrustZone), AN5447 (SBSFU) |
| TrustZone-M tasarım | AN5347 |
| H7 voltaj scaling / overdrive | AN5312 |
| FDCAN bit-timing | AN5348 |

---

## 8. Runtime Lookup — `gh` CLI (en hızlı yol)

ST'de **753 public repo** var. Ezberden HAL adı söylemek yerine **canlı arama** kullan.

### A. HAL/makro/fonksiyon adı doğrulama — `gh search code`

```bash
# Bir HAL fonksiyonunun GERÇEKTEN var olduğunu ve hangi dosyada tanımlı
# olduğunu test et:
gh search code 'HAL_FDCAN_AddMessageToTxFifoQ' \
   --owner=STMicroelectronics --extension=c --limit=5 \
   --json repository,path | \
   jq -r '.[] | "\(.repository.nameWithOwner)  →  \(.path)"'

# Çıktı:
#   STMicroelectronics/stm32h7xx-hal-driver  →  Src/stm32h7xx_hal_fdcan.c
#   STMicroelectronics/stm32u5xx-hal-driver  →  Src/stm32u5xx_hal_fdcan.c
#   ...

# Yanlış ad → ZERO sonuç (catch mekanizması):
gh search code 'HAL_FDCAN_AddMessageToTxFifo(' \
   --owner=STMicroelectronics --extension=c --limit=3
# (boş çıktı → bu fonksiyon yok)
```

**Kural:** Tabloda olmayan HAL adı yazmadan önce `gh search code` ile teyit et.
Sıfır sonuç → ad yanlış / başka bir başkalaşım gerekli.

### B. Konuya göre repo bulma — `gh repo list` + filter

```bash
# ST'nin tüm repolarını JSON olarak listele (cache için):
gh repo list STMicroelectronics --limit 1000 \
   --json name,description,pushedAt > /tmp/st-repos.json

# "Bluetooth" konusunu içeren repoları bul:
jq -r '.[] | select(.description|test("[Bb]luetooth|BLE")) | .name' \
   /tmp/st-repos.json
```

Cache yenileme: `bin/refresh-st-repo-cache.sh` (repo kökünde).

### C. Symbol → yol araması (HAL kullanımı / örnek isteyince)

```bash
# Bir register makrosunun nasıl kullanıldığını gör:
gh search code 'SYSCFG_PWRCR_ODEN' --owner=STMicroelectronics --limit=10 \
   --json repository,path | jq -r '.[] | "\(.repository.nameWithOwner): \(.path)"'

# Bir tüm dosyayı çek (canonical view):
gh api /repos/STMicroelectronics/stm32h7xx-hal-driver/contents/Src/stm32h7xx_hal_fdcan.c \
   --jq '.content' | base64 -d | head -200
```

### D. Karar Akışı

```
Claude HAL adı kullanacak
        │
        ▼
Adı bu dokümanın §9'unda mı?  ──YES──► doğrudan kullan
        │NO
        ▼
gh search code '<ad>' --owner=STMicroelectronics --extension=c
        │
        ├── ≥1 hit  ──► ilk path'i kullan, gerekirse aç ve doğrula
        │
        └── 0 hit   ──► ad YANLIŞ.
                        Kullanıcıya MCU ailesini sor (HAL adı aile-spesifik olabilir)
                        veya benzer adlarla arama:
                        gh search code '<benzer-pattern>' ...
```

### E. WebFetch fallback (gh erişimi yoksa)

```
WebFetch: https://raw.githubusercontent.com/STMicroelectronics/<repo>/main/Src/stm32<f>xx_hal_<periph>.c
          (main → master fallback)
```

### Sık yanılan HAL isimleri (her zaman doğrula)

| Yanlış | Doğru | Repo |
|--------|-------|------|
| `HAL_FDCAN_AddMessageToTxFifo` | `HAL_FDCAN_AddMessageToTxFifoQ` | stm32h7xx-hal-driver |
| `FDCAN_CLOCK_DIVIDER1` | `FDCAN_CLOCK_DIV1` | stm32h7xx-hal-driver |
| `HAL_OSPI_DLYB_GetClockPeriod` | `HAL_DLYB_GetClockPeriod(DLYB_OCTOSPI1, ...)` | stm32h7xx-hal-driver/Src/stm32h7xx_hal_dlyb.c |
| `HAL_OSPI_DLYB_SetConfig` | `HAL_DLYB_SetConfig` | aynı |
| `HAL_ETH_GetMACAddr` | `heth.Init.MACAddr` veya `ETH->MACA0HR/LR` | stm32h7xx-hal-driver |
| `HAL_PWREx_EnterSTOP1Mode` (H7) | `HAL_PWREx_EnterSTOPMode(reg, entry, PWR_D1_DOMAIN)` | stm32h7xx-hal-driver |
| `__HAL_RCC_D3AMR_CLK_ENABLE` | `__HAL_RCC_<periph>_CLKAM_ENABLE` (her peripheral için ayrı) | stm32h7xx-hal-driver |
| `HRTIM_PRESCALERRATIO_MUL32` | `HRTIM_PRESCALERRATIO_DIV1` | stm32g4xx-hal-driver |
| `tinyusb/src/class/msc/msh_host.c` | `tinyusb/src/class/msc/msc_host.c` | hathach/tinyusb (3rd party) |

---

## 9. Şüpheli Aile-Tespit Noktaları

| Soru | Doğru cevap |
|------|--------------|
| H7 DTCM boyutu? | 128 KB (H743/H7A3/H730 dahil — sadece ITCM 64 KB) |
| H7 OTP adresi? | 0x08FFF000 (1 KB) — 0x1FFx_xxxx **DEĞİL** |
| H7 H7A3 vs H743 flash word? | H743 = 256-bit, H7A3 = 128-bit |
| H7 system bootloader? | H743/H750/H730: 0x1FF09800. H7B0/H7A3: 0x1FF00000 |
| F7 system bootloader? | 0x1FF00000 (0x1FFF0000 değil) |
| H5 system bootloader? | 0x0BF87000 |
| L5/U5 system bootloader? | 0x0BF90000 |
| H7 480 MHz nasıl? | VOS0 + SYSCFG_PWRCR.ODEN + ACTVOSRDY poll (rev V silikon) |
| H7A3 max freq? | 280 MHz (VOS0), NOT 480 MHz |
