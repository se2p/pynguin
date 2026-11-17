# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
# SPDX-License-Identifier: MIT
"""Provides access to typeshed stubs, e.g., for constructors of C-implemented classes.

Classes implemented in C, such as ``datetime.date`` or ``decimal.Decimal``, often
have no runtime signature (``inspect.signature`` raises) and never have type hints.
Their constructor parameters and types are only declared in typeshed's stub files.
"""

from __future__ import annotations

import ast
import contextlib
import inspect
import logging
import sys
import typing
from typing import Any

import typeshed_client

_LOGGER = logging.getLogger(__name__)

# Protocols and stub-only aliases that we map to a concrete type we can generate.
_SUBSTITUTIONS: dict[str, Any] = {
    "SupportsIndex": int,
    "SupportsInt": int,
    "SupportsFloat": float,
    "SupportsComplex": complex,
    "ConvertibleToInt": int,
    "ConvertibleToFloat": float,
    "Buffer": bytes,
    "ReadableBuffer": bytes,
    "WriteableBuffer": bytearray,
    "StrPath": str,
    "StrOrBytesPath": str,
    "LiteralString": str,
}

_TYPING_MODULES = frozenset({"typing", "typing_extensions"})


class _Unresolved:
    """Marker for an annotation that cannot be resolved to a runtime type."""


UNRESOLVED: Any = _Unresolved()


def _module_path_name(module_path: Any) -> str:
    """Converts a typeshed_client module path (a tuple of names) to a dotted name."""
    if isinstance(module_path, tuple):
        return ".".join(module_path)
    return str(module_path)


class TypeshedStubs:
    """Looks up names, classes and class members in typeshed stubs.

    Stub modules are parsed lazily and cached.
    """

    MAX_HOPS = 3

    def __init__(self) -> None:
        """Creates a new stub lookup."""
        self._search_context: typeshed_client.finder.SearchContext | None = None
        self._stub_names_cache: dict[str, typeshed_client.NameDict | None] = {}

    def get_stub_names(self, module_name: str) -> typeshed_client.NameDict | None:
        """Returns the (cached) top-level names defined in a module's stub.

        Args:
            module_name: The name of the module

        Returns:
            The names defined in the stub, or None if there is no stub.
        """
        if module_name not in self._stub_names_cache:
            try:
                if self._search_context is None:
                    # Creating a search context scans sys.path, so we only do it once.
                    self._search_context = typeshed_client.get_search_context()
                self._stub_names_cache[module_name] = typeshed_client.get_stub_names(
                    module_name, search_context=self._search_context
                )
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Failed to load typeshed stub for module '%s'", module_name)
                self._stub_names_cache[module_name] = None
        return self._stub_names_cache[module_name]

    def resolve_imported(
        self, info: typeshed_client.NameInfo, module_name: str
    ) -> tuple[typeshed_client.NameInfo | None, str]:
        """Follows ``ImportedName`` indirections to the concrete definition.

        Args:
            info: The name to resolve
            module_name: The module that contains the name

        Returns:
            The concrete definition and the module defining it, or None if it cannot
            be resolved.
        """
        hops = 0
        while isinstance(info.ast, typeshed_client.ImportedName) and hops < self.MAX_HOPS:
            imported = info.ast
            if imported.name is None:
                return None, module_name
            target_module = _module_path_name(imported.module_name) or module_name
            names = self.get_stub_names(target_module)
            if not names or imported.name not in names:
                return None, module_name
            info = names[imported.name]
            module_name = target_module
            hops += 1
        if isinstance(info.ast, typeshed_client.ImportedName):
            return None, module_name
        return info, module_name

    def get_member(
        self,
        node_dict: typeshed_client.NameDict,
        name: str,
        owner_info: typeshed_client.NameInfo | None,
        module_name: str,
    ) -> tuple[typeshed_client.NameInfo | None, str]:
        """Looks up ``name`` in ``node_dict``, falling back to base classes.

        Args:
            node_dict: The names to search
            name: The name to look up
            owner_info: The class whose children ``node_dict`` holds, if any
            module_name: The module that contains ``node_dict``

        Returns:
            The definition and the module defining it, or None if not found.
        """
        info = node_dict.get(name)
        if info is not None:
            return self.resolve_imported(info, module_name)
        if owner_info is None or not isinstance(owner_info.ast, ast.ClassDef):
            return None, module_name
        return self._resolve_via_bases(owner_info.ast, name, module_name, depth=0)

    def _resolve_via_bases(
        self, class_def: ast.ClassDef, name: str, module_name: str, depth: int
    ) -> tuple[typeshed_client.NameInfo | None, str]:
        """Searches base classes (bounded depth) for an inherited member."""
        if depth >= self.MAX_HOPS:
            return None, module_name
        for base_expr in class_def.bases:
            head = self._base_head_name(base_expr)
            if head is None:
                continue
            base_info, base_module = self._resolve_base_name(head, module_name)
            if base_info is None or not isinstance(base_info.ast, ast.ClassDef):
                continue
            member = (base_info.child_nodes or {}).get(name)
            if member is not None:
                resolved_member, member_module = self.resolve_imported(member, base_module)
                if resolved_member is not None:
                    return resolved_member, member_module
            deeper = self._resolve_via_bases(base_info.ast, name, base_module, depth + 1)
            if deeper[0] is not None:
                return deeper
        return None, module_name

    def _resolve_base_name(
        self, head: str, module_name: str
    ) -> tuple[typeshed_client.NameInfo | None, str]:
        """Resolves a base class's leading identifier to a NameInfo + its module."""
        local_names = self.get_stub_names(module_name)
        if local_names and head in local_names:
            return self.resolve_imported(local_names[head], module_name)
        builtin_names = self.get_stub_names("builtins")
        if builtin_names and head in builtin_names:
            return self.resolve_imported(builtin_names[head], "builtins")
        return None, module_name

    @staticmethod
    def _base_head_name(expr: ast.expr) -> str | None:
        """Extracts the leading identifier from a base-class expression."""
        if isinstance(expr, ast.Name):
            return expr.id
        if isinstance(expr, ast.Attribute):
            return expr.attr
        if isinstance(expr, ast.Subscript):
            return TypeshedStubs._base_head_name(expr.value)
        return None

    def lookup(
        self, module_name: str, qualname: str
    ) -> tuple[typeshed_client.NameInfo | None, str]:
        """Looks up a (possibly nested) name in the stub of a module.

        Args:
            module_name: The module that defines the name at runtime
            qualname: The qualified name, e.g., ``date.__new__``

        Returns:
            The definition and the stub module defining it, or None if not found.
        """
        names = self.get_stub_names(module_name)
        if not names:
            return None, module_name
        node_dict: typeshed_client.NameDict = names
        owner_info: typeshed_client.NameInfo | None = None
        info: typeshed_client.NameInfo | None = None
        for part in qualname.split("."):
            info, module_name = self.get_member(node_dict, part, owner_info, module_name)
            if info is None:
                return None, module_name
            owner_info = info
            node_dict = info.child_nodes or {}
        return info, module_name


class _AnnotationResolver:
    """Resolves annotation expressions of a stub to runtime types.

    Only modules that are already imported are consulted, so resolving an
    annotation never imports (and thus never executes) further code.
    """

    _MAX_DEPTH = 8

    def __init__(self, stubs: TypeshedStubs) -> None:
        self._stubs = stubs

    def resolve(self, node: ast.expr, module_name: str, depth: int = 0) -> Any:
        """Resolves an annotation expression.

        Args:
            node: The annotation expression
            module_name: The stub module in which the annotation occurs
            depth: The current recursion depth

        Returns:
            The runtime type, or UNRESOLVED.
        """
        if depth > self._MAX_DEPTH:
            return UNRESOLVED
        if isinstance(node, ast.Constant):
            return self._resolve_constant(node, module_name, depth)
        if isinstance(node, ast.Name):
            return self._resolve_name(node.id, module_name, depth)
        if isinstance(node, ast.Attribute):
            return self._resolve_attribute(node, module_name, depth)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return self._make_union([node.left, node.right], module_name, depth)
        if isinstance(node, ast.Subscript):
            return self._resolve_subscript(node, module_name, depth)
        return UNRESOLVED

    def _resolve_constant(self, node: ast.Constant, module_name: str, depth: int) -> Any:
        if node.value is None:
            return type(None)
        if node.value is Ellipsis:
            return Ellipsis
        if isinstance(node.value, str):
            # A forward reference.
            try:
                parsed = ast.parse(node.value, mode="eval").body
            except SyntaxError:
                return UNRESOLVED
            return self.resolve(parsed, module_name, depth + 1)
        return UNRESOLVED

    def _resolve_name(self, name: str, module_name: str, depth: int) -> Any:
        if name in _SUBSTITUTIONS:
            return _SUBSTITUTIONS[name]
        if module_name in _TYPING_MODULES and hasattr(typing, name):
            return getattr(typing, name)
        for candidate_module in (module_name, "builtins"):
            names = self._stubs.get_stub_names(candidate_module)
            if names and name in names:
                return self._resolve_definition(names[name], candidate_module, name, depth)
        return UNRESOLVED

    def _resolve_definition(
        self, info: typeshed_client.NameInfo, module_name: str, name: str, depth: int
    ) -> Any:
        if isinstance(info.ast, typeshed_client.ImportedName):
            imported = info.ast
            if imported.name is None:
                return UNRESOLVED
            target_module = _module_path_name(imported.module_name)
            return self._resolve_name(imported.name, target_module, depth + 1)
        if isinstance(info.ast, ast.ClassDef):
            module = sys.modules.get(module_name)
            return getattr(module, name, UNRESOLVED) if module is not None else UNRESOLVED
        if isinstance(info.ast, ast.AnnAssign) and info.ast.value is not None:
            return self.resolve(info.ast.value, module_name, depth + 1)
        if isinstance(info.ast, ast.Assign):
            return self.resolve(info.ast.value, module_name, depth + 1)
        if isinstance(info.ast, ast.TypeAlias):
            return self.resolve(info.ast.value, module_name, depth + 1)
        return UNRESOLVED

    def _resolve_attribute(self, node: ast.Attribute, module_name: str, depth: int) -> Any:
        dotted = ast.unparse(node)
        if node.attr in _SUBSTITUTIONS:
            return _SUBSTITUTIONS[node.attr]
        prefix = dotted.rpartition(".")[0]
        if prefix in _TYPING_MODULES:
            return getattr(typing, node.attr, UNRESOLVED)
        if self._stubs.get_stub_names(prefix):
            return self._resolve_name(node.attr, prefix, depth + 1)
        # A module imported under another name, e.g., `import collections.abc as abc`.
        head = self.resolve(node.value, module_name, depth + 1)
        if head is UNRESOLVED:
            return UNRESOLVED
        return getattr(head, node.attr, UNRESOLVED)

    def _make_union(self, elements: list[ast.expr], module_name: str, depth: int) -> Any:
        members: list[Any] = []
        for element in elements:
            resolved = self.resolve(element, module_name, depth + 1)
            if resolved is UNRESOLVED or resolved is Ellipsis:
                # Dropping a member would narrow the type, so give no hint at all.
                return UNRESOLVED
            members.append(resolved)
        try:
            return typing.Union[tuple(members)]  # noqa: UP007
        except TypeError:
            return UNRESOLVED

    def _resolve_subscript(self, node: ast.Subscript, module_name: str, depth: int) -> Any:
        origin = self.resolve(node.value, module_name, depth + 1)
        if origin is UNRESOLVED:
            return UNRESOLVED
        elements = list(node.slice.elts) if isinstance(node.slice, ast.Tuple) else [node.slice]
        if origin is typing.Union:
            return self._make_union(elements, module_name, depth)
        if origin is typing.Optional:
            return self._make_union([*elements, ast.Constant(value=None)], module_name, depth)
        if origin is typing.Literal:
            literal_types = {
                type(element.value) for element in elements if isinstance(element, ast.Constant)
            }
            if not literal_types:
                return UNRESOLVED
            return typing.Union[tuple(literal_types)]  # noqa: UP007
        if origin is getattr(typing, "Annotated", None):
            return self.resolve(elements[0], module_name, depth + 1)
        arguments = []
        for element in elements:
            resolved = self.resolve(element, module_name, depth + 1)
            arguments.append(typing.Any if resolved is UNRESOLVED else resolved)
        try:
            return origin[tuple(arguments)] if len(arguments) > 1 else origin[arguments[0]]
        except Exception:  # noqa: BLE001
            return origin


def _parameters_of(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[ast.arg, inspect._ParameterKind, bool]]:
    """Lists the parameters of a stub method without its ``self``/``cls``.

    Returns:
        The argument nodes, their kinds and whether they have a default value.
    """
    args = function.args
    positional = [*args.posonlyargs, *args.args]
    first_default = len(positional) - len(args.defaults)
    result: list[tuple[ast.arg, inspect._ParameterKind, bool]] = []
    for index, arg in enumerate(positional):
        if index < len(args.posonlyargs) or (
            # Old-style positional-only parameters, e.g., `__x`.
            arg.arg.startswith("__") and not arg.arg.endswith("__")
        ):
            kind = inspect.Parameter.POSITIONAL_ONLY
        else:
            kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
        result.append((arg, kind, index >= first_default))
    if args.vararg is not None:
        result.append((args.vararg, inspect.Parameter.VAR_POSITIONAL, False))
    for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        result.append((arg, inspect.Parameter.KEYWORD_ONLY, default is not None))
    if args.kwarg is not None:
        result.append((args.kwarg, inspect.Parameter.VAR_KEYWORD, False))
    # Drop self/cls, the stub functions are methods.
    if result and result[0][1] in {
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    }:
        result = result[1:]
    return result


def only_takes_var_args(signature: inspect.Signature) -> bool:
    """Whether a signature has parameters, all of them ``*args``/``**kwargs``.

    Args:
        signature: The signature to check

    Returns:
        Whether the signature only takes variadic parameters.
    """
    parameters = list(signature.parameters.values())
    return len(parameters) > 0 and all(
        param.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
        for param in parameters
    )


class StubConstructorResolver:
    """Derives constructor signatures and types of classes from typeshed stubs."""

    def __init__(self, stubs: TypeshedStubs | None = None) -> None:
        """Creates a new resolver.

        Args:
            stubs: The stub lookup to use; a new one if None.
        """
        self._stubs = stubs if stubs is not None else TypeshedStubs()
        self._annotations = _AnnotationResolver(self._stubs)
        self._cache: dict[type, tuple[inspect.Signature, dict[str, Any]] | None] = {}

    def constructor(self, cls: type) -> tuple[inspect.Signature, dict[str, Any]] | None:
        """Builds the constructor signature of a class from its stub.

        The first class in the MRO that has a stub is used, so a Python subclass of a
        C-implemented class without own constructor gets the base class constructor.
        ``__new__`` is preferred over ``__init__``, unless it only takes
        ``*args``/``**kwargs`` and the stub also declares ``__init__``, e.g.,
        ``BaseException.__new__(cls, *args, **kwds)`` next to
        ``BaseException.__init__(self, *args)``. Of an overloaded
        constructor, the first overload that takes parameters is used.

        Args:
            cls: The class

        Returns:
            The signature (without ``cls``/``self``) and the resolved parameter types
            by name, or None if no stub provides a constructor.
        """
        if cls not in self._cache:
            try:
                self._cache[cls] = self._compute(cls)
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Failed to derive constructor of %s from typeshed", cls)
                self._cache[cls] = None
        return self._cache[cls]

    def _compute(self, cls: type) -> tuple[inspect.Signature, dict[str, Any]] | None:
        for base in getattr(cls, "__mro__", (cls,)):
            if base is object:
                break
            module_name = getattr(base, "__module__", None)
            qualname = getattr(base, "__qualname__", None)
            if not isinstance(module_name, str) or not isinstance(qualname, str):
                continue
            class_info, _ = self._stubs.lookup(module_name, qualname)
            if class_info is None or not isinstance(class_info.ast, ast.ClassDef):
                continue
            candidates = []
            for method_name in ("__new__", "__init__"):
                method_info, method_module = self._stubs.lookup(
                    module_name, f"{qualname}.{method_name}"
                )
                function = self._pick_overload(method_info)
                if function is not None:
                    candidates.append(self._build(function, method_module))
            if not candidates:
                return None
            if len(candidates) > 1 and only_takes_var_args(candidates[0][0]):
                return candidates[1]
            return candidates[0]
        return None

    @staticmethod
    def _pick_overload(
        info: typeshed_client.NameInfo | None,
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        if info is None:
            return None
        node: Any = info.ast
        definitions = (
            node.definitions if isinstance(node, typeshed_client.OverloadedName) else [node]
        )
        functions = [
            definition
            for definition in definitions
            if isinstance(definition, ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        for function in functions:
            if _parameters_of(function):
                return function
        return functions[0] if functions else None

    def _build(
        self, function: ast.FunctionDef | ast.AsyncFunctionDef, module_name: str
    ) -> tuple[inspect.Signature, dict[str, Any]]:
        parameters: list[inspect.Parameter] = []
        hints: dict[str, Any] = {}
        for arg, kind, has_default in _parameters_of(function):
            name = arg.arg
            if kind == inspect.Parameter.POSITIONAL_ONLY and name.startswith("__"):
                name = name[2:]
            with contextlib.suppress(ValueError):
                parameters.append(
                    inspect.Parameter(
                        name,
                        kind,
                        # The value itself is irrelevant, only whether there is one.
                        default=None if has_default else inspect.Parameter.empty,
                    )
                )
                if arg.annotation is not None:
                    resolved = self._annotations.resolve(arg.annotation, module_name)
                    if resolved is not UNRESOLVED and resolved is not Ellipsis:
                        hints[name] = resolved
        return inspect.Signature(parameters), hints


_RESOLVER: StubConstructorResolver | None = None


def get_stub_constructor(cls: type) -> tuple[inspect.Signature, dict[str, Any]] | None:
    """Builds the constructor signature of a class from typeshed stubs.

    Uses a shared, cached resolver; see StubConstructorResolver.constructor.

    Args:
        cls: The class

    Returns:
        The signature and the resolved parameter types, or None.
    """
    global _RESOLVER  # noqa: PLW0603
    if _RESOLVER is None:
        _RESOLVER = StubConstructorResolver()
    return _RESOLVER.constructor(cls)


__all__ = [
    "StubConstructorResolver",
    "TypeshedStubs",
    "get_stub_constructor",
    "only_takes_var_args",
]
