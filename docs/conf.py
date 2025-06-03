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
    "hoverxref.extension",
    "sphinx_autodoc_typehints",
]

project = "pynguin"
author = "Pynguin Contributors"
copyright = f"2019–{datetime.datetime.now(datetime.timezone.utc).year}, {author}"
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
hoverxref_role_types = {
    "class": "tooltip",
    "ref": "tooltip",
    "mod": "tooltip",
    "meth": "tooltip",
    "func": "tooltip",
    "attr": "tooltip",
}

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
