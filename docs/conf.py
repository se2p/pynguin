#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Sphinx configuration."""

import datetime
import os
import sys


sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

import pynguin  # noqa  # isort:skip

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    # "sphinx.ext.linkcode",
    "hoverxref.extension",
    "sphinx_autodoc_typehints",
]

project = "pynguin"
author = "Pynguin Contributors"
copyright = f"2019–{datetime.datetime.utcnow().year}, {author}"
html_theme = "sphinx_rtd_theme"

_d = {}
with open(
    os.path.join(os.path.dirname(__file__), "..", "src", "pynguin", "__version__.py"),
    encoding="utf-8",
) as f:
    exec(f.read(), _d)
    version = _d["__version__"]
    release = _d["__version__"]

language = "en"

exclude_patterns = ["_build"]

pygments_style = "sphinx"

todo_include_todos = False

# See https://sphinx-hoverxref.readthedocs.io/en/latest/configuration.html
hoverxref_auto_ref = True
hoverxref_domains = ["py"]

# This config value must be a dictionary of external sites, mapping unique short
# alias names to a base URL and a prefix.
# See https://www.sphinx-doc.org/en/master/usage/extensions/extlinks.html
_repo = "https://github.com/se2p/pynguin/"
extlinks = {
    "commit": (_repo + "commit/%s", "commit %s"),
    "gh-file": (_repo + "blob/main/%s", "%s"),
    "gh-link": (_repo + "%s", "%s"),
    "issue": (_repo + "issues/%s", "issue #%s"),
    "pull": (_repo + "pull/%s", "pull request #%s"),
    "pypi": ("https://pypi.org/project/%s/", "%s"),
}

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "pytest": ("https://docs.pytest.org/en/stable/", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master/", None),
}

# def linkcode_resolve(domain, info):
#     """
#     Resolve a linkcode reference to a GitHub URL.
#
#     This function maps Python objects to their corresponding GitHub URLs.
#     """
#     if domain != 'py':
#         return None
#
#     modname = info['module']
#     fullname = info['fullname']
#
#     # Find the module
#     try:
#         obj = sys.modules[modname]
#         for part in fullname.split('.'):
#             obj = getattr(obj, part)
#
#         # Get the source file
#         import inspect
#         filepath = inspect.getsourcefile(obj)
#         if filepath is None:
#             return None
#
#         # Convert filepath to relative path within the repository
#         filepath = os.path.relpath(filepath, start=os.path.dirname(pynguin.__file__))
#         filepath = f"src/pynguin/{filepath}"
#
#         # Get line numbers
#         try:
#             _, lineno = inspect.getsourcelines(obj)
#             # Create GitHub URL
#             return f"{_repo}blob/main/{filepath}#L{lineno}"
#         except TypeError:
#             # Handle objects that don't support getsourcelines (like Algorithm)
#             return f"{_repo}blob/main/{filepath}"
#     except (ImportError, AttributeError, KeyError, TypeError):
#         return None
