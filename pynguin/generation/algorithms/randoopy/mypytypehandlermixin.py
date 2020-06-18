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
"""A mixin handling the execution of a test case with mypy."""
import logging
from typing import List

import pynguin.testcase.testcase as tc
from pynguin.setup.testcluster import TestCluster


class MyPyTypeHandlerMixin:
    """A mixin handling the execution of a test case with mypy."""

    _logger = logging.getLogger(__name__)

    def retrieve_test_case_type_info_mypy(
        self, test_case: tc.TestCase, test_cluster: TestCluster
    ) -> None:
        """Retrieve type information from a test case using mypy.

        Args:
            test_case: The test case
            test_cluster: The underlying test cluster
        """

    def retrieve_test_suite_type_info_mypy(
        self, test_suite: List[tc.TestCase], test_cluster: TestCluster
    ) -> None:
        """Retrieve type information from a test suite using mypy.

        Args:
            test_suite: The test suite
            test_cluster: The underlying test cluster
        """
