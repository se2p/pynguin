#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import enum
import functools
import inspect
import sys
import types
from dataclasses import dataclass
from typing import NamedTuple
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
from pynguin.analyses.typesystem import InferredSignature
from pynguin.utils.type_utils import (
    get_class_that_defined_method,
    get_method_for_signature,
    given_exception_matches,
    is_arg_or_kwarg,
    is_assertable,
    is_bytes,
    is_collection_type,
    is_dict,
    is_enum,
    is_ignorable_type,
    is_list,
    is_none_type,
    is_numeric,
    is_optional_parameter,
    is_primitive_type,
    is_repr_assertable,
    is_set,
    is_string,
    is_tuple,
)


@pytest.mark.parametrize(
    "type_, result",
    [
        (int, True),
        (float, True),
        (str, True),
        (bool, True),
        (complex, True),
        (type, False),
        (None, False),
    ],
)
def test_is_primitive_type(type_, result):
    assert is_primitive_type(type_) == result


@pytest.mark.parametrize(
    "type_, result",
    [
        (type(None), True),
        (None, False),
        (str, False),
    ],
)
def test_is_none_type(type_, result):
    assert is_none_type(type_) == result


@pytest.mark.parametrize(
    "value, result",
    [(5, True), (5.5, True), ("test", False), (None, False)],
)
def test_is_numeric(value, result):
    assert is_numeric(value) == result


@pytest.mark.parametrize(
    "value, result",
    [(5, False), (5.5, False), ("test", True), (None, False)],
)
def test_is_string(value, result):
    assert is_string(value) == result


@pytest.mark.parametrize(
    "value, result",
    [(b"5", True), ("foo", False), (bytearray("test", "ascii"), True), (None, False)],
)
def test_is_bytes(value, result):
    assert is_bytes(value) == result


@pytest.mark.parametrize(
    "value, result",
    [
        (["foo", "bar"], True),
        ({"foo", "bar"}, False),
        ({"foo": "bar"}, False),
        (("foo", "bar"), False),
    ],
)
def test_is_list(value, result):
    assert is_list(type(value)) == result


@pytest.mark.parametrize(
    "value, result",
    [
        (["foo", "bar"], False),
        ({"foo", "bar"}, True),
        ({"foo": "bar"}, False),
        (("foo", "bar"), False),
    ],
)
def test_is_set(value, result):
    assert is_set(type(value)) == result


@pytest.mark.parametrize(
    "value, result",
    [
        (["foo", "bar"], False),
        ({"foo", "bar"}, False),
        ({"foo": "bar"}, True),
        (("foo", "bar"), False),
    ],
)
def test_is_dict(value, result):
    assert is_dict(type(value)) == result


@pytest.mark.parametrize(
    "value, result",
    [
        (["foo", "bar"], False),
        ({"foo", "bar"}, False),
        ({"foo": "bar"}, False),
        (("foo", "bar"), True),
    ],
)
def test_is_tuple(value, result):
    assert is_tuple(type(value)) == result


def test_is_enum():
    class Foo(enum.Enum):
        pass

    assert is_enum(Foo)


class HasInit:
    def __init__(self):  # noqa: D107
        pass


class ExtendsHasInit(HasInit):
    pass


class HasNoInit:
    pass


@pytest.mark.parametrize(
    "method,replaced",
    [
        (object.__init__, object),
        (object.mro, object.mro),
        (HasInit.__init__, HasInit.__init__),
        (HasNoInit.__init__, object),
        (ExtendsHasInit.__init__, ExtendsHasInit.__init__),
    ],
)
def test_get_method_for_signature(method, replaced):
    actual = get_method_for_signature(method)
    assert actual == replaced


@pytest.mark.parametrize(
    "param_name,result",
    [
        ("normal", False),
        ("args", True),
        ("kwargs", True),
        ("default", True),
    ],
)
def test_should_skip_parameter(param_name, result):
    def inner_func(normal: str, *args, default="foo", **kwargs):
        pass  # pragma: no cover

    inf_sig = MagicMock(InferredSignature, signature=inspect.signature(inner_func))
    assert is_optional_parameter(inf_sig, param_name) == result


@pytest.fixture
def inf_sig_non_hashable():
    class NonHashableParameterKind:
        def __eq__(self, other):
            # Allow equality comparison with inspect.Parameter constants
            return other == inspect.Parameter.VAR_POSITIONAL

        def __hash__(self):
            # Make this class non-hashable
            raise TypeError("unhashable type: '_ParameterKind'")

    # Create a mock parameter with the non-hashable kind
    mock_parameter = MagicMock(spec=inspect.Parameter)
    mock_parameter.kind = NonHashableParameterKind()
    mock_parameter.default = inspect.Parameter.empty

    # Create a mock signature and parameters dictionary
    mock_params = {"args": mock_parameter}
    mock_signature = MagicMock()
    mock_signature.parameters = mock_params

    # Create a mock InferredSignature with our mock signature
    inf_sig = MagicMock(InferredSignature)
    inf_sig.signature = mock_signature

    return inf_sig


def test_is_optional_parameter_not_hashable(inf_sig_non_hashable):
    assert is_optional_parameter(inf_sig_non_hashable, "args") is True


@pytest.mark.parametrize(
    "param_name,result",
    [
        ("normal", False),
        ("args", True),
        ("kwargs", True),
        ("default", False),
    ],
)
def test_is_arg_or_kwarg(param_name, result):
    def inner_func(normal: str, *args, default="foo", **kwargs):
        pass  # pragma: no cover

    inf_sig = MagicMock(InferredSignature, signature=inspect.signature(inner_func))
    assert is_arg_or_kwarg(inf_sig, param_name) == result


def test_is_arg_or_kwarg_not_hashable(inf_sig_non_hashable):
    assert is_arg_or_kwarg(inf_sig_non_hashable, "args") is True


@pytest.mark.parametrize(
    "type_,result",
    [
        (list, True),
        (set, True),
        (dict, True),
        (tuple, True),
        (list[str], True),
        (set[str], True),
        (tuple[str], True),
        (dict[str, str], True),
        (str, False),
    ],
)
def test_is_collection_type(type_, result):
    assert is_collection_type(type_) == result


def test_is_ignorable_type():
    def generator():  # pragma: no cover
        yield from range(10)

    generator_type = type(generator())
    assert is_ignorable_type(generator_type)


def test_is_ignorable_type_async():
    async def async_generator():  # pragma: no cover  # noqa: RUF029
        yield "foo"

    generator_type = type(async_generator())
    assert is_ignorable_type(generator_type)


def test_is_ignorable_type_false():
    assert not is_ignorable_type(str)


@pytest.mark.parametrize(
    "exception,ex_match,result",
    [
        (ValueError, ValueError, True),
        (ValueError(), ValueError, True),
        (ValueError(), Exception, True),
        (ValueError(), NameError, False),
        (None, None, False),
    ],
)
def test_given_exception_matches(exception, ex_match, result):
    assert given_exception_matches(exception, ex_match) == result


@pytest.mark.parametrize(
    "value,result",
    [
        (1, True),
        (MagicMock(), False),
        (enum.Enum("Dummy", "a").a, True),
        ({1, 2}, True),
        ({1, MagicMock()}, False),
        ([1, 2], True),
        ([1, MagicMock()], False),
        ((1, 2), True),
        ((1, MagicMock()), False),
        ({1: 2}, True),
        ({1: MagicMock()}, False),
        ([[[[[[[[]]]]]]]], False),
        ((), True),
        (set(), True),
        ({}, True),
        ([], True),
        ([[]], True),
        ("foobar", True),
        (["a", "b", ["a", "b", MagicMock()]], False),
        (1.5, False),
        ([1, 1.5], False),
        (None, True),
        ([None], True),
    ],
)
def test_is_assertable(value, result):
    assert is_assertable(value) == result


class _DefiningBase:
    def norm(self):
        pass

    @staticmethod
    def stat():
        pass

    @classmethod
    def cls_m(cls):
        pass

    @functools.lru_cache
    def lru_m(self):
        pass

    class Nested:
        def nested_norm(self):
            pass

        @classmethod
        def nested_cls_m(cls):
            pass


class _DefiningSub(_DefiningBase):
    pass


def test_get_class_that_defined_method():
    assert get_class_that_defined_method(_DefiningBase.norm) == _DefiningBase
    assert get_class_that_defined_method(_DefiningBase.stat) == _DefiningBase
    assert get_class_that_defined_method(_DefiningBase.cls_m) == _DefiningBase
    assert get_class_that_defined_method(_DefiningSub.cls_m) == _DefiningBase
    assert get_class_that_defined_method(_DefiningBase.lru_m) == _DefiningBase
    assert get_class_that_defined_method(_DefiningBase.Nested.nested_norm) == _DefiningBase.Nested
    assert get_class_that_defined_method(_DefiningBase.Nested.nested_cls_m) == _DefiningBase.Nested
    assert get_class_that_defined_method(None) is None


# --- Repr-based Assertability -------------------------------------------------


@dataclass
class DummyPoint:
    x: int
    y: int


class DummyNamedTuple(NamedTuple):
    a: int
    b: str


class DummyReprEq:  # noqa: PLW1641
    def __init__(self, val: int) -> None:  # noqa: D107
        self.val = val

    def __repr__(self) -> str:
        return f"DummyReprEq({self.val})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, DummyReprEq) and self.val == other.val


class DummyNoEq:
    def __init__(self, val: int) -> None:  # noqa: D107
        self.val = val

    def __repr__(self) -> str:
        return f"DummyNoEq({self.val})"


class DummyAngleRepr:  # noqa: PLW1641
    def __init__(self, val: int) -> None:  # noqa: D107
        self.val = val

    def __repr__(self) -> str:
        return f"<DummyAngleRepr {self.val}>"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, DummyAngleRepr) and self.val == other.val


class DummySyntaxErrorRepr:  # noqa: PLW1641
    def __repr__(self) -> str:
        return "def invalid syntax("

    def __eq__(self, other: object) -> bool:
        return True


class DummyRaisingRepr:  # noqa: PLW1641
    def __repr__(self) -> str:
        raise RuntimeError("boom")

    def __eq__(self, other: object) -> bool:
        return True


class DummyDifferentTypeRepr:  # noqa: PLW1641
    def __repr__(self) -> str:
        return "42"

    def __eq__(self, other: object) -> bool:
        return other == 42


class DummyUncopyable:  # noqa: PLW1641
    def __repr__(self) -> str:
        return "DummyUncopyable()"

    def __deepcopy__(self, memo: dict) -> None:
        raise TypeError("uncopyable")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, DummyUncopyable)


class DummyEqRaising:  # noqa: PLW1641
    def __repr__(self) -> str:
        return "DummyEqRaising()"

    def __eq__(self, other: object) -> bool:
        raise RuntimeError("cannot compare")


class _PrivateDummy:  # noqa: PLW1641
    def __init__(self, val: int) -> None:
        self.val = val

    def __repr__(self) -> str:
        return f"_PrivateDummy({self.val})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _PrivateDummy) and self.val == other.val


@pytest.mark.parametrize(
    "obj, namespace, expected",
    [
        (DummyPoint(1, 2), {"DummyPoint": DummyPoint}, True),
        (DummyNamedTuple(1, "x"), {"DummyNamedTuple": DummyNamedTuple}, True),
        (DummyReprEq(42), {"DummyReprEq": DummyReprEq}, True),
        (object(), {"object": object}, False),
        (DummyNoEq(1), {"DummyNoEq": DummyNoEq}, False),
        (DummyAngleRepr(1), {"DummyAngleRepr": DummyAngleRepr}, False),
        (DummySyntaxErrorRepr(), {"DummySyntaxErrorRepr": DummySyntaxErrorRepr}, False),
        (DummyRaisingRepr(), {"DummyRaisingRepr": DummyRaisingRepr}, False),
        (DummyDifferentTypeRepr(), {"DummyDifferentTypeRepr": DummyDifferentTypeRepr}, False),
        (DummyUncopyable(), {"DummyUncopyable": DummyUncopyable}, False),
        (DummyEqRaising(), {"DummyEqRaising": DummyEqRaising}, False),
        (_PrivateDummy(1), {"_PrivateDummy": _PrivateDummy}, False),
        (DummyPoint(1, 2), {}, False),  # Not defined in namespace
    ],
)
def test_is_repr_assertable(obj, namespace, expected):
    assert is_repr_assertable(obj, namespace=namespace) is expected


def test_is_assertable_custom_objects():
    ns = {"DummyPoint": DummyPoint}
    p = DummyPoint(1, 2)
    assert is_assertable(p) is False
    assert is_assertable([p, p]) is False
    assert is_repr_assertable(p, namespace=ns) is True
    assert is_repr_assertable([p, p], namespace=ns) is True
    assert is_repr_assertable({"key": p}, namespace=ns) is True
    assert is_repr_assertable((p,), namespace=ns) is True
    assert is_repr_assertable([p, DummyNoEq(1)], namespace=ns) is False


def test_is_repr_assertable_namespace_none_with_sys_modules(monkeypatch):
    mod = types.ModuleType("dummy_test_module")
    mod.DummyPoint = DummyPoint  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "dummy_test_module", mod)
    monkeypatch.setattr(config.configuration, "module_name", "dummy_test_module")

    p = DummyPoint(1, 2)
    assert is_repr_assertable(p, namespace=None) is True
