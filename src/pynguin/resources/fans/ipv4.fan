# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

# Describes an IPv4 address according to RFC 791.
# Limitations: A block may be larger than allowed maximum of 255
# Examples: 1.20.31.4, 127.0.0.1, 500.421.100.4

<start> ::= <ipv4>
<ipv4> ::= <block> "." <block> "." <block> "." <block>
<block> ::= <digit> | <digit> <digit> | <digit> <digit> <digit>
