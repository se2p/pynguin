#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

import ast
import datetime
import decimal
import inspect
import types
import typing
from unittest.mock import patch

import pytest
import typeshed_client

from pynguin.analyses import typeshed_stubs
from pynguin.analyses.typeshed_stubs import (
    UNRESOLVED,
    StubConstructorResolver,
    TypeshedStubs,
    get_stub_constructor,
    only_takes_var_args,
)
from tests.fixtures.cluster.c_type_constructors import OwnDate, PythonInit

P = inspect.Parameter


@pytest.fixture(scope="module")
def resolver() -> StubConstructorResolver:
    return StubConstructorResolver()


@pytest.fixture(scope="module")
def annotations() -> typeshed_stubs._AnnotationResolver:
    return typeshed_stubs._AnnotationResolver(TypeshedStubs())


def _kinds(signature: inspect.Signature) -> dict[str, inspect._ParameterKind]:
    return {name: param.kind for name, param in signature.parameters.items()}


def _has_default(signature: inspect.Signature) -> dict[str, bool]:
    return {name: param.default is not P.empty for name, param in signature.parameters.items()}


def test_date(resolver):
    result = resolver.constructor(datetime.date)
    assert result is not None
    signature, hints = result
    assert list(signature.parameters) == ["year", "month", "day"]
    assert not any(_has_default(signature).values())
    assert hints == {"year": int, "month": int, "day": int}


def test_timedelta_all_optional_floats(resolver):
    result = resolver.constructor(datetime.timedelta)
    assert result is not None
    signature, hints = result
    assert "days" in signature.parameters
    assert all(_has_default(signature).values())
    assert set(hints.values()) == {float}


def test_datetime_keyword_only_and_optional(resolver):
    result = resolver.constructor(datetime.datetime)
    assert result is not None
    signature, hints = result
    assert _kinds(signature)["fold"] == P.KEYWORD_ONLY
    assert _has_default(signature)["tzinfo"]
    assert not _has_default(signature)["day"]
    assert hints["tzinfo"] == typing.Optional[datetime.tzinfo]  # noqa: UP045


def test_decimal_expands_stub_alias(resolver):
    result = resolver.constructor(decimal.Decimal)
    assert result is not None
    _, hints = result
    members = typing.get_args(hints["value"])
    assert {decimal.Decimal, float, str} <= set(members)
    assert hints["context"] == typing.Optional[decimal.Context]  # noqa: UP045


def test_simple_namespace_positional_only_and_kwargs(resolver):
    result = resolver.constructor(types.SimpleNamespace)
    assert result is not None
    signature, _ = result
    assert _kinds(signature) == {
        "mapping_or_iterable": P.POSITIONAL_ONLY,
        "kwargs": P.VAR_KEYWORD,
    }


def test_overload_with_parameters_is_picked(resolver):
    result = resolver.constructor(range)
    assert result is not None
    signature, hints = result
    assert _kinds(signature) == {"stop": P.POSITIONAL_ONLY}
    assert hints == {"stop": int}


def test_init_is_used_if_new_only_takes_var_args(resolver):
    result = resolver.constructor(ValueError)
    assert result is not None
    signature, _ = result
    assert _kinds(signature) == {"args": P.VAR_POSITIONAL}


def test_python_subclass_uses_base_stub(resolver):
    result = resolver.constructor(OwnDate)
    assert result is not None
    assert list(result[0].parameters) == ["year", "month", "day"]


@pytest.mark.parametrize("cls", [object, PythonInit])
def test_no_stub_constructor(resolver, cls):
    assert resolver.constructor(cls) is None


def test_constructor_is_cached(resolver):
    assert resolver.constructor(datetime.date) is resolver.constructor(datetime.date)


def test_constructor_failure_is_none():
    stubs = TypeshedStubs()
    with patch.object(stubs, "lookup", side_effect=RuntimeError("boom")):
        assert StubConstructorResolver(stubs).constructor(datetime.date) is None


def test_get_stub_constructor_shared():
    assert get_stub_constructor(datetime.date) is get_stub_constructor(datetime.date)


def test_only_takes_var_args():
    assert only_takes_var_args(inspect.Signature([P("a", P.VAR_POSITIONAL), P("k", P.VAR_KEYWORD)]))
    assert not only_takes_var_args(inspect.Signature())
    assert not only_takes_var_args(inspect.Signature([P("a", P.POSITIONAL_OR_KEYWORD)]))


def _resolve(annotations, source: str, module: str = "builtins") -> typing.Any:
    return annotations.resolve(ast.parse(source, mode="eval").body, module)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("int", int),
        ("None", type(None)),
        ("SupportsIndex", int),
        ("typing.SupportsFloat", float),
        ("int | None", typing.Optional[int]),  # noqa: UP045
        ("Optional[str]", typing.Optional[str]),  # noqa: UP045
        ("Union[int, str]", typing.Union[int, str]),  # noqa: UP007
        ("Literal['a', 'b']", str),
        ("'int'", int),
        ("list[int]", list[int]),
        ("tuple[int, ...]", tuple[int, ...]),
        ("typing.Any", typing.Any),
    ],
)
def test_resolve_annotation(annotations, source, expected):
    assert _resolve(annotations, source, "typing") == expected


@pytest.mark.parametrize(
    "source",
    [
        "DoesNotExist",
        "int | DoesNotExist",
        "'int +'",
        "1",
        "f(x)",
        "Literal[x]",
        "unknown.module.Name",
    ],
)
def test_resolve_annotation_unresolved(annotations, source):
    assert _resolve(annotations, source) is UNRESOLVED


def test_resolve_annotation_unknown_generic_arguments_become_any(annotations):
    assert _resolve(annotations, "list[DoesNotExist]") == list[typing.Any]


def test_resolve_annotation_bad_subscript_keeps_origin(annotations):
    assert _resolve(annotations, "int[str]") is int


def test_resolve_annotation_annotated(annotations):
    assert _resolve(annotations, "Annotated[int, 'meta']", "typing") is int


def test_resolve_annotation_depth_limit(annotations):
    node = ast.parse("int", mode="eval").body
    assert annotations.resolve(node, "builtins", depth=100) is UNRESOLVED


def test_resolve_class_of_module_not_imported(annotations):
    with patch.dict("sys.modules", {"decimal": None}):
        assert _resolve(annotations, "Decimal", "decimal") is UNRESOLVED


def test_resolve_attribute_via_module_object(annotations):
    with patch.object(annotations, "_resolve_name", return_value=typing):
        assert _resolve(annotations, "alias.Any", "somewhere") is typing.Any


def test_parameters_of_old_style_positional_only():
    function = ast.parse("def __new__(cls, __x: int, y=1, *a, z, w=2, **k): ...").body[0]
    assert isinstance(function, ast.FunctionDef)
    parameters = [
        (arg.arg, kind, default) for arg, kind, default in typeshed_stubs._parameters_of(function)
    ]
    assert parameters == [
        ("__x", P.POSITIONAL_ONLY, False),
        ("y", P.POSITIONAL_OR_KEYWORD, True),
        ("a", P.VAR_POSITIONAL, False),
        ("z", P.KEYWORD_ONLY, False),
        ("w", P.KEYWORD_ONLY, True),
        ("k", P.VAR_KEYWORD, False),
    ]


def test_build_strips_old_style_prefix(resolver):
    function = ast.parse("def __new__(cls, __x: int): ...").body[0]
    signature, hints = resolver._build(function, "builtins")  # type: ignore[arg-type]
    assert list(signature.parameters) == ["x"]
    assert hints == {"x": int}


def test_pick_overload():
    defs = [ast.parse(src).body[0] for src in ("def f(self): ...", "def f(self, x): ...")]
    info = typeshed_client.NameInfo("f", is_exported=True, ast=typeshed_client.OverloadedName(defs))
    assert StubConstructorResolver._pick_overload(info) is defs[1]
    single = typeshed_client.NameInfo("f", is_exported=True, ast=defs[0])
    assert StubConstructorResolver._pick_overload(single) is defs[0]
    assert StubConstructorResolver._pick_overload(None) is None


def test_lookup_missing_stub():
    stubs = TypeshedStubs()
    assert stubs.lookup("pynguin_no_such_module", "X")[0] is None
    assert stubs.get_stub_names("pynguin_no_such_module") is None


def test_lookup_missing_member():
    stubs = TypeshedStubs()
    assert stubs.lookup("datetime", "date.does_not_exist")[0] is None


def test_lookup_inherited_member():
    stubs = TypeshedStubs()
    info, module = stubs.lookup("datetime", "datetime.replace")
    assert info is not None
    assert module == "datetime"


def test_resolve_imported_module_import():
    stubs = TypeshedStubs()
    info = typeshed_client.NameInfo(
        "x",
        is_exported=True,
        ast=typeshed_client.ImportedName(typeshed_client.ModulePath(("os",))),
    )
    assert stubs.resolve_imported(info, "m")[0] is None


def test_resolve_imported_unknown_target():
    stubs = TypeshedStubs()
    info = typeshed_client.NameInfo(
        "x",
        is_exported=True,
        ast=typeshed_client.ImportedName(typeshed_client.ModulePath(("os",)), "does_not_exist"),
    )
    assert stubs.resolve_imported(info, "m")[0] is None


def test_get_stub_names_failure_is_cached():
    stubs = TypeshedStubs()
    with patch.object(typeshed_client, "get_stub_names", side_effect=RuntimeError) as mock:
        assert stubs.get_stub_names("datetime") is None
        assert stubs.get_stub_names("datetime") is None
    mock.assert_called_once()
