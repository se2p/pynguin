#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""In-process test execution validator."""

import sys
import traceback
from pathlib import Path


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


def run_test(test_code: str, module_under_test):
    """Executes a test function from a string and returns pass/fail.

    Args:
        test_code: A string containing the Python code for the test.
        module_under_test: The module that is being tested.

    Returns:
        A tuple (bool, str) for (pass/fail, message).
    """
    # Provide the tested module under its real name for introspection if needed
    _ensure_module_package_on_path(module_under_test)
    scope = {module_under_test.__name__: module_under_test}
    import textwrap  # noqa: PLC0415

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
        # Execute the code and the function
        exec(cleaned_code, scope)  # noqa: S102
        scope[function_name]()  # Call the test function

        return True, "Test passed."
    except AssertionError as e:
        return False, f"AssertionError: {e}\n{traceback.format_exc()}"
    except BaseException as e:  # noqa: BLE001
        # Catch all exceptions including pytest.fail (which raises Failed, a BaseException)
        return False, f"Exception: {e}\n{traceback.format_exc()}"
