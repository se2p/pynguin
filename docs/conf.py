#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Sphinx configuration."""
import os
import sys

sys.path.insert(0, os.path.abspath(".."))

import pynguin  # noqa  # isort:skip

project = "pynguin"
author = "Pynguin Contributors"
copyright = f"2019–2022, {author}"
version = pynguin.__version__.__version__
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
]
