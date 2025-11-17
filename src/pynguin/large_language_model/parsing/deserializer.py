# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
# SPDX-FileCopyrightText: 2023 Microsoft
#
# SPDX-License-Identifier: MIT
#
"""A class to deserialize AST nodes into Statements in a TestCase.

The logic is adapted from the CodaMosa repository with additional refactoring.
https://github.com/microsoft/codamosa
"""

from __future__ import annotations

import ast
import inspect
import logging
from typing import TYPE_CHECKING, Any, cast

import pynguin.testcase.defaulttestcase as dtc
from pynguin import configuration as config
from pynguin.analyses.seeding import get_collection_type
from pynguin.analyses.typesystem import AnyType, Instance, ProperType, TupleType
from pynguin.assertion import assertion as ass
from pynguin.large_language_model.parsing.helpers import _count_all_statements
from pynguin.testcase import statement as stmt
from pynguin.testcase import variablereference as vr
from pynguin.testcase.statement import ASTAssignStatement
from pynguin.testcase.variablereference import FieldReference, Reference
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
    GenericConstructor,
    GenericField,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.type_utils import is_assertable

if TYPE_CHECKING:
    from pynguin.analyses.module import TestCluster
    from pynguin.assertion.assertion import Assertion

logger = logging.getLogger(__name__)


class StatementDeserializer:  # noqa: PLR0904
    """All the utilities to deserialize statements."""

    def __init__(self, test_cluster: TestCluster):  # noqa: D107
        self._test_cluster = test_cluster
        self._ref_dict: dict[str, vr.VariableReference] = {}
        self._testcase = dtc.DefaultTestCase(self._test_cluster)
        self._uninterpreted_statements = 0

    @property
    def uninterpreted_statements(self) -> int:
        """Provides the number of uninterpreted statements.

        Returns:
            The count of uninterpreted statements.
        """
        return self._uninterpreted_statements

    def get_test_case(self) -> dtc.DefaultTestCase:
        """Returns the parsed testcase.

        Returns:
            the parsed testcase
        """
        return self._testcase

    def reset(self) -> None:
        """Resets the state of the deserializer to parse a new test case."""
        self._ref_dict = {}
        self._testcase = dtc.DefaultTestCase(self._test_cluster)

    def add_assert_stmt(self, assert_: ast.Assert) -> bool:
        """Tries to add the assert in `assert_` to the current test case.

        Args:
            assert_: The ast.Assert node

        Returns:
            True if the assert was parsed successfully, False otherwise
        """
        result = self.create_assert_stmt(assert_)
        if result is None:
            return False
        assertion, ref = result

        stmt_position = None
        if isinstance(ref, vr.VariableReference):
            stmt_position = ref.get_statement_position()
        elif isinstance(ref, vr.FieldReference):
            stmt_position = ref.get_variable_reference().get_statement_position()  # type: ignore[union-attr]
        if stmt_position:
            self._testcase.get_statement(stmt_position).add_assertion(assertion)  # type: ignore[arg-type]
        return True

    def add_assign_stmt(self, assign: ast.Assign) -> bool:
        """Tries to add the assignment in `assign` to the current test case.

        Args:
            assign: The ast.Assign node

        Returns:
            True if the assign was parsed successfully, False otherwise
        """
        result = self.create_assign_stmt(assign)
        if result is None:
            return False
        ref_id, stm = result
        var_ref = self._testcase.add_variable_creating_statement(stm)
        self._ref_dict[ref_id] = var_ref
        return True

    def create_assign_stmt(
        self, assign: ast.Assign
    ) -> tuple[str, stmt.VariableCreatingStatement] | None:
        """Creates the corresponding statement from an ast.Assign node.

        Args:
            assign: The ast.Assign node

        Returns:
            The corresponding statement or None if no statement type matches.
        """
        new_stmt: stmt.VariableCreatingStatement | None
        if len(assign.targets) > 1 or not isinstance(assign.targets[0], ast.Name):
            return None
        value = assign.value

        if isinstance(value, ast.Constant):
            new_stmt = self.create_stmt_from_constant(value)
        elif isinstance(value, ast.UnaryOp):
            new_stmt = self.create_stmt_from_unaryop(value)
        elif isinstance(value, ast.Call):
            new_stmt = self.create_stmt_from_call(value)
        elif isinstance(value, ast.List | ast.Set | ast.Dict | ast.Tuple):
            new_stmt = self.create_stmt_from_collection(value)
        else:
            new_stmt = self.create_ast_assign_stmt(value)
        if new_stmt is None:
            return None
        ref_id = str(assign.targets[0].id)
        return ref_id, new_stmt

    def create_ast_assign_stmt(self, rhs: ast.expr) -> ASTAssignStatement | None:
        """Creates an ASTAssignStatement from the given rhs.

        Args:
            rhs: right-hand side as an AST

        Returns:
            the corresponding ASTAssignStatement.
        """
        try:
            self._uninterpreted_statements += 1
            return ASTAssignStatement(self._testcase, rhs, self._ref_dict)
        except ValueError:
            return None

    def create_assert_stmt(
        self, assert_node: ast.Assert
    ) -> tuple[Assertion | None, Reference] | tuple[Assertion, Reference] | None:
        """Creates an assert statement.

        Args:
            assert_node: The AST assert node.

        Returns:
            The corresponding assert statement.
        """
        assertion: ass.Assertion | None = None

        # E.g: assert var
        if (
            isinstance(assert_node, ast.Assert)
            and hasattr(assert_node, "test")
            and isinstance(assert_node.test, ast.Name)
        ):
            source = self._get_source_reference(assert_node.test)
            return ass.ObjectAssertion(source, value=True), source

        try:
            # Assertion on attribute access
            # Example: assert x.attr == 5
            if (
                hasattr(assert_node, "left")
                and hasattr(assert_node, "ops")
                and hasattr(assert_node, "comparators")
            ):
                source = self._get_source_reference(
                    assert_node.left
                )  # Adjusted to handle ast.Attribute
                val_elem = assert_node.comparators[0]
                operator = assert_node.ops[0]
            # Isinstance assertion
            # Example: assert isinstance(x, int)
            elif (
                hasattr(assert_node, "test")
                and hasattr(assert_node.test, "func")
                and assert_node.test.func.id == "isinstance"
            ):
                source = self._get_source_reference(assert_node.test.args[0])  # type: ignore[attr-defined]
                type_elem = assert_node.test.args[1]  # type: ignore[attr-defined]
                assertion = ass.IsInstanceAssertion(source, type_elem)
                return assertion, source
            # Assertion with function call on the left side
            # Example: assert some_function() == expected_value
            elif (
                hasattr(assert_node, "test")
                and hasattr(assert_node.test, "left")
                and hasattr(assert_node.test, "comparators")
                and hasattr(assert_node.test, "ops")
                and hasattr(assert_node.test.left, "func")
            ):
                source = self._get_source_reference(
                    assert_node.test.left.func
                )  # Adjusted to handle ast.Attribute
                val_elem = assert_node.test.comparators[0]
                operator = assert_node.test.ops[0]
            # Standard double-equals comparison
            # Example: assert x == 5
            else:
                source = self._get_source_reference(
                    assert_node.test.left  # type: ignore[attr-defined]
                )  # Adjusted to handle ast.Attribute
                val_elem = assert_node.test.comparators[0]  # type: ignore[attr-defined]
                operator = assert_node.test.ops[0]  # type: ignore[attr-defined]
        # Invalid or not beneficial assert structure
        # Example: assert True
        except (KeyError, AttributeError):
            return None

        if isinstance(operator, ast.Is | ast.Eq):
            assertion = self.create_assertion(source, val_elem)  # type: ignore[arg-type]

        if assertion is not None:
            return assertion, source

        return None

    def _get_source_reference(self, node: ast.AST) -> vr.Reference:
        """Gets the source reference from the AST node, handling attributes and names.

        Args:
            node: The AST node to extract the source reference from.

        Returns:
            The corresponding variable reference.
        """
        if isinstance(node, ast.Attribute):
            source = self._ref_dict[node.value.id]  # type: ignore[attr-defined]
            type_info = source.type.type  # type: ignore[attr-defined]
            attribute = node.attr
            field_type = source.type
            field = GenericField(type_info, attribute, field_type)
            return FieldReference(source, field)
        return self._ref_dict[node.id]  # type: ignore[attr-defined]

    def create_assertion(
        self,
        source: vr.VariableReference,
        val_elem: ast.Constant | ast.UnaryOp | None,
    ) -> ass.Assertion | None:
        """Creates an assertion.

        Args:
            source: The variable reference
            val_elem: The AST element for retrieving the value

        Returns:
            The assertion.
        """
        if isinstance(val_elem, ast.UnaryOp):
            val_elem = val_elem.operand  # type: ignore[assignment]

        # Extract the value from the AST node
        value = self._extract_value_from_ast(val_elem)  # type: ignore[arg-type]

        # Check if the extracted value is assertable
        if isinstance(value, float):
            return ass.FloatAssertion(source, value)
        if is_assertable(value):
            return ass.ObjectAssertion(source, value)

        return None

    def _extract_value_from_ast(self, node: ast.AST) -> Any:
        """Recursively extract values from AST nodes representing collections.

        Args:
            node: The AST node representing a collection or constant.

        Returns:
            The actual value represented by the AST node.
        """
        if isinstance(node, ast.List):
            return [self._extract_value_from_ast(elem) for elem in node.elts]
        if isinstance(node, ast.Name):
            return None
        if isinstance(node, ast.Call):
            return None
        if isinstance(node, ast.Tuple):
            return tuple(self._extract_value_from_ast(elem) for elem in node.elts)
        if isinstance(node, ast.Set):
            return {self._extract_value_from_ast(elem) for elem in node.elts}
        if isinstance(node, ast.Dict):
            return {
                self._extract_value_from_ast(key): self._extract_value_from_ast(value)  # type: ignore[arg-type]
                for key, value in zip(node.keys, node.values, strict=False)
            }
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -self._extract_value_from_ast(node.operand)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
            return self._extract_value_from_ast(node.operand)

        raise ValueError(f"Unsupported AST node type: {type(node)}")

    def create_variable_references_from_call_args(
        self,
        call_args: list[ast.Name | ast.Starred],
        call_keywords: list[ast.keyword],
        gen_callable: GenericCallableAccessibleObject,
    ) -> dict[str, vr.VariableReference] | None:
        """Creates variable reference from call args.

        Args:
            call_args: the positional arguments
            call_keywords: the keyword arguments
            gen_callable: the callable that is called

        Returns:
            The dict with the variable references of the call_args.
        """
        var_refs: dict[str, vr.VariableReference] = {}
        shift_by = (
            1
            if (
                gen_callable.is_method()
                or gen_callable.is_constructor()
                or gen_callable.is_classmethod()
            )
            else 0
        )

        # Handle positional arguments.
        for (name, param), call_arg in zip(
            list(gen_callable.inferred_signature.signature.parameters.items())[shift_by:],
            call_args,
            strict=False,
        ):
            if (
                param.kind
                in {
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                }
            ) and isinstance(call_arg, ast.Name):
                reference = self._ref_dict.get(call_arg.id)
            elif param.kind == inspect.Parameter.VAR_POSITIONAL and isinstance(
                call_arg, ast.Starred
            ):
                reference = self._ref_dict.get(call_arg.value.id)  # type: ignore[attr-defined]
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
                keyword = list(gen_callable.inferred_signature.signature.parameters.keys())[-1]
                if (
                    gen_callable.inferred_signature.signature.parameters[keyword].kind
                    != inspect.Parameter.VAR_KEYWORD
                ):
                    return None
            if not isinstance(call_keyword.value, ast.Name):
                return None
            reference = self._ref_dict.get(call_keyword.value.id)
            if reference is None:
                return None
            var_refs[keyword] = reference

        return var_refs

    def create_stmt_from_constant(
        self, constant: ast.Constant
    ) -> stmt.VariableCreatingStatement | None:
        """Creates a statement from an ast.Constant node.

        Args:
            constant: the ast.Constant statement

        Returns:
            The corresponding statement.
        """
        if constant.value is None:
            return stmt.NoneStatement(self._testcase)

        val = constant.value
        if isinstance(val, bool):
            return stmt.BooleanPrimitiveStatement(self._testcase, val)
        if isinstance(val, int):
            return stmt.IntPrimitiveStatement(self._testcase, val)
        if isinstance(val, float):
            return stmt.FloatPrimitiveStatement(self._testcase, val)
        if isinstance(val, str):
            return stmt.StringPrimitiveStatement(self._testcase, val)
        if isinstance(val, bytes):
            return stmt.BytesPrimitiveStatement(self._testcase, val)
        logger.debug("Could not find case for constant while handling assign statement.")
        return None

    def create_stmt_from_unaryop(
        self, unaryop: ast.UnaryOp
    ) -> stmt.VariableCreatingStatement | None:
        """Creates a statement from an ast.UnaryOp node.

        Args:
            unaryop: the ast.UnaryOp statement

        Returns:
            The corresponding statement.
        """
        if not isinstance(unaryop.operand, ast.Constant):
            return None
        val = unaryop.operand.value
        if isinstance(val, bool):
            return stmt.BooleanPrimitiveStatement(self._testcase, not val)
        if isinstance(val, float):
            return stmt.FloatPrimitiveStatement(self._testcase, (-1) * val)
        if isinstance(val, int):
            return stmt.IntPrimitiveStatement(self._testcase, (-1) * val)
        logger.debug("Could not find case for unary operator while handling assign statement.")
        return None

    def create_stmt_from_call(self, call: ast.Call) -> stmt.VariableCreatingStatement | None:
        """Creates the corresponding statement from an ast.call.

        Depending on the call, this can be a GenericConstructor, GenericMethod
        or GenericFunction statement.

        Args:
            call: the ast.Call node

        Returns:
            The corresponding statement.
        """
        gen_callable = self.find_gen_callable(call)
        if gen_callable is None:
            logger.debug("No such function found: %s", ast.unparse(call.func))
            return self.try_generating_specific_function(call)
        return self.assemble_stmt_from_gen_callable(gen_callable, call)

    def find_gen_callable(  # noqa: C901
        self, call: ast.Call
    ) -> GenericConstructor | GenericMethod | GenericFunction | None:
        """Traverses the accessible objects under test.

        Returns the one matching with the ast.call object. Unfortunately,
        there is no possibility to clearly determine if the ast.call object
        is a constructor, method or function. Hence, the looping over
        all accessible objects is unavoidable. Then, by the name of the ast.call
         and by the owner (functions do not have one, constructors and methods have),
        it is possible to decide which accessible object to choose.

        This should also be unique, because the name of a function should
        be unique in a module. The name of a method should be unique inside one class.
        If two classes in the same module have a method with an equal name, the right
        method can be determined by the type of the object that is calling the method.
        This object has the type of the class of which the method is called.
        To determine between function names and method names, another thing
        needs to be considered. If a method is called, it is called on an object.
        This object must have been created before the function is called on
        that object. Thus, this object must have been initialized before and have
        a variable reference in the ref_dict where all created variable
        references are stored. So, by checking, if a reference is found,
         it can be decided if it is a function or a method.

        Args:
            call: the ast.Call node

        Returns:
            The corresponding generic accessible object under test. This can be a
            GenericConstructor, a GenericMethod or a GenericFunction.
        """
        if isinstance(call.func, ast.Name):
            call_name = call.func.id
        elif isinstance(call.func, ast.Attribute):
            call_name = str(call.func.attr)
        else:
            logger.debug("Strange function call: %s", ast.unparse(call))
            return None
        try:
            call_id = call.func.value.id  # type: ignore[union-attr]
        except AttributeError:
            logger.debug("Can't get called for %s", ast.unparse(call))
            call_id = ""

        for obj in self._test_cluster.accessible_objects_under_test:
            if isinstance(obj, GenericConstructor):
                owner = str(obj.owner).rsplit(".", maxsplit=1)[-1].split("'")[0].rstrip(")")
                if call_name == owner and call_id not in self._ref_dict:
                    return obj
            elif isinstance(obj, GenericMethod):
                if call_name == obj.method_name and call_id in self._ref_dict:
                    obj_from_ast = str(call_id)
                    var_type = self._ref_dict[obj_from_ast].type
                    if isinstance(var_type, AnyType):
                        return obj
                    if var_type == obj.owner or (
                        hasattr(var_type, "type") and var_type.type == obj.owner
                    ):
                        return obj
            elif isinstance(obj, GenericFunction):
                if call_name == obj.function_name:
                    return obj
        return None

    def assemble_stmt_from_gen_callable(
        self, gen_callable: GenericCallableAccessibleObject, call: ast.Call
    ) -> stmt.ParametrizedStatement | None:
        """Takes a generic callable.

        Also assembles the corresponding parametrized statement from it.

        Args:
            gen_callable: the corresponding callable of the cluster
            call: the ast.Call statement

        Returns:
            The corresponding statement.
        """
        for arg in call.args:
            if not isinstance(arg, ast.Name | ast.Starred):
                return None
        for keyword in call.keywords:
            if not isinstance(keyword, ast.keyword):
                return None
        var_refs = self.create_variable_references_from_call_args(
            call.args,  # type: ignore[arg-type]
            call.keywords,
            gen_callable,
        )
        if var_refs is None:
            return None
        if isinstance(gen_callable, GenericFunction):
            return stmt.FunctionStatement(
                self._testcase,
                cast("GenericCallableAccessibleObject", gen_callable),
                var_refs,
            )
        if isinstance(gen_callable, GenericMethod):
            try:
                self._ref_dict[call.func.value.id]  # type: ignore[attr-defined]
            except (KeyError, AttributeError):
                return None
            return stmt.MethodStatement(
                self._testcase,
                gen_callable,
                self._ref_dict[call.func.value.id],  # type: ignore[attr-defined]
                var_refs,
            )
        if isinstance(gen_callable, GenericConstructor):
            return stmt.ConstructorStatement(
                self._testcase,
                cast("GenericCallableAccessibleObject", gen_callable),
                var_refs,
            )
        return None

    def create_stmt_from_collection(
        self, coll_node: ast.List | ast.Set | ast.Dict | ast.Tuple
    ) -> stmt.VariableCreatingStatement | None:
        """Creates the corresponding statement from an ast.List node.

        Lists contain other statements.

        Args:
            coll_node: the ast node. It has the type of one of the collection types.

        Returns:
            The corresponding list statement.
        """
        coll_elems: (
            list[vr.VariableReference] | list[tuple[vr.VariableReference, vr.VariableReference]]
        ) | None
        if isinstance(coll_node, ast.Dict):
            keys = self.create_elements(coll_node.keys)
            values = self.create_elements(coll_node.values)
            if keys is None or values is None:
                return None
            coll_elems_type: ProperType = Instance(
                self._test_cluster.type_system.to_type_info(dict),
                (get_collection_type(keys), get_collection_type(values)),
            )
            coll_elems = list(zip(keys, values, strict=True))
        else:
            elements = coll_node.elts
            coll_elems = self.create_elements(elements)
            if coll_elems is None:
                return None
            coll_elems_type = self.get_collection_type(coll_node, coll_elems)
        return self.create_specific_collection_stmt(coll_node, coll_elems_type, coll_elems)

    def create_elements(  # noqa: C901
        self, elements: Any
    ) -> list[vr.VariableReference] | None:
        """Creates the elements of a collection.

        This is done by calling the corresponding methods
        for creation. This can be recursive.

        Args:
            elements: The elements of the collection

        Returns:
            A list of variable references or None if something goes wrong while
            creating the elements.
        """
        coll_elems: list[vr.VariableReference] = []
        for elem in elements:
            statement: stmt.VariableCreatingStatement | None
            if isinstance(elem, ast.Constant):
                statement = self.create_stmt_from_constant(elem)
                if not statement:
                    return None
                coll_elems.append(self._testcase.add_variable_creating_statement(statement))
            elif isinstance(elem, ast.UnaryOp):
                statement = self.create_stmt_from_unaryop(elem)
                if not statement:
                    return None
                coll_elems.append(self._testcase.add_variable_creating_statement(statement))
            elif isinstance(elem, ast.Call):
                statement = self.create_stmt_from_call(elem)
                if not statement:
                    return None
                coll_elems.append(self._testcase.add_variable_creating_statement(statement))
            elif isinstance(elem, ast.List | ast.Tuple | ast.Set | ast.Dict):
                statement = self.create_stmt_from_collection(elem)
                if not statement:
                    return None
                coll_elems.append(self._testcase.add_variable_creating_statement(statement))
            elif isinstance(elem, ast.Name):
                try:
                    coll_elems.append(self._ref_dict[elem.id])
                except (KeyError, AttributeError):
                    return None
            else:
                return None
        return coll_elems

    def get_collection_type(
        self,
        coll_node: ast.List | ast.Set | ast.Dict | ast.Tuple,
        coll_elems: list[vr.VariableReference],
    ) -> Any:
        """Returns the type of collection.

        If objects of multiple types are in the collection, this function returns None.

        Args:
            coll_node: the ast node. It has the type of one of the collection types.
            coll_elems: a list of variable references

        Returns:
            The type of the collection.
        """
        if coll_elems is None:
            return None
        if isinstance(coll_node, ast.Tuple):
            coll_elems_type = TupleType(tuple(tp.type for tp in coll_elems))
        elif isinstance(coll_node, ast.List):
            coll_elems_type = Instance(  # type:ignore[assignment]
                self._test_cluster.type_system.to_type_info(list),
                (get_collection_type(coll_elems),),
            )
        else:
            coll_elems_type = Instance(  # type:ignore[assignment]
                self._test_cluster.type_system.to_type_info(set),
                (get_collection_type(coll_elems),),
            )
        return coll_elems_type

    def create_specific_collection_stmt(
        self,
        coll_node: ast.List | ast.Set | ast.Dict | ast.Tuple,
        coll_elems_type: Any,
        coll_elems: list[Any],
    ) -> (stmt.ListStatement | stmt.SetStatement | stmt.DictStatement | stmt.TupleStatement) | None:
        """Creates the corresponding collection statement from an ast node.

        Args:
            coll_node: the ast node
            coll_elems: a list of variable references or a list of tuples of
            variables for a dict statement.
            coll_elems_type: the type of the elements of the collection statement.

        Returns:
            The corresponding collection statement.
        """
        if isinstance(coll_node, ast.List):
            return stmt.ListStatement(self._testcase, coll_elems_type, coll_elems)
        if isinstance(coll_node, ast.Set):
            return stmt.SetStatement(self._testcase, coll_elems_type, coll_elems)
        if isinstance(coll_node, ast.Dict):
            return stmt.DictStatement(self._testcase, coll_elems_type, coll_elems)
        if isinstance(coll_node, ast.Tuple):
            return stmt.TupleStatement(self._testcase, coll_elems_type, coll_elems)
        return None

    def try_generating_specific_function(  # noqa: C901
        self, call: ast.Call
    ) -> stmt.VariableCreatingStatement | None:
        """Calls to creating a collection.

        The collection could be(list, set, tuple, dict) via their keywords
        and not via literal syntax are considered as ast.Call statements. But for these
        calls, no accessible object under test is in the test_cluster. To parse them
        anyway, these method transforms them to the corresponding ast statement, for
        example a call of a list with 'list()' to an ast.List statement.

        Args:
            call: the ast.Call node

        Returns:
            The corresponding statement.
        """
        try:
            func_id = str(call.func.id)  # type: ignore[attr-defined]
        except AttributeError:
            return None

        # It appears that sometimes builtins is a dictionary and other times it is
        # a module, depending on your python interpreter... curious.
        builtins_dict = __builtins__ if isinstance(__builtins__, dict) else __builtins__.__dict__

        if func_id in builtins_dict:
            return self.create_ast_assign_stmt(call)

        if func_id == "set":
            try:
                set_node = ast.Set(elts=call.args)
            except AttributeError:
                return None
            return self.create_stmt_from_collection(set_node)
        if func_id == "list":
            try:
                list_node = ast.List(
                    elts=call.args,
                    ctx=ast.Load(),
                )
            except AttributeError:
                return None
            return self.create_stmt_from_collection(list_node)
        if func_id == "tuple":
            try:
                tuple_node = ast.Tuple(
                    elts=call.args,
                    ctx=ast.Load(),
                )
            except AttributeError:
                return None
            return self.create_stmt_from_collection(tuple_node)
        if func_id == "dict":
            try:
                dict_node = ast.Dict(
                    keys=call.args[0].keys if call.args else [],  # type: ignore[attr-defined]
                    values=call.args[0].values if call.args else [],  # type: ignore[attr-defined]
                )
            except AttributeError:
                return None
            return self.create_stmt_from_collection(dict_node)
        return None


class AstToTestCaseTransformer(ast.NodeVisitor):
    """An AST NodeVisitor.

    It tries to convert an AST into our internal
    test case representation.
    """

    def __init__(  # noqa: D107
        self, test_cluster: TestCluster, *, create_assertions: bool
    ):
        self._deserializer = StatementDeserializer(test_cluster)
        self._current_parsable: bool = True
        self._testcases: list[dtc.DefaultTestCase] = []
        self._number_found_testcases: int = 0
        self._create_assertions = create_assertions
        self.total_statements = 0
        self.total_parsed_statements = 0
        self._current_parsed_statements = 0
        self._current_max_num_statements = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:  # noqa:N802
        """Visits a function definition node and processes it if it starts with 'test_'.

        Args:
            node: The function definition node.
        """
        if not node.name.startswith("test_") and not node.name.startswith("seed_test_"):
            return
        self._number_found_testcases += 1
        self._deserializer.reset()
        self._current_parsable = True
        self._current_parsed_statements = 0
        self._current_max_num_statements = _count_all_statements(node)
        self.generic_visit(node)
        self.total_statements += self._current_max_num_statements
        self.total_parsed_statements += self._current_parsed_statements
        current_testcase = self._deserializer.get_test_case()
        if self._current_parsable:
            self._testcases.append(current_testcase)
            logger.debug("Successfully imported %s.", node.name)
        elif self._current_parsed_statements > 0:
            logger.debug(
                "Partially parsed %s. Retrieved %s/%s statements.",
                node.name,
                self._current_parsed_statements,
                self._current_max_num_statements,
            )
            self._testcases.append(current_testcase)
        else:
            logger.debug("Failed to parse %s.", node.name)

    def visit_Assign(self, node: ast.Assign) -> Any:  # noqa:N802
        """Visits an assignment node and tries to add it to the current test case.

        Args:
            node: The assignment node.
        """
        if self._deserializer.add_assign_stmt(node):
            self._current_parsed_statements += 1
        else:
            logger.debug("Failed to parse %s.", node)
            self._current_parsable = False

    def visit_Assert(self, node: ast.Assert) -> Any:  # noqa:N802
        """Visits an assert node and tries to add it to the current test case.

        Args:
            node: The assert node.
        """
        if self._create_assertions:
            if hasattr(node.test, "op") and isinstance(node.test.op, ast.Or):
                for assertion in node.test.values:  # type: ignore[attr-defined]
                    self._deserializer.add_assert_stmt(assertion)
            else:
                self._deserializer.add_assert_stmt(node)

    @property
    def testcases(self) -> list[dtc.DefaultTestCase]:
        """Provides the testcases that could be generated from the given AST.

        It is possible that not every aspect of the AST could be transformed
        to our internal representation.

        Returns:
            The generated testcases.
        """
        return self._testcases

    @property
    def deserializer(self):
        """Returns the deserializer instance."""
        return self._deserializer


def deserialize_code_to_testcases(
    test_file_contents: str, test_cluster: TestCluster
) -> tuple[list[dtc.DefaultTestCase], int, int, int] | None:
    """Extracts as many TestCase objects as possible from the given code.

    Args:
        test_file_contents: code containing tests
        test_cluster: the TestCluster to deserialize with

    Returns:
        extracted test cases
    """
    transformer = AstToTestCaseTransformer(
        test_cluster,
        create_assertions=config.configuration.test_case_output.assertion_generation
        == config.AssertionGenerator.LLM,
    )
    try:
        transformer.visit(ast.parse(test_file_contents))
        uninterpreted_statements = transformer.deserializer.uninterpreted_statements
        return (
            transformer.testcases,
            transformer.total_statements,
            transformer.total_parsed_statements,
            uninterpreted_statements,
        )
    except BaseException as e:  # noqa: BLE001
        logger.error(e)
        return None
