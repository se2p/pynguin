#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides byte-code instrumentation mechanisms."""

from __future__ import annotations

import logging
import re

from abc import abstractmethod
from dataclasses import dataclass
from types import CodeType
from typing import TYPE_CHECKING
from typing import Protocol
from typing import TypeAlias

from astroid.exceptions import AstroidError
from astroid.nodes import ClassDef
from astroid.nodes import ComprehensionScope
from astroid.nodes import For
from astroid.nodes import FunctionDef
from astroid.nodes import If
from astroid.nodes import Lambda
from astroid.nodes import Module
from astroid.nodes import NodeNG
from astroid.nodes import While
from bytecode import Bytecode

from pynguin.analyses.module import read_module_ast
from pynguin.instrumentation import controlflow as cf
from pynguin.instrumentation import tracer
from pynguin.instrumentation import version


if TYPE_CHECKING:
    from collections.abc import Collection
    from collections.abc import Iterable

    from bytecode.instr import Instr
    from typing_extensions import Self

    from pynguin.analyses.constants import DynamicConstantProvider

PYNGUIN_NO_COVER_PATTERN = re.compile(r"# +?pynguin: +?no +?cover")
PRAGMA_NO_COVER_PATTERN = re.compile(r"# +?pragma: +?no +?cover")


ScopeNode: TypeAlias = Module | ClassDef | FunctionDef | Lambda | ComprehensionScope


@dataclass(frozen=True)
class ModuleAnnotatedAst:
    """A class responsible for storing a module AST along with its metadata."""

    module_ast: Module

    # Metadata
    only_cover_lines: frozenset[int]
    no_cover_lines: frozenset[int]

    def get_scope(self, lineno: int) -> AnnotatedAst | None:
        """Get the annotated AST of the scope.

        Args:
            lineno: The line number of the scope.

        Returns:
            The annotated AST of the scope, or None if there are no scope at lineno
        """
        ast: ScopeNode | None = next(
            iter(
                scope
                for scope in self.module_ast.nodes_of_class(ScopeNode)
                if scope.fromlineno == lineno
            ),
            None,
        )

        if ast is None:
            return None

        return AnnotatedAst(ast=ast, module=self)

    @classmethod
    def _find_lines_in_source_code(
        cls,
        source_code: str,
        pattern: re.Pattern[str],
    ) -> Iterable[int]:
        """Find the lines that contain the pattern in the source code.

        Returns:
            The iterable of lines that contain the pattern.
        """
        return (
            lineno
            for lineno, line in enumerate(source_code.splitlines(), start=1)
            if pattern.search(line) is not None
        )

    @classmethod
    def _get_scope_names(
        cls,
        scope_node: ScopeNode,
        parent_scope: str = "",
    ) -> Iterable[tuple[str, int]]:
        """Get the scope names in a AST.

        Args:
            scope_node: The AST node.
            parent_scope: The parent scope.

        Returns:
            The scope names and line numbers.
        """
        assert scope_node.lineno is not None

        scope_name = (
            f"<generator-{scope_node.lineno}>"
            if isinstance(scope_node, ComprehensionScope)
            else scope_node.name
        )
        full_scope_name = f"{parent_scope}.{scope_name}" if parent_scope else scope_name

        if not isinstance(scope_node, Module):
            yield (full_scope_name, scope_node.lineno)

        for child in scope_node.get_children():
            if isinstance(child, ScopeNode):
                yield from cls._get_scope_names(child, full_scope_name)

    @classmethod
    def _find_lines_in_ast(cls, ast: Module, target_scope_names: Collection[str]) -> Iterable[int]:
        """Find the lines that contain the target identifiers in the module AST.

        Args:
            ast: The module AST.
            target_scope_names: The collection of target scope names.

        Returns:
            The iterable of lines that contain the target identifiers.
        """
        return (
            lineno
            for scope_name, lineno in cls._get_scope_names(ast)
            if scope_name in target_scope_names
        )

    @classmethod
    def from_path(  # noqa: PLR0917
        cls,
        module_path: str,
        module_name: str,
        only_cover: Collection[str],
        no_cover: Collection[str],
        enable_inline_pynguin_no_cover: bool,  # noqa: FBT001
        enable_inline_pragma_no_cover: bool,  # noqa: FBT001
    ) -> Self | None:
        """Create an AnnotatedAst from a module path.

        Args:
            module_path: The path of the module.
            module_name: The name of the module.
            only_cover: The collection of functions, methods or classes to only cover.
            no_cover: The collection of functions, methods or classes to not cover.
            enable_inline_pynguin_no_cover: Enable inline `pynguin: no cover`.
            enable_inline_pragma_no_cover: Enable inline `pragma: no cover`.

        Returns:
            The AnnotatedAst of the module path, or None.
        """
        try:
            module_ast, source_code = read_module_ast(module_path, module_name)
        except (OSError, AstroidError):
            return None

        only_cover_lines = frozenset(cls._find_lines_in_ast(module_ast, only_cover))

        no_cover_lines = frozenset((
            *cls._find_lines_in_ast(module_ast, no_cover),
            *(
                cls._find_lines_in_source_code(source_code, PYNGUIN_NO_COVER_PATTERN)
                if enable_inline_pynguin_no_cover
                else ()
            ),
            *(
                cls._find_lines_in_source_code(source_code, PRAGMA_NO_COVER_PATTERN)
                if enable_inline_pragma_no_cover
                else ()
            ),
        ))

        return cls(
            module_ast=module_ast,
            only_cover_lines=only_cover_lines,
            no_cover_lines=no_cover_lines,
        )


@dataclass(frozen=True)
class AnnotatedAst:
    """A class representing a scope of a module annotated AST."""

    ast: ScopeNode
    module: ModuleAnnotatedAst

    def _in_cover(self, lineno: int) -> bool:
        """Check if the lineno is in cover.

        Args:
            lineno: The line number.

        Returns:
            True if it is in cover, False otherwise.
        """
        if lineno in self.module.no_cover_lines:
            return False

        return (
            not self.module.only_cover_lines
            or lineno in self.module.only_cover_lines
            or any(
                child_lineno in self.module.only_cover_lines
                for child_lineno in range(self.ast.fromlineno, self.ast.tolineno + 1)
                if child_lineno not in self.module.no_cover_lines
            )
        )

    @staticmethod
    def _in_body(body: list[NodeNG], lineno: int) -> bool:
        """Check if the lineno is contained in the body.

        Args:
            body: The instructions in the body.
            lineno: The line number.

        Returns:
            True if it is included, False otherwise.
        """
        return bool(body) and body[0].fromlineno <= lineno <= body[-1].tolineno

    def should_be_covered(self) -> bool:
        """Check if self should be covered.

        This means that self must be in the cover lines,
        as well as the potential functions and classes that contains it.

        Returns:
            True if self should be covered, False otherwise.
        """
        return self._in_cover(self.ast.fromlineno) and all(
            self._in_cover(definition_node.fromlineno)
            for definition_node in self.module.module_ast.nodes_of_class(FunctionDef | ClassDef)
            if definition_node.fromlineno <= self.ast.fromlineno <= definition_node.tolineno
        )

    def should_cover_line(self, lineno: int) -> bool:
        """Check if a line number should be covered.

        This means that the instruction itself must be in the cover lines, as well as
        all conditional instructions in which it is contained.

        Args:
            lineno: The line number.

        Returns:
            True if it should be covered, False otherwise.
        """
        if not self._in_cover(lineno):
            return False

        # Handle branches
        for branch_node in self.ast.nodes_of_class(If | For | While):
            # Skip nodes that do not contains the lineno
            if lineno < branch_node.fromlineno or branch_node.tolineno < lineno:
                continue

            # Check the "True" branch
            if (
                self._in_body(branch_node.body, lineno)
                and branch_node.fromlineno in self.module.no_cover_lines
            ):
                return False

            # Do not check for a "else" when there is a "elif" or in a "while"
            if (isinstance(branch_node, If) and branch_node.has_elif_block()) or isinstance(
                branch_node, While
            ):
                continue

            # Check the "False" branch
            # We don't have access to the exact location of the else statement so we check
            # all lines in which it could be defined for now
            if self._in_body(branch_node.orelse, lineno) and any(
                else_lineno in self.module.no_cover_lines
                for else_lineno in range(
                    branch_node.body[-1].tolineno + 1,
                    branch_node.orelse[0].fromlineno,
                )
            ):
                return False

        return True


class InstrumentationAdapter(Protocol):
    """Protocol for byte-code instrumentation adapters.

    General notes:

    A POP_TOP instruction is required after calling a method, because each method
    implicitly returns None.

    This class defines visit_* methods that are called from the
    InstrumentationTransformer. Each subclass should override the visit_* methods
    where it wants to do something.
    """

    def visit_cfg(
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
    ) -> None:
        """Called when the CFG is visited.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
        """
        return

    def visit_node(
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        """Called for each basic block node in the CFG.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
        """
        return


class BranchCoverageInstrumentationAdapter(InstrumentationAdapter):
    """Instruments code objects to enable tracking branch distances.

    This results in branch coverage.
    """

    @abstractmethod
    def __init__(self, subject_properties: tracer.SubjectProperties) -> None:
        """Initialize the branch coverage instrumentation adapter.

        Args:
            subject_properties: The properties of the subject that is being instrumented.
        """

    @abstractmethod
    def visit_for_loop(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instrument the for-loops.

        We want to instrument each iteration of the for-loop as well as its natural exit.
        The natural exit is when the for-loop ends because there is nothing left to yield.
        Therefore, it is important to be careful not to trigger the tracer if the loop is exited
        by a break or return statement, as this would prevent us from tracing the natural exits.

        Since Python is a structured programming language, there can be no jumps
        directly into the loop that bypass the loop header (e.g., GOTO).
        Jumps which reach the loop header from outside the loop will still target
        the original loop header, so they don't need to be modified.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction that is the for-loop header.
            instr_index: The index of the instruction in the basic block.
        """

    def visit_none_based_conditional_jump(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instrument none-based conditional jumps.

        It is only used in Python 3.11 and later versions.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction that is the comparison operation.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_compare_based_conditional_jump(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instrument compare-based conditional jumps.

        We add a call to the tracer which reports the values that will be used
        in the following comparison operation on which the conditional jump is based.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction that is the comparison operation.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_exception_based_conditional_jump(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instrument exception-based conditional jumps.

        We add a call to the tracer which reports the values that will be used
        in the following exception matching case.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction that is the conditional jump.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_bool_based_conditional_jump(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instrument boolean-based conditional jumps.

        We add a call to the tracer which reports the value on which the conditional
        jump will be based.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction that is the conditional jump.
            instr_index: The index of the instruction in the basic block.
        """


class LineCoverageInstrumentationAdapter(InstrumentationAdapter):
    """Instruments code objects to enable tracking of executed lines.

    This results in line coverage.
    """

    @abstractmethod
    def __init__(self, subject_properties: tracer.SubjectProperties) -> None:
        """Initialize the line coverage instrumentation adapter.

        Args:
            subject_properties: The properties of the subject that is being instrumented.
        """

    @abstractmethod
    def visit_line(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instrument a line.

        We add a call to the tracer which reports a line was executed.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The first instruction of a line.
            instr_index: The index of the instruction in the basic block.
        """


class CheckedCoverageInstrumentationAdapter(InstrumentationAdapter):
    """Instruments code objects to enable tracking of executed instructions.

    Special instructions get instrumented differently to track information
    required to calculate the percentage of instructions in a backward slice for
    an assertion, thus checked coverage.

    We instrument memory accesses, control flow instruction and
    attribute access instructions.

    The instruction number in combination with the line number and the filename can
    uniquely identify the traced instruction in the original basic block. Since
    instructions have a fixed length of two bytes since version 3.6, this is rather
    trivial to keep track of.
    """

    @abstractmethod
    def __init__(self, subject_properties: tracer.SubjectProperties) -> None:
        """Initialize the checked coverage instrumentation adapter.

        Args:
            subject_properties: The properties of the subject that is being instrumented.
        """

    @abstractmethod
    def visit_line(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument a line.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_generic(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument generic instructions.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_local_access(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument local variable accesses.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_attr_access(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument attribute accesses.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_subscr_access(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument subscription accesses.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    def visit_slice_access(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument slice accesses.

        It is only used in Python 3.12 and later versions.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_name_access(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument name accesses.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_import_name_access(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument import name accesses.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_global_access(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument global variable accesses.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_deref_access(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument dereferenced variable accesses.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_jump(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument jump instructions.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_call(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument call instructions.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_return(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument return instructions.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """


class DynamicSeedingInstrumentationAdapter(InstrumentationAdapter):
    """Instruments code objects to enable dynamic constant seeding.

    Supported is collecting values of the types int, float and string.

    Instrumented are the common compare operations (==, !=, <, >, <=, >=) and the string
    methods contained in the STRING_FUNCTION_NAMES list. This means, if one of the
    above operations and methods is used in an if-conditional, corresponding values
    are added to the dynamic constant pool.

    The dynamic pool is implemented in the module constantseeding.py. The dynamicseeding
    module contains methods for managing the dynamic pool during the algorithm
    execution.
    """

    @abstractmethod
    def __init__(self, dynamic_constant_provider: DynamicConstantProvider) -> None:
        """Initialize the dynamic seeding instrumentation.

        Args:
            dynamic_constant_provider: The dynamic constant provider that is used to
                manage the dynamic constant pool.
        """

    @abstractmethod
    def visit_compare_op(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instruments the compare operations.

        Stores the values extracted at runtime.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_string_function_without_arg(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instruments the isalnum function.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_startswith_function(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instruments the startswith function.

        Stores for the expression 'string1.startswith(string2)' the value
        'string2 + string1' in the _dynamic_pool.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_endswith_function(  # noqa: PLR0917
        self,
        annotated_ast: AnnotatedAst | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instruments the endswith function.

        Stores for the expression 'string1.startswith(string2)' the value
        'string1 + string2' in the _dynamic_pool.

        Args:
            annotated_ast: The annotated AST, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
        """


class InstrumentationTransformer:
    """Applies a given list of instrumentation adapters to code objects.

    This class is responsible for traversing all nested code objects and their
    basic blocks and requesting their instrumentation from the given adapters.

    Ideally we would want something like ASM with nested visitors where changes from
    different adapters don't affect each other, but that's a bit of overkill for now.
    """

    _logger = logging.getLogger(__name__)

    def __init__(  # noqa: PLR0917
        self,
        subject_properties: tracer.SubjectProperties,
        instrumentation_adapters: list[InstrumentationAdapter],
        only_cover: list[str] | None = None,
        no_cover: list[str] | None = None,
        enable_inline_pynguin_no_cover: bool = True,  # noqa: FBT001, FBT002
        enable_inline_pragma_no_cover: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        """Initialize the instrumentation transformer.

        Args:
            subject_properties: The properties of the subject that is being instrumented.
            instrumentation_adapters: The list of instrumentation adapters that should be used.
            only_cover: The list of functions, methods or classes to only cover.
            no_cover: The list of functions, methods or classes to not cover.
            enable_inline_pynguin_no_cover: Enable inline `pynguin: no cover`.
            enable_inline_pragma_no_cover: Enable inline `pragma: no cover`.
        """
        self._subject_properties = subject_properties
        self._instrumentation_adapters = instrumentation_adapters
        self._only_cover = only_cover if only_cover is not None else []
        self._no_cover = no_cover if no_cover is not None else []
        self._enable_inline_pynguin_no_cover = enable_inline_pynguin_no_cover
        self._enable_inline_pragma_no_cover = enable_inline_pragma_no_cover

    @property
    def subject_properties(self) -> tracer.SubjectProperties:
        """Get the subject properties that are used for the instrumentation.

        Returns:
            The subject properties that are used for the instrumentation.
        """
        return self._subject_properties

    def instrument_code(self, code: CodeType, module_name: str = "") -> CodeType:
        """Instrument the given code object.

        Args:
            code: The code object to instrument.
            module_name: The name of the module in which the code object is defined.

        Returns:
            The instrumented code object.
        """
        for metadata in self._subject_properties.existing_code_objects.values():
            if metadata.code_object is code:
                # Abort instrumentation, since we have already
                # instrumented this code object.
                raise AssertionError("Tried to instrument already code object.")

        module_annotated_ast = ModuleAnnotatedAst.from_path(
            code.co_filename,
            module_name,
            self._only_cover,
            self._no_cover,
            self._enable_inline_pynguin_no_cover,
            self._enable_inline_pragma_no_cover,
        )

        return self._instrument_code_recursive(code, module_annotated_ast)

    def _instrument_code_recursive(
        self,
        code: CodeType,
        module_annotated_ast: ModuleAnnotatedAst | None,
        parent_code_object_id: int | None = None,
    ) -> CodeType:
        annotated_ast = (
            module_annotated_ast.get_scope(
                # Special case as the line number of a module is 1
                # in its code object but is 0 in its AST
                0 if code.co_name == "<module>" else code.co_firstlineno
            )
            if module_annotated_ast is not None
            else None
        )

        if annotated_ast is not None and not annotated_ast.should_be_covered():
            self._logger.debug("Skipping instrumentation of %s", code.co_name)
            return code

        self._logger.debug("Instrumenting Code Object for %s", code.co_name)

        code_object_id = self._subject_properties.create_code_object_id()

        cfg = cf.CFG.from_bytecode(version.add_for_loop_no_yield_nodes(Bytecode.from_code(code)))

        for adapter in self._instrumentation_adapters:
            adapter.visit_cfg(annotated_ast, cfg, code_object_id)

        for node in cfg.basic_block_nodes:
            for adapter in self._instrumentation_adapters:
                adapter.visit_node(annotated_ast, cfg, code_object_id, node)

        instrumented_code = cfg.bytecode_cfg.to_code()

        code_object = instrumented_code.replace(
            co_consts=tuple(
                self._instrument_code_recursive(const, module_annotated_ast, code_object_id)
                if isinstance(const, CodeType)
                else const
                for const in instrumented_code.co_consts
            )
        )

        self._subject_properties.register_code_object(
            code_object_id,
            tracer.CodeObjectMetaData(
                code_object=code_object,
                parent_code_object_id=parent_code_object_id,
                cfg=cfg,
                cdg=cf.ControlDependenceGraph.compute(cfg),
            ),
        )

        return code_object
