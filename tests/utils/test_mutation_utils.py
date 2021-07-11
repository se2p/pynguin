#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock

from pynguin.utils.mutation_utils import alpha_exponent_insertion


def test_alpha_exponent_insertion():
    insert = []
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.2
        alpha_exponent_insertion(insert, lambda: 5)
        assert insert == [5, 5, 5]
