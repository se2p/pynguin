# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

# Describes a numeric literal. It allows either intergers or floating-point
# numbers. All numeric literals can be signed with "+" or "-" or have no sign.
# Examples: 1283, +4953, -12.59921, +.424

<start> ::= <signed_number> | <unsigned_number>
<signed_number> ::= "+" <number> | "-" <number>
<unsigned_number> ::= <number>
<number> ::= <digits> | <float>
<float> ::= <digits> "." <digits> | "." <digits> | <digits>
<digits> ::= <digit>+
