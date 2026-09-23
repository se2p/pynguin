#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


def shadowed(text: str) -> str:
    """Return the given text unchanged.

    Exists so the enclosing package can re-export it under the same name as this
    submodule, reproducing the shadowing scenario of issue #277.
    """
    return text
