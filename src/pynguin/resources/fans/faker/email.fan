# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

from faker import Faker

fake = Faker()

include("../email.fan")

<start> ::= <email> := fake.email()
