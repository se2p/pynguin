#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import copy
import enum
import functools
import gc
import inspect
import operator
import pickle  # noqa: S403
import sys
import types
import weakref
from dataclasses import dataclass
from typing import Any, NamedTuple
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
from pynguin.analyses.typesystem import InferredSignature
from pynguin.utils.type_utils import (
    get_class_that_defined_method,
    get_method_for_signature,
    get_signature,
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
    is_type_picklable,
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


def test_is_type_picklable():
    assert is_type_picklable(int) is True
    assert is_type_picklable(str) is True
    assert is_type_picklable(list[int]) is True
    assert is_type_picklable(dict[str, int]) is True
    assert is_type_picklable(int | str) is True
    assert is_type_picklable(None) is True
    assert is_type_picklable(type(None)) is True
    assert is_type_picklable(42) is True

    # Local class inside a function cannot be pickled by global name
    def _make_local():
        class _Local:
            pass

        return _Local

    local_cls = _make_local()
    assert is_type_picklable(local_cls) is False
    assert is_type_picklable(list[local_cls]) is False
    assert is_type_picklable(int | local_cls) is False

    # C-extension type not exposed on its module (like _json.Scanner)
    try:
        import json.scanner  # noqa: PLC0415

        scanner = json.scanner.c_make_scanner
        assert is_type_picklable(scanner) is False
        assert is_type_picklable(list[scanner]) is False
    except (ImportError, AttributeError):
        pass


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
@pytest.mark.parametrize("name, parameter", [("length", "obj"), ("Box.size", "other")])
def test_get_signature_keeps_unresolvable_annotation_as_forward_ref(
    name: str, parameter: str
) -> None:
    import annotationlib  # noqa: PLC0415

    from tests.fixtures.types import deferred_annotations  # noqa: PLC0415

    signature = get_signature(operator.attrgetter(name)(deferred_annotations))
    annotation = signature.parameters[parameter].annotation
    assert isinstance(annotation, annotationlib.ForwardRef)
    assert annotation.__forward_arg__ == "Sized"
    assert signature.return_annotation is int
    # Without an owner, the forward reference can be copied and shows no address.
    assert copy.deepcopy(signature) == signature
    assert "0x" not in repr(annotation)


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
@pytest.mark.parametrize(
    "name, expected",
    [
        pytest.param("pick", "(x: 'int' | None, y: int) -> int", id="type-error"),
        pytest.param("divide", "(x: 1 / 0) -> int", id="zero-division-error"),
        pytest.param("Box", "(n: 'int' | None) -> None", id="constructor"),
    ],
)
def test_get_signature_keeps_annotations_that_evaluate(name: str, expected: str) -> None:
    from tests.fixtures.types import deferred_annotations  # noqa: PLC0415

    assert str(get_signature(getattr(deferred_annotations, name))) == expected


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
def test_get_signature_without_source_drops_annotations_that_fail() -> None:
    namespace: dict[str, Any] = {}
    exec('def pick(x: "int" | None, y: int) -> int: ...', namespace)  # noqa: S102
    assert str(get_signature(namespace["pick"])) == "(x, y)"


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
def test_get_signature_leaves_inspect_unchanged() -> None:
    import annotationlib  # noqa: PLC0415

    from tests.fixtures.types.deferred_annotations import length  # noqa: PLC0415

    assert str(get_signature(length)) == "(obj: Sized) -> int"
    assert inspect.get_annotations is annotationlib.get_annotations
    with pytest.raises(NameError):
        inspect.signature(length)


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
@pytest.mark.parametrize(
    "name, expected",
    [
        pytest.param(
            "Outer.method",
            "(self, x: tests.fixtures.types.deferred_annotations.Outer.Inner, y: Sized)"
            " -> tests.fixtures.types.deferred_annotations.Outer.Inner",
            id="class-body",
        ),
        pytest.param(
            "closure",
            "(x: tests.fixtures.types.deferred_annotations.make_closure.<locals>.Local,"
            " y: Sized) -> tests.fixtures.types.deferred_annotations.make_closure.<locals>.Local",
            id="closure",
        ),
        pytest.param("renamed", "(x: 'int' | None, y: int) -> int", id="renamed"),
        pytest.param("nothing", "(x: 'int' | None, z: 'int') -> None", id="quoted"),
    ],
)
def test_get_signature_evaluates_annotations_in_their_scope(name: str, expected: str) -> None:
    from tests.fixtures.types import deferred_annotations  # noqa: PLC0415

    assert str(get_signature(operator.attrgetter(name)(deferred_annotations))) == expected


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
def test_get_signature_of_bound_method() -> None:
    from tests.fixtures.types.deferred_annotations import Box  # noqa: PLC0415

    assert str(get_signature(Box(None).size)) == "(other: Sized) -> int"


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
def test_get_signature_evaluates_failing_annotations_once() -> None:
    calls: list[str] = []

    def failing(name: str) -> Any:
        calls.append(name)
        raise NameError(name)

    namespace: dict[str, Any] = {"failing": failing}
    exec("def f(x: failing('x')) -> int: ...", namespace)  # noqa: S102
    assert str(get_signature(namespace["f"])) == "(x: failing('x')) -> int"
    evaluations = len(calls)
    assert str(get_signature(namespace["f"])) == "(x: failing('x')) -> int"
    assert len(calls) == evaluations


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
def test_get_signature_of_class_and_method_evaluates_failing_annotations_once() -> None:
    calls: list[str] = []

    def failing(name: str) -> Any:
        calls.append(name)
        raise NameError(name)

    namespace: dict[str, Any] = {"failing": failing}
    exec(  # noqa: S102
        "class C:\n"
        "    def __init__(self, x: failing('x')) -> None: ...\n"
        "    def m(self, y: failing('y')) -> int: ...",
        namespace,
    )
    cls = namespace["C"]
    for obj in (cls, cls(None).m):
        expected = str(get_signature(obj))
        evaluations = len(calls)
        assert str(get_signature(obj)) == expected
        assert len(calls) == evaluations


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
def test_get_signature_does_not_hash_callable() -> None:
    class Meta(type):
        def __hash__(cls) -> int:
            raise RuntimeError

    class Unhashable(metaclass=Meta):
        def __init__(self, x: int) -> None: ...

        def __call__(self, y: int) -> None: ...

        def __hash__(self) -> int:
            raise RuntimeError

    assert str(get_signature(Unhashable)) == "(x: int) -> None"
    assert str(get_signature(Unhashable.__new__(Unhashable))) == "(y: int) -> None"


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
def test_get_signature_does_not_keep_failing_callables_alive() -> None:
    def failing(name: str) -> Any:
        raise NameError(name)

    namespace: dict[str, Any] = {"failing": failing}
    exec(  # noqa: S102
        "class Node:\n    def merge(self, other: Node, y: failing('y')) -> Node: ...",
        namespace,
    )
    node = namespace["Node"]
    assert "other: Node" in str(get_signature(node.merge))
    reference = weakref.ref(node)
    del node
    namespace.clear()
    gc.collect()
    assert reference() is None


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
def test_get_signature_ignores_state_copied_by_wraps() -> None:
    def failing(name: str) -> Any:
        raise NameError(name)

    namespace: dict[str, Any] = {"failing": failing}
    exec("def f(x: failing('x'), y: int) -> int: ...", namespace)  # noqa: S102
    func = namespace["f"]
    assert str(get_signature(func)) == "(x: failing('x'), y: int) -> int"

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    signature = inspect.Signature([inspect.Parameter("z", inspect.Parameter.KEYWORD_ONLY)])
    wrapper.__signature__ = signature  # type: ignore[attr-defined]
    assert get_signature(wrapper) == signature


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
def test_get_signature_failure_depends_on_eval_str() -> None:
    namespace: dict[str, Any] = {}
    exec(  # noqa: S102
        "from __future__ import annotations\ndef f(x: Missing, y: int) -> int: ...",
        namespace,
    )
    func = namespace["f"]
    assert str(get_signature(func, eval_str=True)) == "(x: Missing, y: int) -> int"
    assert str(get_signature(func)) == "(x: 'Missing', y: 'int') -> 'int'"


def test_get_signature_without_signature_raises() -> None:
    with pytest.raises(TypeError):
        get_signature(42)  # type: ignore[arg-type]


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
@pytest.mark.parametrize(
    "name, expected",
    [
        pytest.param("caller", "(x: Sized) -> int", id="callable-instance"),
        pytest.param("partial_length", "(obj: Sized) -> int", id="partial"),
    ],
)
def test_get_signature_keeps_annotations_of_callable_instance_and_partial(
    name: str, expected: str
) -> None:
    from tests.fixtures.types import deferred_annotations  # noqa: PLC0415

    assert str(get_signature(getattr(deferred_annotations, name))) == expected


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
def test_get_signature_stays_picklable_after_forward_ref_is_evaluated() -> None:
    from tests.fixtures.types import deferred_annotations  # noqa: PLC0415

    annotation = get_signature(deferred_annotations.length).parameters["obj"].annotation
    # Evaluating a forward reference, as get_type_hints does, stores code on it.
    assert annotation.__forward_code__ is not None
    signature = get_signature(deferred_annotations.length)
    assert pickle.loads(pickle.dumps(signature)) == signature  # noqa: S301


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
def test_get_signature_keeps_quoted_annotations_without_eval_str() -> None:
    def failing(name: str) -> Any:
        raise NameError(name)

    namespace: dict[str, Any] = {"failing": failing}
    exec("def f(x: failing('x'), y: 'int') -> 'int': ...", namespace)  # noqa: S102
    func = namespace["f"]
    # The same as for a signature that does not fail.
    assert str(get_signature(func)) == "(x: failing('x'), y: 'int') -> 'int'"
    assert str(get_signature(func, eval_str=True)) == "(x: failing('x'), y: int) -> int"
    assert str(get_signature(func)) == "(x: failing('x'), y: 'int') -> 'int'"


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
def test_get_signature_does_not_change_the_function() -> None:
    from tests.fixtures.types import deferred_annotations  # noqa: PLC0415

    get_signature(deferred_annotations.length)
    get_signature(deferred_annotations.length, eval_str=True)
    assert vars(deferred_annotations.length) == {}


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Annotations are deferred from Python 3.14")
def test_get_signature_of_function_decorated_in_other_module() -> None:
    from tests.fixtures.types.deferred_annotations import decorated  # noqa: PLC0415

    assert str(get_signature(decorated)) == (
        "(x: 'int' | None, y: tests.fixtures.types.deferred_annotations.Item) -> int"
    )
