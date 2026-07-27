<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
SPDX-License-Identifier: MIT
-->

# Implementation Plan: Configurable Refinement Granularity

Status: implemented (`llm_refinement.refinement_granularity`, default `combined`)
Scope: `src/pynguin/refinement/`, `src/pynguin/large_language_model/prompts/`,
`src/pynguin/configuration.py`
Related: `docs/evosuite-llm-paper-vs-pynguin.md` (cost analysis this plan builds on)

## 1. Background & goal

Today the LLM refinement pipeline refines **each test function independently**: for every
test it sends one **readability** request and one **semantic-assertion** request, then runs
a per-test repair loop. For a suite of `T` tests that is `2T` requests just for the
generation stages (plus `0–2T` repair). See `docs/evosuite-llm-paper-vs-pynguin.md`.

**Goal:** let the user choose the granularity of the readability and
assertion-generation stages, so those `2T` requests can collapse to `1` or `2` per module.

### Three modes

| Mode | Readability + assertions | Requests (those stages) |
| --- | --- | --- |
| `combined` (**new default**) | one module-level prompt doing both stages | **1** |
| `module_separate` | two module-level prompts (readability, then assertions) | **2** |
| `per_test` (previous behavior) | per-test readability + per-test assertions | **2T** |

**Invariant across all three modes:**
- **Repair stays per-broken-test.** `validator.run_test()` already runs one function at a
  time and returns `(passed, message)`; `_run_repair_loop` only calls the LLM when a test
  fails (assertion-failures are stripped locally, no LLM). Do not batch repair.
- **Mutation-strengthening stays per-test** (survivor detection is inherently per-test).
- Only the **readability** and **assertion-generation** stages change granularity.

> **Behavior change:** the default becomes `combined`, which is a deliberate change from
> the current per-test behavior. It is the most token-efficient but highest-variance
> output mode (one prompt renames *and* adds assertions across the whole module). The
> per-test path remains available and fully supported as `per_test`, and is the automatic
> fallback whenever a module-level response is truncated or drops/renames tests.

## 2. Current-state facts the plan relies on

- `refinement/refiner.py: refine_generated_tests(...)`:
  - calls `_load_test_functions(test_file_path) -> (import_block, test_functions)`,
  - loops `for func in test_functions[:limit]: _process_one_test(...)`,
  - `limit = max_tests if max_tests is not None else len(test_functions)`
    (`llm_refinement.max_tests` defaults to `None` → all tests).
- `_process_one_test` → `TestRefiner.process_test_end_to_end(original_code, max_retries)`.
- `refinement/pipeline.py`:
  - `_prepare_refined_code(original_code)` runs: `structural_analysis` (pure AST, no LLM) →
    `refine_readability` (1 LLM call, `pipeline.py:392`) → `generate_semantic_assertions`
    (1 LLM call, `:408`) → `filter_vacuous_assertions` (mutation, no LLM) → optional
    `_run_mutation_strengthening_loop` (off by default).
  - `_run_repair_loop(...)` (`:659`) calls `repair_test_code` (1 LLM call, `:447`) only on
    failing tests, capped at `max_repair_iterations` (default 2).
  - All LLM calls go through `self.llm_client.generate_from_prompt(prompt_obj)`.
- Prompts: YAML in `prompts/resources/*.yaml` + a `Prompt` subclass with `_template_vars()`
  and `render_request()`. `defaults.yaml` supplies `temperature: 0.0`. `Prompt`
  construction fails if referenced Jinja vars ≠ declared `_template_vars()`.
- `OpenAIClient.send()` counts **one logical request** regardless of retries
  (`client.py:230`); retries fan out to ≤ `max_retries=8` real API calls + 1 temperature
  fallback.
- Config choice-options use the `class X(str, enum.Enum)` pattern (see `Algorithm`,
  `AssertionGenerator`, `MutationStrategy` in `configuration.py`).

## 3. Changes

### 3.1 Config (`configuration.py` + config-writer test)

- Add near the other enums (~line 80):
  ```python
  class RefinementGranularity(str, enum.Enum):
      """Granularity of the LLM readability & assertion refinement stages."""
      COMBINED = "combined"                # one module-level prompt (both stages)
      MODULE_SEPARATE = "module_separate"  # two module-level prompts
      PER_TEST = "per_test"                # per-test prompts (previous behavior)
  ```
- Add to `LLMRefinementConfiguration`:
  ```python
  refinement_granularity: RefinementGranularity = RefinementGranularity.COMBINED
  """Whether readability refinement and semantic-assertion generation are done with a
  single combined module-level prompt (``combined``, default; most token-efficient,
  highest-variance), two separate module-level prompts (``module_separate``), or one
  prompt per test (``per_test``; previous behavior, most robust). Repair and
  mutation-strengthening are always per-test regardless of this setting."""
  ```
- Update `tests/utils/test_configuration_writer.py`: add the field to the serialized-config
  golden string and the sorted `--llm_refinement.refinement_granularity` CLI-arg block
  (same locations the stall-detection commit touched).

### 3.2 New prompts (`prompts/resources/` + `prompts/`)

Mirror `ReadabilityRefinementPrompt` / `SemanticAssertionsPrompt`. All inherit
`temperature: 0.0`; set a **higher `max_tokens`** for whole-module output (see §3.5).

1. `module_readability_refinement.yaml` + `ModuleReadabilityRefinementPrompt`
   - vars: `module_test_code`, `sut_context`
   - instruction: refine readability of **all** test functions; keep every function with
     its **exact original name**; preserve imports & `module_0.` prefixes; output the whole
     module, code only.
2. `module_semantic_assertions.yaml` + `ModuleSemanticAssertionsPrompt`
   - vars: `module_test_code`, `sut_context`; assertion-focused, same preservation rules.
3. `module_refinement_combined.yaml` + `ModuleRefinementPrompt`
   - vars: `module_test_code`, `sut_context`; does readability **and** assertions in one
     pass; same preservation rules.

Per-test prompts stay unchanged for `per_test`.

### 3.3 Pipeline methods (`pipeline.py`)

Add module-level generators, each just builds the new prompt and calls
`self.llm_client.generate_from_prompt(...)` (identical plumbing to the existing 3 sites),
returning the refined module string (with `# LLM error` sentinel handling and
`_restore_import_block`):
- `refine_readability_module(module_code, sut_context) -> str`
- `generate_semantic_assertions_module(module_code, sut_context) -> str`
- `refine_module_combined(module_code, sut_context) -> str`

### 3.4 Refiner dispatch (`refiner.py`)

In `refine_generated_tests`, after `_load_test_functions(...)`, branch on
`config.configuration.llm_refinement.refinement_granularity`:
- `PER_TEST` → existing per-function loop (unchanged).
- `MODULE_SEPARATE` / `COMBINED` → new `_process_module(...)`.

New `_process_module(refiner, import_block, test_functions, granularity, max_repair_iterations)`:
1. Assemble one module blob: `import_block` + `test_functions[:limit]` (respect `max_tests`).
2. Build `sut_context` once at module level (drop per-test focal-method context — noted
   quality tradeoff).
3. Batched generation:
   - `COMBINED` → `refine_module_combined(...)` (1 request).
   - `MODULE_SEPARATE` → `refine_readability_module(...)` then
     `generate_semantic_assertions_module(...)` (2 requests).
4. **Split & map:** `ast.parse` the returned module, index refined functions by name, match
   to originals. Validate every original test name is present and parseable.
5. **Per-test finish (reuse existing machinery):** for each matched test run the
   mutation-vacuous filter + `_run_repair_loop` so repair stays per-broken-test; produce the
   same `_TestOutcome` values as the per-test path.
6. **Fallback:** any test missing / unparseable / from a truncated response → refine via the
   existing `_process_one_test` per-test path. `log()` what fell back (no silent drops).

Stats accounting (`_TestOutcome`, readability deltas, mutation accumulation,
`_maybe_write_refined_file`) is unchanged because the module path yields the same per-test
outcomes.

### 3.5 Truncation handling (main risk)

- Raise `max_tokens` on the three module-level prompts.
- Detect truncated/unparseable module response (fails `ast.parse`, or missing test names) →
  trigger the §3.4.6 per-test fallback rather than dropping tests. Log the fallback.

## 4. Tests

- Pipeline unit tests (mock `generate_from_prompt`): assert `combined` = 1 call,
  `module_separate` = 2 calls, `per_test` = 2T calls.
- Refiner tests: split/map correctness; fallback on dropped/renamed/truncated test;
  `max_tests` cap respected; repair still runs per-test on batched output.
- Render/characterization tests for the 3 new prompts (interpolation, `temperature==0.0`,
  system message present).
- Config-writer test update (§3.1).
- Full check: `poetry run pytest tests/refinement tests/large_language_model tests/utils`
  `poetry run pre-commit run --files <changed>` + `poetry run mypy <changed modules>`.

## 5. Request-count impact (per module)

`T` = tests in final suite. Leading `1` = stall query; repair unchanged (per-broken-test).

| Mode | readability+assertions | total per module |
| --- | --- | --- |
| `combined` (default) | 1 | `1 + 1 + (0–2T)` |
| `module_separate` | 2 | `1 + 2 + (0–2T)` |
| `per_test` | 2T | `1 + T·(2–4)` |

For `T≈15`: generation stages drop from ~30 requests to 1 (combined) / 2 (separate); repair
becomes the dominant variable term.

## 6. Open decisions / tradeoffs

- **Default = `combined`** (chosen). Most token-efficient, highest output variance; relies
  on the per-test fallback for robustness.
- **Lost per-test focal context** in module modes is a minor quality cost, noted in the
  docstring.
- **Combined prompt** must be carefully worded (rename *and* assert in one pass) — invest in
  the template + a characterization test.

## 7. Suggested landing order

1. Config enum + field + config-writer test (behavior-neutral until wired).
2. `module_separate` prompts + pipeline methods + refiner dispatch + split/map/fallback
   (lower-risk than combined; validates the whole batched path).
3. `combined` prompt + method; flip default to `combined`.
4. Tests + docs (`AGENTS.md`, `docs/evosuite-llm-paper-vs-pynguin.md`).
