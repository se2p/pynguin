#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest import mock
from unittest.mock import MagicMock

from pynguin.utils.mutation_utils import alpha_exponent_insertion


def test_alpha_exponent_insertion():
    insert = []
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.2
        with mock.patch("pynguin.utils.randomness.next_int") as int_mock:
            int_mock.side_effect = 1, 0
            func = MagicMock()
            func.side_effect = [0, 1, 2]
            alpha_exponent_insertion(insert, func)
            assert insert == [2, 0, 1]


def test_alpha_exponent_insertion_none():
    insert = []
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.2
        func = MagicMock()
        func.return_value = None
        alpha_exponent_insertion(insert, func)
        assert insert == []
