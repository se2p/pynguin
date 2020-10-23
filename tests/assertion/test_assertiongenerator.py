#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.assertion.assertiongenerator as ag


def test_init():
    executor = MagicMock()
    ag.AssertionGenerator(executor)
    assert executor.add_observer.call_count == 2


def test_add_assertions():
    executor = MagicMock()
    trace = MagicMock()
    result = MagicMock(output_traces={"": trace})
    executor.execute.return_value = result
    generator = ag.AssertionGenerator(executor)
    test_case = MagicMock()
    generator.add_assertions(test_case)
    trace.add_assertions.assert_called_with(test_case)
