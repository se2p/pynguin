#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Simulate a large test cluster.
from dataclasses import dataclass


for i in range(100):
    exec(
        f"""
class Foo{i}:
    attribute_{i} = {i}

    def __init__(self):
        pass


class Bar{i}:
    attribute_{i} = {100 - i}

    def __init__(self):
        pass"""
    )


@dataclass
class Square:
    a: float


@dataclass
class Circle:
    r: float


@dataclass
class Triangle:
    h: float
    b: float


class Invoice:
    def __init__(self):
        self.elements = []

    def add_item(self, item):
        self.elements.append(item)


class InvoiceElement:
    def __init__(self, price, amount):
        self._price = price
        self._amount = amount

    def get_total(self):
        return self._price * self._amount
