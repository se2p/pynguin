#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Implements simple constant seeding strategies."""

from __future__ import annotations

import ast
import inspect
import logging
import os

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import AnyStr
from typing import cast

import pynguin.assertion.assertion as ass
import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as stmt
import pynguin.utils.statistics.stats as stat

from pynguin.analyses.typesystem import ANY
from pynguin.analyses.typesystem import Instance
from pynguin.analyses.typesystem import ProperType
from pynguin.analyses.typesystem import TupleType
from pynguin.utils import randomness
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.generic.genericaccessibleobject import GenericConstructor
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.generic.genericaccessibleobject import GenericMethod
from pynguin.utils.statistics.runtimevariable import RuntimeVariable
from pynguin.utils.type_utils import is_assertable


if TYPE_CHECKING:
    import pynguin.testcase.testcase as tc
    import pynguin.testcase.testfactory as tf
    import pynguin.testcase.variablereference as vr

    from pynguin.analyses.constants import ConstantProvider
    from pynguin.analyses.module import ModuleTestCluster


logger = logging.getLogger(__name__)


class InitialPopulationProvider:
    """Class for seeding the initial population with previously existing testcases."""

    def __init__(
        self,
        test_cluster: ModuleTestCluster,
        test_factory: tf.TestFactory,
        constant_provider: ConstantProvider,
    ):
        """Create new population provider.

        Args:
            test_cluster: Test cluster used to construct test cases
            test_factory: Test factory used to construct test cases
            constant_provider: Constant provider for primitives
        """
        self._testcases: list[dtc.DefaultTestCase] = []
        self._test_cluster: ModuleTestCluster = test_cluster
        self._test_factory: tf.TestFactory = test_factory
        self._constant_provider: ConstantProvider = constant_provider

    @staticmethod
    def _get_ast_tree(module_path: AnyStr | os.PathLike[AnyStr]) -> ast.Module | None:
        """Returns the ast tree from a module.

        Args:
            module_path: The path to the project's root

        Returns:
            The ast tree of the given module.
        """
        module_name = config.configuration.module_name.rsplit(".", maxsplit=1)[-1]
        logger.debug("Module name: %s", module_name)
        result: list[Path] = []
        for root, _, files in os.walk(module_path):
            root_path = Path(root).resolve()  # type: ignore[arg-type]
            for name in files:
                assert isinstance(name, str)
                if module_name in name and "test_" in name:
                    result.append(root_path / name)
                    break
        try:
            if len(result) > 0:
                logger.debug("Module name found: %s", result[0])
                stat.track_output_variable(RuntimeVariable.SuitableTestModule, value=True)
                with result[0].open(mode="r", encoding="utf-8") as module_file:
                    return ast.parse(module_file.read())
            else:
                logger.debug("No suitable test module found.")
                stat.track_output_variable(RuntimeVariable.SuitableTestModule, value=False)
                return None
        except BaseException as exception:
            logger.exception("Cannot read module: %s", exception)
            stat.track_output_variable(RuntimeVariable.SuitableTestModule, value=False)
            return None

    def collect_testcases(self, module_path: AnyStr | os.PathLike[AnyStr]) -> None:
        """Collect all test cases from a module.

        Args:
            module_path: Path to the module to collect the test cases from
        """
        tree = self._get_ast_tree(module_path)
        if tree is None:
            logger.info("Provided testcases are not used.")
            return
        transformer = AstToTestCaseTransformer(
            self._test_cluster,
            config.configuration.test_case_output.assertion_generation
            != config.AssertionGenerator.NONE,
            constant_provider=self._constant_provider,
        )
        transformer.visit(tree)
        self._testcases = transformer.testcases
        stat.track_output_variable(RuntimeVariable.FoundTestCases, len(self._testcases))
        stat.track_output_variable(RuntimeVariable.CollectedTestCases, len(self._testcases))
        self._mutate_testcases_initially()

    def _mutate_testcases_initially(self):
        """Mutates the initial population."""
        for _ in range(config.configuration.seeding.initial_population_mutations):
            for testcase in self._testcases:
                testcase_wrapper = tcc.TestCaseChromosome(testcase, self._test_factory)
                testcase_wrapper.mutate()
                if not testcase_wrapper.test_case.statements:
                    self._testcases.remove(testcase)  # noqa: B909

    def random_testcase(self) -> tc.TestCase:
        """Provides a random seeded test case.

        Returns:
            A random test case
        """
        return randomness.choice(self._testcases)

    def __len__(self) -> int:
        """Number of parsed test cases.

        Returns:
            Number of parsed test cases
        """
        return len(self._testcases)


def create_assign_stmt(
    assign: ast.Assign,
    testcase: tc.TestCase,
    ref_dict: dict[str, vr.VariableReference],
    test_cluster: ModuleTestCluster,
    constant_provider: ConstantProvider,
) -> tuple[str, stmt.VariableCreatingStatement] | None:
    """Creates the corresponding statement from an ast.Assign node.

    Args:
        assign: The ast.Assign node
        testcase: The testcase of the statement
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references.
        test_cluster: The test cluster that is used to resolve classes, methods, etc.
        constant_provider: Constant provider for primitives

    Returns:
        The corresponding statement or None if no statement type matches.
    """
    new_stmt: stmt.VariableCreatingStatement | None
    value = assign.value
    objs_under_test = test_cluster.accessible_objects_under_test
    callable_objects_under_test: set[GenericCallableAccessibleObject] = {
        o for o in objs_under_test if isinstance(o, GenericCallableAccessibleObject)
    }
    if isinstance(value, ast.Constant):
        new_stmt = create_stmt_from_constant(value, testcase, constant_provider=constant_provider)
    elif isinstance(value, ast.UnaryOp):
        new_stmt = create_stmt_from_unaryop(value, testcase, constant_provider=constant_provider)
    elif isinstance(value, ast.Call):
        new_stmt = create_stmt_from_call(
            value,
            testcase,
            callable_objects_under_test,
            ref_dict,
            constant_provider=constant_provider,
        )
    elif isinstance(value, ast.List | ast.Set | ast.Dict | ast.Tuple):
        new_stmt = create_stmt_from_collection(
            value,
            testcase,
            callable_objects_under_test,
            ref_dict,
            constant_provider=constant_provider,
        )
    else:
        logger.info("Assign statement could not be parsed.")
        new_stmt = None
    if new_stmt is None:
        return None
    ref_id = str(assign.targets[0].id)  # type: ignore[attr-defined]
    return ref_id, new_stmt


def create_assert_stmt(
    ref_dict: dict[str, vr.VariableReference], assert_node: ast.Assert
) -> tuple[ass.Assertion, vr.VariableReference] | None:
    """Creates an assert statement.

    Args:
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references.
        assert_node: the ast assert node.

    Returns:
        The corresponding assert statement.
    """
    assertion: ass.Assertion | None = None
    try:
        source = ref_dict[assert_node.test.left.id]  # type: ignore[attr-defined]
        val_elem = assert_node.test.comparators[0]  # type: ignore[attr-defined]
        operator = assert_node.test.ops[0]  # type: ignore[attr-defined]
    except (KeyError, AttributeError):
        return None
    if isinstance(operator, ast.Is | ast.Eq):
        assertion = create_assertion(source, val_elem)
    if assertion is not None:
        return assertion, source
    return None


def create_assertion(
    source: vr.VariableReference,
    val_elem: ast.Constant | ast.UnaryOp | None,
) -> ass.Assertion | None:
    """Creates an assertion.

    Args:
        source: The variable reference
        val_elem: The ast element for retrieving the value

    Returns:
        The assertion.
    """
    if isinstance(val_elem, ast.UnaryOp):
        val_elem = val_elem.operand  # type: ignore[assignment]

    if isinstance(val_elem, ast.Constant) and is_assertable(val_elem.value):
        return ass.ObjectAssertion(source, val_elem.value)
    return None


def create_variable_references_from_call_args(
    call_args: list[ast.Name | ast.Starred],
    call_keywords: list[ast.keyword],
    gen_callable: GenericCallableAccessibleObject,
    ref_dict: dict[str, vr.VariableReference],
) -> dict[str, vr.VariableReference] | None:
    """Creates variable references from call arguments.

    Takes the arguments of an ast.Call node and returns the variable references of
    the corresponding statements.

    Args:
        call_args: the positional arguments
        call_keywords: the keyword arguments
        gen_callable: the callable that is called
        ref_dict: a dictionary containing the variable references

    Returns:
        The dict with the variable references of the call_args.
    """
    var_refs: dict[str, vr.VariableReference] = {}
    # We have to ignore the first parameter (usually 'self') for regular methods and
    # constructors because it is filled by the runtime.
    # TODO(fk) also consider @classmethod, because their first argument is the class,
    #  which is also filled by the runtime.

    shift_by = 1 if gen_callable.is_method() or gen_callable.is_constructor() else 0

    # Handle positional arguments.
    # TODO(sl) check for the zip, it sometimes gets lists of different lengths, where it
    #  silently swallows the rest of the longer list—the strict parameter would prevent
    #  this but causes failures in our test suite; needs investigation...
    for (name, param), call_arg in zip(  # noqa: B905
        list(gen_callable.inferred_signature.signature.parameters.items())[shift_by:],
        call_args,
    ):
        if (
            param.kind
            in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            }
        ) and isinstance(call_arg, ast.Name):
            reference = ref_dict.get(call_arg.id)
        elif param.kind == inspect.Parameter.VAR_POSITIONAL and isinstance(call_arg, ast.Starred):
            reference = ref_dict.get(call_arg.value.id)  # type: ignore[attr-defined]
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
            keyword = list(gen_callable.inferred_signature.signature.parameters.keys())[-1]
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


def create_stmt_from_constant(
    constant: ast.Constant, testcase: tc.TestCase, constant_provider: ConstantProvider
) -> stmt.VariableCreatingStatement | None:
    """Creates a statement from an ast.constant node.

    Args:
        constant: the ast.Constant statement
        testcase: the testcase containing the statement
        constant_provider: Constant provider for primitives

    Returns:
        The corresponding statement.
    """
    if constant.value is None:
        return stmt.NoneStatement(testcase)

    val = constant.value
    if isinstance(val, bool):
        return stmt.BooleanPrimitiveStatement(testcase, val)
    if isinstance(val, int):
        return stmt.IntPrimitiveStatement(testcase, val, constant_provider=constant_provider)
    if isinstance(val, float):
        return stmt.FloatPrimitiveStatement(testcase, val, constant_provider=constant_provider)
    if isinstance(val, str):
        return stmt.StringPrimitiveStatement(testcase, val, constant_provider=constant_provider)
    if isinstance(val, bytes):
        return stmt.BytesPrimitiveStatement(testcase, val, constant_provider=constant_provider)
    logger.info("Could not find case for constant while handling assign statement.")
    return None


def create_stmt_from_unaryop(
    unaryop: ast.UnaryOp, testcase: tc.TestCase, constant_provider: ConstantProvider
) -> stmt.VariableCreatingStatement | None:
    """Creates a statement from an ast.unaryop node.

    Args:
        unaryop: the ast.UnaryOp statement
        testcase: the testcase containing the statement
        constant_provider: Constant provider for primitives

    Returns:
        The corresponding statement.
    """
    val = unaryop.operand.value  # type: ignore[attr-defined]
    if isinstance(val, bool):
        return stmt.BooleanPrimitiveStatement(testcase, not val)
    if isinstance(val, float):
        return stmt.FloatPrimitiveStatement(
            testcase, (-1) * val, constant_provider=constant_provider
        )
    if isinstance(val, int):
        return stmt.IntPrimitiveStatement(testcase, (-1) * val, constant_provider=constant_provider)
    logger.info("Could not find case for unary operator while handling assign statement.")
    return None


def create_stmt_from_call(
    call: ast.Call,
    testcase: tc.TestCase,
    objs_under_test: set[GenericCallableAccessibleObject],
    ref_dict: dict[str, vr.VariableReference],
    constant_provider: ConstantProvider,
) -> stmt.VariableCreatingStatement | None:
    """Creates the corresponding statement from an ast.call node.

    Depending on the call, this can be a GenericConstructor, GenericMethod, or
    GenericFunction statement.

    Args:
        call: the ast.Call node
        testcase: the testcase of the statement
        objs_under_test: the accessible objects under test
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references.
        constant_provider: Constant provider for primitives

    Returns:
        The corresponding statement.
    """
    try:
        call.func.attr  # type: ignore[attr-defined]  # noqa: B018
    except AttributeError:
        return try_generating_specific_function(
            call,
            testcase,
            objs_under_test,
            ref_dict,
            constant_provider=constant_provider,
        )
    gen_callable = find_gen_callable(call, objs_under_test, ref_dict)
    if gen_callable is None:
        logger.info("No such function found...")
        return None
    return assemble_stmt_from_gen_callable(testcase, gen_callable, call, ref_dict)


def find_gen_callable(
    call: ast.Call,
    objs_under_test: set,
    ref_dict: dict[str, vr.VariableReference],
) -> GenericConstructor | GenericMethod | GenericFunction | None:
    """Find a call object.

    Traverses the accessible objects under test and returns the one matching with the
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
    call_name = str(call.func.attr)  # type: ignore[attr-defined]
    for obj in objs_under_test:
        if isinstance(obj, GenericConstructor):
            assert obj.owner
            owner = str(obj.owner.name)
            call_id = call.func.value.id  # type: ignore[attr-defined]
            if call_name == owner and call_id not in ref_dict:
                return obj
        elif isinstance(obj, GenericMethod):
            # test if the type of the calling object is equal to the type of the owner
            # of the generic method
            call_id = call.func.value.id  # type: ignore[attr-defined]
            if call_name == obj.method_name and call_id in ref_dict:
                obj_from_ast = str(call.func.value.id)  # type: ignore[attr-defined]
                var_type = ref_dict[obj_from_ast].type
                if isinstance(var_type, Instance) and var_type.type == obj.owner:
                    return obj
        elif isinstance(obj, GenericFunction) and call_name == obj.function_name:
            return obj
    return None


def assemble_stmt_from_gen_callable(
    testcase: tc.TestCase,
    gen_callable: GenericCallableAccessibleObject,
    call: ast.Call,
    ref_dict: dict[str, vr.VariableReference],
) -> stmt.ParametrizedStatement | None:
    """Takes a generic callable and assembles the corresponding parametrized statement.

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
        if not isinstance(arg, ast.Name | ast.Starred):
            return None
    for keyword in call.keywords:
        if not isinstance(keyword, ast.keyword):
            return None
    var_refs = create_variable_references_from_call_args(
        call.args,  # type: ignore[arg-type]
        call.keywords,
        gen_callable,
        ref_dict,
    )
    if var_refs is None:
        return None
    if isinstance(gen_callable, GenericFunction):
        return stmt.FunctionStatement(
            testcase, cast("GenericCallableAccessibleObject", gen_callable), var_refs
        )
    if isinstance(gen_callable, GenericMethod):
        return stmt.MethodStatement(
            testcase,
            gen_callable,
            ref_dict[call.func.value.id],  # type: ignore[attr-defined]
            var_refs,
        )
    if isinstance(gen_callable, GenericConstructor):
        return stmt.ConstructorStatement(
            testcase, cast("GenericCallableAccessibleObject", gen_callable), var_refs
        )
    return None


def create_stmt_from_collection(
    coll_node: ast.List | ast.Set | ast.Dict | ast.Tuple,
    testcase: tc.TestCase,
    objs_under_test: set[GenericCallableAccessibleObject],
    ref_dict: dict[str, vr.VariableReference],
    constant_provider: ConstantProvider,
) -> stmt.VariableCreatingStatement | None:
    """Creates the corresponding statement from an ast.List node.

    Lists contain other statements.

    Args:
        coll_node: the ast node. It has the type of one of the collection types.
        testcase: the testcase of the statement
        objs_under_test: the accessible objects under test. Not needed for the
                         collection statement, but lists can contain other statements
                         (e.g. call) needing this.
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references. Not needed for the collection statement, but
                  lists can contain other statements (e.g. call) needing this.
        constant_provider: Constant provider for primitives

    Returns:
        The corresponding list statement.
    """
    coll_elems: None | (  # noqa: RUF036
        list[vr.VariableReference] | list[tuple[vr.VariableReference, vr.VariableReference]]
    )
    if isinstance(coll_node, ast.Dict):
        keys = create_elements(
            coll_node.keys,
            testcase,
            objs_under_test,
            ref_dict,
            constant_provider=constant_provider,
        )
        values = create_elements(
            coll_node.values,
            testcase,
            objs_under_test,
            ref_dict,
            constant_provider=constant_provider,
        )
        if keys is None or values is None:
            return None
        coll_elems_type: ProperType = Instance(
            testcase.test_cluster.type_system.to_type_info(dict),
            (get_collection_type(keys), get_collection_type(values)),
        )
        coll_elems = list(zip(keys, values, strict=True))
    else:
        elements = coll_node.elts
        coll_elems = create_elements(
            elements,
            testcase,
            objs_under_test,
            ref_dict,
            constant_provider=constant_provider,
        )
        if coll_elems is None:
            return None
        if isinstance(coll_node, ast.Tuple):
            coll_elems_type = TupleType(tuple(tp.type for tp in coll_elems))
        elif isinstance(coll_node, ast.List):
            coll_elems_type = Instance(
                testcase.test_cluster.type_system.to_type_info(list),
                (get_collection_type(coll_elems),),
            )
        else:
            coll_elems_type = Instance(
                testcase.test_cluster.type_system.to_type_info(set),
                (get_collection_type(coll_elems),),
            )
    return create_specific_collection_stmt(testcase, coll_node, coll_elems_type, coll_elems)


def create_elements(  # noqa: C901
    elements: Any,
    testcase: tc.TestCase,
    objs_under_test: set[GenericCallableAccessibleObject],
    ref_dict: dict[str, vr.VariableReference],
    constant_provider: ConstantProvider,
) -> list[vr.VariableReference] | None:
    """Creates the elements of a collection.

    Calls the corresponding methods for creation. This can be recursive.

    Args:
        elements: The elements of the collection
        testcase: the corresponding testcase
        objs_under_test: A set of generic accessible objects under test
        ref_dict: a dictionary containing key value pairs of variable ids and
                  variable references
        constant_provider: Constant provider for primitives

    Returns:
        A list of variable references or None if something goes wrong while creating the
        elements.
    """
    coll_elems: list[vr.VariableReference] = []
    for elem in elements:
        statement: stmt.VariableCreatingStatement | None
        if isinstance(elem, ast.Constant):
            statement = create_stmt_from_constant(
                elem, testcase, constant_provider=constant_provider
            )
            if not statement:
                return None
            coll_elems.append(testcase.add_variable_creating_statement(statement))
        elif isinstance(elem, ast.UnaryOp):
            statement = create_stmt_from_unaryop(
                elem, testcase, constant_provider=constant_provider
            )
            if not statement:
                return None
            coll_elems.append(testcase.add_variable_creating_statement(statement))
        elif isinstance(elem, ast.Call):
            statement = create_stmt_from_call(
                elem,
                testcase,
                objs_under_test,
                ref_dict,
                constant_provider=constant_provider,
            )
            if not statement:
                return None
            coll_elems.append(testcase.add_variable_creating_statement(statement))
        elif isinstance(elem, ast.List | ast.Tuple | ast.Set | ast.Dict):
            statement = create_stmt_from_collection(
                elem,
                testcase,
                objs_under_test,
                ref_dict,
                constant_provider=constant_provider,
            )
            if not statement:
                return None
            coll_elems.append(testcase.add_variable_creating_statement(statement))
        elif isinstance(elem, ast.Name):
            try:
                coll_elems.append(ref_dict[elem.id])
            except AttributeError:
                return None
        else:
            return None
    return coll_elems


def get_collection_type(coll_elems: list[vr.VariableReference]) -> ProperType:
    """Returns the type of a collection.

    If objects of multiple types are in the collection, this function returns None.

    Args:
        coll_elems: a list of variable references

    Returns:
        The type of the collection.
    """
    if len(coll_elems) == 0:
        return ANY
    coll_type = coll_elems[0].type
    for elem in coll_elems:
        if elem.type != coll_type:
            coll_type = ANY
            break
    return coll_type


def create_specific_collection_stmt(
    testcase: tc.TestCase,
    coll_node: ast.List | ast.Set | ast.Dict | ast.Tuple,
    coll_elems_type: ProperType,
    coll_elems: list[Any],
) -> None | (  # noqa: RUF036
    stmt.ListStatement | stmt.SetStatement | stmt.DictStatement | stmt.TupleStatement
):
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
    objs_under_test: set[GenericCallableAccessibleObject],
    ref_dict: dict[str, vr.VariableReference],
    constant_provider: ConstantProvider,
) -> stmt.VariableCreatingStatement | None:
    """Aims to generate specific functions.

    Calls to creating a collection (list, set, tuple, dict) via their keywords and
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
        constant_provider: Constant provider for primitives

    Returns:
        The corresponding statement.
    """
    try:
        func_id = str(call.func.id)  # type: ignore[attr-defined]
    except AttributeError:
        return None
    if func_id == "set":
        try:
            set_node = ast.Set(
                elts=call.args,
                ctx=ast.Load(),  # type: ignore[call-arg]
            )
        except AttributeError:
            return None
        return create_stmt_from_collection(
            set_node,
            testcase,
            objs_under_test,
            ref_dict,
            constant_provider=constant_provider,
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
            list_node,
            testcase,
            objs_under_test,
            ref_dict,
            constant_provider=constant_provider,
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
            tuple_node,
            testcase,
            objs_under_test,
            ref_dict,
            constant_provider=constant_provider,
        )
    if func_id == "dict":
        try:
            dict_node = ast.Dict(  # type: ignore[call-arg]
                keys=(
                    call.args[0].keys if call.args else []  # type: ignore[attr-defined]
                ),
                values=(
                    call.args[0].values  # type: ignore[attr-defined]
                    if call.args
                    else []
                ),
                ctx=ast.Load(),
            )
        except AttributeError:
            return None
        return create_stmt_from_collection(
            dict_node,
            testcase,
            objs_under_test,
            ref_dict,
            constant_provider=constant_provider,
        )
    return None


class AstToTestCaseTransformer(ast.NodeVisitor):
    """Transforms a Python AST into our internal test-case representation."""

    def __init__(  # noqa: D107
        self,
        test_cluster: ModuleTestCluster,
        create_assertions: bool,  # noqa: FBT001
        constant_provider: ConstantProvider,
    ):
        self._current_testcase: dtc.DefaultTestCase = dtc.DefaultTestCase(test_cluster)
        self._current_parsable: bool = True
        self._var_refs: dict[str, vr.VariableReference] = {}
        self._testcases: list[dtc.DefaultTestCase] = []
        self._number_found_testcases: int = 0
        self._test_cluster = test_cluster
        self._create_assertions = create_assertions
        self._constant_provider = constant_provider

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:  # noqa: D102, N802
        self._number_found_testcases += 1
        self._current_testcase = dtc.DefaultTestCase(self._test_cluster)
        self._current_parsable = True
        self._var_refs.clear()
        self.generic_visit(node)
        if self._current_parsable:
            self._testcases.append(self._current_testcase)

    def visit_Assign(self, node: ast.Assign) -> Any:  # noqa: D102, N802
        if self._current_parsable:
            if (
                result := create_assign_stmt(
                    node,
                    self._current_testcase,
                    self._var_refs,
                    self._test_cluster,
                    self._constant_provider,
                )
            ) is None:
                self._current_parsable = False
            else:
                ref_id, stm = result
                var_ref = self._current_testcase.add_variable_creating_statement(stm)
                self._var_refs[ref_id] = var_ref

    def visit_Assert(self, node: ast.Assert) -> Any:  # noqa: D102, N802
        if self._current_parsable and self._create_assertions:  # noqa: SIM102
            if (result := create_assert_stmt(self._var_refs, node)) is not None:
                assertion, var_ref = result
                self._current_testcase.get_statement(
                    var_ref.get_statement_position()
                ).add_assertion(assertion)

    @property
    def testcases(self) -> list[dtc.DefaultTestCase]:
        """Provides the testcases that could be generated from the given AST.

        It is possible that not every aspect of the AST could be transformed
        to our internal representation.

        Returns:
            The generated testcases.
        """
        return self._testcases
