#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from tests.fixtures.cluster.dependency import SomeArgumentType


class ConstructMeWithDependency:
    def __init__(self, x: SomeArgumentType) -> None:
        pass
