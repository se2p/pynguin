# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

# Defines a color hex code pattern. Starts with "#" followed by six hex digits
# Examples: #A3C1D1, #FF5733, #123ABC

<start> ::= <colour>
<colour> ::= "#" <hexdigit> <hexdigit> <hexdigit> <hexdigit> <hexdigit> <hexdigit>
