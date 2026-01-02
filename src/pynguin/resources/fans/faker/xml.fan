# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

from faker import Faker

fake = Faker()

include("../xml.fan")

<start> ::= <xml_doc> := fake.xml(nb_elements=3)
