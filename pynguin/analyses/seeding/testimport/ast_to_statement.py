import ast
from typing import cast, Set, List, Tuple, Dict

import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.primitivestatements as prim_stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
from pynguin.testcase.statements.statement import Statement
from pynguin.utils.generic.genericaccessibleobject import GenericCallableAccessibleObject


class AstToStatement:
    @staticmethod
    def create_assign_stmt(
        assign: ast.Assign,
        testcase: tc.TestCase,
        objs_under_test: Set,
        ref_dict: Dict[str, vr.VariableReference]
    ) -> Tuple[str, Statement]:
        """Creates the corresponding statement from an ast.Assign node.

        Args:
            assign: The ast.Assign node
            testcase: The testcase of the statement
            objs_under_test: the accessible objects under test
            ref_dict: a dictionary containing key value pairs of variable ids and variable references.

        Returns:
            The corresponding statement or None if no statement type matches
        """
        if type(assign.value) is ast.Constant:
            new_stmt = AstToStatement._create_stmt_from_constant(assign, testcase)
        elif type(assign.value) is ast.UnaryOp:
            new_stmt = AstToStatement._create_stmt_from_unaryop(assign, testcase)
        elif type(assign.value) is ast.Call:
            new_stmt = AstToStatement._create_stmt_from_call(assign, testcase, objs_under_test, ref_dict)
        else:
            new_stmt = None

        ref_id = assign.targets[0].id
        return ref_id, new_stmt

    @staticmethod
    def _create_variable_references_from_call_args(
        call_args: List[ast.Name],
        ref_dict: Dict[str, vr.VariableReference]
    ) -> List[vr.VariableReference]:

        var_refs: List[vr.VariableReference] = []
        for arg in call_args:
            var_refs.append(ref_dict.get(arg.id))
        return var_refs

    @staticmethod
    def _create_stmt_from_constant(assign: ast.Assign, testcase: tc.TestCase):
        if assign.value.value is None:
            return prim_stmt.NoneStatement(testcase, assign.value.value)

        val = assign.value.value
        if isinstance(val, bool):
            return prim_stmt.BooleanPrimitiveStatement(testcase, assign.value.value)
        elif isinstance(val, int):
            return prim_stmt.IntPrimitiveStatement(testcase, assign.value.value)
        elif isinstance(val, float):
            return prim_stmt.FloatPrimitiveStatement(testcase, assign.value.value)
        elif isinstance(val, str):
            return prim_stmt.StringPrimitiveStatement(testcase, assign.value.value)
        else:
            return None

    @staticmethod
    def _create_stmt_from_unaryop(assign: ast.Assign, testcase: tc.TestCase):
        val = assign.value.operand.value
        if isinstance(val, bool):
            return prim_stmt.BooleanPrimitiveStatement(testcase, not assign.value.operand.value)
        elif isinstance(val, float):
            return prim_stmt.FloatPrimitiveStatement(testcase, (-1) * assign.value.operand.value)
        elif isinstance(val, int):
            return prim_stmt.IntPrimitiveStatement(testcase, (-1) * assign.value.operand.value)

    @staticmethod
    def _create_stmt_from_call(
        assign: ast.Assign,
        testcase: tc.TestCase,
        objs_under_test: Set,
        ref_dict: Dict[str, vr.VariableReference]
    ) -> param_stmt.FunctionStatement:
        """Creates a function statement from an ast.assign node.

        Args:
            assign: the ast.Assign node
            testcase: the testcase of the statement
            objs_under_test: the accessible objects under test
            ref_dict: a dictionary containing key value pairs of variable ids and variable references.

        Returns:
            The corresponding function statement
        """
        gen_callable = None
        call = assign.value
        func_name = str(call.func.attr)
        for obj in objs_under_test:
            if func_name == obj.function_name:
                gen_callable = obj
        func_stmt = param_stmt.FunctionStatement(
            testcase,
            cast(GenericCallableAccessibleObject, gen_callable),
            AstToStatement._create_variable_references_from_call_args(call.args, ref_dict)
        )
        return func_stmt
