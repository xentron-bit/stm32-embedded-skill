# Graphify — Capabilities & How to USE the Output in Code Analysis

> Graphify is the code-map engine behind the Mode B+ pipeline. The point is not to
> *build* a graph — it is to **consume** the graph's outputs (GRAPH_REPORT.md god
> nodes / surprising connections, `graph.json` queries) to drive and verify findings.
> See CLAUDE.md §"Graphify-First Gate". Commands/outputs below are verified against the
> installed build (**v0.8.39**); re-verify with `graphify --help` after upgrades.

## 1. Core capabilities

- **Multi-modal extraction** — parses code (`.c/.h/.py/.js/.go/.java/…` via Tree-sitter
  → ASTs, **call graphs**, docstrings), Markdown, PDFs, and images (LLM/vision for prose
  & diagrams). For STM32: extracts the firmware call graph (functions, IRQ handlers,
  HAL/LL calls, includes).
- **Knowledge-graph build** — merges nodes/edges into a NetworkX graph; **Leiden**
  community detection (semantic clusters) — **no vector embeddings**.
- **God nodes & surprises** — flags the highest-degree "**god nodes**" (your core
  abstractions / hubs) and **surprising connections** (unexpected cross-file /
  cross-domain edges worth investigating).
- **Interactive outputs** — `graph.html` (interactive), `graph.json` (queryable),
  `GRAPH_REPORT.md` (human-readable audit).
- **Assistant integration** — `/graphify`, `graphify query|path|explain|affected`.
- **Secure by design** — strict input validation (http/https only, size/timeout limits,
  path containment, HTML-escaped labels) → SSRF/injection/XSS defense.

## 2. Commands (verified v0.8.39)

| Command | Use |
|---------|-----|
| `graphify update <path>` | **build/refresh** the graph — AST-only, **no LLM key** (DEFAULT for code review) → writes `<path>/graphify-out/graph.json` + `graph.html` + `GRAPH_REPORT.md` |
| `graphify extract <path>` | headless full extraction for CI/scripts. **Code-only corpus = fully offline, NO API key** (tree-sitter local). The semantic-LLM pass + a backend key are needed **only** when the corpus includes docs/PDF/images (or via the IDE `/graphify` skill, the IDE's own model does it — no extra key). `--mode deep`, `--backend ollama` (local), `--force` |
| `graphify query "<question>" --graph <json>` | **BFS** traversal → returns the relevant subgraph (nodes+edges) for a question (`--budget N` caps tokens, `--dfs`, `--context`) |
| `graphify affected "<symbol>" --graph <json>` | **reverse** traversal — what is impacted by X (`--relation`, `--depth`) |
| `graphify path "A" "B" --graph <json>` | shortest call path between two nodes |
| `graphify explain "X" --graph <json>` | plain-language explanation of a node + its neighbors |
| `graphify diagnose multigraph --graph <json>` | same-endpoint edge-collapse risk |
| `graphify benchmark <json>` | measure token reduction vs naive full-corpus |
| `graphify update . --no-cluster` / `cluster-only <path> --no-viz` | skip clustering / skip HTML (big graphs / CI) |

> Tool Bootstrap: if `graphify` (binary) is missing → ASK the user, then `pip install
> graphifyy`; if present → `pip list --outdated` update check (offer upgrade with
> permission). Detect the **binary `graphify`**, not the pip name `graphifyy`.

## 3. `GRAPH_REPORT.md` structure (verified) — read THIS first

```
## Corpus Check                # file counts / coverage
## Summary                     # nodes / edges / communities
## Community Hubs (Navigation) # links to each Leiden community
## God Nodes (most connected)  # ← core abstractions / hubs to scrutinize
## Surprising Connections      # ← unexpected cross-file edges = bug candidates
## Import Cycles               # coupling smells
## Communities (N total)       # each cluster + members
```

## 4. How to USE the output in STM32 code analysis (mandatory consumption)

Building the graph is step 0 — these are what make it worth it:

1. **Read `GRAPH_REPORT.md` first.**
   - **God Nodes** → the hub functions/types everything depends on (e.g. a shared
     `HAL_GetTick`, a global `CAN1_RxIndex`, a single `USERFile`). Hubs touched from
     many places are prime spots for **races, shared-state, reentrancy** bugs — scrutinize them.
   - **Surprising Connections** → unexpected cross-file/cross-domain edges are **bug
     candidates**: e.g. an ISR reaching into a blocking driver, a "dead" module
     (`can2.c`) still linked to a hub, a config parser calling flash. Investigate each.
   - **Import Cycles / Communities** → coupling and the real subsystem map (often differs
     from the folder layout).
2. **Query the graph per risk area** instead of reading whole files:
   - `graphify query "DMA buffer cache clean invalidate"` → walk returned nodes
     (`SPI1_Dma2IrqHandler spi1.c:180`, `MX_DMA_Init dma.c:39`, fault handlers) to source.
   - `graphify affected "CAN1_RxIndex"` → every site that touches the shared ISR index
     (race surface). `graphify path "FDCAN1_IT0_IRQHandler" "ParseObd"` → the ISR→task chain.
3. **Walk node → file:line → Read** the actual source; **verify** the finding against the
   bytes on disk. **Citation-cancellation:** if `graphify query`/`grep` shows the symbol
   is actually defined/handled, **cancel** the finding (mark verified-present). A finding
   with no graph/source citation is forbidden (SKILL.md Faz 6 rules).
4. Findings must **derive from the graph + source**, not from a brute-force full-file
   read or memory. (The graph gives ~7.4× token reduction per query — see §2 benchmark.)

## 5. AST-only vs semantic (both run offline on code)

- `graphify update` (AST-only) gives an accurate **structural** call graph — sufficient
  for god-nodes, surprises, call paths, affected-by. Incremental (SHA256 cache).
- `graphify extract` does the same AST pass; the **semantic LLM pass only runs on
  docs/PDF/images** — so on a **code-only STM32 project both are offline/key-less**.
  The LLM pass (richer prose/INFERRED edges) needs a backend key **only** for non-code,
  or is supplied free by the IDE session when run via the `/graphify` skill.
- **Data residency (confidential firmware):** code never leaves the machine (local
  tree-sitter). If you *do* run semantic extraction on docs, prefer **`--backend ollama`**
  (fully local) or the `claude` CLI (your subscription) over cloud keys. Query logging
  goes to `~/.cache/graphify-queries.log` (JSONL); disable with `GRAPHIFY_QUERY_LOG_DISABLE=1`.

### Concrete query examples (from graphify docs)
```bash
graphify query "what connects auth to the database?" --graph graphify-out/graph.json
graphify query "show the auth flow" --dfs --budget 1500
graphify path "FDCAN1_IT0_IRQHandler" "ParseObd"     # call chain between two nodes
graphify affected "CAN1_RxIndex"                      # every site impacted by a symbol
graphify explain "MX_DMA_Init"                        # a node + its neighbours
```

### graphify's own assistant rules (AGENTS.md — adopt these)
1. **Before** answering architecture/codebase questions, **read `graphify-out/GRAPH_REPORT.md`**
   (god nodes + community structure).
2. If **`graphify-out/wiki/index.md`** exists, **navigate it instead of reading raw files**.
3. After modifying code in a session, run **`graphify update .`** to keep the graph current
   (AST-only, no API cost).

## 6. Most-efficient use — official best practices (graphify GitHub / graphify.net)

- **Query-first, NOT read-first (the core efficiency rule).** graphify's own assistant
  config tells the agent to **prefer scoped `graphify query "<question>"` over reading
  the full report or grepping raw files**. On Claude Code a PreToolUse **hook fires
  before Bash-search and one-by-one Read/Glob** and nudges to the graph path. So: before
  opening files, ask the graph. (`graphify claude install` wires this hook + CLAUDE.md.)
- **Two-pass extraction.** Pass 1 = Tree-sitter AST, **local, 0 API tokens, 25 languages**
  (functions/classes/imports/call-graph). Pass 2 = LLM, **only for PDF/image/markdown**
  semantics. → `graphify update` (code) is free & key-less; only non-code needs a backend.
- **Incremental.** `graphify update` re-extracts **only changed files** (SHA256 cache).
  `graphify watch <path>` rebuilds on save; `graphify hook install` adds post-commit/
  post-checkout git hooks (embeds the interpreter path — re-run after upgrades).
- **Confidence tags (ties to No-Guess).** Every edge is tagged **`EXTRACTED`** (found),
  **`INFERRED`**, or **`AMBIGUOUS`** (guessed). Treat `INFERRED`/`AMBIGUOUS` as **leads to
  verify against source**, never as established facts — exactly the Fact-Based rule.
- **The "why" nodes.** `# NOTE:`/`# WHY:`/`# HACK:` comments + docstrings are extracted as
  separate nodes linked to the code — read these to understand intent before flagging.
- **Token economy.** Official figure ~**71.5×** (≈1.7k vs ≈123k tokens/query); measured
  **7.4×** on the XENCHECK AST-only graph (smaller corpus, no semantic pass). Either way:
  query, don't dump.
- **Team option.** One person runs `graphify update .` and **commits `graphify-out/`** so
  everyone shares the map. (This skill **gitignores** `graphify-out/` — it's per-analysis
  cache here; commit it only if you want a shared, versioned map.)
- **Install via `uv`** (recommended — puts `graphify` on PATH): `uv tool install graphifyy`
  (extras: `graphifyy[pdf|gemini|anthropic|sql]`). Backend keys: `GEMINI_API_KEY` /
  `ANTHROPIC_API_KEY` (`--backend claude`) etc. — needed **only** for the semantic pass on
  **non-code** (docs/PDF/images); code is always extracted offline. Auto-detect priority:
  Gemini → Kimi → Claude → OpenAI → DeepSeek → Azure → Bedrock → Ollama.
- **Latest is v0.8.41** (this machine: v0.8.39 — update check per §2 / Tool Bootstrap).

**STM32 review do/don't:**
- ✅ Read `GRAPH_REPORT.md` (god nodes + surprising connections) → pick suspects → `query`/
  `affected`/`path` → walk to `file:line` → verify → cite. ✅ Use `update` (key-less, fast).
- ❌ Don't brute-force read all files / grep first. ❌ Don't trust `INFERRED`/`AMBIGUOUS`
  edges without source verification. ❌ Don't run `extract --mode deep` (heavier) when the
  incremental `update` (AST, key-less) suffices for a code-only project.

## Cross-links
- CLAUDE.md §"Graphify-First Gate" (no project analysis without graphify) + §"Graphify
  Follow-Up". SKILL.md §"Mode B+" Faz 4/5 (build), Faz 6 (citation rules).

## Sources (best practices)
- github.com/safishamsi/graphify (README — query-first config + hooks, two-pass extraction,
  god nodes / surprising connections / "why" nodes / confidence tags, incremental `--update`,
  `uv` install, backends). Web: augmentcode.com (v0.8.41, 71.5× token figure), dev.to /
  mindstudio guides. graphify.net returned 403 to automated fetch; GitHub README is the
  authoritative mirror.

## Sources
- Graphify official capabilities (graphify project description) + verified `graphify
  --help` (v0.8.39) and a real `GRAPH_REPORT.md` produced from the XENCHECK project
  (God Nodes / Surprising Connections / Communities confirmed present). `graphify
  benchmark` measured 7.4× avg token reduction on that project's graph.
