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
"""Provides classes to record coverage for executed sequences during test generation."""
import logging
import os
import sys


# pylint: disable=too-few-public-methods
class CoverageRecorder:
    """Records coverage for executed sequences."""

    _logger = logging.getLogger(__name__)


# pylint: disable=attribute-defined-outside-init
class HiddenPrints:
    """A context-managing class that binds stdout to a null device."""

    def __enter__(self) -> None:
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, mode="w")

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        sys.stdout.close()
        sys.stdout = self._original_stdout
