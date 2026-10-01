<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# LLM Test Refinement

<!-- Parent: ../AGENTS.md -->

Post-processing pipeline that refines Pynguin-generated tests with an LLM: it improves
readability, adds behavior-based assertions, filters vacuous assertions via mutation,
and repairs tests that break. Enabled with `llm_refinement.enabled=True`.

**Timestamp:** 2026-07-27

## Entry point

`refiner.refine_generated_tests(test_file_path, module_name, ...)` (called from
`generator.py` after export):
1. `_load_test_functions` → `(preamble, test_functions)`. The preamble is every
   top-level statement that is *not* a `def test_*` (imports, the
   `<mod>_ = sys.modules[...]` alias, the autouse reseed fixture, ...), so refined
   tests referencing those names still resolve.
2. Dispatch on `llm_refinement.refinement_granularity` (see below).
3. Accumulate per-test outcomes (`_TestOutcome`) into statistics and write
   `<stem>_refined.py`.

## Refinement granularity

`refinement_granularity` (enum `configuration.RefinementGranularity`) controls the
readability and semantic-assertion stages. Mutation strengthening is controlled by
`mutation_granularity` (enum `configuration.MutationStrengtheningGranularity`, default: `full_module`).
Repair stays per-broken-test. Let `T` = number of tests.

| Mode | Readability + assertions | Requests (those stages) | Path |
| --- | --- | --- | --- |
| `combined` (**default**) | one module-level prompt doing both | **1** | `_process_module` |
| `module_separate` | two module-level prompts | **2** | `_process_module` |
| `per_test` | per-test readability + per-test assertions | **2T** | `_process_one_test` loop |

`combined` is the most token-efficient and highest-variance mode; `per_test` is the most
robust and is the automatic **fallback**.

### Mutation strengthening granularity (`mutation_granularity`)

- `full_module` (**default**): Detects surviving mutants across the whole suite, batches them (up to `max_mutants_per_prompt`, default 15), and prompts the LLM to strengthen existing tests or add new boundary tests using `ModuleMutationStrengthenPrompt`. Employs a 3-gate validation pipeline per chunk: clean SUT execution with assertion stripping (failing new tests are discarded), mutant verification (the chunk must kill additional mutants; added assertions and new tests that kill none are pruned), and a coverage preservation check. Test functions in a module are run one by one with pytest's `xfail` semantics (`validator.call_test_functions`), so an expected failure neither counts as a kill nor hides later tests.
- `per_test`: Legacy loop prompting up to 10 surviving mutants per test function.

### Module path (`_process_module`)

1. Assemble all selected tests into one module blob (`_assemble_module_blob`).
2. Build a module-level `sut_context` from the SUT source (`build_module_sut_context`;
   per-test focal-method context is intentionally dropped — a minor quality tradeoff).
3. Batched generation (`_generate_module`): `combined` → `refine_module_combined` (1 call);
   `module_separate` → `refine_readability_module` then
   `generate_semantic_assertions_module` (2 calls).
4. Split & map: `ast.parse` the response, parse functions in order
   (`_parse_refined_functions`). When test count matches, map positionally to support
   descriptive test function renaming (`test_0` → `test_<behavior>`); otherwise fall back
   to name-based matching (`_index_refined_functions`), and slice each function's source text
   (`_slice_function_source`, preserves comments/AAA markers).
5. Per-test finish: `TestRefiner.finish_refined_test` runs the mutation-vacuous filter,
   optional mutation strengthening, and the per-broken-test repair loop — identical
   machinery to the per-test path, producing the same `_TestOutcome` values.

### Fallback (no silent test drops)

Any test that is **missing** (when count mismatches and name is not found), from a
**truncated/unparseable** response, or whose finish stage raises falls back to the
per-test path (`_process_one_test`) and is logged. A whole-module `# LLM error` sentinel
or parse failure falls the entire module back to per-test.

## Key files

- `refiner.py` — entry point, granularity dispatch, module split/map/fallback, statistics.
- `pipeline.py` — `TestRefiner`: structural analysis, per-test and module-level generators,
  mutation filtering/strengthening, repair loop (`_run_repair_loop`), coverage/AAA finish.
- `llm_client.py` — thin OpenAI wrapper; `generate_from_prompt`; `LLM_ERROR_PREFIX` sentinel.
- `mutation_analyzer.py`, `coverage_checker.py`, `validator.py`, `sut_inspector.py`,
  `ast_analyzer.py`, `aaa_inserter.py`, `readability_metrics.py` — supporting stages.

## Invariants

- **Repair stays per-broken-test.** `validator.run_test` runs one function at a time;
  `_run_repair_loop` calls the LLM only on failing tests (assertion failures are stripped
  locally, no LLM). Never batch repair.
- **Mutation-strengthening supports full_module (default) and per_test.**
- Module-level responses must preserve imports and `module_0.` call prefixes.

## Prompts

Per-test: `ReadabilityRefinementPrompt`, `SemanticAssertionsPrompt`, `RepairPrompt`,
`MutationStrengthenPrompt`. Module-level: `ModuleReadabilityRefinementPrompt`,
`ModuleSemanticAssertionsPrompt`, `ModuleRefinementPrompt`, `ModuleMutationStrengthenPrompt` (see
`../large_language_model/prompts/AGENTS.md`).
