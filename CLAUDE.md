# STM32 Embedded Development Skill

## Code Analysis — Graphify (Required)

Before reviewing any project, build the knowledge graph with Graphify:

```bash
# Install once
pip install git+https://github.com/safishamsi/graphify

# Per-project setup (writes CLAUDE.md hook + PreToolUse)
graphify claude install

# Build graph — use Claude Code slash command (uses Claude's API key)
/graphify .

# Query the graph
graphify query "who uses DMA buffer" --graph graphify-out/graph.json
graphify path "FuncA" "FuncB" --graph graphify-out/graph.json
```

The graph output is at `graphify-out/GRAPH_REPORT.md`. Read it before diving into files — saves 70x tokens on large projects.

## Skill Activation

```
/stm32-embedded-dev
```

Activates the 5-phase workflow: Analyze Constraints → Design Architecture → Implement Drivers → Optimize Resources → Test & Verify.

## Reference Files

| File | Topic |
|------|-------|
| `ref-qspi-octospi-highspeed.md` | QSPI/OCTOSPI high-speed issues, sample shift, DLYB, dummy cycles |
| `ref-communication-protocols.md` | I2C, SPI DMA, UART ring buffer, FDCAN |
| `ref-rtos-patterns.md` | FreeRTOS & RTX5 task, ISR, mutex, event patterns |
| `ref-keil-armclang.md` | Keil MDK / AC6: LTO traps, scatter, RTX5 pitfalls |
| `ref-compiler-hardening.md` | volatile, barriers, DMA cache, ISR reorder |
| `ref-fault-handlers.md` | HardFault decode, BusFault, reset cause |
| `ref-memory-optimization.md` | Compiler flags, memory pools, linker script |
| `ref-mpu-trustzone.md` | MPU stack guard, non-cacheable DMA, TrustZone |
