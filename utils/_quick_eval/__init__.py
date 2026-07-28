# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Internal package for the quick_eval developer tool.

Split out of the former monolithic ``utils/quick_eval.py`` into focused modules:

* :mod:`.tasks`     - discover the modules to run (bundled examples / rundefinition XML)
* :mod:`.runner`    - invoke Pynguin on a module and collect its result
* :mod:`.stats`     - the :class:`~._quick_eval.stats.ModuleResult` model + statistics.csv parsing
* :mod:`.report`    - Rich tables, deltas and JSON serialisation
* :mod:`.worktree`  - git-worktree / cached-venv management for baseline comparison
* :mod:`.commands`  - the ``run`` / ``compare`` / ``compare-branch`` subcommand bodies
* :mod:`.cli`       - argparse wiring and dispatch

The public entry point remains ``utils/quick_eval.py`` so ``python utils/quick_eval.py``
keeps working unchanged.
"""

from __future__ import annotations

import logging

from rich.console import Console

_LOG = logging.getLogger("quick_eval")
console = Console()
err_console = Console(stderr=True)

# Wall-clock limit for a single Pynguin run, independent of --maximum-search-time.
# A run spends substantial time *after* the search budget is exhausted — chiefly
# MUTATION_ANALYSIS assertion generation, which scales with the number of mutants
# and can take minutes on its own. The limit only exists to kill genuinely hung
# runs, so it is deliberately generous rather than derived from the budget.
DEFAULT_TIMEOUT_S = 3600
