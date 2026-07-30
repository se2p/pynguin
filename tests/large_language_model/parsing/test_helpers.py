#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the helpers module."""

import ast

from pynguin.large_language_model.parsing.helpers import add_line_numbers



def test_add_line_numbers():
    code_as_string: str = "def test_function(x): \n if x > 0: \n  return x \n else: \n  return -x"
    result = add_line_numbers(code_as_string)
    expected = (
        "1: def test_function(x): \n2:  if x > 0: \n3:   return x \n4:  else: \n5:   return -x"
    )
    assert result == expected
