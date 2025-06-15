# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

# Defines a CamelCase patters where every words starts with an uppercase letter
# followed by lowercase letters.
# Examples: HelloWorld, FooBarTest

<start> ::= <camel_case>
<camel_case> ::= <camel_word>+
<camel_word> ::= <ascii_uppercase_letter><ascii_lowercase_letter>+
