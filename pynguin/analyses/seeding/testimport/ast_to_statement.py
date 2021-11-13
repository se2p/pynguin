#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an implementation to generate statements out of an AST."""
from __future__ import annotations

import ast
import inspect
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union, cast

import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as stmt
from pynguin.assertion.noneassertion import NoneAssertion
from pynguin.assertion.primitiveassertion import PrimitiveAssertion
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)

if TYPE_CHECKING:
    import pynguin.testcase.testcase as tc
    import pynguin.testcase.variablereference as vr
    from pynguin.assertion.assertion import Assertion
    from pynguin.setup.testcluster import TestCluster

logger = logging.getLogger(__name__)


def create_assign_stmt(
    assign: ast.Assign,
    testcase: tc.TestCase,
    ref_dict: Dict[str, vr.VariableReference],
    test_cluster: TestCluster,
) -> Optional[Tuple[str, stmt.Statement]]:
    """Creates the corresponding statement from an ast.Assign node.

    Args:
        assign: The ast.Assign node
        testcase: The testcase of the statement
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references.
        test_cluster: The test cluster that is used to resolve classes, methods, etc.

    Returns:
        The corresponding statement or None if no statement type matches.
    """
    new_stmt: Optional[stmt.Statement]
    value = assign.value
    objs_under_test = test_cluster.accessible_objects_under_test
    callable_objects_under_test: Set[GenericCallableAccessibleObject] = {
        o for o in objs_under_test if isinstance(o, GenericCallableAccessibleObject)
    }
    if isinstance(value, ast.Constant):
        new_stmt = create_stmt_from_constant(value, testcase)
    elif isinstance(value, ast.UnaryOp):
        new_stmt = create_stmt_from_unaryop(value, testcase)
    elif isinstance(value, ast.Call):
        new_stmt = create_stmt_from_call(
            value, testcase, callable_objects_under_test, ref_dict
        )
    elif isinstance(value, (ast.List, ast.Set, ast.Dict, ast.Tuple)):
        new_stmt = create_stmt_from_collection(
            value, testcase, callable_objects_under_test, ref_dict
        )
    else:
        logger.info("Assign statement could not be parsed.")
        new_stmt = None
    if new_stmt is None:
        return None
    ref_id = str(assign.targets[0].id)  # type: ignore
    return ref_id, new_stmt


def create_assert_stmt(
    ref_dict: Dict[str, vr.VariableReference], assert_node: ast.Assert
) -> Optional[Tuple[Assertion, vr.VariableReference]]:
    """Creates an assert statement.

    Args:
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references.
        assert_node: the ast assert node.

    Returns:
        The corresponding assert statement.
    """
    assertion: Optional[Union[PrimitiveAssertion, NoneAssertion]] = None
    try:
        source = ref_dict[assert_node.test.left.id]  # type: ignore
        val_elem = assert_node.test.comparators[0]  # type: ignore
        operator = assert_node.test.ops[0]  # type: ignore
    except (KeyError, AttributeError):
        return None
    if isinstance(operator, (ast.Is, ast.Eq)):
        assertion = create_assertion(source, val_elem)
    if assertion is not None:
        return assertion, source
    return None


def create_assertion(
    source: vr.VariableReference,
    val_elem: Optional[Union[ast.Constant, ast.UnaryOp]],
) -> Optional[Union[PrimitiveAssertion, NoneAssertion]]:
    """Creates an assertion.

    Args:
        source: The variable reference
        val_elem: The ast element for retrieving the value

    Returns:
        The assertion.
    """
    if isinstance(val_elem, ast.Constant) and val_elem.value is None:
        return NoneAssertion(source, val_elem.value)
    if isinstance(val_elem, ast.Constant):
        return PrimitiveAssertion(source, val_elem.value)
    if isinstance(val_elem, ast.UnaryOp):
        return PrimitiveAssertion(source, val_elem.operand.value)  # type: ignore
    return None


def create_variable_references_from_call_args(
    call_args: List[Union[ast.Name, ast.Starred]],
    call_keywords: List[ast.keyword],
    gen_callable: GenericCallableAccessibleObject,
    ref_dict: Dict[str, vr.VariableReference],
) -> Optional[Dict[str, vr.VariableReference]]:
    """Takes the arguments of an ast.Call node and returns the variable references of
    the corresponding statements.

    Args:
        call_args: the positional arguments
        call_keywords: the keyword arguments
        gen_callable: the callable that is called
        ref_dict: a dictionary containing the variable references

    Returns:
        The dict with the variable references of the call_args.

    """
    var_refs: Dict[str, vr.VariableReference] = {}
    # Handle positional arguments.
    for (name, param), call_arg in zip(
        gen_callable.inferred_signature.signature.parameters.items(), call_args
    ):
        if (
            param.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ) and isinstance(call_arg, ast.Name):
            reference = ref_dict.get(call_arg.id)
        elif param.kind == inspect.Parameter.VAR_POSITIONAL and isinstance(
            call_arg, ast.Starred
        ):
            reference = ref_dict.get(call_arg.value.id)  # type: ignore
        else:
            return None
        if reference is None:
            # Reference could not be resolved
            return None
        var_refs[name] = reference

    # Handle keyword arguments
    for call_keyword in call_keywords:
        keyword = call_keyword.arg
        if keyword is None:
            # **kwargs has to be the last parameter?
            keyword = list(gen_callable.inferred_signature.signature.parameters.keys())[
                -1
            ]
            if (
                gen_callable.inferred_signature.signature.parameters[keyword].kind
                != inspect.Parameter.VAR_KEYWORD
            ):
                return None
        if not isinstance(call_keyword.value, ast.Name):
            return None
        reference = ref_dict.get(call_keyword.value.id)
        if reference is None:
            return None
        var_refs[keyword] = reference

    return var_refs


# pylint: disable=too-many-return-statements
def create_stmt_from_constant(
    constant: ast.Constant, testcase: tc.TestCase
) -> Optional[stmt.PrimitiveStatement]:
    """Creates a statement from an ast.constant node.

    Args:
        constant: the ast.Constant statement
        testcase: the testcase containing the statement

    Returns:
        The corresponding statement.
    """
    if constant.value is None:
        return stmt.NoneStatement(testcase, constant.value)

    val = constant.value
    if isinstance(val, bool):
        return stmt.BooleanPrimitiveStatement(testcase, val)
    if isinstance(val, int):
        return stmt.IntPrimitiveStatement(testcase, val)
    if isinstance(val, float):
        return stmt.FloatPrimitiveStatement(testcase, val)
    if isinstance(val, str):
        return stmt.StringPrimitiveStatement(testcase, val)
    if isinstance(val, bytes):
        return stmt.BytesPrimitiveStatement(testcase, val)
    logger.info("Could not find case for constant while handling assign statement.")
    return None


def create_stmt_from_unaryop(
    unaryop: ast.UnaryOp, testcase: tc.TestCase
) -> Optional[stmt.PrimitiveStatement]:
    """Creates a statement from an ast.unaryop node.

    Args:
        unaryop: the ast.UnaryOp statement
        testcase: the testcase containing the statement

    Returns:
        The corresponding statement.
    """
    val = unaryop.operand.value  # type: ignore
    if isinstance(val, bool):
        return stmt.BooleanPrimitiveStatement(testcase, not val)
    if isinstance(val, float):
        return stmt.FloatPrimitiveStatement(testcase, (-1) * val)
    if isinstance(val, int):
        return stmt.IntPrimitiveStatement(testcase, (-1) * val)
    logger.info(
        "Could not find case for unary operator while handling assign statement."
    )
    return None


def create_stmt_from_call(
    call: ast.Call,
    testcase: tc.TestCase,
    objs_under_test: Set[GenericCallableAccessibleObject],
    ref_dict: Dict[str, vr.VariableReference],
) -> Optional[Union[stmt.CollectionStatement, stmt.ParametrizedStatement]]:
    """Creates the corresponding statement from an ast.call node. Depending on the call,
    this can be a GenericConstructor, GenericMethod or GenericFunction statement.

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
        return try_generating_specific_function(
            call, testcase, objs_under_test, ref_dict
        )
    gen_callable = find_gen_callable(call, objs_under_test, ref_dict)
    if gen_callable is None:
        logger.info("No such function found...")
        return None
    return assemble_stmt_from_gen_callable(testcase, gen_callable, call, ref_dict)


def find_gen_callable(
    call: ast.Call,
    objs_under_test: Set,
    ref_dict: Dict[str, vr.VariableReference],
) -> Optional[Union[GenericConstructor, GenericMethod, GenericFunction]]:
    """Traverses the accessible objects under test and returns the one matching with the
    ast.call object. Unfortunately, there is no possibility to clearly determine if the
    ast.call object is a constructor, method or function. Hence, the looping over all
    accessible objects is unavoidable. Then, by the name of the ast.call and by the
    owner (functions do not have one, constructors and methods have), it is possible to
    decide which accessible object to choose. This should also be unique, because the
    name of a function should be unique in a module. The name of a method should be
    unique inside one class. If two classes in the same module have a method with an
    equal name, the right method can be determined by the type of the object that is
    calling the method. This object has the type of the class of which the method is
    called. To determine between function names and method names, another thing needs
    to be considered. If a method is called, it is called on an object. This object must
    have been created before the function is called on that object. Thus, this object
    must have been initialized before and have a variable reference in the ref_dict
    where all created variable references are stored. So, by checking, if a reference is
    found, it can be decided if it is a function or a method.

        Args:
            call: the ast.Call node
            objs_under_test: the accessible objects under test
            ref_dict: a dictionary containing key value pairs of variable ids and
                      variable references.

        Returns:
            The corresponding generic accessible object under test. This can be a
            GenericConstructor, a GenericMethod or a GenericFunction.
    """
    call_name = str(call.func.attr)  # type: ignore
    for obj in objs_under_test:
        if isinstance(obj, GenericConstructor):
            owner = str(obj.owner).rsplit(".", maxsplit=1)[-1].split("'")[0]
            call_id = call.func.value.id  # type: ignore
            if call_name == owner and call_id not in ref_dict:
                return obj
        elif isinstance(obj, GenericMethod):
            # test if the type of the calling object is equal to the type of the owner
            # of the generic method
            call_id = call.func.value.id  # type: ignore
            if call_name == obj.method_name and call_id in ref_dict:
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
    gen_callable: GenericCallableAccessibleObject,
    call: ast.Call,
    ref_dict: Dict[str, vr.VariableReference],
) -> Optional[stmt.ParametrizedStatement]:
    """Takes a generic callable and assembles the corresponding parametrized statement
    from it.

    Args:
        testcase: the testcase of the statement
        gen_callable: the corresponding callable of the cluster
        call: the ast.Call statement
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references.

    Returns:
        The corresponding statement.
    """
    for arg in call.args:
        if not isinstance(arg, (ast.Name, ast.Starred)):
            return None
    for keyword in call.keywords:
        if not isinstance(keyword, ast.keyword):
            return None
    var_refs = create_variable_references_from_call_args(
        call.args, call.keywords, gen_callable, ref_dict  # type: ignore
    )
    if var_refs is None:
        return None
    if isinstance(gen_callable, GenericFunction):
        return stmt.FunctionStatement(
            testcase, cast(GenericCallableAccessibleObject, gen_callable), var_refs
        )
    if isinstance(gen_callable, GenericMethod):
        return stmt.MethodStatement(
            testcase,
            gen_callable,
            ref_dict[call.func.value.id],  # type: ignore
            var_refs,
        )
    if isinstance(gen_callable, GenericConstructor):
        return stmt.ConstructorStatement(
            testcase, cast(GenericCallableAccessibleObject, gen_callable), var_refs
        )
    return None


def create_stmt_from_collection(
    coll_node: Union[ast.List, ast.Set, ast.Dict, ast.Tuple],
    testcase: tc.TestCase,
    objs_under_test: Set[GenericCallableAccessibleObject],
    ref_dict: Dict[str, vr.VariableReference],
) -> Optional[
    Union[
        stmt.ListStatement, stmt.SetStatement, stmt.DictStatement, stmt.TupleStatement
    ]
]:
    """Creates the corresponding statement from an ast.List node. Lists contain other
    statements.

    Args:
        coll_node: the ast node. It has the type of one of the collection types.
        testcase: the testcase of the statement
        objs_under_test: the accessible objects under test. Not needed for the
        collection statement, but lists can contain other statements (e.g. call) needing
        this.
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references. Not needed for the collection statement, but
                  lists can contain other statements (e.g. call) needing this.

    Returns:
        The corresponding list statement.
    """
    coll_elems: Optional[
        Union[
            List[vr.VariableReference],
            List[Tuple[vr.VariableReference, vr.VariableReference]],
        ]
    ]
    if isinstance(coll_node, ast.Dict):
        keys = create_elements(coll_node.keys, testcase, objs_under_test, ref_dict)
        values = create_elements(coll_node.values, testcase, objs_under_test, ref_dict)
        if keys is None or values is None:
            return None
        coll_elems_type = get_collection_type(values)
        coll_elems = list(zip(keys, values))
    else:
        elements = coll_node.elts
        coll_elems = create_elements(elements, testcase, objs_under_test, ref_dict)
        if coll_elems is None:
            return None
        coll_elems_type = get_collection_type(coll_elems)
    return create_specific_collection_stmt(
        testcase, coll_node, coll_elems_type, coll_elems
    )


def create_elements(
    elements: Any,
    testcase: tc.TestCase,
    objs_under_test: Set[GenericCallableAccessibleObject],
    ref_dict: Dict[str, vr.VariableReference],
) -> Optional[List[vr.VariableReference]]:
    """Creates the elements of a collection by calling the corresponding methods for
    creation. This can be recursive.

    Args:
        elements: The elements of the collection
        testcase: the corresponding testcase
        objs_under_test: A set of generic accessible objects under test
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references

    Returns:
        A list of variable references or None if something goes wrong while creating the
        elements.
    """
    coll_elems: List[vr.VariableReference] = []
    for elem in elements:
        statement: Optional[
            Union[
                stmt.PrimitiveStatement,
                stmt.CollectionStatement,
                stmt.ParametrizedStatement,
            ]
        ]
        if isinstance(elem, ast.Constant):
            statement = create_stmt_from_constant(elem, testcase)
            if not statement:
                return None
            coll_elems.append(testcase.add_statement(statement))
        elif isinstance(elem, ast.UnaryOp):
            statement = create_stmt_from_unaryop(elem, testcase)
            if not statement:
                return None
            coll_elems.append(testcase.add_statement(statement))
        elif isinstance(elem, ast.Call):
            statement = create_stmt_from_call(elem, testcase, objs_under_test, ref_dict)
            if not statement:
                return None
            coll_elems.append(testcase.add_statement(statement))
        elif isinstance(elem, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
            statement = create_stmt_from_collection(
                elem, testcase, objs_under_test, ref_dict
            )
            if not statement:
                return None
            coll_elems.append(testcase.add_statement(statement))
        elif isinstance(elem, ast.Name):
            try:
                coll_elems.append(ref_dict[elem.id])
            except AttributeError:
                return None
        else:
            return None
    return coll_elems


def get_collection_type(coll_elems: List[vr.VariableReference]) -> Any:
    """Returns the type of a collection. If objects of multiple types are in the
    collection, this function returns None.

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


def create_specific_collection_stmt(
    testcase: tc.TestCase,
    coll_node: Union[ast.List, ast.Set, ast.Dict, ast.Tuple],
    coll_elems_type: Any,
    coll_elems: List[Any],
) -> Optional[
    Union[
        stmt.ListStatement, stmt.SetStatement, stmt.DictStatement, stmt.TupleStatement
    ]
]:
    """Creates the corresponding collection statement from an ast node.

    Args:
        testcase: The testcase of the statement
        coll_node: the ast node
        coll_elems: a list of variable references or a list of tuples of variables for a
        dict statement.
        coll_elems_type: the type of the elements of the collection statement.

    Returns:
        The corresponding collection statement.
    """
    if isinstance(coll_node, ast.List):
        return stmt.ListStatement(testcase, coll_elems_type, coll_elems)
    if isinstance(coll_node, ast.Set):
        return stmt.SetStatement(testcase, coll_elems_type, coll_elems)
    if isinstance(coll_node, ast.Dict):
        return stmt.DictStatement(testcase, coll_elems_type, coll_elems)
    if isinstance(coll_node, ast.Tuple):
        return stmt.TupleStatement(testcase, coll_elems_type, coll_elems)
    return None


def try_generating_specific_function(
    call: ast.Call,
    testcase: tc.TestCase,
    objs_under_test: Set[GenericCallableAccessibleObject],
    ref_dict: Dict[str, vr.VariableReference],
) -> Optional[stmt.CollectionStatement]:
    """Calls to creating a collection (list, set, tuple, dict) via their keywords and
    not via literal syntax are considered as ast.Call statements. But for these calls,
    no accessible object under test is in the test_cluster. To parse them anyway, these
    method transforms them to the corresponding ast statement, for example a call of a
    list with 'list()' to an ast.List statement.

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
    if func_id == "set":
        try:
            set_node = ast.Set(
                elts=call.args,
                ctx=ast.Load(),
            )
        except AttributeError:
            return None
        return create_stmt_from_collection(
            set_node, testcase, objs_under_test, ref_dict
        )
    if func_id == "list":
        try:
            list_node = ast.List(
                elts=call.args,
                ctx=ast.Load(),
            )
        except AttributeError:
            return None
        return create_stmt_from_collection(
            list_node, testcase, objs_under_test, ref_dict
        )
    if func_id == "tuple":
        try:
            tuple_node = ast.Tuple(
                elts=call.args,
                ctx=ast.Load(),
            )
        except AttributeError:
            return None
        return create_stmt_from_collection(
            tuple_node, testcase, objs_under_test, ref_dict
        )
    if func_id == "dict":
        try:
            dict_node = ast.Dict(
                keys=call.args[0].keys if call.args else [],  # type: ignore
                values=call.args[0].values if call.args else [],  # type: ignore
                ctx=ast.Load(),
            )
        except AttributeError:
            return None
        return create_stmt_from_collection(
            dict_node, testcase, objs_under_test, ref_dict
        )
    return None


# pylint: disable=invalid-name, missing-function-docstring
class AstToTestCaseTransformer(ast.NodeVisitor):
    """A AST NodeVisitor that tries to convert an AST into our internal
    test case representation."""

    def __init__(self, test_cluster: TestCluster, create_assertions: bool):
        self._current_testcase: dtc.DefaultTestCase = dtc.DefaultTestCase()
        self._current_parsable: bool = True
        self._var_refs: Dict[str, vr.VariableReference] = {}
        self._testcases: List[dtc.DefaultTestCase] = []
        self._number_found_testcases: int = 0
        self._test_cluster = test_cluster
        self._create_assertions = create_assertions

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._number_found_testcases += 1
        self._current_testcase = dtc.DefaultTestCase()
        self._current_parsable = True
        self._var_refs.clear()
        self.generic_visit(node)
        if self._current_parsable:
            self._testcases.append(self._current_testcase)

    def visit_Assign(self, node: ast.Assign) -> Any:
        if self._current_parsable:
            if (
                result := create_assign_stmt(
                    node, self._current_testcase, self._var_refs, self._test_cluster
                )
            ) is None:
                self._current_parsable = False
            else:
                ref_id, stm = result
                var_ref = self._current_testcase.add_statement(stm)
                self._var_refs[ref_id] = var_ref

    def visit_Assert(self, node: ast.Assert) -> Any:
        if self._current_parsable and self._create_assertions:
            if (result := create_assert_stmt(self._var_refs, node)) is not None:
                assertion, var_ref = result
                self._current_testcase.get_statement(
                    var_ref.get_statement_position()
                ).add_assertion(assertion)

    @property
    def testcases(self) -> List[dtc.DefaultTestCase]:
        """Provides the testcases that could be generated from the given AST.
        It is possible that not every aspect of the AST could be transformed
        to our internal representation.

        Returns:
            The generated testcases.
        """
        return self._testcases
