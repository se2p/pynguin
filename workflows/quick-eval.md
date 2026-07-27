---
description: Local coverage/regression evaluation for Pynguin changes via utils/quick_eval.py — diff a branch against a baseline (primary), or run/compare saved results manually.
---

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
- **LLM / LLMOSA** — add `--llm` to run the LLM configuration (LLMOSA + LLM
  assertions, uncovered-target and stall-detection calls) and report LLM stats
  (calls, input/output tokens, query time, parsed statements). Requires the LLM
  credentials above:
  ```bash
  poetry run python utils/quick_eval.py run --rundefinition coverage-check --llm --budget 30
  ```
  **Start method / fair `--llm` comparisons (macOS only).** Pynguin picks the
  `multiprocess` start method per run: `fork` normally, but `spawn` when LLM
  features are active on macOS (`fork()` crashes there once the LLM client has
  initialised Objective-C frameworks). `spawn` is correct but ~5–6× slower for
  C-extension subjects (the subprocess executor re-instruments the SUT per spawn),
  so a with/without-`--llm` comparison on macOS mixes substrates and is **not**
  apples-to-apples. To compare fairly, pin both sides to the same method via the
  `PYNGUIN_MP_START_METHOD={fork,spawn}` env var (must be `spawn` for the `--llm`
  side on macOS):
  ```bash
  PYNGUIN_MP_START_METHOD=spawn poetry run python utils/quick_eval.py run --use-bundled-examples --save nollm.json --budget 60
  PYNGUIN_MP_START_METHOD=spawn poetry run python utils/quick_eval.py run --use-bundled-examples --llm --save llm.json --budget 60
  poetry run python utils/quick_eval.py compare nollm.json llm.json
  ```
  On Linux both LLM and non-LLM use `fork`, so comparisons are fair with no override.

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
