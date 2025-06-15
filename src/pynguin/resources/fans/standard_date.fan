# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

# Defines dates in multiple formats:
# - YMD separated by "-" (ISO 8601)
# - YMD separated by "/"
# - YMD separated by "."
# - DMY separated by "-"
# - DMY separated by "/"
# - DMY separated by "."
# Limitations: Date or month may be larger than allowed
# Examples: 2014-05-12, 1402/12/4, 2054.05.10, 31-01-1954, 52/4/1902, 10.20.1999

<start> ::= <date>
<date> ::= <date_ymd_dot> | <date_ymd_slash> | <date_ymd_minus> | <date_dmy_dot> | <date_dmy_slash> | <date_dmy_minus>
<two_digit> ::= <digit> <digit>? | "0" <digit>
<year> ::= <digit> <digit> <digit> <digit>
<date_ymd_dot> ::= <year> "." <two_digit> "." <two_digit>
<date_ymd_slash> ::= <year> "/" <two_digit> "/" <two_digit>
<date_ymd_minus> ::= <year> "-" <two_digit> "-" <two_digit>
<date_dmy_dot> ::= <two_digit> "." <two_digit> "." <year>
<date_dmy_slash> ::= <two_digit> "/" <two_digit> "/" <year>
<date_dmy_minus> ::= <two_digit> "-" <two_digit> "-" <year>
