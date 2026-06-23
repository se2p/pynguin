#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""AAA (Arrange-Act-Assert) marker insertion for test functions."""

_MARKERS = {"# Arrange", "# Act", "# Assert"}


def _strip_existing_markers(lines: list[str]) -> list[str]:
    """Drop any pre-existing AAA marker lines so insertion stays idempotent."""
    return [line for line in lines if line.strip() not in _MARKERS]


def _find_function_start(lines: list[str]) -> int | None:
    """Return the index of the ``def test_...`` line, or ``None`` if absent."""
    for index, line in enumerate(lines):
        if line.strip().startswith("def test_"):
            return index
    return None


def _find_body_start(lines: list[str], func_start: int) -> int:
    """Return the index of the first executable line after signature/docstring."""
    body_start = func_start + 1
    in_docstring = False
    while body_start < len(lines):
        stripped = lines[body_start].strip()
        if not stripped:
            body_start += 1
            continue
        if stripped.startswith('"""'):
            # A line that both opens and closes (>= 2 quotes) or that closes an
            # open docstring terminates it; otherwise it opens one.
            in_docstring = not (in_docstring or stripped.count('"""') >= 2)
            body_start += 1
            continue
        if in_docstring:
            if '"""' in stripped:
                in_docstring = False
            body_start += 1
            continue
        break
    return body_start


def _find_first_assert(lines: list[str], body_start: int) -> int | None:
    """Return the index of the first ``assert`` line at or after *body_start*."""
    for index in range(body_start, len(lines)):
        if lines[index].strip().lower().startswith("assert"):
            return index
    return None


def _resolve_focal_index(
    lines: list[str],
    body_start: int,
    first_assert_idx: int | None,
    focal_line_number: int,
) -> int:
    """Pick the focal (Act) line index, honouring the caller hint when valid."""
    candidate = focal_line_number - 1  # convert 1-based hint to 0-based index
    if (
        focal_line_number > 0
        and body_start <= candidate < len(lines)
        and lines[candidate].strip()
        and (first_assert_idx is None or candidate < first_assert_idx)
    ):
        return candidate

    # Fallback heuristic: last non-blank line before the first assert.
    focal_idx = first_assert_idx - 1 if first_assert_idx is not None else len(lines) - 1
    while focal_idx > body_start and not lines[focal_idx].strip():
        focal_idx -= 1
    return focal_idx


def _build_with_markers(
    lines: list[str],
    body_start: int,
    focal_idx: int,
    first_assert_idx: int | None,
) -> str:
    """Reassemble the test body with ``# Arrange``/``# Act``/``# Assert`` markers."""
    new_lines = lines[:body_start]

    new_lines.append("    # Arrange")
    new_lines.extend(lines[body_start:focal_idx])

    if body_start <= focal_idx < len(lines):
        new_lines.append("    # Act")
        new_lines.append(lines[focal_idx])

    if first_assert_idx is not None and first_assert_idx < len(lines):
        # Preserve lines between the Act line and the first assertion
        # (e.g. capturing a return value into a variable).
        new_lines.extend(lines[focal_idx + 1 : first_assert_idx])
        new_lines.append("    # Assert")
        new_lines.extend(lines[first_assert_idx:])
    else:
        new_lines.extend(line for line in lines[focal_idx + 1 :] if line.strip())

    return "\n".join(new_lines)


def insert_aaa_markers_simple(
    test_code: str,
    focal_line_number: int,
) -> str:
    """Insert deterministic AAA markers into a test function.

    Uses *focal_line_number* (1-based, relative to the code snippet) when
    it points to a valid line; otherwise falls back to the heuristic
    "last non-blank line before the first assert".

    Args:
        test_code: The refined test code.
        focal_line_number: 1-based line number of the focal method call.

    Returns:
        Test code with ``# Arrange``, ``# Act``, ``# Assert`` markers.
    """
    try:
        lines = _strip_existing_markers(test_code.split("\n"))

        func_start = _find_function_start(lines)
        if func_start is None:
            return test_code

        body_start = _find_body_start(lines, func_start)
        if body_start >= len(lines):
            return test_code

        first_assert_idx = _find_first_assert(lines, body_start)
        focal_idx = _resolve_focal_index(lines, body_start, first_assert_idx, focal_line_number)
        return _build_with_markers(lines, body_start, focal_idx, first_assert_idx)
    except (IndexError, ValueError):
        return test_code
