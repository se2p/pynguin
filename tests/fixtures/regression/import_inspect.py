#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Importing unittest also imports inspect. Importing BeautifulSoup afterward
# causes an error for an unknown reason. This regression file checks that the error
# is not reintroduced.
import unittest

from bs4 import BeautifulSoup
