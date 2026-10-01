#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""In-process test execution validator."""

import ast
import sys
import textwrap
import traceback
from pathlib import Path

from pynguin.utils.timeout import TestExecutionTimeoutError, resolve_timeout, time_limit

#: Message prefix used when a ``@pytest.mark.xfail(strict=True)`` test unexpectedly
#: passes (pytest reports this as ``XPASS(strict)``, which is a *failure*).
XPASS_STRICT_MESSAGE = "XPASS(strict): test is marked xfail(strict=True) but passed."


def _xfail_marker_of(node: ast.FunctionDef) -> tuple[bool, bool]:
    """Return ``(is_xfail, is_strict)`` for the decorators of *node*."""
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute) and target.attr == "xfail":
            strict = False
            if isinstance(decorator, ast.Call):
                strict = any(
                    kw.arg == "strict"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                    for kw in decorator.keywords
                )
            return True, strict
    return False, False


def _find_xfail_marker(test_code: str, function_name: str) -> tuple[bool, bool]:
    """Detect a ``@pytest.mark.xfail`` decorator on the called test function.

    Args:
        test_code: The full test source (imports + one decorated function).
        function_name: Name of the function that will be executed.

    Returns:
        A tuple ``(is_xfail, is_strict)``.  ``is_strict`` is only meaningful when
        ``is_xfail`` is *True*.  Returns ``(False, False)`` when the source cannot
        be parsed or the function carries no ``xfail`` marker.
    """
    try:
        tree = ast.parse(textwrap.dedent(test_code.strip()))
    except SyntaxError:
        return False, False

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return _xfail_marker_of(node)
    return False, False


def collect_test_functions(test_code: str) -> list[tuple[str, bool, bool]]:
    """Return ``(name, is_xfail, is_strict)`` for each top-level ``test_*`` function.

    Args:
        test_code: The test source (imports + one or more test functions).

    Returns:
        The test functions in source order, or an empty list if the code cannot be
        parsed.
    """
    try:
        tree = ast.parse(textwrap.dedent(test_code.strip()))
    except SyntaxError:
        return []
    return [
        (node.name, *_xfail_marker_of(node))
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]


def _call_and_capture(func) -> tuple[bool, str]:
    """Call *func* and return ``(raised, message)``; timeouts are propagated."""
    try:
        func()
    except TestExecutionTimeoutError:
        raise
    except AssertionError as e:
        return True, f"AssertionError: {e}\n{traceback.format_exc()}"
    except BaseException as e:  # noqa: BLE001
        # Catch all exceptions including pytest.fail (which raises Failed, a BaseException)
        return True, f"Exception: {e}\n{traceback.format_exc()}"
    return False, "Test passed."


def call_test_functions(scope: dict, tests: list[tuple[str, bool, bool]]) -> None:
    """Call each test function of *scope* individually, honouring ``xfail`` markers.

    Each test runs on its own, so an ``xfail`` test that raises as expected neither
    aborts the remaining tests nor counts as a failure.  The first real failure is
    raised: an exception from a regular test, or an ``AssertionError`` when a
    ``xfail(strict=True)`` test passes (pytest's ``XPASS(strict)``).

    Args:
        scope: The globals the test code was executed in.
        tests: The tests to call, as returned by :func:`collect_test_functions`.

    Raises:
        AssertionError: If a strict ``xfail`` test unexpectedly passes.
    """
    for name, is_xfail, is_strict in tests:
        func = scope.get(name)
        if not callable(func):
            continue
        if not is_xfail:
            func()
        elif not _call_and_capture(func)[0] and is_strict:
            raise AssertionError(XPASS_STRICT_MESSAGE)


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

    # Extract the function name
    function_name = ""
    for line in test_code.split("\n"):
        if line.startswith("def "):
            function_name = line.split("def ")[1].split("(")[0]
            break

    if not function_name:
        return False, "Could not find function name in test code."

    is_xfail, is_strict = _find_xfail_marker(test_code, function_name)

    # Clean up code indentation before execution
    cleaned_code = textwrap.dedent(test_code.strip())

    def _exec_and_call() -> None:
        # Executing the generated test code is the core purpose of this validator.
        exec(cleaned_code, scope)  # noqa: S102
        scope[function_name]()  # Call the test function

    try:
        with time_limit(resolve_timeout(timeout)):
            raised, message = _call_and_capture(_exec_and_call)
    except TestExecutionTimeoutError as e:
        # A timeout is a hard failure regardless of any xfail marker.
        return False, f"TimeoutError: {e}"

    # Map the raw outcome to the real pytest result, honouring xfail markers so
    # the caller's notion of pass/fail matches what pytest would report.
    if is_xfail:
        if raised:
            # The body failed as the xfail marker expects -> pytest reports xfail (pass).
            return True, "xfail: test failed as expected."
        if is_strict:
            # Body passed but the test is marked strict -> pytest reports XPASS(strict).
            return False, XPASS_STRICT_MESSAGE
        # Non-strict xfail that passes is only a warning, not a failure.
        return True, "Test passed (xpass)."

    return (False, message) if raised else (True, message)
