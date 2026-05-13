# STM32 Embedded Development Skill

## Code Analysis — Graphify (Automatic)

**Graph yoksa SKILL otomatik çalıştırır — manuel `/graphify .` gerekmez.**

Skill invoke edilince Claude şunu yapar:
1. `graphify-out/GRAPH_REPORT.md` var mı kontrol et
2. Yoksa → `Skill(skill="graphify", args="<proje-dizini>")` ile otomatik build et
3. Varsa → oku ve analize başla

```bash
# Sorgu (graph hazır olduktan sonra)
graphify query "who uses DMA buffer" --graph graphify-out/graph.json
graphify path "FuncA" "FuncB" --graph graphify-out/graph.json
```

Graph çıktısı: `graphify-out/GRAPH_REPORT.md` — God nodes, call chains, paylaşılan değişkenler.

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
