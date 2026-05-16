# STM32 Embedded Development Skill — Project Notes

> **Canonical skill content lives in [SKILL.md](SKILL.md).** This file holds
> only project-specific overrides and post-graph follow-up rules.
> The full Reference Files table is in SKILL.md §"Reference Files" — do NOT
> duplicate it here.

## Skill Activation

```
/stm32-embedded-dev
```

Activates the 5-phase workflow: Analyze Constraints → Design Architecture →
Implement Drivers → Optimize Resources → Test & Verify. See
[SKILL.md](SKILL.md) §"Operating Modes" for the response-shape rules.

## Code Analysis — Graphify Follow-Up

The graphify auto-run procedure is in [SKILL.md](SKILL.md) §"Step 1 —
Generate the Code Map". It only runs when scope is ≥3 `.c` files; single-file
snippets skip the graph (no install required, no time wasted).

After a graph report is presented to the user, Claude should:

1. **Pick the most interesting question** from the Suggested Questions list —
   prefer the one crossing the most community boundaries or bridging the most
   surprising node.

2. **Surface it and ask permission:**
   > "En ilginç soru: **[question]**. Takip etmemi ister misin? / Want me to follow up?"

3. **If the user agrees — drive it with `graphify query`:**
   ```bash
   graphify query "[question]" --graph graphify-out/graph.json
   ```
   - Verify BFS-returned nodes/edges against the actual source (Read tool)
   - Walk the call chain step-by-step: which node → which file → which line
   - Merge findings with prior manual review notes
   - Close each follow-up with a natural next step: "Bu X'e bağlanıyor —
     daha derine inmek ister misin?"

4. **If the user declines** — close the graph and continue normal analysis.

**Principle:** Graph = map, Claude = guide. Analysis is an interactive
exploration, not a one-shot report.

## Errata Cross-Check (mandatory before every review)

When MCU is detected, **before** opening any `.c` file:

1. Determine MCU family from part number → [stm32-families.md](stm32-families.md)
2. Look up the relevant ST errata sheet:

   | Family | Errata sheet |
   |--------|--------------|
   | STM32H743 / H753 / H750 | ES0480 |
   | STM32H723 / H725 / **H730** / H733 / H735 (Value line) | **ES0491** |
   | STM32H7B0 / H7A3 / H7B3 | ES0392 |
   | STM32H5 (H563/H573) | ES0584 |
   | STM32F7 | ES0334 |
   | STM32F4 | ES0182 |
   | STM32G4 (G431/G441/G473/G474/G483/G484/G491/G4A1) | ES0430 |
   | STM32G0 | ES0418 |
   | STM32L4 | ES0335 |
   | STM32L4+ (L4R/L4S) | ES0393 |
   | STM32U5 | ES0499 |
   | STM32WB | ES0394 |
   | STM32WL | ES0500 |

3. Cross-check [ref-stm32-errata.md](ref-stm32-errata.md) for known issues
4. If a critical erratum applies, tag the finding: `errata: [ES0480 §2.x.y]`
5. If behavior is suspicious and the on-disk errata doesn't cover it, fetch
   the ST errata PDF from the web and verify.

**Principle:** Code that looks wrong may be a hardware/driver-level
workaround. Every review evaluates code logic *and* silicon constraints.

## DoIP References (for future use)

- Keil MDK Network middleware: https://www.keil.com/pack/doc/mw/Network/html/index.html
- STM32H5 LwIP examples (NUCLEO-H563ZI): https://github.com/STMicroelectronics/stm32h5-classic-coremw-apps/tree/main/Projects/NUCLEO-H563ZI/Applications/LwIP
