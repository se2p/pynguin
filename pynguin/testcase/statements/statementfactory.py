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
"""Provides a factory that creates a statement instance for a callable."""
from inspect import Parameter
from typing import Callable, List, Tuple, Any

import pynguin.testcase.testcase as tc
import pynguin.testcase.statements.statement as stmt


# pylint: disable=too-few-public-methods
class StatementFactory:
    """A factory that creates a statement instance for a callable."""

    @classmethod
    def create_statement(
        cls,
        test_case: tc.TestCase,
        callable_: Callable,
        values: List[Tuple[str, Parameter, Any]],
    ) -> stmt.Statement:
        """Creates a statement for a callable.

        :param test_case: The test case for which we generate the statement
        :param callable_: The callable for which we generate the statement
        :param values: The list of parameter values
        :return: A statement representing this method call
        """
