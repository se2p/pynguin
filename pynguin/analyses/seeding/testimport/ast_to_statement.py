import ast
from typing import cast, Set, List, Tuple, Dict

import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.primitivestatements as prim_stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
from pynguin.utils.generic.genericaccessibleobject import GenericCallableAccessibleObject


class AstToStatement:
    @staticmethod
    def create_prim_stmt(assign: ast.Assign, testcase: tc.TestCase) -> Tuple[str, prim_stmt.PrimitiveStatement]:
        """Creates a primitive statement from an ast.Assign node.

        Args:
            assign: The ast.Assign node
            testcase: The testcase of the statement

        Returns:
            The corresponding primitive statement
        """
        if type(assign.value) is ast.Constant:
            new_stmt = AstToStatement._create_stmt_from_constant(assign, testcase)
        elif type(assign.value) is ast.UnaryOp:
            new_stmt = AstToStatement._create_stmt_from_unaryop(assign, testcase)
        elif type(assign.value) is ast.Call:
            new_stmt = AstToStatement._create_stmt_from_call(assign, testcase)
        elif isinstance(assign.value.operand.value, int):
            new_stmt = prim_stmt.IntPrimitiveStatement(testcase, (-1) * assign.value.operand.value)
        elif isinstance(assign.value.operand.value, float):
            new_stmt = prim_stmt.FloatPrimitiveStatement(testcase, (-1) * assign.value.operand.value)
        elif isinstance(assign.value.operand.value, str):
            new_stmt = prim_stmt.StringPrimitiveStatement(testcase, assign.value.operand.value)
        elif isinstance(assign.value.operand.value, bool):
            new_stmt = prim_stmt.BooleanPrimitiveStatement(testcase, assign.value.operand.value)
        else:
            raise Exception

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
    def create_function_stmt(
        expr: ast.Expr,
        testcase: tc.TestCase,
        objs_under_test: Set,
        ref_dict: Dict[str, vr.VariableReference]
    ) -> param_stmt.FunctionStatement:
        """Creates a function statement from an ast.Expr node.

        Args:
            expr: the ast.Expr node
            testcase: the testcase of the statement
            objs_under_test: the accessible objects under test
            ref_dict: a dictionary containing key value pairs of variable ids and variable references.

        Returns:
            The corresponding function statement
        """
        gen_callable = None
        call = expr.value
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

    @staticmethod
    def _create_stmt_from_constant(assign: ast.Assign, testcase: tc.TestCase):
        if assign.value.value is None:
            return prim_stmt.NoneStatement(testcase, assign.value.value)

        val = assign.value.value
        if isinstance(val, int):
            return prim_stmt.IntPrimitiveStatement(testcase, assign.value.value)
        elif isinstance(val, float):
            return prim_stmt.FloatPrimitiveStatement(testcase, assign.value.value)
        elif isinstance(val, str):
            return prim_stmt.StringPrimitiveStatement(testcase, assign.value.value)
        else:
            return None

