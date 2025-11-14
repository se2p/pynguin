# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

# Defines a simplified CSV file format. The file consists of a header row
# followed by one or more data records. Each record contains one or more
# comma separated values.
# Limitations: Number of values per row is not consistent
# Examples:
#  id,score
#  1,104
#  2,40
#
#  name,age
#  Alice,30,xyz
#  Bob,42,"foo",bar

<start> ::= <csv>
<csv> ::= <csv_row> <csv_rows>
<csv_rows> ::= <csv_row>*
<csv_row> ::= <values> "\r\n"
<values> ::= <value> | <value> "," <values>
<value> ::= '"' <value_char>+ '"' | <value_char>+
<value_char> ::= r"[a-zA-Z0-9 .,]"
