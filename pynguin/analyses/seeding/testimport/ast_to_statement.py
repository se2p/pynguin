import ast
import logging
from typing import Dict, List, Optional, Set, Tuple, cast

import pynguin.analyses.seeding.initialpopulationseeding as initpopseeding
import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.primitivestatements as prim_stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
from pynguin.assertion.assertion import Assertion
from pynguin.testcase.statements.statement import Statement
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)


class AstToStatement:

    _logger = logging.getLogger(__name__)

    @staticmethod
    def create_assign_stmt(
        assign: ast.Assign,
        testcase: tc.TestCase,
        ref_dict: Dict[str, vr.VariableReference],
    ) -> Tuple[str, Optional[Statement]]:
        """Creates the corresponding statement from an ast.Assign node.

        Args:
            assign: The ast.Assign node
            testcase: The testcase of the statement
            ref_dict: a dictionary containing key value pairs of variable ids and variable references.

        Returns:
            The corresponding statement or None if no statement type matches
        """
        new_stmt: Optional[Statement]
        if type(assign.value) is ast.Constant:
            new_stmt = AstToStatement._create_stmt_from_constant(assign, testcase)
        elif type(assign.value) is ast.UnaryOp:
            new_stmt = AstToStatement._create_stmt_from_unaryop(assign, testcase)
        elif type(assign.value) is ast.Call:
            test_cluster = initpopseeding.initialpopulationseeding.test_cluster
            objs_under_test = test_cluster.accessible_objects_under_test
            new_stmt = AstToStatement._create_stmt_from_call(
                assign, testcase, objs_under_test, ref_dict
            )
        else:
            AstToStatement._logger.info("Assign statement could not be parsed.")
            new_stmt = None
        ref_id = str(assign.targets[0].id)  # type: ignore
        return ref_id, new_stmt

    @staticmethod
    def create_assert_stmt(
        ref_dict: Dict[str, vr.VariableReference], assert_node: ast.Assert
    ) -> Assertion:
        """Creates an assert statement.

        Args:
            ref_dict: a dictionary containing key value pairs of variable ids and
                      variable references.
            assert_node: the ast assert node.

        Returns:
            The corresponding assert statement.
        """
        source = ref_dict.get(assert_node.test.left.id)  # type: ignore
        assert source is not None, "No source node found for assertion"
        return Assertion(source, assert_node.test.comparators[0].value)  # type: ignore

    @staticmethod
    def _create_variable_references_from_call_args(
        call_args: List[ast.Name], ref_dict: Dict[str, vr.VariableReference]
    ) -> List[vr.VariableReference]:

        var_refs: List[vr.VariableReference] = []
        for arg in call_args:
            reference = ref_dict.get(arg.id)
            assert reference is not None, "Reference not found"
            var_refs.append(reference)
        return var_refs

    @staticmethod
    def _create_stmt_from_constant(
        assign: ast.Assign, testcase: tc.TestCase
    ) -> Optional[prim_stmt.PrimitiveStatement]:
        if assign.value.value is None:  # type: ignore
            return prim_stmt.NoneStatement(testcase, assign.value.value)  # type: ignore

        val = assign.value.value  # type: ignore
        if isinstance(val, bool):
            return prim_stmt.BooleanPrimitiveStatement(
                testcase, assign.value.value  # type: ignore
            )
        elif isinstance(val, int):
            return prim_stmt.IntPrimitiveStatement(
                testcase, assign.value.value  # type: ignore
            )
        elif isinstance(val, float):
            return prim_stmt.FloatPrimitiveStatement(
                testcase, assign.value.value  # type: ignore
            )
        elif isinstance(val, str):
            return prim_stmt.StringPrimitiveStatement(
                testcase, assign.value.value  # type: ignore
            )
        else:
            AstToStatement._logger.info(
                "Could not find case for constant while handling assign statement."
            )
            return None

    @staticmethod
    def _create_stmt_from_unaryop(
        assign: ast.Assign, testcase: tc.TestCase
    ) -> Optional[prim_stmt.PrimitiveStatement]:
        val = assign.value.operand.value  # type: ignore
        if isinstance(val, bool):
            return prim_stmt.BooleanPrimitiveStatement(
                testcase, not assign.value.operand.value  # type: ignore
            )
        elif isinstance(val, float):
            return prim_stmt.FloatPrimitiveStatement(
                testcase, (-1) * assign.value.operand.value  # type: ignore
            )
        elif isinstance(val, int):
            return prim_stmt.IntPrimitiveStatement(
                testcase, (-1) * assign.value.operand.value  # type: ignore
            )
        else:
            AstToStatement._logger.info(
                "Could not find case for unary operator while handling assign"
                " statement."
            )
            return None

    @staticmethod
    def _create_stmt_from_call(
        assign: ast.Assign,
        testcase: tc.TestCase,
        objs_under_test: Set,
        ref_dict: Dict[str, vr.VariableReference],
    ) -> Optional[param_stmt.FunctionStatement]:
        """Creates a function statement from an ast.assign node.

        Args:
            assign: the ast.Assign node
            testcase: the testcase of the statement
            objs_under_test: the accessible objects under test
            ref_dict: a dictionary containing key value pairs of variable ids and
                      variable references.

        Returns:
            The corresponding function statement.
        """
        gen_callable = None
        call = assign.value
        try:
            func_name = str(call.func.attr)  # type: ignore
        except AttributeError:
            AstToStatement._logger.info("Instantiation not supported")
            return None
        for obj in objs_under_test:
            if func_name == obj.function_name:
                gen_callable = obj
        if gen_callable is None:
            AstToStatement._logger.info("No such function found...")
            return None
        func_stmt = param_stmt.FunctionStatement(
            testcase,
            cast(GenericCallableAccessibleObject, gen_callable),
            AstToStatement._create_variable_references_from_call_args(
                call.args, ref_dict  # type: ignore
            ),
        )
        return func_stmt
