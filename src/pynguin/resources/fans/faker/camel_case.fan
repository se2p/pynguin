# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

from faker import Faker

fake = Faker()

include("../camel_case.fan")

<camel_word> ::= <ascii_uppercase_letter><ascii_lowercase_letter>* := fake.word().capitalize()
