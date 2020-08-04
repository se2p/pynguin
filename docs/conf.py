"""Sphinx configuration."""
import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "pynguin"
author = "Pynguin Contributors"
copyright = f"2020, {author}"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
]
