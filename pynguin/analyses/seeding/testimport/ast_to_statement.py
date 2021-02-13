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
from pynguin.testcase.statements.collectionsstatements import ListStatement, SetStatement, DictStatement, TupleStatement
from pynguin.testcase.statements.statement import Statement
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject, GenericMethod, GenericFunction, GenericConstructor,
)

logger = logging.getLogger(__name__)


def create_assign_stmt(
    assign: ast.Assign,
    testcase: tc.TestCase,
    ref_dict: Dict[str, vr.VariableReference],
) -> Tuple[Optional[str], Optional[Statement], bool]:
    """Creates the corresponding statement from an ast.Assign node.

    Args:
        assign: The ast.Assign node
        testcase: The testcase of the statement
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references.

    Returns:
        The corresponding statement or None if no statement type matches.
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
    elif isinstance(value, (ast.List, ast.Set, ast.Dict, ast.Tuple)):
        new_stmt = create_stmt_from_collection(value, testcase, objs_under_test, ref_dict)
    else:
        logger.info("Assign statement could not be parsed.")
        new_stmt = None
    if new_stmt is None:
        return None, None, False
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
) -> Optional[List[vr.VariableReference]]:
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
        if not reference:
            return None
        var_refs.append(reference)
    return var_refs


def create_stmt_from_constant(
    constant: ast.Constant, testcase: tc.TestCase
) -> Optional[prim_stmt.PrimitiveStatement]:
    """ Creates a statement from an ast.constant node.

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
    """ Creates a statement from an ast.unaryop node.

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
    """ Creates the corresponding statement from an ast.call node. Depending on the call, this can be a
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
    try:
        call.func.attr  # type: ignore
    except AttributeError:
        # this is very ugly...
        return try_generating_specific_function(call, testcase, objs_under_test, ref_dict)
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
    for arg in call.args:  # type: ignore
        if not isinstance(arg, ast.Name):
            return None
    var_refs = create_variable_references_from_call_args(
                call.args, ref_dict  # type: ignore
    )
    if not var_refs:
        return None
    if isinstance(gen_callable, GenericFunction):
        return param_stmt.FunctionStatement(
            testcase,
            cast(GenericCallableAccessibleObject, gen_callable),
            var_refs
        )
    elif isinstance(gen_callable, GenericMethod):
        return param_stmt.MethodStatement(
            testcase,
            gen_callable,
            ref_dict[call.func.value.id],  # type: ignore
            var_refs
        )
    elif isinstance(gen_callable, GenericConstructor):
        return param_stmt.ConstructorStatement(
            testcase,
            cast(GenericCallableAccessibleObject, gen_callable),
            var_refs
        )
    else:
        return None


def create_stmt_from_collection(
    coll_node: Union[ast.List, ast.Set, ast.Dict, ast.Tuple],
    testcase: tc.TestCase,
    objs_under_test: Set[GenericCallableAccessibleObject],
    ref_dict: Dict[str, vr.VariableReference],
) -> Optional[Union[ListStatement, SetStatement, DictStatement, TupleStatement]]:
    """ Creates the corresponding statement from an ast.List node. Lists contain other statements.

    Args:
        coll_node: the ast node. It has the type of one of the collection types.
        testcase: the testcase of the statement
        objs_under_test: the accessible objects under test. Not needed for the collection statement, but lists can
                         contain other statements (e.g. call) needing this.
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references. Not needed for the collection statement, but lists can contain other statements
                  (e.g. call) needing this.

    Returns:
        The corresponding list statement.
    """
    if isinstance(coll_node, ast.Dict):
        keys = create_elements(coll_node.keys, testcase, objs_under_test, ref_dict)
        values = create_elements(coll_node.values, testcase, objs_under_test, ref_dict)
        coll_elems_type = get_collection_type(values)
        coll_elems = list(zip(keys, values))
    else:
        elements = coll_node.elts  # type: ignore
        coll_elems = create_elements(elements, testcase, objs_under_test, ref_dict)
        coll_elems_type = get_collection_type(coll_elems)
    return create_specific_collection_call(testcase, coll_node, coll_elems_type, coll_elems)


def create_elements(
    elements: Any,
    testcase: tc.TestCase,
    objs_under_test: Set[GenericCallableAccessibleObject],
    ref_dict: Dict[str, vr.VariableReference],
) -> Optional[List[vr.VariableReference]]:
    coll_elems: List[vr.VariableReference] = []
    for elem in elements:
        if isinstance(elem, ast.Constant):
            coll_elems.append(testcase.add_statement(create_stmt_from_constant(elem, testcase)))
        elif isinstance(elem, ast.UnaryOp):
            coll_elems.append(testcase.add_statement(create_stmt_from_unaryop(elem, testcase)))
        elif isinstance(elem, ast.Call):
            coll_elems.append(testcase.add_statement(create_stmt_from_call(elem, testcase, objs_under_test, ref_dict)))
        elif isinstance(elem, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
            coll_elems.append(
                testcase.add_statement(create_stmt_from_collection(elem, testcase, objs_under_test, ref_dict)))
        elif isinstance(elem, ast.Name):
            try:
                coll_elems.append(ref_dict[elem.id])  # type: ignore
            except AttributeError:
                return None
        else:
            return None
    return coll_elems


def get_collection_type(coll_elems: List[vr.VariableReference]) -> Any:
    """ Returns the type of a collection. If objects of multiple types are in the collection, this function returns
    None.

    Args:
        coll_elems: a list of variable references

    Returns:
        The type of the collection.
    """
    if len(coll_elems) == 0:
        return None
    coll_type = coll_elems[0].variable_type
    for elem in coll_elems:
        if not elem.variable_type == coll_type:
            coll_type = None
            break
    return coll_type


def create_specific_collection_call(
    testcase: tc.TestCase,
    coll_node: Union[ast.List, ast.Set, ast.Dict, ast.Tuple],
    coll_elems_type: Any,
    coll_elems: List[vr.VariableReference]
) -> Optional[Union[ListStatement, SetStatement, DictStatement, TupleStatement]]:
    if isinstance(coll_node, ast.List):
        return ListStatement(testcase, coll_elems_type, coll_elems)
    elif isinstance(coll_node, ast.Set):
        return SetStatement(testcase, coll_elems_type, coll_elems)
    elif isinstance(coll_node, ast.Dict):
        return DictStatement(testcase, coll_elems_type, coll_elems)
    elif isinstance(coll_node, ast.Tuple):
        return TupleStatement(testcase, coll_elems_type, coll_elems)
    else:
        return None


def try_generating_specific_function(
    call: ast.Call,
    testcase: tc.TestCase,
    objs_under_test: Set[GenericCallableAccessibleObject],
    ref_dict: Dict[str, vr.VariableReference],
) -> Optional[Union[param_stmt.ConstructorStatement, param_stmt.MethodStatement, param_stmt.FunctionStatement]]:
    """ Calls to creating a collection (list, set, tuple, dict) via their keywords and not via literal syntax are
    considered as ast.Call statements. But for these calls, no accessible object under test is in the test_cluster.
    To parse them anyway, these method transforms them to the corresponding ast statement, for example a call of a list
    with 'list()' to an ast.List statement.

    Args:
        call: the ast.Call node
        testcase: the testcase of the statement
        objs_under_test: the accessible objects under test
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references.

    Returns:
        The corresponding statement.

    """
    try:
        func_id = str(call.func.id)  # type: ignore
    except AttributeError:
        return None
    if func_id == 'set':
        try:
            set_node = ast.Set(
                    elts=call.args,  # type: ignore
                    ctx=ast.Load(),
            )
        except AttributeError:
            return None
        return create_stmt_from_collection(set_node, testcase, objs_under_test, ref_dict)
    elif func_id == 'list':
        try:
            list_node = ast.List(
                    elts=call.args,  # type: ignore
                    ctx=ast.Load(),
            )
        except AttributeError:
            return None
        return create_stmt_from_collection(list_node, testcase, objs_under_test, ref_dict)
    elif func_id == 'tuple':
        try:
            tuple_node = ast.Tuple(
                    elts=call.args,  # type: ignore
                    ctx=ast.Load(),
            )
        except AttributeError:
            return None
        return create_stmt_from_collection(tuple_node, testcase, objs_under_test, ref_dict)
    elif func_id == 'dict':
        try:
            dict_node = ast.Dict(
                    keys=call.args[0].keys if call.args else [],  # type: ignore
                    values=call.args[0].values if call.args else [],  # type: ignore
                    ctx=ast.Load(),
            )
        except AttributeError:
            return None
        return create_stmt_from_collection(dict_node, testcase, objs_under_test, ref_dict)
    else:
        return None
