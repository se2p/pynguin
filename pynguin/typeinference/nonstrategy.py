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
"""Provides a strategy that never does any type inference."""
from typing import Callable

from pynguin.typeinference.strategy import TypeInferenceStrategy, InferredMethodType


# pylint: disable=too-few-public-methods
class NoTypeInferenceStrategy(TypeInferenceStrategy):
    """Provides a strategy that never does any type inference."""

    def infer_type_info(self, method: Callable) -> InferredMethodType:
        return InferredMethodType()
