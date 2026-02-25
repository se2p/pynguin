#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""In-process test execution validator."""

import traceback


def run_test(test_code: str, module_under_test):
    """Executes a test function from a string and returns pass/fail.

    Args:
        test_code: A string containing the Python code for the test.
        module_under_test: The module that is being tested.

    Returns:
        A tuple (bool, str) for (pass/fail, message).
    """
    # Provide the tested module under its real name for introspection if needed
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
