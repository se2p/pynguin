#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import enum
import inspect

from unittest.mock import MagicMock

import pytest

from pynguin.analyses.typesystem import InferredSignature
from pynguin.utils.type_utils import given_exception_matches
from pynguin.utils.type_utils import is_arg_or_kwarg
from pynguin.utils.type_utils import is_assertable
from pynguin.utils.type_utils import is_bytes
from pynguin.utils.type_utils import is_collection_type
from pynguin.utils.type_utils import is_dict
from pynguin.utils.type_utils import is_enum
from pynguin.utils.type_utils import is_ignorable_type
from pynguin.utils.type_utils import is_list
from pynguin.utils.type_utils import is_none_type
from pynguin.utils.type_utils import is_numeric
from pynguin.utils.type_utils import is_optional_parameter
from pynguin.utils.type_utils import is_primitive_type
from pynguin.utils.type_utils import is_set
from pynguin.utils.type_utils import is_string
from pynguin.utils.type_utils import is_tuple


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
