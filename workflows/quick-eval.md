---
description: Local coverage/regression evaluation for Pynguin changes via utils/quick_eval.py — diff a branch against a baseline (primary), or run/compare saved results manually.
---

<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
SPDX-License-Identifier: MIT
-->

# quick-eval — local coverage/regression evaluation for Pynguin

Fast, local feedback loop for changes to Pynguin. Runs Pynguin over a set of
subject modules, collects branch coverage (plus optional mutation score and LLM
statistics), and compares a feature branch against a baseline — all on this
machine, no cluster required.

Implementation: `utils/quick_eval.py` (thin entry) → `utils/_quick_eval/` package.
Run everything through Poetry: `poetry run python utils/quick_eval.py …`.

---

## Prerequisites

- **Subjects & rundefinitions** live in the sibling checkout
  `../pynguin-experiments/`:
  - rundefinition XMLs: `../pynguin-experiments/rundefinitions/*.xml`
  - project sources: `../pynguin-experiments/projects/` (e.g. `emse-projects/<proj>`)
- **LLM credentials** (only for `--llm`) are read from the environment. They are
  loaded automatically from `../pynguin-experiments/.env` (keys `LLM_API_KEY`,
  `LLM_BASE_URL`, `LLM_MODEL`); a local `.env` in the repo root or the real
  environment overrides them.
- For `compare-branch`, the git working tree should be clean or committed (it
  checks out the baseline ref in a temporary worktree).

Convenience defaults (so commands stay short):
- `--rundefinition <name>` accepts a **bare name** — `coverage-check` resolves to
  `../pynguin-experiments/rundefinitions/coverage-check.xml`. A full path also works.
- `--projects-dir` defaults to `../pynguin-experiments/projects` when omitted.

---

## Primary flow: `compare-branch` (branch vs baseline, one command)

This is the default way to check a change. It checks out `<ref>` in a temporary
worktree with its own cached venv, runs both versions on the same tasks, and
prints a side-by-side delta table. Exit code is `1` if any module regressed
(useful in scripts).
```bash
# Against the real subjects:
poetry run python utils/quick_eval.py compare-branch main \
    --rundefinition coverage-check --budget 30 --jobs 4

# Fast sanity check on bundled examples (no experiments checkout needed):
poetry run python utils/quick_eval.py compare-branch main --use-bundled-examples --budget 30
```

## Variants (same tool, when `compare-branch` doesn't fit)

**Just measure the current tree — `run`.** Use when you only want absolute
numbers, not a comparison (e.g. exploring a rundefinition):
```bash
poetry run python utils/quick_eval.py run --rundefinition coverage-check \
    --modules codetiming._timers apimd.compiler --budget 30
```

**Manual / incremental comparison — `run --save` then `compare`.** Use when you
want to archive results across many edits instead of re-running a baseline each
time:
```bash
poetry run python utils/quick_eval.py run --rundefinition coverage-check --save baseline.json --budget 30
# ... make changes ...
poetry run python utils/quick_eval.py run --rundefinition coverage-check --save current.json  --budget 30
poetry run python utils/quick_eval.py compare baseline.json current.json
```

---

## Optional metrics

- **Mutation score** — add `--mutation` to `run` / `compare-branch` (uses Pynguin's
  built-in mutation analysis; significantly slower):
  ```bash
  poetry run python utils/quick_eval.py compare-branch main --use-bundled-examples --mutation --budget 30
  ```
- **LLM / LLMOSA** — three mutually-exclusive modes select the LLM configuration and
  add LLM stats (calls, input/output tokens, query time, parsed statements) to the
  output. Both `--llm` and `--min-llm` require the LLM credentials above.
  - *(no flag)* — **non-LLM**: pure SBST (DynaMOSA), the default.
  - `--llm` — **full**: every combinable LLM feature — LLMOSA + pre-search
    initial-population seeding + pre-search uncovered-targets call + stagnation-triggered
    querying + in-search LLM assertion generation (`--assertion-generation LLM`).
  - `--min-llm` — **minimal / paper-faithful**: the paper's cost-optimal *deployed*
    configuration (`docs/evosuite-llm-paper-vs-pynguin.md`) — LLMOSA with
    stagnation-triggered querying **only**, plus the post-processing refinement pipeline
    (`llm_refinement.enabled`: readability + semantic assertions + repair). Pre-search
    seeding and the uncovered-targets call stay **off**, since the paper finds the
    cost–coverage optimum is stagnation-triggered injection alone.

  Both modes inherit Pynguin's already paper-calibrated defaults (30 s stagnation window,
  45 s late-budget guard, 2 repair iterations, 1 intervention, 64 000-char context, 30 s
  timeout) and enable response caching.
  ```bash
  # Full LLM:
  poetry run python utils/quick_eval.py run --rundefinition coverage-check --llm --budget 30
  # Paper-faithful minimal LLM:
  poetry run python utils/quick_eval.py run --rundefinition coverage-check --min-llm --budget 30
  # Fair three-way comparison (non-LLM baseline vs. each mode):
  poetry run python utils/quick_eval.py run --rundefinition coverage-check --save base.json --budget 60
  poetry run python utils/quick_eval.py run --rundefinition coverage-check --min-llm --save min.json --budget 60
  poetry run python utils/quick_eval.py run --rundefinition coverage-check --llm --save full.json --budget 60
  poetry run python utils/quick_eval.py compare base.json min.json
  ```
  **Start method / fair LLM comparisons (macOS only).** Pynguin picks the
  `multiprocess` start method per run: `fork` normally, but `spawn` when LLM
  features are active on macOS (`fork()` crashes there once the LLM client has
  initialised Objective-C frameworks). This applies to both `--llm` and `--min-llm`.
  `spawn` is correct but ~5–6× slower for C-extension subjects (the subprocess executor
  re-instruments the SUT per spawn), so comparing an LLM mode against the non-LLM
  baseline on macOS mixes substrates and is **not** apples-to-apples. To compare fairly,
  pin both sides to the same method via the `PYNGUIN_MP_START_METHOD={fork,spawn}` env
  var (must be `spawn` for any LLM-enabled side on macOS):
  ```bash
  PYNGUIN_MP_START_METHOD=spawn poetry run python utils/quick_eval.py run --use-bundled-examples --save nollm.json --budget 60
  PYNGUIN_MP_START_METHOD=spawn poetry run python utils/quick_eval.py run --use-bundled-examples --llm --save llm.json --budget 60
  poetry run python utils/quick_eval.py compare nollm.json llm.json
  ```
  On Linux both LLM and non-LLM use `fork`, so comparisons are fair with no override.

### Coverage-only mode — `--no-assertions`

When you only care about **coverage** (not assertion strength / mutation score), add
`--no-assertions` to `run` / `compare-branch`. It makes the run coverage-focused by
disabling everything that costs wall-clock without moving coverage:

- **All assertion generation is turned off** (`--test-case-output.assertion-generation
  NONE`), so the post-search mutation-analysis phase never runs. That phase re-executes
  the suite against every mutant and, unbounded, can be killed before exporting any
  tests on loop-heavy subjects (see `docs/hybrid-testgen-investigation.md`). Skipping it
  makes runs export sooner and never time out in that phase.
- **Non-coverage LLM requests are dropped** — under `--min-llm` the refinement pipeline
  (`llm_refinement.enabled`: readability + semantic assertions + repair) is disabled;
  under `--llm` the in-search LLM assertion generation is disabled. The coverage-driving
  LLM calls stay on (LLMOSA, stagnation-triggered querying, and full mode's
  uncovered-targets + initial-population seeding).

Coverage is still measured on the exported suite exactly as before — assertions do not
affect coverage — so this is the fastest way to compare a change's coverage impact.
`--no-assertions` does **not** combine with `--mutation` (no assertions ⇒ no mutation
score).
```bash
# Coverage-only, pure SBST:
poetry run python utils/quick_eval.py run --use-bundled-examples --no-assertions --budget 60
# Coverage-only, paper-faithful minimal LLM (refinement dropped):
poetry run python utils/quick_eval.py run --rundefinition coverage-check --min-llm --no-assertions --budget 60
```

Any unrecognised flags are forwarded verbatim to the Pynguin CLI, e.g.:
```bash
poetry run python utils/quick_eval.py run --use-bundled-examples --budget 30 \
    -- --algorithm DYNAMOSA
```

---

## Reading the output

Every run reports **two** coverage numbers per module:
- **Branch Cov** — what Pynguin itself reports internally (from `statistics.csv`).
- **Suite Cov** — the **independent, trustworthy** number: the *exported* test suite
  actually run under `coverage.py` + `pytest`, restricted to the module (combined
  line+branch). This is always measured. A large gap (high Branch Cov, low Suite Cov)
  means the generated suite doesn't really achieve what Pynguin claims — e.g. the
  exported tests fail to run or assert. If the suite can't be measured, the cell shows
  a short reason (`no generated tests`, `no tests collected`, `N failed`, …).

Other columns / signals:
- **Δ Branch / Δ Suite / Δ Mut** in the delta table — `IMPROVED` / `REGRESSED` /
  `unchanged` (threshold ±0.1%); status regresses if *any* of these drops.
  `compare` / `compare-branch` return exit code `1` if anything regressed.
- **Exit** — non-zero means the Pynguin run itself crashed (`-1` is a wall-clock timeout).
- **Time (s)** — watch for large regressions in generation time.

The generated-suite measurement needs `pytest` + `coverage` in the runner env; they
are installed automatically (including into baseline worktree venvs). Each suite is
capped at 120s wall-clock so a slow/hung generated test can't balloon a run.

### Flaky vs. real regressions

Low budgets and parallel oversubscription produce spurious `REGRESSED` rows. Before
trusting a regression, sanity-check it: use a **fair budget (≥60s)** and the same
budget on both sides, and reproduce the flagged module in isolation with low
parallelism —
`… run --use-bundled-examples --modules <mod> --budget 60 --jobs 1`. A row with
`exit≠0`, `duration ≫ budget`, or `N/A` Suite Cov is almost certainly harness
flakiness, not a coverage change; if the baseline side was degraded, the delta isn't
apples-to-apples. Only a *reproducible* crash/regression is real.

---

## Knobs

| Flag | Meaning | Default |
|------|---------|---------|
| `--budget N` | `--maximum-search-time` per module (seconds) | 60 |
| `--timeout N` | wall-clock kill limit per run (covers post-search work e.g. mutation) | 3600 |
| `--no-assertions` | coverage-only: disable assertion generation + non-coverage LLM requests | off |
| `--jobs N` | parallel worker processes | 10 |
| `--seed N` | random seed | 0 |
| `--save FILE` / `--save-baseline` / `--save-current` | archive results as JSON | — |
| `--output {table,json}` | `run` output format | table |

Baseline venvs are cached at `~/.cache/pynguin-eval/venvs/<commit>/`, so repeated
`compare-branch` runs against the same ref reuse the install.

---

## Extending

Each concern is isolated in `utils/_quick_eval/`:
`tasks.py` (subject discovery), `runner.py` (invoking Pynguin), `stats.py`
(`statistics.csv` → `ModuleResult`), `report.py` (tables/deltas/JSON),
`worktree.py` (baseline worktrees), `commands.py` + `cli.py` (CLI). To capture a
new metric, add one `_StatSpec` entry in `stats.py`, a field on `ModuleResult`,
and a column in `report.py`.
