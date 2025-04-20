#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from tests.fixtures.cluster.complex_dependency import SomeOtherType


class SomeClass:
    def __init__(self, arg0: SomeOtherType):
        pass
