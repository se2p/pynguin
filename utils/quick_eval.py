# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
r"""Quick evaluation script for Pynguin — fast local coverage feedback.

This is a thin entry point; the implementation lives in the :mod:`_quick_eval`
package next to this file. Run ``python utils/quick_eval.py --help`` for usage.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the sibling _quick_eval package importable when run as a script.
_UTILS_DIR = Path(__file__).resolve().parent
if str(_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(_UTILS_DIR))

# Load environment variables before anything reads them. The LLM credentials
# (LLM_API_KEY / LLM_BASE_URL / LLM_MODEL) live in the pynguin-experiments
# checkout; a local .env in this repo root (or the real environment) takes precedence.
try:
    import dotenv

    _repo_root = _UTILS_DIR.parent
    dotenv.load_dotenv(_repo_root.parent / "pynguin-experiments" / ".env", override=False)
    dotenv.load_dotenv(_repo_root / ".env", override=True)
except ImportError:
    pass

from _quick_eval.cli import main  # noqa: E402, PLC2701

if __name__ == "__main__":
    sys.exit(main())
