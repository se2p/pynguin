# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

from faker import Faker

fake = Faker()

include("../csv.fan")

<start> ::= <csv> := fake.csv(num_rows=3)
<value_char> ::= r"[a-zA-Z0-9 \n.,]"
