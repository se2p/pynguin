#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pytest

import pynguin.configuration as config
from pynguin.generation.algorithms.randoopy.monkeytypehandlermixin import (
    MonkeyTypeHandlerMixin,
)
from pynguin.setup.testclustergenerator import TestClusterGenerator


@pytest.fixture
def mixin():
    return MonkeyTypeHandlerMixin()


def test_execute_test_case_monkey_type(mixin, short_test_case):
    module_name = "tests.fixtures.accessibles.accessible"
    config.INSTANCE.module_name = module_name
    test_cluster = TestClusterGenerator(module_name).generate_cluster()
    mixin.execute_test_case_monkey_type([short_test_case], test_cluster)


def test_full_name_for_callable_without_module(mixin):
    callable_ = object.__init__
    result = mixin._full_name(callable_)
    assert result == "callable"
