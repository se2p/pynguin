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
from typing import TYPE_CHECKING, Protocol, TypeAlias

from astroid.exceptions import AstroidError
from astroid.nodes import (
    ClassDef,
    ComprehensionScope,
    For,
    FunctionDef,
    If,
    Lambda,
    Match,
    MatchCase,
    Module,
    NodeNG,
    Try,
    TryStar,
    While,
)
from bytecode import Bytecode
from bytecode.instr import Instr

from pynguin.analyses.module import read_module_ast
from pynguin.configuration import ToCoverConfiguration
from pynguin.instrumentation import controlflow as cf
from pynguin.instrumentation import tracer, version

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from typing_extensions import Self

    from pynguin.analyses.constants import DynamicConstantProvider

_LOGGER = logging.getLogger(__name__)

PYNGUIN_NO_COVER_PATTERN = re.compile(r"# +?pynguin: +?no +?cover")
PRAGMA_NO_COVER_PATTERN = re.compile(r"# +?pragma: +?no +?cover")


ScopeNode: TypeAlias = Module | ClassDef | FunctionDef | Lambda | ComprehensionScope


@dataclass(frozen=True)
class ModuleAstInfo:
    """Encapsulates the AST of a Python module with metadata about lines in-/excluded for coverage."""  # noqa: E501

    module_ast: Module

    # Metadata
    only_cover_lines: frozenset[int]
    no_cover_lines: frozenset[int]

    def __post_init__(self) -> None:
        overlap = self.only_cover_lines & self.no_cover_lines

        if overlap:
            raise ValueError(
                f"Conflicting cover lines {sorted(overlap)} "
                f"are present in both only_cover and no_cover sets"
            )

    def get_scope(self, lineno: int) -> AstInfo | None:
        """Get the AST info of the scope.

        Args:
            lineno: The line number of the scope.

        Returns:
            The AST info of the scope, or None if there are no scope at lineno
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

        return AstInfo(ast=ast, module=self)

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

        if isinstance(scope_node, Module):
            full_scope_name = ""
        else:
            full_scope_name = f"{parent_scope}.{scope_name}" if parent_scope else scope_name
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
        scope_names = dict(cls._get_scope_names(ast))
        for scope_name in target_scope_names:
            if (lineno := scope_names.get(scope_name)) is not None:
                yield lineno
            else:
                _LOGGER.warning(
                    "Target scope name '%s' not found in AST. Did you specify the right name?",
                    scope_name,
                )

    @classmethod
    def from_path(
        cls,
        module_path: str,
        module_name: str,
        to_cover_config: ToCoverConfiguration,
    ) -> Self | None:
        """Create an AstInfo from a module path.

        Args:
            module_path: The path of the module.
            module_name: The name of the module.
            to_cover_config: the configuration of which code elements are used as coverage goals.

        Raises:
            ValueError: if a line is in both only_cover and no_cover sets.

        Returns:
            The AstInfo of the module path, or None.
        """
        try:
            module_ast, source_code = read_module_ast(module_path, module_name)
        except (OSError, AstroidError):
            return None

        only_cover_lines = frozenset(cls._find_lines_in_ast(module_ast, to_cover_config.only_cover))

        no_cover_lines = frozenset((
            *cls._find_lines_in_ast(module_ast, to_cover_config.no_cover),
            *(
                cls._find_lines_in_source_code(source_code, PYNGUIN_NO_COVER_PATTERN)
                if to_cover_config.enable_inline_pynguin_no_cover
                else ()
            ),
            *(
                cls._find_lines_in_source_code(source_code, PRAGMA_NO_COVER_PATTERN)
                if to_cover_config.enable_inline_pragma_no_cover
                else ()
            ),
        ))

        return cls(
            module_ast=module_ast,
            only_cover_lines=only_cover_lines,
            no_cover_lines=no_cover_lines,
        )


@dataclass(frozen=True)
class AstInfo:
    """Specific scope of a module AST with metadata about in-/excluded lines.

    Wraps a scope node (e.g. function or class) within a `ModuleAstInfo`
    and provides methods to determine whether the scope or its lines should be included in coverage.
    """

    ast: ScopeNode
    module: ModuleAstInfo

    def _in_cover(self, lineno: int) -> bool:
        """Check if the lineno is in cover.

        The priority for being covered is:

        1. Not in `no_cover_lines`
        2. In `only_cover_lines`, `only_cover_lines` is empty or a parent is in `only_cover_lines`

        If a line is in both `no_cover_lines` and `only_cover_lines`, it is not being covered.

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

    @staticmethod
    def _inter_lines(previous_body: list[NodeNG], after_body: list[NodeNG]) -> Iterable[int]:
        if previous_body and after_body:
            yield from range(
                previous_body[-1].tolineno + 1,
                after_body[0].fromlineno,
            )

    @staticmethod
    def _else_lines(node: If | For | While) -> Iterable[int]:
        return AstInfo._inter_lines(node.body, node.orelse)

    @staticmethod
    def _try_else_lines(node: Try | TryStar) -> Iterable[int]:
        if node.handlers:
            return AstInfo._inter_lines(node.handlers[-1].body, node.orelse)

        return AstInfo._inter_lines(node.body, node.orelse)

    @staticmethod
    def _try_finally_lines(node: Try | TryStar) -> Iterable[int]:
        if node.orelse:
            return AstInfo._inter_lines(node.orelse, node.finalbody)

        if node.handlers:
            return AstInfo._inter_lines(node.handlers[-1].body, node.finalbody)

        return AstInfo._inter_lines(node.body, node.finalbody)

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
        all conditional instructions in which it is contained. In other words, if the instruction
        itself or any of its conditional instructions are part of the `no_cover_lines`, the line
        should not be covered.

        Args:
            lineno: The line number.

        Returns:
            True if it should be covered, False otherwise.
            Defaults to True if there is no instruction at lineno.
        """
        if not self._in_cover(lineno):
            return False

        for branch_node in self.ast.nodes_of_class(If | For | While | Match | Try | TryStar):
            # Skip nodes that do not contains the lineno
            if lineno < branch_node.fromlineno or branch_node.tolineno < lineno:
                continue

            # Handle the "Match" nodes by checking that they are in the cover lines and
            # by checking that the branch in which the line number is contained is also
            # in the cover lines.
            if isinstance(branch_node, Match) and (
                branch_node.fromlineno in self.module.no_cover_lines
                or any(
                    case_node.fromlineno in self.module.no_cover_lines
                    for case_node in branch_node.cases
                    if self._in_body(case_node.body, lineno)
                )
            ):
                return False

            # Handle the "True" branch of "If", "For" and "While" nodes and
            # the "try" branch of "Try" and "TryStar" nodes by checking that the
            # branch in which the line number is contained is in the cover lines.
            if (
                isinstance(branch_node, If | For | While | Try | TryStar)
                and self._in_body(branch_node.body, lineno)
                and branch_node.fromlineno in self.module.no_cover_lines
            ):
                return False

            # Handle the "except", "else" and "finally" branches of "Try" and "TryStar" nodes
            # by checking that the branch in which the line number is contained is in the
            # cover lines.
            if isinstance(branch_node, Try | TryStar) and (  # noqa: PLR0916
                any(
                    handler_node.fromlineno in self.module.no_cover_lines
                    for handler_node in branch_node.handlers
                    if self._in_body(handler_node.body, lineno)
                )
                or (
                    self._in_body(branch_node.orelse, lineno)
                    and any(
                        else_lineno in self.module.no_cover_lines
                        for else_lineno in self._try_else_lines(branch_node)
                    )
                )
                or (
                    self._in_body(branch_node.finalbody, lineno)
                    and any(
                        final_lineno in self.module.no_cover_lines
                        for final_lineno in self._try_finally_lines(branch_node)
                    )
                )
            ):
                return False

            # Handle the "False" branch of "If", "For" and "While" nodes by checking that
            # the branch in which the line number is contained is in the cover lines.
            # The "elif" branches are ignored because they are already covered by the "True"
            # branches, and if they were in the `no_cover_lines`, it would also influence
            # all the "elif" and "else" branches they contain.
            if (
                isinstance(branch_node, If | For | While)
                and (not isinstance(branch_node, If) or not branch_node.has_elif_block())
                and self._in_body(branch_node.orelse, lineno)
                and any(
                    else_lineno in self.module.no_cover_lines
                    for else_lineno in self._else_lines(branch_node)
                )
            ):
                return False

        return True

    def should_cover_conditional_statement(self, lineno: int) -> bool:
        """Check if the conditional statement at the line number should be covered.

        This means that the conditional statement must have all its branches in the cover lines,
        as well as all conditional instructions in which it is contained.

        Args:
            lineno: The line number of the conditional statement.

        Returns:
            True if it should be covered, False otherwise.
            Defaults to True if there is no conditional statement at lineno.
        """
        for branch_node in self.ast.nodes_of_class(If | For | While | MatchCase):
            if branch_node.fromlineno == lineno or (
                isinstance(branch_node, If | For | While)
                and lineno in self._else_lines(branch_node)
            ):
                return self.should_cover_line(branch_node.fromlineno) and (
                    isinstance(branch_node, MatchCase)
                    or (isinstance(branch_node, If) and branch_node.has_elif_block())
                    or all(
                        self.should_cover_line(else_lineno)
                        for else_lineno in self._else_lines(branch_node)
                    )
                )

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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
    ) -> None:
        """Called when the CFG is visited.

        Args:
            ast_info: The AST info, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
        """
        return

    def visit_node(
        self,
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        """Called for each basic block node in the CFG.

        Args:
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
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
            ast_info: The AST info, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction that is the for-loop header.
            instr_index: The index of the instruction in the basic block.
        """

    def visit_none_based_conditional_jump(  # noqa: PLR0917
        self,
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instrument none-based conditional jumps.

        It is only used in Python 3.11 and later versions.

        Args:
            ast_info: The AST info, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction that is the comparison operation.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_compare_based_conditional_jump(  # noqa: PLR0917
        self,
        ast_info: AstInfo | None,
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
            ast_info: The AST info, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction that is the comparison operation.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_exception_based_conditional_jump(  # noqa: PLR0917
        self,
        ast_info: AstInfo | None,
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
            ast_info: The AST info, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction that is the conditional jump.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_bool_based_conditional_jump(  # noqa: PLR0917
        self,
        ast_info: AstInfo | None,
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
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instrument a line.

        We add a call to the tracer which reports a line was executed.

        Args:
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument a line.

        Args:
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument generic instructions.

        Args:
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument local variable accesses.

        Args:
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument attribute accesses.

        Args:
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument subscription accesses.

        Args:
            ast_info: The AST info, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    def visit_slice_access(  # noqa: PLR0917
        self,
        ast_info: AstInfo | None,
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
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument name accesses.

        Args:
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument import name accesses.

        Args:
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument global variable accesses.

        Args:
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument dereferenced variable accesses.

        Args:
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument jump instructions.

        Args:
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument call instructions.

        Args:
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument return instructions.

        Args:
            ast_info: The AST info, if it exists.
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
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instruments the compare operations.

        Stores the values extracted at runtime.

        Args:
            ast_info: The AST info, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_string_function_without_arg(  # noqa: PLR0917
        self,
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instruments the isalnum function.

        Args:
            ast_info: The AST info, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_startswith_function(  # noqa: PLR0917
        self,
        ast_info: AstInfo | None,
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
            ast_info: The AST info, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_endswith_function(  # noqa: PLR0917
        self,
        ast_info: AstInfo | None,
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
            ast_info: The AST info, if it exists.
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

    def __init__(
        self,
        subject_properties: tracer.SubjectProperties,
        instrumentation_adapters: list[InstrumentationAdapter],
        to_cover_config: ToCoverConfiguration | None = None,
    ) -> None:
        """Initialize the instrumentation transformer.

        Args:
            subject_properties: The properties of the subject that is being instrumented.
            instrumentation_adapters: The list of instrumentation adapters that should be used.
            to_cover_config: the configuration of which code elements are used as coverage goals,
                defaults to a new ToCoverConfiguration.
        """
        self._subject_properties = subject_properties
        self._instrumentation_adapters = instrumentation_adapters
        self._to_cover_config = to_cover_config or ToCoverConfiguration()

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

        module_ast_info = ModuleAstInfo.from_path(
            code.co_filename,
            module_name,
            to_cover_config=self._to_cover_config,
        )

        return self._instrument_code_recursive(code, module_ast_info)

    def _instrument_code_recursive(
        self,
        code: CodeType,
        module_ast_info: ModuleAstInfo | None,
        parent_code_object_id: int | None = None,
    ) -> CodeType:
        # Ignore CPython's internal annotation helper introduced with PEP 649.
        # It appears as a synthetic function named "__annotate__" and should not
        # influence instrumentation or coverage goals.
        if code.co_name == "__annotate__":
            self._logger.debug("Skipping instrumentation of internal helper %s", code.co_name)
            return code

        ast_info = (
            module_ast_info.get_scope(
                # Special case as the line number of a module is 1
                # in its code object but is 0 in its AST
                0 if code.co_name == "<module>" else code.co_firstlineno
            )
            if module_ast_info is not None
            else None
        )

        if ast_info is not None and not ast_info.should_be_covered():
            self._logger.debug("Skipping instrumentation of %s", code.co_name)
            return code

        self._logger.debug("Instrumenting Code Object for %s", code.co_name)

        code_object_id = self._subject_properties.create_code_object_id()

        cfg = cf.CFG.from_bytecode(version.add_for_loop_no_yield_nodes(Bytecode.from_code(code)))

        for adapter in self._instrumentation_adapters:
            adapter.visit_cfg(ast_info, cfg, code_object_id)

        for node in cfg.basic_block_nodes:
            for adapter in self._instrumentation_adapters:
                adapter.visit_node(ast_info, cfg, code_object_id, node)

        instrumented_code = cfg.bytecode_cfg.to_code()

        code_object = instrumented_code.replace(
            co_consts=tuple(
                self._instrument_code_recursive(const, module_ast_info, code_object_id)
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
                cdg=self._create_covered_cdg(cfg, ast_info),
            ),
        )

        return code_object

    def _create_covered_cdg(
        self,
        cfg: cf.CFG,
        ast_info: AstInfo | None,
    ) -> cf.ControlDependenceGraph:
        cdg = cf.ControlDependenceGraph.compute(cfg)

        if ast_info is not None:
            # Remove nodes that should not be covered
            for node in tuple(cdg.graph):
                # Skip artificial nodes and nodes without "real" instructions (e.g., TryBegin, ...)
                if not isinstance(node, cf.BasicBlockNode) or all(
                    not isinstance(instr, Instr) for instr in node.basic_block
                ):
                    continue

                # Skip nodes that have at least one instruction that should be covered and
                # whose last instruction is either not a conditional statement or a conditional
                # statement that should be covered. `should_cover_conditional_statement`
                # defaults to True if there is no conditional statement at the line.
                if (
                    (last_instr := node.try_get_instruction(-1)) is None
                    or not isinstance(last_instr.lineno, int)
                    or ast_info.should_cover_conditional_statement(last_instr.lineno)
                ) and (
                    any(
                        not isinstance(instr.lineno, int)
                        or ast_info.should_cover_line(instr.lineno)
                        for instr in node.original_instructions
                    )
                ):
                    continue

                assert ast_info.module.only_cover_lines or ast_info.module.no_cover_lines, (
                    f"Node {node} should not be removed as only_cover_lines and no_cover_lines "
                    "are both empty."
                )

                predecessors = cdg.get_predecessors(node)
                successors = cdg.get_successors(node)

                predecessors.discard(node)
                successors.discard(node)
                cdg.graph.remove_node(node)

                for pred in predecessors:
                    for succ in successors:
                        cdg.graph.add_edge(pred, succ)

        return cdg
