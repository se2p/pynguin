#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Regression tests for ``extract_python_code`` fence/prose handling."""

from pynguin.large_language_model.client import extract_python_code


def test_python_fenced_block_is_extracted():
    assert extract_python_code("Here:\n```python\nx = 1\n```") == "x = 1\n"


def test_plain_fenced_block_is_extracted():
    assert extract_python_code("```\ny = 2\n```") == "y = 2\n"


def test_py_fence_language_token_not_leaked():
    """A ```py fence must not leak the ``py`` language token into the code (#2)."""
    result = extract_python_code("```py\nz = 3\n```")
    assert result == "z = 3\n"
    assert "py" not in result.splitlines()[0]


def test_alternate_language_token_not_leaked():
    """An arbitrary language identifier after the fence is stripped (#2)."""
    result = extract_python_code("```python3\nvalue = 42\n```")
    assert result == "value = 42\n"


def test_prose_without_fence_returns_empty_string():
    """Non-Python prose without any fence must yield '' rather than prose (#3)."""
    assert not extract_python_code("This is just text, no code here.")


def test_raw_valid_python_without_fence_is_returned():
    """Valid Python without a fence is still accepted as code (#3)."""
    assert extract_python_code("a = 1\nb = 2") == "a = 1\nb = 2"


def test_empty_input_returns_empty_string():
    assert not extract_python_code("")
    assert not extract_python_code(None)
