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
"""A collection of utility functions."""
import inspect


def get_members_from_module(module):
    """Returns the members from a module.

    Args:
        module: A module

    Returns:
        A list of types that are members of the module
    """

    def filter_members(member):
        return (
            inspect.isclass(member)
            or inspect.isfunction(member)
            or inspect.ismethod(member)
        ) and member.__module__ == module.__name__

    members = inspect.getmembers(module, filter_members)
    return members
