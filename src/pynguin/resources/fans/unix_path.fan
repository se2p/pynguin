# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

# Describes a unix file path syntax. File paths may be both relative or full
# paths.
# Examples: /home/user/file.txt, project/README.md

<start> ::= <path>
<path> ::= "/" <path_tail> | <relative_path>
<path_tail> ::= "" | <name> | <name> "/" <path_tail>
<relative_path> ::= <name> | <name> "/" <relative_path>
<name> ::= <char>+
<char> ::= r"[a-zA-Z0-9._-]"
