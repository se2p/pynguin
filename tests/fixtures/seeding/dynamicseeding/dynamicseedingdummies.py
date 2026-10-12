#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Dummy method for testing adding a value
def compare_op_dummy(x, y):
    if x == y:
        return 0
    else:
        return 1


# Dummy method for testing a comparison inside an inlined comprehension
def comprehension_compare_dummy(values, y):
    return [x for x in values if x == y]
