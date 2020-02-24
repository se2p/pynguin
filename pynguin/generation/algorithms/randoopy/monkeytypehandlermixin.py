# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""A mixin handling the execution of a test case with MonkeyType."""
import logging
from typing import List

import pynguin.testcase.testcase as tc
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.execution.monkeytypeexecutor import MonkeyTypeExecutor


class MonkeyTypeHandlerMixin:
    """A mixin handling the execution of a test case with MonkeyType."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        self._monkey_type_executor = MonkeyTypeExecutor()

    def handle_test_case(self, test_case: tc.TestCase, _: TestCluster):
        """Handles a test case, i.e., executes it and propagates the results back.

        :param test_case:
        :param test_cluster:
        :return:
        """
        self._monkey_type_executor.execute(test_case)

    def handle_test_suite(self, test_suite: List[tc.TestCase], _: TestCluster):
        """Handles a test suite, i.e., executes it and propagates the results back.

        :param test_suite:
        :param test_cluster:
        :return:
        """
        self._monkey_type_executor.execute_test_suite(test_suite)
