#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from tests.fixtures.cluster.complex_dependency import SomeOtherType


class SomeClass:
    def __init__(self, arg0: SomeOtherType):
        pass
