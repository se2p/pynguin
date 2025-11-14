# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

from faker import Faker

fake = Faker()

include("../ipv4.fan")

<start> ::= <ipv4> := fake.ipv4()
