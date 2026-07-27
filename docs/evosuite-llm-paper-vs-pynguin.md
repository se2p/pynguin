<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
SPDX-License-Identifier: MIT
-->

# EvoSuite-LLM Paper vs. Pynguin — Feature & Config Comparison

Source paper: *"Do We Still Need Search? Large Language Models in Search-Based Unit
Test Generation"* (`evosuite_search_llm.pdf`, anonymous, 12 pp.).

> The paper describes an **EvoSuite (Java)** extension of DynaMOSA; Pynguin is a
> **Python** SBST tool. A few paper features (bytecode / decompiled context modes)
> are therefore N/A for Pynguin, which always has source available. The recent
> Pynguin changes (30 s stagnation window, 45 s late-budget guard, diagnostic
> problem cards, 64 000-char context, 2 repair iterations) map almost exactly onto
> the paper's *deployed* configuration — this looks like a deliberate port.

## Paper in one paragraph

The paper integrates LLMs into EvoSuite's genetic search at **three entry points**:
(1) pre-search seeding, (2) asynchronous background injection, (3) stagnation-triggered
querying. Headline finding: **how** the LLM is integrated matters far more than **which**
model is used. The **cost–coverage optimum is stagnation-triggered injection only** —
call the LLM solely when the wall-clock search plateaus, validate/repair each candidate,
and retain survivors without letting them dominate the population. Pre-search seeding
spends early budget and occasionally hurts; diversity preservation (speciation) is
coverage-neutral (a safeguard, not a coverage lever); asynchronous injection is
statistically tied with stagnation-only.

## Feature comparison

| Paper feature (EvoSuite + LLM) | In Pynguin? | Notes |
|---|---|---|
| **Context extraction** | | |
| Source-code SUT context | ✅ Yes | `get_module_source_code()`; Python always has source |
| Multiple context modes (bytecode / decompiled / signature-only) | ⛔ N/A | Java-specific; Python needs only source |
| Char-budget truncation of context | ✅ Yes | `max_context_chars=64000` — same budget the paper selects |
| Cluster compaction → dependency signature summaries | ✅ Yes | `SUTInspector.inspect_dependencies` (`enable_dependency_context`) |
| Usage-example extraction | ✅ Yes (beyond paper) | `inspect_usage_examples` (`enable_usage_examples`) |
| Diagnostic "problem cards" per uncovered goal | 🟡 Partial | Pynguin has **2** categories (never-reached, branch-polarity); paper defines **~9** (type, reachability, mock-dep, environment, unreached, exception, branch-polarity, control-dep, state-div) |
| **Parsing & repair** | | |
| Parse/scaffold LLM output into test representation | ✅ Yes | `parsing/rewriter.py`; no "uninterpreted statement" escape hatch like EvoSuite |
| Multi-turn repair loop | ✅ Yes | `pipeline.repair_test_code` / `_run_repair_loop`, `max_repair_iterations=2` (matches paper's deployed 2) |
| Cluster expansion on unresolved types during repair | ⛔ No | — |
| Salvaging (keep coverage of failing test as covering-exception) | ⛔ No | Only referenced in a docstring; not implemented |
| **Hybrid search integration** | | |
| (1) Pre-search initial-population seeding | ✅ Yes | `hybrid_initial_population` + `llm_test_case_percentage` |
| Pre-search one-off uncovered-targets call | ✅ Yes | `call_llm_for_uncovered_targets` |
| Pool enrichment (constant / cast-class / object pools) | ⛔ No | Pynguin injects whole test chromosomes only, no typed-pool seeding |
| (2) Asynchronous background producer | ⛔ No | **Missing** — Pynguin is synchronous only |
| (3) Stagnation-triggered querying (wall-clock window) | ✅ Yes | `call_llm_on_stall_detection` + `stall_detection_window_seconds=30` |
| Late-budget guard | ✅ Yes | `min_remaining_budget_for_llm=45` |
| Iteration-count plateau fallback | ✅ Yes | `max_plateau_len=25` (Pynguin keeps as fallback; paper uses time only) |
| Diversity preservation via speciation/niching | ⛔ No | **Missing** — no species/Jaccard grouping in Pynguin |
| Admission modes: raw / blending / lineage-elitism protection | ⛔ No | Pynguin uses raw admission only (prepends chromosomes) |
| **Post-processing** | | |
| Readability refinement | ✅ Yes | `pipeline.refine_readability` |
| Assertion generation (semantic) | ✅ Yes | `generate_semantic_assertions` |
| Mutation filtering of vacuous assertions | ✅ Yes | `mutation_analyzer` |
| Mutation-driven assertion strengthening | ✅ Yes (beyond paper) | `enable_mutation_strengthening` |
| **Extras (Pynguin-specific)** | | |
| LLM local search on statements | ✅ Yes | `local_search_llm` |
| Type/subtype inference prompts | ✅ Yes | Needed for untyped Python |
| Response caching | ✅ Yes | `enable_response_caching` |

**Bottom line:** Pynguin covers the paper's *winning* path (stagnation-triggered
querying + source context + light repair + diagnostic hints). The biggest gaps vs. the
paper are **asynchronous injection**, **speciation/diversity preservation**,
**blending/lineage-elitism admission**, and the **full 9-category diagnostic taxonomy** —
all of which the paper shows are secondary to the stagnation trigger anyway.

## Default configuration

Paper **deployed** config vs. Pynguin **out-of-the-box defaults** (`configuration.py`):

| Parameter | Paper (deployed) | Pynguin default | Match? |
|---|---|---|---|
| Integration mode | Stagnation-only injection | All LLM hooks **OFF** by default | ⚠️ off until enabled |
| `call_llm_on_stall_detection` | on | `False` | enable to match |
| `hybrid_initial_population` | off | `False` | ✅ |
| `call_llm_for_uncovered_targets` | off | `False` | ✅ |
| Context representation | source code | source (only option) | ✅ |
| `max_context_chars` | 64 000 | `64000` | ✅ |
| Stagnation window | 30 s (~1/10 of budget) | `stall_detection_window_seconds=30` | ✅ |
| Late-budget guard | 45 s | `min_remaining_budget_for_llm=45` | ✅ |
| Repair iterations | 2 | `max_repair_iterations=2` | ✅ |
| Interventions per run | fires once per plateau | `max_llm_interventions=1` | ✅ |
| Request timeout | ~30 s (nano) | `request_timeout=30.0` | ✅ |
| Model | gpt-5.4-nano | `gpt-4o-mini` | different model |
| Search budget | 300 s/class | (project/run-set) | n/a |
| Admission / speciation | blending + lineage-elitism, speciation off | raw admission, no speciation | ⚠️ not implemented |

Pynguin's defaults are pre-tuned to the paper's calibrated values, but **the LLM is
disabled by default**. Recommended setup: flip **only** `call_llm_on_stall_detection=True`
(plus `llm_refinement.enabled=True` for repair/readability/assertions), leaving seeding
and the pre-search call off.

## LLM requests per module under the recommended config

Recommended = `call_llm_on_stall_detection=True`, `llm_refinement.enabled=True`,
seeding + pre-search call OFF, mutation-strengthening OFF (default). Counts are
**logical requests** (`OpenAIClient.send` increments its call counter once per logical
request — `client.py:230`); each logical request may fan out to up to `max_retries=8`
real API calls on transient errors, plus one extra temperature-fallback retry.

Let **T** = number of test functions in the final suite (the dominant driver; refinement
processes *all* of them because `llm_refinement.max_tests` defaults to `None`).

| Feature | Code path | Requests | When |
|---|---|---|---|
| Stall-triggered uncovered-targets query | `LLMOSAAlgorithm._maybe_intervene_on_stall` → `call_llm_for_uncovered_targets` → `query` | **0–1** | Fires once if search idles ≥30 s with ≥45 s budget left; capped by `max_llm_interventions=1` |
| Pre-search seeding / one-off uncovered call | `_target_initial_uncovered_goals` | **0** | Disabled in recommended config |
| Readability refinement | `pipeline.refine_readability` | **T × 1** | Once per refined test (always) |
| Semantic assertion generation | `pipeline.generate_semantic_assertions` | **T × 1** | Once per refined test (always) |
| Repair loop | `_run_repair_loop` → `repair_test_code` | **T × (0–2)** | Only when a refined test fails to run; ≤ `max_repair_iterations=2`; assertion-failure iterations remove the assertion instead of calling the LLM |
| Mutation strengthening | `_run_mutation_strengthening_loop` | **0** (T × 0–3 if enabled) | Off by default |

**Per-module total ≈ `(0–1) + T × (2 … 4)`**

- Floor (no repairs): `1 + 2T`
- Ceiling (every test hits the 2-repair cap): `1 + 4T`

> **Configurable via `llm_refinement.refinement_granularity`.** The `2T` readability +
> assertion floor above assumes `per_test`. The default is now `combined` (one
> module-level prompt doing both stages → **1** request for those stages), with
> `module_separate` (**2** requests) as a middle ground. Repair stays per-broken-test in
> all modes, and any truncated/dropped-test module response falls back to `per_test`. See
> `docs/refinement-granularity-plan.md` and `src/pynguin/refinement/AGENTS.md`.
>
> | Mode | readability+assertions | total per module |
> | --- | --- | --- |
> | `combined` (default) | 1 | `1 + 1 + (0–2T)` |
> | `module_separate` | 2 | `1 + 2 + (0–2T)` |
> | `per_test` | 2T | `1 + T·(2–4)` |

Worked estimate for a mid-size suite **T ≈ 15**:

| Scenario | Requests |
|---|---|
| Best case (no repairs needed) | ~31 |
| Typical (~half the tests need 1 repair) | ~39 |
| Worst case (every test hits repair cap) | ~61 |

**Estimation caveats:**
- **T is the key unknown** and is highly module-dependent (trivial modules → a handful
  of tests; complex modules → several dozen). Refinement dominates: readability +
  assertions alone are a hard `2T` floor.
- The stall query is ~1 for any non-trivial module (they typically plateau) and 0 for
  modules covered before the first 30 s window.
- Repair frequency depends on how often the LLM's readability/assertion edits break an
  otherwise-passing Pynguin test — unknown without measurement; the range 0–2T bounds it.
- With `enable_mutation_strengthening=True`, add up to `T × max_mutation_iterations`
  (=3) more, i.e. the ceiling jumps to `1 + 7T`.
- Actual API/HTTP calls can exceed logical requests by up to ~8× per request under
  rate-limit/timeout retries.
