# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

# Defines a simplified version of a RFC 5322 email address.
# The local part consists of upper or lowercase letters with additional
# characters "_", ".", ",", "-", "+".
# A domain consists of upper or lowercase letters or "-"
# Limitations: Local part or domain may start with invalid characters, e.g.
#  .test@example.org
# Examples: foo@bar.com, example1@domain.org, +test.@domain.de

<start> ::= <email>
<email> ::= <local_part> "@" <domain>
<local_part> ::= <email_char>+
<domain> ::= <domain_char>+ "." <domain_char>+
<domain_char> ::= r"[a-zA-Z0-9\-]"
<email_char> ::= r"[a-zA-Z0-9_.\-\+]"
