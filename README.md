# STM32 Embedded Development — Claude Skill

A comprehensive Claude Code skill for STM32 embedded systems development covering bare-metal, RTOS (Keil RTX5/CMSIS-RTOS2, FreeRTOS), XIP debug, industrial best practices, and automated code review.

## Contents

| File | Description |
|------|-------------|
| [SKILL.md](SKILL.md) | Main skill — 5-phase workflow, RTOS patterns, peripheral drivers, code review checklist |
| [stm32-families.md](stm32-families.md) | Complete STM32 family catalog with HAL repos, CMSIS device links, Keil RTX5 config |
| [ref-communication-protocols.md](ref-communication-protocols.md) | I2C, SPI DMA, UART ring buffer, FDCAN patterns |
| [ref-rtos-patterns.md](ref-rtos-patterns.md) | FreeRTOS periodic tasks, ISR→task, mutex, event groups, stack monitoring |
| [ref-power-optimization.md](ref-power-optimization.md) | Sleep/Stop modes, dynamic clock scaling, peripheral gating, battery-adaptive |
| [ref-memory-optimization.md](ref-memory-optimization.md) | Compiler flags, memory pools, packed structs, ring buffer, linker script |

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
