#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pytest

import pynguin.configuration as config
from pynguin.generation.algorithms.randoopy.mypytypehandlermixin import (
    MyPyTypeHandlerMixin,
)
from pynguin.setup.testclustergenerator import TestClusterGenerator


@pytest.fixture
def mixin():
    return MyPyTypeHandlerMixin()


def test_retrieve_test_case_type_info_mypy(mixin, short_test_case):
    module_name = "tests.fixtures.accessibles.accessible"
    config.INSTANCE.module_name = module_name
    test_cluster = TestClusterGenerator(module_name).generate_cluster()
    mixin.retrieve_test_case_type_info_mypy(short_test_case, test_cluster)


def test_retrieve_test_suite_type_info_mypy(mixin, short_test_case):
    module_name = "tests.fixtures.accessibles.accessible"
    config.INSTANCE.module_name = module_name
    test_cluster = TestClusterGenerator(module_name).generate_cluster()
    mixin.retrieve_test_suite_type_info_mypy([short_test_case], test_cluster)
