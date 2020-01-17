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
"""Provides an executor that executes generated sequences."""
import logging
from typing import Tuple, Union, Any

import pynguin.testcase.testcase as tc
from pynguin.utils.proxy import MagicProxy


def _recording_isinstance(
    obj: Any, obj_type: Union[type, Tuple[Union[type, tuple], ...]]
) -> bool:
    if isinstance(obj, MagicProxy):
        # pylint: disable=protected-access
        obj._instance_check_type = obj_type  # type: ignore
    return isinstance(obj, obj_type)


# pylint: disable=too-few-public-methods
class Executor:
    """An executor that executes the generated sequences."""

    _logger = logging.getLogger(__name__)

    def execute(self, test_case: tc.TestCase) -> bool:
        """Executes the statements in a test case.

        The return value indicates, whether or not the execution was successful,
        i.e., whether or not any unexpected exceptions were thrown.

        :param test_case: The test case that shall be executed
        :return: Whether or not the execution was successful
        """
