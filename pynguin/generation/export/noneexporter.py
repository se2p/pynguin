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
"""Provides a no op exporter."""
import os
from typing import List, Union

from pynguin.generation.export.abstractexporter import AbstractTestExporter
from pynguin.testcase import testcase as tc


# pylint: disable=too-few-public-methods
class NoneExporter(AbstractTestExporter):
    """An exporter, which does basically nothing."""

    def export_sequences(
        self, path: Union[str, os.PathLike], test_cases: List[tc.TestCase]
    ):
        pass
