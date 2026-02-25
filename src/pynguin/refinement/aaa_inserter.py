#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""AAA (Arrange-Act-Assert) marker insertion for test functions."""


def insert_aaa_markers_simple(  # noqa: C901
    test_code: str,
    _focal_line_number: int,
    verbose: bool = True,  # noqa: FBT001, FBT002
) -> str:
    """Simpler version: Just insert AAA comments at appropriate positions.

    This version doesn't try to reparse with AST, just inserts comments
    at strategic points based on line numbers.

    Args:
        test_code: The refined test code
        focal_line_number: Line number of the focal method call
        verbose: Whether to print debug information

    Returns:
        Test code with AAA markers inserted
    """
    try:
        lines = test_code.split("\n")

        # Remove existing AAA markers first
        lines = [line for line in lines if line.strip() not in {"# Arrange", "# Act", "# Assert"}]

        # Find function body start
        func_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("def test_"):
                func_start = i
                break

        if func_start is None:
            return test_code

        # Find actual body start (after def line)
        body_start = func_start + 1
        while body_start < len(lines) and (
            not lines[body_start].strip() or lines[body_start].strip().startswith('"""')
        ):
            body_start += 1

        if body_start >= len(lines):
            return test_code

        if verbose:
            pass

        # Find indices in the modified lines list
        # We need to find where the focal method call is
        focal_idx = None
        first_assert_idx = None

        for i in range(body_start, len(lines)):
            line_lower = lines[i].lower()

            # Look for assert statements
            if line_lower.strip().startswith("assert") and first_assert_idx is None:
                first_assert_idx = i

            # Approximate: if line is roughly at focal_line_number, mark as focal
            # (This is approximate since we removed markers and counts may shift)
            # For now, use: focal is between arrange and first assert

        # If we found an assert, focal should be before it
        if first_assert_idx is not None:
            focal_idx = first_assert_idx - 1
            while focal_idx > body_start and not lines[focal_idx].strip():
                focal_idx -= 1
        else:
            # No assertion found - use all lines as act section
            # Find the last meaningful line
            focal_idx = len(lines) - 1
            while focal_idx > body_start and not lines[focal_idx].strip():
                focal_idx -= 1

        if verbose:
            pass

        # Build new lines with markers
        new_lines = lines[:body_start]  # Imports + function signature + docstring

        # Always add arrange marker
        new_lines.append("    # Arrange")

        # Add arrange section (everything before focal)
        for i in range(body_start, focal_idx):
            new_lines.append(lines[i])

        # Add act marker and focal call
        if focal_idx < len(lines) and focal_idx >= body_start:
            new_lines.append("    # Act")
            new_lines.append(lines[focal_idx])

        # Add assert marker and assertions (if any)
        if first_assert_idx is not None and first_assert_idx < len(lines):
            # Only add Assert marker if there are actual assertions
            new_lines.append("    # Assert")
            for i in range(first_assert_idx, len(lines)):
                new_lines.append(lines[i])
        else:
            # No assertions - just add any remaining lines (shouldn't happen normally)
            for i in range(focal_idx + 1, len(lines)):
                if lines[i].strip():
                    new_lines.append(lines[i])

        result = "\n".join(new_lines)

        if verbose:
            pass

        return result

    except Exception:  # noqa: BLE001
        return test_code
