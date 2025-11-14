# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

# Defines a simplified XML document format. An XML document consists of at
# least one element with an opening tag, text content and a closing tag.
# Limitations: Opening and closing tags mismatch
# Examples:
#  <a><b>text</b></a>
#
#  <a>foo</x>

<start> ::= <xml_doc>
<xml_doc> ::= '<?xml version="1.0" encoding="utf-8"?>\n'? <xml_tree>
<xml_tree> ::= <xml_tag_start> <inner_xml_tree> <xml_tag_end>
<inner_xml_tree> ::= <xml_tag_start> <text> <xml_tag_end>
<xml_tag_start> ::= "<" <id> (" " <xml_attributes>)? ">" | "<" <id> ">"
<xml_tag_end> ::= "</" <id> ">"
<xml_attributes> ::= <xml_attribute> | <xml_attribute> " " <xml_attributes>
<xml_attribute> ::= <id> '=\"' <text> '\"'
<id> ::= <id_char>+
<id_char> ::= r"[a-zA-Z0-9\-_.]"

<text> ::= <printable>+
