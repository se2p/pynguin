#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from abc import abstractmethod


class Prompt:
    def __init__(self, module_code, module_path):
        self.module_code = module_code
        self.module_path = module_path

    @abstractmethod
    def build_prompt(self) -> str:
        pass
