# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

# Defines words separated by either ",", ":", ";" or "|".
# Examples: word1,word2 test:example foo;bar;word hello|world

<start> ::= <comma_delimited> | <colon_delimited> | <semi_colon_delimited> | <pipe_delimited>
<comma_delimited> ::= <word> | <comma_delimited> "," <word>
<colon_delimited> ::= <word> | <colon_delimited> ":" <word>
<semi_colon_delimited> ::= <word> | <semi_colon_delimited> ";" <word>
<pipe_delimited> ::= <word> | <pipe_delimited> "|" <word>
<word> ::= <alphanum>+
