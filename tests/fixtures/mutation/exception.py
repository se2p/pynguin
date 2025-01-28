#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
def foo() -> None:
    alist = [1, 2]
    # Fails on mutation
    if len(alist) != 2:
        raise ValueError()
    return None
