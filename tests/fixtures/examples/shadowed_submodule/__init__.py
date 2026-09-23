#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# The re-export below binds the name ``shadowed`` on this package to the
# function, shadowing the ``shadowed`` submodule (mirrors ``python-slugify``'s
# ``from slugify.slugify import slugify``). See issue #277.
from tests.fixtures.examples.shadowed_submodule.shadowed import shadowed


__all__ = ["shadowed"]
