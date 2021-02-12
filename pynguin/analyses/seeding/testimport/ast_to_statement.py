#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an implementation to generate statements out of an AST."""
import ast
import logging
from typing import Dict, List, Optional, Set, Tuple, cast, Union, Any

import pynguin.analyses.seeding.initialpopulationseeding as initpopseeding
import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.primitivestatements as prim_stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
from pynguin.assertion.assertion import Assertion
from pynguin.assertion.noneassertion import NoneAssertion
from pynguin.assertion.primitiveassertion import PrimitiveAssertion
from pynguin.testcase.statements.collectionsstatements import ListStatement
from pynguin.testcase.statements.statement import Statement
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject, GenericMethod, GenericFunction, GenericConstructor,
)

logger = logging.getLogger(__name__)


def create_assign_stmt(
    assign: ast.Assign,
    testcase: tc.TestCase,
    ref_dict: Dict[str, vr.VariableReference],
) -> Tuple[str, Optional[Statement], bool]:
    """Creates the corresponding statement from an ast.Assign node.

    Args:
        assign: The ast.Assign node
        testcase: The testcase of the statement
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references.

    Returns:
        The corresponding statement or None if no statement type matches
    """
    new_stmt: Optional[Statement]
    value = assign.value
    test_cluster = initpopseeding.initialpopulationseeding.test_cluster
    objs_under_test = test_cluster.accessible_objects_under_test
    if isinstance(value, ast.Constant):
        new_stmt = create_stmt_from_constant(value, testcase)
    elif isinstance(value, ast.UnaryOp):
        new_stmt = create_stmt_from_unaryop(value, testcase)
    elif isinstance(value, ast.Call):
        new_stmt = create_stmt_from_call(
            value, testcase, objs_under_test, ref_dict
        )
    elif isinstance(value, ast.List):
        new_stmt = create_stmt_from_list(value, testcase, objs_under_test, ref_dict)
    else:
        logger.info("Assign statement could not be parsed.")
        new_stmt = None
    if new_stmt is None:
        return 'no_id', None, False
    ref_id = str(assign.targets[0].id)  # type: ignore
    return ref_id, new_stmt, True


def create_assert_stmt(
    ref_dict: Dict[str, vr.VariableReference], assert_node: ast.Assert
) -> Tuple[Optional[Assertion], Optional[vr.VariableReference]]:
    """Creates an assert statement.

    Args:
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references.
        assert_node: the ast assert node.

    Returns:
        The corresponding assert statement.
    """
    try:
        source = ref_dict[assert_node.test.left.id]  # type: ignore
        val = assert_node.test.comparators[0].value
    except (KeyError, AttributeError):  # pylint: disable=broad-except
        return None, None
    val_elem = assert_node.test.comparators[0]
    if isinstance(val_elem, ast.Constant) and val is None:  # type: ignore
        return NoneAssertion(source, assert_node.test.comparators[0].value), source  # type: ignore
    elif isinstance(val_elem, ast.Constant) and val is not None:  # type: ignore
        return PrimitiveAssertion(source, assert_node.test.comparators[0].value), source  # type: ignore
    else:
        return None, None


def create_variable_references_from_call_args(
    call_args: List[ast.Name], ref_dict: Dict[str, vr.VariableReference]
) -> List[vr.VariableReference]:
    """ Takes the arguments of an ast.Call node and returns the variable references of the corresponding statements.

        Args:
            call_args: a list of arguments
            ref_dict: a dictionary containing the variable references

        Returns:
            The list with the variable references of the call_args.

    """
    var_refs: List[vr.VariableReference] = []
    for arg in call_args:
        reference = ref_dict.get(arg.id)
        assert reference is not None, "Reference not found"
        var_refs.append(reference)
    return var_refs


def create_stmt_from_constant(
    constant: ast.Constant, testcase: tc.TestCase
) -> Optional[prim_stmt.PrimitiveStatement]:
    """ Creates a statement from an ast.assign node containing an ast.constant node.

        Args:
            constant: the ast.Constant statement
            testcase: the testcase containing the statement

        Returns:
            The corresponding statement.
    """
    if constant.value is None:  # type: ignore
        return prim_stmt.NoneStatement(testcase, constant.value)  # type: ignore

    val = constant.value  # type: ignore
    if isinstance(val, bool):
        return prim_stmt.BooleanPrimitiveStatement(
            testcase, val  # type: ignore
        )
    if isinstance(val, int):
        return prim_stmt.IntPrimitiveStatement(
            testcase, val  # type: ignore
        )
    if isinstance(val, float):
        return prim_stmt.FloatPrimitiveStatement(
            testcase, val  # type: ignore
        )
    if isinstance(val, str):
        return prim_stmt.StringPrimitiveStatement(
            testcase, val  # type: ignore
        )
    if isinstance(val, bytes):
        return prim_stmt.BytesPrimitiveStatement(
            testcase, val  # type: ignore
        )
    logger.info(
        "Could not find case for constant while handling assign statement."
    )
    return None


def create_stmt_from_unaryop(
    unaryop: ast.UnaryOp, testcase: tc.TestCase
) -> Optional[prim_stmt.PrimitiveStatement]:
    """ Creates a statement from an ast.assign node containing an ast.unaryop node.

        Args:
            unaryop: the ast.UnaryOp statement
            testcase: the testcase containing the statement

        Returns:
            The corresponding statement.
    """
    val = unaryop.operand.value  # type: ignore
    if isinstance(val, bool):
        return prim_stmt.BooleanPrimitiveStatement(
            testcase, not val  # type: ignore
        )
    if isinstance(val, float):
        return prim_stmt.FloatPrimitiveStatement(
            testcase, (-1) * val  # type: ignore
        )
    if isinstance(val, int):
        return prim_stmt.IntPrimitiveStatement(
            testcase, (-1) * val  # type: ignore
        )
    logger.info(
        "Could not find case for unary operator while handling assign statement."
    )
    return None


def create_stmt_from_call(
    call: ast.Call,
    testcase: tc.TestCase,
    objs_under_test: Set[GenericCallableAccessibleObject],
    ref_dict: Dict[str, vr.VariableReference],
) -> Optional[Union[param_stmt.ConstructorStatement, param_stmt.MethodStatement, param_stmt.FunctionStatement]]:
    """ Creates the corresponding statement from an ast.assign node. Depending on the call, this can be a
    GenericConstructor, GenericMethod or GenericFunction statement.

    Args:
        call: the ast.Call node
        testcase: the testcase of the statement
        objs_under_test: the accessible objects under test
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references.

    Returns:
        The corresponding statement.
    """
    gen_callable = find_gen_callable(call, objs_under_test, ref_dict)
    if gen_callable is None:
        logger.info("No such function found...")
        return None
    else:
        return assemble_stmt_from_gen_callable(
            testcase,
            gen_callable,
            call,
            ref_dict
        )


def find_gen_callable(
    call: ast.Call,
    objs_under_test: Set,
    ref_dict: Dict[str, vr.VariableReference],
) -> Optional[Union[GenericConstructor, GenericMethod, GenericFunction]]:
    """Traverses the accessible objects under test and returns the one matching with the ast.call object.
    Unfortunately, there is no possibility to clearly determine if the ast.call object is a constructor, method or
    function. Hence, the looping over all accessible objects is unavoidable. Then, by the name of the ast.call and
    by the owner (functions do not have one, constructors and methods have), it is possible to decide which accessible
    object to choose. This should also be unique, because the name of a function should be unique in a module. The name
    of a method should be unique inside one class. If two classes in the same module have a method with an equal name,
    the right method can be determined by the type of the object that is calling the method. This object has the type of
    the class of which the method is called. To determine between function names and method names, another thing needs
    to be considered. If a method is called, it is called on an object. This object must have been created before the
    function is called on that object. Thus, this object must have been initialized before and have a variable reference
    in the ref_dict where all created variable references are stored. So, by checking, if a reference is found, it can
    be decided if it is a function or a method.

        Args:
            call: the ast.Call node
            objs_under_test: the accessible objects under test
            ref_dict: a dictionary containing key value pairs of variable ids and
                      variable references.

        Returns:
            The corresponding generic accessible object under test. This can be a GenericConstructor, a GenericMethod or
            a GenericFunction.
        """
    call_name = str(call.func.attr)  # type: ignore
    for obj in objs_under_test:
        if isinstance(obj, GenericConstructor):
            owner = str(obj.owner).split('.')[-1].split('\'')[0]
            if call_name == owner and call.func.value.id not in ref_dict:  # type: ignore
                return obj
        elif isinstance(obj, GenericMethod):
            # test if the type of the calling object is equal to the type of the owner of the generic method
            if call_name == obj.method_name and call.func.value.id in ref_dict:  # type: ignore
                obj_from_ast = str(call.func.value.id)  # type: ignore
                var_type = ref_dict[obj_from_ast].variable_type
                if var_type == obj.owner:
                    return obj
        elif isinstance(obj, GenericFunction):
            if call_name == obj.function_name:
                return obj
    return None


def assemble_stmt_from_gen_callable(
    testcase: tc.TestCase,
    gen_callable: Union[GenericConstructor, GenericMethod, GenericFunction],
    call: ast.Call,
    ref_dict: Dict[str, vr.VariableReference],
) -> Optional[Union[param_stmt.ConstructorStatement, param_stmt.MethodStatement, param_stmt.FunctionStatement]]:
    """ Takes a generic callable and assembles the corresponding parametrized statement from it.

        Args:
            testcase: the testcase of the statement
            gen_callable: the corresponding callable of the cluster
            call: the ast.Call statement
            ref_dict: a dictionary containing key value pairs of variable ids and
                      variable references.

        Returns:
            The corresponding statement.
    """
    if isinstance(gen_callable, GenericFunction):
        return param_stmt.FunctionStatement(
            testcase,
            cast(GenericCallableAccessibleObject, gen_callable),
            create_variable_references_from_call_args(
                call.args, ref_dict  # type: ignore
            ),
        )
    elif isinstance(gen_callable, GenericMethod):
        return param_stmt.MethodStatement(
            testcase,
            gen_callable,
            ref_dict[call.func.value.id],  # type: ignore
            create_variable_references_from_call_args(
                call.args, ref_dict
            )
        )
    elif isinstance(gen_callable, GenericConstructor):
        return param_stmt.ConstructorStatement(
            testcase,
            cast(GenericCallableAccessibleObject, gen_callable),
            create_variable_references_from_call_args(
                call.args, ref_dict  # type: ignore
            ),
        )
    else:
        return None


def create_stmt_from_list(
    list_node: ast.List,
    testcase: tc.TestCase,
    objs_under_test: Set[GenericCallableAccessibleObject],
    ref_dict: Dict[str, vr.VariableReference],
) -> Optional[ListStatement]:
    """ Creates the corresponding statement from an ast.List node. Lists contain other statements.

    Args:
        list_node: the ast.List node. intentionally named list_node because list would shadow the built-in name.
        testcase: the testcase of the statement
        objs_under_test: the accessible objects under test. Not needed for the list statement, but lists can contain
                         other statements (e.g. call) needing this.
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references. Not needed for the list statement, but lists can contain other statements
                  (e.g. call) needing this.

    Returns:
        The corresponding list statement.
    """
    elements = list_node.elts  # type: ignore
    list_elems: List[vr.VariableReference] = []
    list_type: Any
    for elem in elements:
        if isinstance(elem, ast.Constant):
            list_elems.append(testcase.add_statement(create_stmt_from_constant(elem, testcase)))
        elif isinstance(elem, ast.UnaryOp):
            list_elems.append(testcase.add_statement(create_stmt_from_unaryop(elem, testcase)))
        elif isinstance(elem, ast.Call):
            list_elems.append(testcase.add_statement(create_stmt_from_call(elem, testcase, objs_under_test, ref_dict)))
        elif isinstance(elem, ast.List):
            list_elems.append(testcase.add_statement(create_stmt_from_list(elem, testcase, objs_under_test, ref_dict)))
        else:
            return None
    list_type = get_list_type(list_elems)
    return ListStatement(testcase, list_type, list_elems)


def get_list_type(list_elems: List[vr.VariableReference]) -> Any:
    """ Returns the type of a list. If objects of multiple types are in the list, this function returns None.

    Args:
        list_elems: a list of variable references

    Returns:
        The type of the list.
    """
    list_type = list_elems[0].variable_type
    for elem in list_elems:
        if not elem.variable_type == list_type:
            list_type = None
            break
    return list_type
