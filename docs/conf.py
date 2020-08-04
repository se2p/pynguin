"""Sphinx configuration."""
import os
import sys

sys.path.insert(0, os.path.abspath(".."))

import pynguin  # noqa  # isort:skip

project = "pynguin"
author = "Pynguin Contributors"
copyright = f"2020, {author}"
version = pynguin.__version__
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
]
