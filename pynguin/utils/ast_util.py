#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Utility methods for AST manipulation."""
import ast
from typing import Optional

import pynguin.testcase.variable.variablereference as vr
from pynguin.utils.namingscope import NamingScope


def create_var_name(
    variable_names: NamingScope, var: Optional[vr.VariableReference], load: bool
) -> ast.Name:
    """Create a name node for the corresponding variable.

    Args:
        variable_names: the naming scope for the variables
        var: the variable reference
        load: load or store?

    Returns:
        the name node
    """
    return ast.Name(
        id=variable_names.get_name(var),
        ctx=ast.Load() if load else ast.Store(),
    )
