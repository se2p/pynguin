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
"""Provides a wrapping string type to capture already observed strings."""
from typing import Any, List, Optional, Text, Tuple, Union


class String(str):
    """Provides a wrapping string type to capture already observed strings."""

    observed: List[str] = []

    def __eq__(self, other: Any) -> bool:
        String._maybe_record(other)
        return super().__eq__(other)

    # pylint: disable=useless-super-delegation
    def __hash__(self) -> int:
        return super().__hash__()

    def startswith(
        self,
        prefix: Union[Text, Tuple[Text, ...]],
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> bool:
        String._maybe_record(prefix)
        return super().startswith(prefix, start, end)

    def endswith(
        self,
        suffix: Union[Text, Tuple[Text, ...]],
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> bool:
        String._maybe_record(suffix)
        return super().endswith(suffix, start, end)

    @staticmethod
    def _maybe_record(value: Any) -> None:
        if (
            isinstance(value, str)
            and hasattr(value, "__str__")
            and value.__str__() not in String.observed
        ):
            String.observed.append(value.__str__())
