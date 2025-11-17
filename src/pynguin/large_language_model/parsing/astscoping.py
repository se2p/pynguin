# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
# SPDX-FileCopyrightText: 2023 Microsoft
#
# SPDX-License-Identifier: MIT
#
"""Modified python AST that contains Pynguin VariableReferences.

VariableReferences In place of variable names, used to support
uninterpreted statements.

The logic is adapted from the CodaMosa repository with additional refactoring.
https://github.com/microsoft/codamosa
"""

import ast
import copy
from collections.abc import Callable
from typing import Any

import pynguin.testcase.variablereference as vr
from pynguin.utils import randomness


class VariableReferenceVisitor:
    """A class which visits an ast and returns a copied ast.

    With an operation applied to all the instances of vr.VariableReferences.
    """

    def __init__(self, *, copy: bool, operation: Callable[[vr.VariableReference], Any]):
        """Initializes the visitor with the given operation.

        Args:
            copy: whether to return a copy of the visited tree
            operation: operation to apply to any VariableReference encountered
                during visiting.
        """
        self._copy = copy
        self._vr_operator = operation

    def visit(self, node):
        """Delegate to the appropriate visitor method, or generic_visit.

        Args:
            node: the ast.AST node to visit

        Returns:
            a copy of the node, with `self._operator` applied to all VariableReferences
        """
        method = "visit_" + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):  # noqa: C901
        """Visits everything, copying the node `node`.

        Except that `self._vr_operator` is applied to any children
        that are VariableReferences.

        Args:
            node: the ast.AST node to visit

        Returns:
            a copy of the node, with `self._vr_operator` applied
            to all VariableReferences
        """
        if isinstance(node, vr.VariableReference):
            return self._vr_operator(node)

        fields_to_assign = {}
        for field, old_value in ast.iter_fields(node):
            if isinstance(old_value, list):
                new_values = []
                for element in old_value:
                    if isinstance(element, ast.AST):
                        new_element = self.visit(element)
                    elif isinstance(element, vr.VariableReference):
                        new_element = self._vr_operator(element)
                    else:
                        new_element = element
                    # In a list, can return a list...
                    if new_element is None:
                        continue
                    if isinstance(new_element, list):
                        new_values.extend(new_element)
                        continue
                    new_values.append(new_element)
                fields_to_assign[field] = new_values
            elif isinstance(old_value, ast.AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    pass
                else:
                    fields_to_assign[field] = new_node
            elif isinstance(old_value, vr.VariableReference):
                new_node = self._vr_operator(old_value)
                if new_node is None:
                    pass
                else:
                    fields_to_assign[field] = new_node
            elif self._copy:
                fields_to_assign[field] = old_value
        if self._copy:
            return node.__class__(**fields_to_assign)
        return None


class FreeVariableOperator(VariableReferenceVisitor):
    """A class which visits an ast and returns a copied ast.

    With an operation applied to all the free variables
    """

    def __init__(self, operation: Callable[[ast.Name], Any]):  # noqa: D107
        super().__init__(copy=True, operation=lambda x: x)
        self._bound_variables: set[str] = set()
        self._name_operator = operation

    def visit_Name(self, node: ast.Name) -> Any:  # noqa:N802
        """Visits an ast.Name node and applies the operation if the name is not bound.

        Args:
            node: The ast.Name node

        Returns:
            The result of the operation if the name is not bound, otherwise a deepcopy
            of the node.
        """
        if node.id not in self._bound_variables:
            return self._name_operator(node)
        return copy.deepcopy(node)

    def visit_Call(self, node: ast.Call) -> ast.Call:  # noqa:N802
        """Visits an ast.Call node.

        Args:
            node: The ast.Call node

        Returns:
            A new ast.Call node with the operation applied
            to its arguments and keywords.
        """
        new_args = [self.visit(arg) for arg in node.args]
        new_kwargs = [
            ast.keyword(arg=copy.deepcopy(kwarg.arg), value=self.visit(kwarg.value))
            for kwarg in node.keywords
        ]
        return ast.Call(func=copy.deepcopy(node.func), args=new_args, keywords=new_kwargs)

    def visit_Lambda(self, node: ast.Lambda) -> ast.Lambda:  # noqa:N802
        """Visits an ast.Lambda node.

        Args:
            node: The ast.Lambda node

        Returns:
            A new ast.Lambda node with the operation applied to its body.
        """
        bound_variables_before = set(self._bound_variables)
        all_args: ast.arguments = node.args
        for arg in all_args.args + all_args.kwonlyargs:
            arg_name = arg.arg
            self._bound_variables.add(arg_name)
        if all_args.kwarg is not None:
            self._bound_variables.add(all_args.kwarg.arg)
        if all_args.vararg is not None:
            self._bound_variables.add(all_args.vararg.arg)
        new_body = self.visit(node.body)
        self._bound_variables = bound_variables_before
        return ast.Lambda(args=copy.deepcopy(node.args), body=new_body)

    def get_comprehension_bound_vars(self, node: ast.comprehension) -> list[str]:
        """Gets the bound variables in a comprehension node.

        Args:
            node: The ast.comprehension node

        Returns:
            A list of bound variable names
        """
        return [elem.id for elem in ast.walk(node.target) if isinstance(elem, ast.Name)]

    def _visit_generators_common(self, generators: list[ast.comprehension]):
        """Common logic for visiting comprehension generators.

        Args:
            generators: The list of ast.comprehension nodes

        Returns:
            A list of new ast.comprehension nodes with the operation applied
        """
        new_generators = []
        for comp in generators:
            self._bound_variables.update(self.get_comprehension_bound_vars(comp))
            new_generators.append(
                ast.comprehension(
                    target=copy.deepcopy(comp.target),
                    iter=self.visit(comp.iter),
                    ifs=[self.visit(iff) for iff in comp.ifs],
                    is_async=comp.is_async,
                )
            )
        return new_generators

    def visit_ListComp(self, node: ast.ListComp) -> ast.ListComp:  # noqa:N802
        """Visits an ast.ListComp node.

        Args:
            node: The ast.ListComp node

        Returns:
            A new ast.ListComp node with the operation applied
            to its elements and generators.
        """
        bound_variables_before = set(self._bound_variables)
        new_generators = self._visit_generators_common(node.generators)
        new_elt = self.visit(node.elt)
        ret_val = ast.ListComp(elt=new_elt, generators=new_generators)
        self._bound_variables = bound_variables_before
        return ret_val

    def visit_SetComp(self, node: ast.SetComp) -> ast.SetComp:  # noqa:N802
        """Visits an ast.SetComp node.

        Args:
            node: The ast.SetComp node

        Returns:
            A new ast.SetComp node with the operation applied
            to its elements and generators.
        """
        bound_variables_before = set(self._bound_variables)
        new_generators = self._visit_generators_common(node.generators)
        new_elt = self.visit(node.elt)
        ret_val = ast.SetComp(elt=new_elt, generators=new_generators)
        self._bound_variables = bound_variables_before
        return ret_val

    def visit_DictComp(self, node: ast.DictComp) -> ast.DictComp:  # noqa:N802
        """Visits an ast.DictComp node.

        Args:
            node: The ast.DictComp node

        Returns:
            A new ast.DictComp node with the operation applied
            to its keys, values, and generators.
        """
        bound_variables_before = set(self._bound_variables)
        new_generators = self._visit_generators_common(node.generators)
        new_key = self.visit(node.key)
        new_value = self.visit(node.value)
        ret_val = ast.DictComp(key=new_key, value=new_value, generators=new_generators)
        self._bound_variables = bound_variables_before
        return ret_val


def operate_on_variable_references(
    node: ast.AST, operation: Callable[[vr.VariableReference], Any]
) -> None:
    """Visits `node` and applies an operation on all the VariableReferences in `node`.

    Args:
        node: the node to visit
        operation: the operation to apply on variable references
    """
    _ = VariableReferenceVisitor(copy=False, operation=operation).visit(node)


def copy_and_operate_on_variable_references(
    node: ast.AST, operation: Callable[[vr.VariableReference], Any]
) -> ast.AST:
    """Visits `node` and applies an operation on all the VariableReferences in `node`.

    Replacing any VariableReference v that is a free variable with the result of
    operation(v)

    Args:
        node: the node to visit
        operation: the operation to apply on variable references

    Returns:
        a, possibly strange, ast.AST
    """
    return VariableReferenceVisitor(copy=True, operation=operation).visit(node)


def operate_on_free_variables(node: ast.AST, operation: Callable[[ast.Name], Any]) -> ast.AST:
    """Visits `node` and applies an operation on all the free variables in `node`.

    Replacing any `ast.Name` node n that is a free variable with the result of
    operation(n)

    Args:
        node: the node to visit
        operation: the operation to apply on free variables

    Returns:
        a, possibly strange, ast.AST
    """
    return FreeVariableOperator(operation).visit(node)


def _replace_with_var_refs(node: ast.AST, ref_dict: dict[str, vr.VariableReference]):
    """Returns a new ast with all non-bound variables (ast.Name nodes).

    Replaced with the corresponding vr.VariableReference in ref_dict.

    Args:
        node: the ast to analyze
        ref_dict: the mapping of free variables to VariableReferences

    Returns:
        a new ast with all free variables replaced with a vr.VariableReference

    Raises:
        a ValueError if there is a non-bound variable whose name is not in ref_dict.
    """

    def replacer(name_node: ast.Name):
        if name_node.id not in ref_dict:
            raise ValueError(f"The Name node with name: {ast.unparse} is an unresolved reference")
        return ref_dict[name_node.id]

    return operate_on_free_variables(node, replacer)


class VariableRefAST:
    """This class stores an AST.

    But where name nodes that belong to
    a vr.VariableReference are replaced with that reference.
    """

    def __init__(self, node: ast.AST, ref_dict: dict[str, vr.VariableReference]):
        """Initializes the VariableRefAST with the given node and reference dictionary.

        Args:
            node: The AST node.
            ref_dict: The mapping of variable names to VariableReferences.
        """
        self._node = _replace_with_var_refs(node, ref_dict)

    def structural_hash(self, memo: dict[vr.VariableReference, int]):
        """Compute a structural hash for this object.

        Uses structural_hash() for variable references.

        Returns:
            a hash of this object
        """

        def value_hash(current_hash, value: Any) -> int:
            if isinstance(value, ast.AST):
                current_hash += hash_ast_helper(current_hash, value)
            elif isinstance(value, vr.VariableReference):
                current_hash += 17 * value.structural_hash(memo)
            else:
                current_hash += 17 * hash(value)
            return current_hash

        def hash_ast_helper(current_hash: int, node: ast.AST) -> int:
            field_dict = dict(ast.iter_fields(node))
            for field, value in field_dict.items():
                current_hash += 17 * hash(field)
                if isinstance(value, list):
                    for elem in value:
                        current_hash = value_hash(current_hash, elem)
                else:
                    current_hash = value_hash(current_hash, value)
            return current_hash

        return value_hash(31, self._node)

    def structural_eq(  # noqa:C901
        self,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> bool:
        """Compares whether the two AST nodes are equal w.r.t. memo.

        Args:
            memo: the varref mapping

        Returns:
            whether second is structurally equal to self w.r.t. memo
        """

        def value_equal_helper(first: Any, second: Any) -> bool:
            if type(first) is not type(second):
                return False
            if isinstance(first, ast.AST):
                return equal_helper_ast(first, second)
            if isinstance(first, vr.VariableReference):
                return first.structural_eq(second, memo)
            return first == second

        def equal_helper_ast(first: ast.AST, second: ast.AST) -> bool:
            if type(first) is not type(second):
                return False
            first_fields = dict(ast.iter_fields(first))
            second_fields = dict(ast.iter_fields(second))
            if set(first_fields.keys()) != set(second_fields.keys()):
                return False
            for field, first_value in first_fields.items():
                second_value = second_fields[field]
                if isinstance(first_value, list) and isinstance(second_value, list):
                    if len(first_value) != len(second_value):
                        return False
                    for i in range(len(first_value)):
                        first_elem = first_value[i]
                        second_elem = second_value[i]
                        if not value_equal_helper(first_elem, second_elem):
                            return False
                elif not value_equal_helper(first_value, second_value):
                    return False
            return True

        return True

    def clone(self, memo: dict[vr.VariableReference, vr.VariableReference]) -> "VariableRefAST":
        """Clone the node as an ast, doing any replacement given in memo.

        Args:
            memo: the vr.VariableReference replacements to do.

        Returns:
            a clone of this AST

        Raises:
            ValueError: if there is a missing mapping in memo
        """

        def replace_var_ref(v: vr.VariableReference):
            return v.clone(memo)

        cloned = copy_and_operate_on_variable_references(self._node, replace_var_ref)

        # There should be no effect from re-visiting cloned, since all its free
        # variables have been replaced by VariableReferences, and thus will not
        # be visited.
        try:
            return VariableRefAST(cloned, {})
        except ValueError:
            # This should never happen because cloned is created by operating on
            # self._node, which was converted to a weird AST already.
            raise ValueError(
                "clone was called on a VariableRefAST which was incorrectly converted"
            ) from None

    def count_var_refs(self) -> int:
        """Count the number of variable references in self._node.

        Returns:
            the number of variable references in self._node, including dupes
        """
        num_refs = 0

        def count_var_refs(v: vr.VariableReference):  # noqa: ARG001
            nonlocal num_refs
            num_refs += 1

        operate_on_variable_references(self._node, count_var_refs)

        return num_refs

    def get_all_var_refs(self) -> set[vr.VariableReference]:
        """Returns all the variable references that are used in node.

        Returns:
            all the variable references that appear in self._node
        """
        var_refs = set()

        def store_var_ref(v: vr.VariableReference):
            var_refs.add(v)

        operate_on_variable_references(self._node, store_var_ref)

        return var_refs

    def mutate_var_ref(self, var_refs: set[vr.VariableReference]) -> bool:
        """Mutate one of the variable references in `self._node`.

         So that it points to some other variable reference in var_refs.

        Args:
            var_refs: the variable references we can choose from

        Returns:
            true if self._node was successfully mutated.
        """
        num_var_refs = self.count_var_refs()

        # Can't mutate if there are no variable references or
        # if there is only one declared variable.
        if num_var_refs == 0:
            return False
        if len(var_refs) == 1:
            return False

        at_least_one_mutated = False
        mutate_position = randomness.choice(list(range(num_var_refs)))
        vr_idx = 0

        def mutate_ref(v: vr.VariableReference):
            nonlocal vr_idx, mutate_position, at_least_one_mutated
            if vr_idx == mutate_position:
                vr_idx += 1
                candidate_refs = list(var_refs.difference({v}))
                replacer = randomness.choice(candidate_refs)
                at_least_one_mutated = True
                return replacer
            vr_idx += 1
            return v

        self._node = copy_and_operate_on_variable_references(self._node, mutate_ref)

        return at_least_one_mutated

    def replace_var_ref(
        self, old_var: vr.VariableReference, new_var: vr.VariableReference
    ) -> "VariableRefAST":
        """Replace occurrences of old_var with the new_var.

        Args:
            old_var: the variable to replace
            new_var: the variable to replace it with

        Returns:
            a copy of this object, with new_var instead of old_var
        """
        replace_dict = {var_ref: var_ref for var_ref in self.get_all_var_refs()}
        replace_dict[old_var] = new_var
        return self.clone(replace_dict)

    def get_normal_ast(
        self, vr_replacer: Callable[[vr.VariableReference], ast.Name | ast.Attribute]
    ) -> ast.AST:
        """Gets a normal ast out of the stored AST in self._node.

         Which has variable references in places of names.

        Args:
            vr_replacer: the function that replaces vr.VariableReferences with ast.ASTs

        Returns:
            an AST with all VariableReferences replaced by ast.Names or ast.Attributes,
            as mandated by vr_replacer.
        """
        return copy_and_operate_on_variable_references(self._node, vr_replacer)

    def is_call(self):
        """Are we just storing a call?

        Returns:
            True if the underlying ast is a call
        """
        return isinstance(self._node, ast.Call)
