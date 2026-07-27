#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Crash minimization and safety helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pynguin.configuration as config
import pynguin.ga.postprocess as pp
from pynguin.utils.exceptions import MinimizationFailureError
from pynguin.utils.statistics import stats as stat
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import pynguin.testcase.testcase as tc
    from pynguin.testcase.subprocess_executor import SubprocessTestCaseExecutor

_LOGGER = logging.getLogger(__name__)


def minimize_and_safe(
    executor: SubprocessTestCaseExecutor,
    test_case: tc.TestCase,
    exit_code: int | None,
) -> None:
    """Minimize a crashing test case and save it.

    Args:
        executor: The executor driving the execution
        test_case: The crashing test case
        exit_code: The exit code of the crash
    """
    # Calculate hash before to ensure the same hash for minimized and non-minimized one
    test_case_hash = str(hash(test_case))

    # Store hash and track CrashRevealingSize output variable if new hash
    crash_revealing_count = executor.register_crash_revealing_hash(test_case_hash)
    if crash_revealing_count is not None:
        stat.track_output_variable(
            RuntimeVariable.CrashRevealingSize,
            crash_revealing_count,
        )

    safe_crash_test(test_case, hash_str=test_case_hash)
    try:
        minimized_test_case = minimize(executor, test_case, exit_code)
        safe_crash_test(minimized_test_case, hash_str=test_case_hash, minimized=True)
    except MinimizationFailureError:
        _LOGGER.warning("Minimized the test case failed. Not storing minimized test case.")


def minimize(
    executor: SubprocessTestCaseExecutor,
    test_case: tc.TestCase,
    exit_code: int | None,
) -> tc.TestCase:
    """Minimize a crashing test case using the postprocess minimizer.

    Args:
        executor: The executor driving the execution
        test_case: The test case to minimize
        exit_code: The expected exit code of the crash

    Returns:
        The minimized test case

    Raises:
        MinimizationFailureError: If the minimized test case does not crash anymore
    """
    test_case_to_minimize = test_case.clone()
    minimizer = pp.CrashPreservingMinimizationVisitor(executor)
    # The per-test-case minimisation visitors are invoked directly.
    minimizer.visit_default_test_case(test_case_to_minimize)

    # Verify that the minimized test case still crashes
    new_exit_code = executor.execute_with_exit_code(test_case_to_minimize)
    if exit_code == new_exit_code:
        _LOGGER.info(
            "Minimized crashed test case from %d to %d statements",
            test_case.size(),
            test_case_to_minimize.size(),
        )
        return test_case_to_minimize
    raise MinimizationFailureError(
        "Minimizing the test case failed, as it does not cause the same crash anymore."
    )


def safe_crash_test(
    test_case: tc.TestCase,
    hash_str: str | None = None,
    *,
    minimized: bool = False,
) -> None:
    """Save a crashing test case to the configured crash path.

    Args:
        test_case: The test case to save
        hash_str: The hash identifying the test case
        minimized: Whether the test case is minimized
    """
    postfix = "_minimized" if minimized else ""
    if hash_str is None:
        hash_str = str(hash(test_case))
    output_path = (
        config.configuration.test_case_output.crash_path
        or config.configuration.test_case_output.output_path
    )
    target_file = Path(output_path).resolve() / f"crash_test_{hash_str}{postfix}.py"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(test_case.to_code())
