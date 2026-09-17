#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Builders for mock statements in the libcst-backed test case representation.

There are no :class:`~pynguin.testcase.testcase.Statement` subclasses in the
current architecture, so a mock is a plain ``Statement`` whose ``node`` renders
the ``var = MagicMock()`` construction together with one assignment per
configured setup, e.g.::

    var_0 = MagicMock()
    var_0.get.return_value.status_code = 200

The whole mock lives in a single ``node`` so that cloning, single-point
crossover and variable renaming treat it as one atomic unit.  The search-mutable
state (which candidate is chosen for each :class:`~pynguin.large_language_model.\
mock_generation.mock_generator.MutableSetup`, and the value of each method-config
parameter) is carried in the statement's
:class:`~pynguin.testcase.testcase.MockStatementInfo`; mutation re-picks a
candidate and re-renders the node (see
:meth:`~pynguin.testcase.testfactory.TestFactory.mutate_value`), mirroring how ML
statements use ``ml_info``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import libcst as cst

from pynguin.large_language_model.mock_generation.mock_generator import RaiseException
from pynguin.testcase.testcase import MockStatementInfo, Statement, _VariableRenamer
from pynguin.utils import randomness

if TYPE_CHECKING:
    import pynguin.testcase.testcase as tc
    from pynguin.large_language_model.mock_generation.mock_generator import MockTemplate


def default_setup_choices(template: MockTemplate) -> list[int]:
    """Pick a random candidate index for each mutable setup of *template*.

    Fresh statements pick a random candidate so the population explores every
    branch value immediately, not only via later mutation.

    Args:
        template: The mock template.

    Returns:
        One candidate index per ``template.mutable_setups`` entry.
    """
    return [
        # next_int's upper bound is exclusive, so pass len (not len - 1).
        randomness.next_int(0, len(setup.candidates)) if setup.candidates else 0
        for setup in template.mutable_setups
    ]


def default_parameter_values(template: MockTemplate) -> dict[str, Any]:
    """Return each parameter's default value keyed by name.

    Args:
        template: The mock template.

    Returns:
        A mapping from parameter name to its default value.
    """
    return {param.name: param.default_value for param in template.parameters}


def current_setup_value(template: MockTemplate, setup_choices: list[int], index: int) -> Any:
    """Return the chosen value for the mutable setup at *index*.

    Args:
        template: The mock template.
        setup_choices: The current candidate index for each mutable setup.
        index: The mutable-setup index.

    Returns:
        The candidate value currently selected for that setup.
    """
    setup = template.mutable_setups[index]
    choice = setup_choices[index] % len(setup.candidates)
    return setup.candidates[choice]


def _magic_mock_call() -> cst.Call:
    """Return a ``MagicMock()`` call node.

    Returns:
        The CST call node.
    """
    return cst.Call(func=cst.Name("MagicMock"))


def _value_to_expr(value: Any) -> cst.BaseExpression:
    """Convert a Python constant (or :class:`RaiseException`) to a CST expression.

    A :class:`RaiseException` marker renders as a bare builtin-exception name
    (e.g. ``KeyError``) so it can be assigned to ``side_effect`` and make the
    mocked call raise.  Any value whose ``repr`` does not parse back into an
    expression falls back to ``MagicMock()``.

    Args:
        value: The value to render.

    Returns:
        The CST expression node.
    """
    if isinstance(value, RaiseException):
        return cst.Name(value.name)
    try:
        return cst.parse_expression(repr(value))
    except Exception:  # noqa: BLE001 - defensive: exotic values fall back to a bare mock
        return _magic_mock_call()


def _attribute_chain(var_name: str, attrs: list[str]) -> cst.BaseAssignTargetExpression:
    """Build an attribute-access chain ``var_name.attrs[0].attrs[1]...``.

    Args:
        var_name: The root variable name.
        attrs: The attribute names to chain onto the root.

    Returns:
        The CST expression for the attribute chain.
    """
    expr: cst.BaseAssignTargetExpression = cst.Name(var_name)
    for attr in attrs:
        expr = cst.Attribute(value=expr, attr=cst.Name(attr))
    return expr


def _assign(target: cst.BaseAssignTargetExpression, value: cst.BaseExpression) -> cst.Assign:
    """Build a ``target = value`` assignment small-statement.

    Args:
        target: The assignment target expression.
        value: The assigned value expression.

    Returns:
        The CST assignment node.
    """
    return cst.Assign(targets=[cst.AssignTarget(target=target)], value=value)


def _render_setup_line(line: str, var_name: str) -> cst.Assign | None:
    """Parse a raw ``placeholder.<attr>... = value`` setup line, renaming its root.

    Returns ``None`` when the line is not a simple assignment whose target is an
    attribute chain rooted at a name, so arbitrary code cannot slip in.

    Args:
        line: The raw setup line, e.g. ``"mock.request.return_value.status = 200"``.
        var_name: The mock variable name the placeholder is renamed to.

    Returns:
        The renamed assignment node, or ``None`` when the line is not accepted.
    """
    try:
        module = cst.parse_module(line.strip())
    except Exception:  # noqa: BLE001 - a malformed proxy line is simply skipped
        return None
    if len(module.body) != 1 or not isinstance(module.body[0], cst.SimpleStatementLine):
        return None
    statement_line = module.body[0]
    if len(statement_line.body) != 1 or not isinstance(statement_line.body[0], cst.Assign):
        return None
    assign = statement_line.body[0]
    if len(assign.targets) != 1:
        return None
    target = assign.targets[0].target
    if not isinstance(target, cst.Attribute):  # must be placeholder.<attr>... = value
        return None
    root: cst.BaseExpression = target
    while isinstance(root, cst.Attribute):
        root = root.value
    if not isinstance(root, cst.Name):
        return None
    renamed = assign.visit(_VariableRenamer({root.value: var_name}))
    assert isinstance(renamed, cst.Assign)
    return renamed


def render_mock_node(
    var_name: str,
    template: MockTemplate,
    setup_choices: list[int],
    parameter_values: dict[str, Any],
) -> cst.SimpleStatementLine:
    """Render the mock's ``var = MagicMock()`` node and all of its setup lines.

    The primary assignment and every setup line are emitted as small statements
    of a single :class:`~libcst.SimpleStatementLine` so the whole mock is one
    atomic node.  Black splits the semicolon-joined line into one physical line
    per setup when the generated file is formatted.

    Args:
        var_name: The mock variable name.
        template: The mock template.
        setup_choices: The candidate index chosen for each mutable setup.
        parameter_values: The current value of each method-config parameter.

    Returns:
        The CST node representing the whole mock.
    """
    body: list[cst.BaseSmallStatement] = [
        _assign(cst.Name(var_name), _magic_mock_call()),
    ]

    # var.<method>.return_value = <parameter value | MagicMock()>
    for method_config in template.method_configs:
        if method_config.parameters:
            param = method_config.parameters[0]
            value_expr = _value_to_expr(parameter_values.get(param.name, param.default_value))
        else:
            value_expr = _magic_mock_call()
        body.append(
            _assign(
                _attribute_chain(var_name, [method_config.method_name, "return_value"]),
                value_expr,
            )
        )

    # var.<attr> = <value> for each proxy return-value hint.
    for attr, value in template.attribute_values.items():
        body.append(_assign(_attribute_chain(var_name, [attr]), _value_to_expr(value)))

    # Raw proxy return-value setup lines with the placeholder renamed to var_name.
    for line in template.setup_lines:
        assign = _render_setup_line(line, var_name)
        if assign is not None:
            body.append(assign)

    # var.<target> = <chosen value>, where the value varies across tests so
    # value-dependent branches are covered.
    for index, setup in enumerate(template.mutable_setups):
        body.append(
            _assign(
                _attribute_chain(var_name, setup.target.split(".")),
                _value_to_expr(current_setup_value(template, setup_choices, index)),
            )
        )

    return cst.SimpleStatementLine(body=body)


def build_mock_statement(
    var_name: str,
    template: MockTemplate,
    setup_choices: list[int] | None = None,
    parameter_values: dict[str, Any] | None = None,
    bound_type: type | None = None,
) -> Statement:
    """Build a :class:`Statement` that creates a configured mock.

    Args:
        var_name: The variable name the mock is bound to.
        template: The mock template describing the dependency and its setups.
        setup_choices: Optional candidate index per mutable setup; defaults to a
            random choice per setup.
        parameter_values: Optional method-config parameter values; defaults to
            each parameter's default value.
        bound_type: Optional type the mock stands in for, so the type registry
            can reuse it where that type is required.

    Returns:
        A statement carrying the mock node and its :class:`MockStatementInfo`.
    """
    chosen = default_setup_choices(template) if setup_choices is None else list(setup_choices)
    values = (
        default_parameter_values(template) if parameter_values is None else dict(parameter_values)
    )
    node = render_mock_node(var_name, template, chosen, values)
    return Statement(
        node=node,
        bound_variable=var_name,
        bound_type=bound_type,
        mock_info=MockStatementInfo(
            template=template,
            setup_choices=chosen,
            parameter_values=values,
        ),
    )


def create_mock_statement(
    test_case: tc.TestCase,
    template: MockTemplate,
    position: int,
    bound_type: type | None = None,
) -> str:
    """Insert a fresh mock statement into *test_case* at *position*.

    Args:
        test_case: The test case to insert the mock into.
        template: The mock template.
        position: The index at which to insert the statement.
        bound_type: Optional type the mock stands in for.

    Returns:
        The variable name the mock is bound to.
    """
    var_name = test_case.next_var_name()
    test_case.insert_statement(
        position, build_mock_statement(var_name, template, bound_type=bound_type)
    )
    return var_name
