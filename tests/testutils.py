#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Some utilites to make testing easier."""
import ast

import pynguin.utils.generic.genericaccessibleobject as gao

from pynguin.analyses.typesystem import Instance
from pynguin.analyses.typesystem import ProperType
from pynguin.analyses.typesystem import TypeSystem
from pynguin.assertion.mutation_analysis.operators import MutationOperator
from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer
from pynguin.assertion.mutation_analysis.transformer import create_module


def feed_typesystem(system: TypeSystem, generic: gao.GenericAccessibleObject):
    """Small helper because TypeInfos need to be aligned, and we don't have one
    large typesystem during testing but create them in various places."""

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
):
    module_ast = ParentNodeTransformer.create_ast(source_code)
    module = create_module(module_ast, "mutant")

    expected_mutants_processed_source_code = {
        ast.unparse(ParentNodeTransformer.create_ast(mutant_source_code)): mutant_info
        for mutant_source_code, mutant_info in expected_mutants_source_code.items()
    }

    for mutation, mutant_ast in operator.mutate(module_ast, module):
        assert mutation.operator is operator, f"{mutation.operator} is not {operator}"
        assert mutation.visitor_name in dir(
            operator
        ), f"{mutation.visitor_name} not in {dir(operator)}"

        mutant_source_code = ast.unparse(mutant_ast)

        assert (
            mutant_source_code in expected_mutants_processed_source_code
        ), f"{repr(mutant_source_code)} not in {expected_mutants_processed_source_code}"

        visitor_name, node_type, replacement_node_type = (
            expected_mutants_processed_source_code.pop(mutant_source_code)
        )

        assert (
            mutation.visitor_name == visitor_name
        ), f"{mutation.visitor_name} is not {visitor_name}"
        assert isinstance(
            mutation.node, node_type
        ), f"{mutation.node} is not {node_type}"
        assert isinstance(
            mutation.replacement_node, replacement_node_type
        ), f"{mutation.replacement_node} is not {replacement_node_type}"

    assert (
        not expected_mutants_processed_source_code
    ), f"Remaining mutants: {expected_mutants_processed_source_code}"
