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
"""Defines an abstract test case visitor."""

from abc import ABC, abstractmethod


# pylint: disable=too-few-public-methods
class TestCaseVisitor(ABC):
    """An abstract test case visitor."""

    @abstractmethod
    def visit_default_test_case(self, test_case) -> None:
        """Visit a default test case.

        Args:
            test_case: The test case
        """
