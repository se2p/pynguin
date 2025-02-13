#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Some utilites to make testing easier."""

import ast
import importlib
import inspect

from pathlib import Path

import pynguin.utils.generic.genericaccessibleobject as gao

from pynguin.analyses.typesystem import Instance
from pynguin.analyses.typesystem import ProperType
from pynguin.analyses.typesystem import TypeSystem
from pynguin.assertion.mutation_analysis.mutators import FirstOrderMutator
from pynguin.assertion.mutation_analysis.operators.arithmetic import (
    ArithmeticOperatorReplacement,
)
from pynguin.assertion.mutation_analysis.operators.base import Mutation
from pynguin.assertion.mutation_analysis.operators.base import MutationOperator
from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer
from pynguin.assertion.mutation_analysis.transformer import create_module


def feed_typesystem(system: TypeSystem, generic: gao.GenericAccessibleObject):
    """Feeds the type system.

    Small helper because TypeInfos need to be aligned, and we don't have one
    large typesystem during testing but create them in various places.

    Args:
        system: the type system to feed
        generic: an accessible to query
    """

    # TODO(fk) think about making this less hacky.
    def feed(typ: ProperType):
        if isinstance(typ, Instance):
            system.to_type_info(typ.type.raw_type)

    if isinstance(generic, gao.GenericCallableAccessibleObject):
        feed(generic.inferred_signature.return_type)
        for para in generic.inferred_signature.original_parameters.values():
            feed(para)

    if isinstance(generic, gao.GenericConstructor):
        assert generic.owner
        system.to_type_info(generic.owner.raw_type)

    if isinstance(generic, gao.GenericField):
        system.to_type_info(generic.owner.raw_type)


def assert_mutation(
    operator: type[MutationOperator],
    source_code: str,
    expected_mutants_source_code: dict[str, tuple[str, type[ast.AST], type[ast.AST]]],
) -> None:
    module_ast = ParentNodeTransformer.create_ast(source_code)
    module = create_module(module_ast, "mutant")

    expected_mutants_processed_source_code = {
        ast.unparse(ParentNodeTransformer.create_ast(expected_code)): expected_info
        for expected_code, expected_info in expected_mutants_source_code.items()
    }

    for mutation, mutant_ast in operator.mutate(module_ast, module):
        assert mutation.operator is operator, f"{mutation.operator} is not {operator}"
        assert mutation.visitor_name in dir(operator), (
            f"{mutation.visitor_name} not in {dir(operator)}"
        )

        mutant_source_code = ast.unparse(mutant_ast)

        assert mutant_source_code in expected_mutants_processed_source_code, (
            f"{mutant_source_code!r} not in {expected_mutants_processed_source_code}"
        )

        expected_mutant_info = expected_mutants_processed_source_code.pop(mutant_source_code)

        mutant_info = (
            mutation.visitor_name,
            type(mutation.node),
            type(mutation.replacement_node),
        )

        assert expected_mutant_info == mutant_info, f"{expected_mutant_info} != {mutant_info}"

    assert not expected_mutants_processed_source_code, (
        f"Remaining mutants: {expected_mutants_processed_source_code}"
    )

    processed_source_code = ast.unparse(module_ast)
    expected_source_code = ast.unparse(ast.parse(source_code))

    assert expected_source_code == processed_source_code, (
        f"Source code changed: {processed_source_code} != {expected_source_code}"
    )


def assert_mutator_mutation(
    mutator: FirstOrderMutator,
    source_code: str,
    expected_mutants_source_code: dict[
        str, set[tuple[type[MutationOperator], str, type[ast.AST], type[ast.AST]]]
    ],
) -> None:
    module_ast = ParentNodeTransformer.create_ast(source_code)
    module = create_module(module_ast, "mutant")

    expected_mutants_processed_source_code = {
        ast.unparse(ParentNodeTransformer.create_ast(expected_code)): expected_info
        for expected_code, expected_info in expected_mutants_source_code.items()
    }

    for mutations, mutant_ast in mutator.mutate(module_ast, module):
        mutant_source_code = ast.unparse(mutant_ast)

        assert mutant_source_code in expected_mutants_processed_source_code, (
            f"{mutant_source_code!r} not in {expected_mutants_processed_source_code}"
        )

        expected_mutant_info = expected_mutants_processed_source_code.pop(mutant_source_code)

        mutant_info = {
            (
                mutation.operator,
                mutation.visitor_name,
                type(mutation.node),
                type(mutation.replacement_node),
            )
            for mutation in mutations
        }

        assert expected_mutant_info == mutant_info, f"{expected_mutant_info} != {mutant_info}"

    assert not expected_mutants_processed_source_code, (
        f"Remaining mutants: {expected_mutants_processed_source_code}"
    )

    processed_source_code = ast.unparse(module_ast)
    expected_source_code = ast.unparse(ast.parse(source_code))

    assert expected_source_code == processed_source_code, (
        f"Source code changed: {processed_source_code} != {expected_source_code}"
    )


def create_aor_mutation_on_substraction(node: ast.Sub | None = None) -> Mutation:
    if node is None:
        node = ast.Sub(children=[])

    return Mutation(
        node=node,
        replacement_node=ast.Add(children=[]),
        operator=ArithmeticOperatorReplacement,
        visitor_name="mutate_Sub",
    )


def module_to_path(module: str) -> Path:
    project_root = Path(__file__).parent.parent
    file_name = module.replace(".", "/") + ".py"
    return project_root / file_name


def import_module_safe(module_name):
    def import_using_spec(module_name):
        spec = importlib.util.find_spec(module_name)
        assert spec is not None, f"Module {module_name} not found."
        module = importlib.util.module_from_spec(spec)
        file_name = module_to_path(module_name)
        module_source_code = Path(file_name).read_text(encoding="utf-8")
        return module, module_source_code

    try:
        module = importlib.import_module(module_name)
        module_source_code = inspect.getsource(module)
    except (SystemExit, Exception):
        return import_using_spec(module_name)

    return module, module_source_code
