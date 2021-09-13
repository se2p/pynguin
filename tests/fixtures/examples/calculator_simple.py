#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


class Calculator:
    results = []

    def __init__(self):
        self.amount_calculation = 0

    def add(self, a: float, b: float) -> float:
        self.amount_calculation += 1
        ret = a + b
        Calculator.results.append(ret)
        return ret

    def sub(self, a: float, b: float) -> float:
        self.amount_calculation += 1
        ret = a - b
        Calculator.results.append(ret)
        return ret

    def mult(self, a: float, b: float) -> float:
        self.amount_calculation += 1
        ret = a * b
        Calculator.results.append(ret)
        return ret

    def div(self, a: float, b: float) -> float:
        self.amount_calculation += 1
        ret = a / b
        Calculator.results.append(ret)
        return ret

    def __eq__(self, other) -> bool:
        if isinstance(other, Calculator):
            return self.amount_calculation == other.amount_calculation
        return False
