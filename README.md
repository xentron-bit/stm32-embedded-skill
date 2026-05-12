# STM32 Embedded Development — Claude Skill

A comprehensive Claude Code skill for STM32 embedded systems development covering bare-metal, RTOS (Keil RTX5/CMSIS-RTOS2, FreeRTOS), XIP debug, industrial best practices, and automated code review.

## Contents

| File | Description |
|------|-------------|
| [SKILL.md](SKILL.md) | Main skill — 5-phase workflow, RTOS patterns, peripheral drivers, code review checklist |
| [stm32-families.md](stm32-families.md) | Complete STM32 family catalog with HAL repos, CMSIS device links, Keil RTX5 config |
| **Drivers & Protocols** | |
| [ref-communication-protocols.md](ref-communication-protocols.md) | I2C, SPI DMA, UART ring buffer, FDCAN patterns |
| [ref-uds-iso14229.md](ref-uds-iso14229.md) | ISO 14229 UDS protocol: services, session management, NRC codes, STM32 FDCAN |
| [ref-j1939.md](ref-j1939.md) | SAE J1939 protocol: PGN structure, address claiming, transport protocol, STM32 FDCAN |
| [ref-modbus-rtu.md](ref-modbus-rtu.md) | Modbus RTU over UART/RS-485: frame format, CRC, master/slave state machines |
| [ref-usb-host-filesystem.md](ref-usb-host-filesystem.md) | USB Host (MSC), FatFS integration, SDMMC, common pitfalls |
| [ref-adc-timer.md](ref-adc-timer.md) | ADC (injected/regular/DMA), timer PWM, input capture, encoder patterns |
| **RTOS** | |
| [ref-rtos-patterns.md](ref-rtos-patterns.md) | FreeRTOS periodic tasks, ISR→task, mutex, event groups, stack monitoring |
| [ref-keil-armclang.md](ref-keil-armclang.md) | Keil MDK / AC6: LTO traps, scatter file, RTX5 pitfalls (13 categories), FDCAN mode, NVIC |
| **Memory & Optimization** | |
| [ref-memory-optimization.md](ref-memory-optimization.md) | Compiler flags, memory pools, packed structs, ring buffer, linker script, dynamic alloc guidance |
| [ref-power-optimization.md](ref-power-optimization.md) | Sleep/Stop modes, dynamic clock scaling, peripheral gating, battery-adaptive |
| **Safety & Hardening** | |
| [ref-compiler-hardening.md](ref-compiler-hardening.md) | Optimizer bug prevention: volatile, barriers, DMA cache size formula, ISR reorder, LTO |
| [ref-fault-handlers.md](ref-fault-handlers.md) | HardFault register dump, BusFault/MemManage decode, reset cause detection, noinit persist |
| [ref-mpu-trustzone.md](ref-mpu-trustzone.md) | MPU stack guard, null-pointer trap, non-cacheable DMA region, peripheral access control |
| [ref-trustzone.md](ref-trustzone.md) | TrustZone-M (STM32L5/U5/H5): SAU, GTZC, NSC, CMSE, secure boot chain |
| **System** | |
| [ref-boot-clock.md](ref-boot-clock.md) | Clock tree, PLL config, HSE/HSI, bootloader entry, option bytes |
| [ref-iap-ota.md](ref-iap-ota.md) | In-Application Programming, dual-bank OTA, bootloader design, CRC verify |
| **Low-level** | |
| [ref-arm-asm.md](ref-arm-asm.md) | Thumb-2 assembly: registers, AAPCS, LDREX/STREX, HardFault decode, startup code |
| **Code Quality** | |
| [ref-c-code-style.md](ref-c-code-style.md) | MaJerle C style, naming, types, memcpy safety, bounds checking, timeout patterns |

## Features

- **5-Phase Workflow**: Analyze Constraints → Design Architecture → Implement Drivers → Optimize Resources → Test & Verify
- **RTOS Support**: Keil RTX5/CMSIS-RTOS2 and FreeRTOS with static allocation patterns
- **Industrial Code Review**: 10-category checklist (ISR discipline, cache coherency, watchdog, FDCAN, etc.)
- **Compiler Optimization**: Pitfall detection (`volatile`, LTO ISR visibility, barriers, `printf` bloat)
- **XIP Debug**: SWD/JTAG via Keil MDK + STM32CubeIDE, SWO/ITM trace, DWT cycle counter
- **DMA Cache Safety**: M7 D-cache clean/invalidate patterns with 32-byte alignment
- **STM32 Family Coverage**: All 20+ families from C0 (M0+) to N6 (M55+NPU)

## Installation

```bash
# Copy to Claude skills directory
cp -r . ~/.claude/skills/stm32-embedded-dev
```

Then use the skill in Claude Code:
```
/stm32-embedded-dev
```

## Sources

- [STMicroelectronics GitHub](https://github.com/orgs/STMicroelectronics/repositories) — HAL drivers, CMSIS device packs
- [ARM CMSIS-RTX](https://github.com/ARM-software/CMSIS-RTX) — Keil RTX5 / CMSIS-RTOS2

## License

MIT
