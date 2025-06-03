#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Utility methods for AST manipulation."""

from __future__ import annotations

import ast
import typing


if typing.TYPE_CHECKING:
    import pynguin.testcase.variablereference as vr
    import pynguin.utils.namingscope as ns


def create_full_name(
    variable_names: ns.AbstractNamingScope,
    module_names: ns.AbstractNamingScope,
    var: vr.Reference,
    *,
    load: bool,
) -> ast.Name | ast.Attribute:
    """Create a name node for the corresponding variable.

    Args:
        variable_names: the naming scope for the variables
        module_names: the naming scope for the modules
        var: the variable reference
        load: load or store?

    Returns:
        the name node
    """
    names = var.get_names(variable_names, module_names)
    loads = [True for _ in names[:-1]]
    loads.append(load)
    # First has to be ast.Name
    res: ast.Name | ast.Attribute = create_ast_name(names[0], store=not loads[0])
    # Remaining are ast.Attribute
    for name, loa in zip(names[1:], loads[1:], strict=True):
        res = create_ast_attribute(name, res, store=not loa)
    return res


def create_ast_name(name_id: str, *, store: bool = False) -> ast.Name:
    """Creates an AST name node.

    Args:
         name_id: for the name of the node
         store: store or load?

    Returns:
        the name node
    """
    return ast.Name(id=name_id, ctx=ast.Store() if store else ast.Load())


def create_ast_assign(target, value) -> ast.Assign:
    """Creates an AST assign node.

    Args:
         target: for the element where the value should be assigned to
         value: or the value which should be assigned

    Returns:
        the assign node
    """
    return ast.Assign(targets=[target], value=value)


def create_ast_attribute(attr, value, *, store: bool = False) -> ast.Attribute:
    """Creates an AST attribute node.

    Args:
        attr: for the name of the attribute
        value: for the value of the attribute
        store: store or load?

    Returns:
        the attribute node
    """
    return ast.Attribute(attr=attr, ctx=ast.Store() if store else ast.Load(), value=value)


def create_ast_list(elts, *, store: bool = False) -> ast.List:
    """Creates an AST list node.

    Args:
        elts: for the elements of the list
        store: store or load?

    Returns:
         the list node
    """
    return ast.List(ctx=ast.Store() if store else ast.Load(), elts=elts)


def create_ast_dict(keys, values) -> ast.Dict:
    """Creates an AST dict node.

    Args:
        keys: collection of the keys of the dictionary
        values: collection of the values of the dictionary

    Returns:
        the dict node
    """
    return ast.Dict(keys=keys, values=values)


def create_ast_set(elts) -> ast.Set:
    """Creates an AST set node.

    Args:
        elts: collection of the elements of the set

    Returns:
        the set node
    """
    return ast.Set(elts=elts)


def create_ast_tuple(elts, *, store: bool = False) -> ast.Tuple:
    """Creates an AST tuple node.

    Args:
        elts: collection of the elements of the tuple
        store: store or load?

    Returns:
        the tuple node
    """
    return ast.Tuple(ctx=ast.Store() if store else ast.Load(), elts=elts)


def create_ast_constant(value) -> ast.Constant:
    """Creates an AST constant node.

    Args:
        value: for the value of the constant

    Returns:
        the constant node
    """
    return ast.Constant(value=value, kind=None)


def create_ast_assert(test) -> ast.Assert:
    """Creates an AST assert node.

    Args:
        test: for the comparator

    Returns:
        the assert node
    """
    return ast.Assert(test=test, msg=None)


def create_ast_compare(left, operator, comparator) -> ast.Compare:
    """Creates an AST compare node.

    Args:
        left: for the element which should be compared
        operator: for the operator which should be used for comparison
        comparator: for the elements which should be used for comparison

    Returns:
        the compare node
    """
    return ast.Compare(left=left, ops=[operator], comparators=[comparator])


def create_ast_call(func, args, keywords) -> ast.Call:
    """Creates an AST call node.

    Args:
        func: for the callable which should be called
        args: collection of all the non positional arguments
        keywords: collection of all the positional arguments

    Returns:
        the call node
    """
    return ast.Call(func=func, args=args, keywords=keywords)


def create_ast_keyword(arg, value) -> ast.keyword:
    """Creates an AST keyword node.

    Args:
        arg: for the name of the keyword
        value: for the value of the keyword

    Returns:
        the keyword node
    """
    return ast.keyword(arg=arg, value=value)


def create_ast_for_nested_list(nested: list) -> ast.List | ast.Constant:
    """Recursively convert a nested list into a corresponding AST node.

    Args:
        nested: nested list

    Returns:
        the nested list node
    """
    if isinstance(nested, list):
        return ast.List(
            elts=[create_ast_for_nested_list(item) for item in nested],
            ctx=ast.Load(),
        )
    return ast.Constant(value=nested)
