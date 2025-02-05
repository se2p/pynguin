#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


def print_dunder(obj):
    """Prints all dunder (__) attributes of an object row by row.

    :param obj: The object to inspect.
    """
    for attr in dir(obj):
        if attr.startswith("__"):
            print(f"{attr}: {getattr(obj, attr)}")  # noqa: T201
