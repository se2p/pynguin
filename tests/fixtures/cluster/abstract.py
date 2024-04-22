#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from abc import ABC
from abc import abstractmethod


class Foo(ABC):
    @abstractmethod
    def foo(self):
        pass
