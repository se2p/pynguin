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
"""Provides a proxy that wraps objects to inspect them."""
# pylint: disable=too-few-public-methods
from typing import Any


class Proxy:
    """A transparent object proxy for (almost) all object.

    This code is taken from an ActiveState Code Recipe, which can be found at
    https://code.activestate.com/recipes/496741-object-proxying/.

    For further information on proxying types see, e.g.,
    - https://rszalski.github.io/magicmethods/#comparisons
    - https://theorangeduck.com/page/tracing-functions-python
    """

    __slots__ = ["_obj", "__weakref__"]

    def __init__(self, obj: Any) -> None:
        object.__setattr__(self, "_obj", obj)


class MagicProxy(Proxy):
    """A proxy that captures all method calls to the wrapped object."""

    __slots__ = ["_obj", "_weakref", "_hasError", "_errorCode", "_instance_check_type"]

    def __init__(self, obj: Any) -> None:
        super().__init__(obj)
        object.__setattr__(self, "_hasError", False)
        object.__setattr__(self, "_errorCode", False)
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_instance_check_type", None)
