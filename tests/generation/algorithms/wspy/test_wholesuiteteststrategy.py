#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


@pytest.fixture
def executor():
    return MagicMock(TestCaseExecutor)


def test_generate_sequences(executor):
    # TODO(fk) TEST ME!
    pass
