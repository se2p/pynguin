#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
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
