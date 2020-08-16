#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
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
