#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""In-process test execution validator."""

import signal
import sys
import textwrap
import threading
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pynguin.configuration as config


class TestExecutionTimeoutError(BaseException):
    """Raised when a generated test exceeds its execution time limit.

    Inherits from :class:`BaseException` rather than :class:`Exception` so that a
    ``try: ... except Exception:`` block inside the executed test code cannot swallow
    it -- the whole point is that a runaway test must not be able to keep running.
    """


def resolve_timeout(timeout: float | None) -> float:
    """Resolve an explicit timeout against the configured per-test execution timeout.

    Args:
        timeout: An explicit timeout in seconds, or *None* to use the configured
            ``stopping.maximum_test_execution_timeout``.

    Returns:
        The timeout in seconds; values <= 0 disable the limit.
    """
    if timeout is not None:
        return timeout
    return config.configuration.stopping.maximum_test_execution_timeout


@contextmanager
def time_limit(seconds: float) -> Iterator[None]:
    """Abort the wrapped block with a :class:`TestExecutionTimeoutError` after *seconds*.

    Uses ``SIGALRM``, which is only available on POSIX and only settable from the main
    thread; the limit is silently skipped when either precondition does not hold, or
    when *seconds* is <= 0.

    Note:
        Signal handlers only run between bytecode instructions, so a block spending its
        time inside a single long-running C call (a pathological regular-expression
        match, say) is only interrupted once that call returns.

    Args:
        seconds: The time limit in seconds; <= 0 disables the limit.

    Yields:
        Nothing; the wrapped block runs under the time limit.
    """
    can_alarm = (
        seconds > 0
        and hasattr(signal, "SIGALRM")
        and threading.current_thread() is threading.main_thread()
    )
    if not can_alarm:
        yield
        return

    def _handler(_signum, _frame):
        raise TestExecutionTimeoutError(f"Execution exceeded the {seconds}s time limit")

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


def _ensure_module_package_on_path(module_under_test) -> str | None:
    """Add the top-level package root to ``sys.path`` if not already present.

    When the generated test contains ``import test_subject.string_utils as
    module_0``, the **parent** of the ``test_subject`` package must be on
    ``sys.path`` for the import to succeed inside ``exec()``.

    Returns:
        The path that was added, or *None* if nothing was added.
    """
    module_file = getattr(module_under_test, "__file__", None)
    if not module_file:
        return None

    # Walk up from the module file through any __init__.py-bearing
    # ancestors to find the top-level package root.
    pkg_dir = Path(module_file).resolve().parent
    while (pkg_dir.parent / "__init__.py").exists():
        pkg_dir = pkg_dir.parent

    # The directory *containing* the top-level package
    root = str(pkg_dir.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
        return root
    return None


def run_test(test_code: str, module_under_test, timeout: float | None = None):
    """Executes a test function from a string and returns pass/fail.

    Args:
        test_code: A string containing the Python code for the test.
        module_under_test: The module that is being tested.
        timeout: Maximum execution time in seconds; *None* uses the configured
            ``stopping.maximum_test_execution_timeout``, values <= 0 disable the limit.

    Returns:
        A tuple (bool, str) for (pass/fail, message).
    """
    # Provide the tested module under its real name for introspection if needed
    _ensure_module_package_on_path(module_under_test)
    scope = {module_under_test.__name__: module_under_test}

    try:
        # Extract the function name
        function_name = ""
        for line in test_code.split("\n"):
            if line.startswith("def "):
                function_name = line.split("def ")[1].split("(")[0]
                break

        if not function_name:
            return False, "Could not find function name in test code."

        # Clean up code indentation before execution
        cleaned_code = textwrap.dedent(test_code.strip())
        with time_limit(resolve_timeout(timeout)):
            # Executing the generated test code is the core purpose of this validator.
            exec(cleaned_code, scope)  # noqa: S102
            scope[function_name]()  # Call the test function

        return True, "Test passed."
    except TestExecutionTimeoutError as e:
        return False, f"TimeoutError: {e}"
    except AssertionError as e:
        return False, f"AssertionError: {e}\n{traceback.format_exc()}"
    except BaseException as e:  # noqa: BLE001
        # Catch all exceptions including pytest.fail (which raises Failed, a BaseException)
        return False, f"Exception: {e}\n{traceback.format_exc()}"
