#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import inspect
import math
import operator

from builtins import isinstance as real_isinstance
from unittest.mock import MagicMock

import pytest

import pynguin.utils.typetracing as tt

from pynguin.utils.orderedset import OrderedSet


def test_type_tracing_max_depth():
    proxy = tt.ObjectProxy(MagicMock())
    for _i in range(tt._MAX_PROXY_NESTING):
        proxy = proxy["foo"]
    assert isinstance(proxy, tt.ObjectProxy)


def test_type_tracing_max_depth_after():
    proxy = tt.ObjectProxy(MagicMock())
    for _i in range(tt._MAX_PROXY_NESTING + 1):
        proxy = proxy["foo"]
    assert not isinstance(proxy, tt.ObjectProxy)


def test_type_tracing_max_depth_get_attr():
    mock = MagicMock()
    mock.foo = mock
    proxy = tt.ObjectProxy(mock)
    for _i in range(tt._MAX_PROXY_NESTING):
        proxy = proxy.foo
    assert isinstance(proxy, tt.ObjectProxy)


def test_type_tracing_max_depth_after_get_attr():
    mock = MagicMock()
    mock.foo = mock
    proxy = tt.ObjectProxy(mock)
    for _i in range(tt._MAX_PROXY_NESTING + 1):
        proxy = proxy.foo
    assert not isinstance(proxy, tt.ObjectProxy)


def test_type_tracing_max_depth_iter():
    mock = [[[[[[[MagicMock()]]]]]]]
    proxy = tt.ObjectProxy(mock)
    for _i in range(tt._MAX_PROXY_NESTING):
        proxy = next(iter(proxy))
    assert isinstance(proxy, tt.ObjectProxy)


def test_type_tracing_max_depth_after_iter():
    mock = [[[[[[[MagicMock()]]]]]]]
    proxy = tt.ObjectProxy(mock)
    for _i in range(tt._MAX_PROXY_NESTING + 1):
        proxy = next(iter(proxy))
    assert not isinstance(proxy, tt.ObjectProxy)


def test_isinstance_shim():
    assert inspect.isbuiltin(isinstance)
    with tt.shim_isinstance():
        assert not inspect.isbuiltin(isinstance)
        assert inspect.isbuiltin(real_isinstance)
    assert inspect.isbuiltin(isinstance)


def test_non_existing_attribute():
    proxy = tt.ObjectProxy(42)
    with pytest.raises(AttributeError):
        proxy.foo()
    assert "foo" in tt.UsageTraceNode.from_proxy(proxy).children


def test_method_called():
    proxy = tt.ObjectProxy("foo")
    assert proxy.startswith("fo")
    assert "startswith" in tt.UsageTraceNode.from_proxy(proxy).children
    assert "__call__" in tt.UsageTraceNode.from_proxy(proxy).children["startswith"].children


def test_loop_over_list():
    proxy = tt.ObjectProxy(["foo", "bar"])
    with tt.shim_isinstance():
        for element in proxy:
            assert isinstance(element, str)
    assert str in tt.UsageTraceNode.from_proxy(proxy).children["__iter__"].type_checks


def test_dict():
    proxy = tt.ObjectProxy({"foo": 42})
    assert proxy == {"foo": 42}
    assert dict in tt.UsageTraceNode.from_proxy(proxy).children["__eq__"].arg_types[0]


def test_dont_record_objectproxy_instance_check():
    proxy = tt.ObjectProxy(42)
    with tt.shim_isinstance():
        assert isinstance(proxy, tt.ObjectProxy)
    assert len(tt.UsageTraceNode.from_proxy(proxy).type_checks) == 0


def test_dont_record_objectproxy_instance_check_2():
    proxy = tt.ObjectProxy(42)
    with tt.shim_isinstance():
        assert isinstance(proxy, (tt.ObjectProxy, bytes))
    assert len(tt.UsageTraceNode.from_proxy(proxy).type_checks) == 0


def test_dont_record_objectproxy_instance_check_3():
    proxy = tt.ObjectProxy(42)
    with tt.shim_isinstance(), pytest.raises(TypeError):
        assert isinstance(proxy, tt.ObjectProxy(int))
    assert inspect.isbuiltin(isinstance)
    assert len(tt.UsageTraceNode.from_proxy(proxy).type_checks) == 0


def test_dont_record_objectproxy_instance_check_4():
    proxy = tt.ObjectProxy(42)
    with tt.shim_isinstance(), pytest.raises(TypeError):
        assert isinstance(proxy, (tt.ObjectProxy(int), float))
    assert inspect.isbuiltin(isinstance)
    assert len(tt.UsageTraceNode.from_proxy(proxy).type_checks) == 0


def test_objectproxy_instance_check():
    proxy = tt.ObjectProxy(42)
    with tt.shim_isinstance():
        assert isinstance(proxy, (int, float))
    assert len(tt.UsageTraceNode.from_proxy(proxy).type_checks) == 2


def test_setattr():
    class Foo:
        def __init__(self):
            self.foo = 42

    proxy = tt.ObjectProxy(Foo())
    proxy.foo = 42
    assert "foo" in tt.UsageTraceNode.from_proxy(proxy).children


@pytest.mark.parametrize("obj", [42, "foo", 42.3, {}])
def test_same_dir(obj):
    proxy = tt.ObjectProxy(obj)
    assert dir(proxy) == dir(obj)


def test_isinstance_check():
    proxy = tt.ObjectProxy(42)
    with tt.shim_isinstance():
        assert isinstance(proxy, int)
    assert int in tt.UsageTraceNode.from_proxy(proxy).type_checks


def test_isinstance_check_2():
    proxy = tt.ObjectProxy(42)
    with tt.shim_isinstance():
        assert isinstance(proxy, (int, str))
    assert int in tt.UsageTraceNode.from_proxy(proxy).type_checks
    assert str in tt.UsageTraceNode.from_proxy(proxy).type_checks


def test_merge():
    copy = proxy = tt.ObjectProxy(42)
    proxy2 = tt.ObjectProxy("42")
    copy += 3
    assert proxy2 + "3"
    with tt.shim_isinstance():
        assert isinstance(proxy, int)
        assert isinstance(proxy2, str)
    knowledge1 = tt.UsageTraceNode.from_proxy(proxy)
    knowledge2 = tt.UsageTraceNode.from_proxy(proxy2)
    knowledge1.merge(knowledge2)
    assert int in knowledge1.children["__iadd__"].arg_types[0]
    assert str in knowledge1.children["__add__"].arg_types[0]
    assert int in knowledge1.type_checks
    assert str in knowledge1.type_checks


@pytest.mark.parametrize(
    "op,name",
    [
        (operator.eq, "__eq__"),
        (operator.ne, "__ne__"),
        (operator.le, "__le__"),
        (operator.lt, "__lt__"),
        (operator.ge, "__ge__"),
        (operator.gt, "__gt__"),
    ],
)
def test_compares_op(op, name):
    proxy = tt.ObjectProxy(42)
    assert op(proxy, 42) == op(42, 42)
    assert int in tt.UsageTraceNode.from_proxy(proxy).children[name].arg_types[0]


def test_contains():
    proxy = tt.ObjectProxy([42])
    assert 42 in proxy
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__contains__"].arg_types[0]


def test_len():
    proxy = tt.ObjectProxy(["entry"])
    length = len(proxy)
    assert length == 1
    assert "__len__" in tt.UsageTraceNode.from_proxy(proxy).children


def test_hash():
    proxy = tt.ObjectProxy("entry")
    assert hash(proxy) == hash("entry")


def test_class():
    proxy = tt.ObjectProxy("entry")
    assert proxy.__class__ == "entry".__class__


def test_name():
    class Foo:
        pass

    proxy = tt.ObjectProxy(Foo)
    assert proxy.__name__ == Foo.__name__


def test_contains_proxy():
    proxy = tt.ObjectProxy([42])
    proxy2 = tt.ObjectProxy(42)
    assert proxy2 in proxy
    assert len(tt.UsageTraceNode.from_proxy(proxy).children["__contains__"].arg_types[0]) == 0


def test_bytes():
    value = 4
    proxy = tt.ObjectProxy(value)
    assert bytes(value) == bytes(proxy)
    assert "__bytes__" in tt.UsageTraceNode.from_proxy(proxy).children


# Regular operators


def test_add():
    value = 42
    proxy = tt.ObjectProxy(value)
    assert value + 1 == proxy + 1
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__add__"].arg_types[0]


def test_sub():
    value = 42
    proxy = tt.ObjectProxy(value)
    assert value - 1 == proxy - 1
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__sub__"].arg_types[0]


def test_mul():
    value = 42
    proxy = tt.ObjectProxy(value)
    assert value * 2 == proxy * 2
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__mul__"].arg_types[0]


def test_truediv():
    value = 7
    proxy = tt.ObjectProxy(value)
    assert value / 2 == proxy / 2
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__truediv__"].arg_types[0]


def test_floordiv():
    value = 7
    proxy = tt.ObjectProxy(value)
    assert value // 2 == proxy // 2
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__floordiv__"].arg_types[0]


def test_mod():
    value = 7
    proxy = tt.ObjectProxy(value)
    assert value % 3 == proxy % 3
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__mod__"].arg_types[0]


def test_divmod():
    value = 7
    proxy = tt.ObjectProxy(value)
    assert divmod(value, 3) == divmod(proxy, 3)
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__divmod__"].arg_types[0]


def test_pow():
    value = 2
    proxy = tt.ObjectProxy(value)
    assert value**2 == proxy**2
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__pow__"].arg_types[0]


def test_lshift():
    value = 2
    proxy = tt.ObjectProxy(value)
    assert value << 3 == proxy << 3
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__lshift__"].arg_types[0]


def test_rshift():
    value = 2
    proxy = tt.ObjectProxy(value)
    assert value >> 3 == proxy >> 3
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__rshift__"].arg_types[0]


def test_and():
    value = 2
    proxy = tt.ObjectProxy(value)
    assert value & 1 == proxy & 1
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__and__"].arg_types[0]


def test_xor():
    value = 2
    proxy = tt.ObjectProxy(value)
    assert value ^ 1 == proxy ^ 1
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__xor__"].arg_types[0]


def test_or():
    value = 2
    proxy = tt.ObjectProxy(value)
    assert value | 1 == proxy | 1
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__or__"].arg_types[0]


# Reverse operators


def test_radd():
    value = 42
    proxy = tt.ObjectProxy(value)
    assert 1 + value == 1 + proxy
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__radd__"].arg_types[0]


def test_rsub():
    value = 42
    proxy = tt.ObjectProxy(value)
    assert 1 - value == 1 - proxy
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__rsub__"].arg_types[0]


def test_rmul():
    value = 42
    proxy = tt.ObjectProxy(value)
    assert 2 * value == 2 * proxy
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__rmul__"].arg_types[0]


def test_rtruediv():
    value = 2
    proxy = tt.ObjectProxy(value)
    assert 7 / value == 7 / proxy
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__rtruediv__"].arg_types[0]


def test_rfloordiv():
    value = 2
    proxy = tt.ObjectProxy(value)
    assert 7 // value == 7 // proxy
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__rfloordiv__"].arg_types[0]


def test_rmod():
    value = 3
    proxy = tt.ObjectProxy(value)
    assert 7 % value == 7 % proxy
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__rmod__"].arg_types[0]


def test_rdivmod():
    value = 3
    proxy = tt.ObjectProxy(value)
    assert divmod(7, value) == divmod(7, proxy)
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__rdivmod__"].arg_types[0]


def test_rpow():
    value = 2
    proxy = tt.ObjectProxy(value)
    assert 3**value == 3**proxy
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__rpow__"].arg_types[0]


def test_rlshift():
    value = 2
    proxy = tt.ObjectProxy(value)
    assert 3 << value == 3 << proxy
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__rlshift__"].arg_types[0]


def test_rrshift():
    value = 2
    proxy = tt.ObjectProxy(value)
    assert 3 >> value == 3 >> proxy
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__rrshift__"].arg_types[0]


def test_rand():
    value = 2
    proxy = tt.ObjectProxy(value)
    assert 1 & value == 1 & proxy
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__rand__"].arg_types[0]


def test_rxor():
    value = 2
    proxy = tt.ObjectProxy(value)
    assert 1 ^ value == 1 ^ proxy
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__rxor__"].arg_types[0]


def test_ror():
    value = 2
    proxy = tt.ObjectProxy(value)
    assert 1 | value == 1 | proxy
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__ror__"].arg_types[0]


# Inplace operators


def test_iadd():
    value = 42
    copy = proxy = tt.ObjectProxy(value)
    value += 1
    proxy += 1
    assert value == proxy
    assert int in tt.UsageTraceNode.from_proxy(copy).children["__iadd__"].arg_types[0]


def test_isub():
    value = 42
    copy = proxy = tt.ObjectProxy(value)
    value -= 1
    proxy -= 1
    assert value == proxy
    assert int in tt.UsageTraceNode.from_proxy(copy).children["__isub__"].arg_types[0]


def test_imul():
    value = 42
    copy = proxy = tt.ObjectProxy(value)
    value *= 2
    proxy *= 2
    assert value == proxy
    assert int in tt.UsageTraceNode.from_proxy(copy).children["__imul__"].arg_types[0]


def test_itruediv():
    value = 42
    copy = proxy = tt.ObjectProxy(value)
    value /= 2
    proxy /= 2
    assert value == proxy
    assert int in tt.UsageTraceNode.from_proxy(copy).children["__itruediv__"].arg_types[0]


def test_ifloordiv():
    value = 42
    copy = proxy = tt.ObjectProxy(value)
    value //= 3
    proxy //= 3
    assert value == proxy
    assert int in tt.UsageTraceNode.from_proxy(copy).children["__ifloordiv__"].arg_types[0]


def test_imod():
    value = 42
    copy = proxy = tt.ObjectProxy(value)
    value %= 3
    proxy %= 3
    assert value == proxy
    assert int in tt.UsageTraceNode.from_proxy(copy).children["__imod__"].arg_types[0]


def test_ipow():
    value = 2
    copy = proxy = tt.ObjectProxy(value)
    value **= 3
    proxy **= 3
    assert value == proxy
    assert int in tt.UsageTraceNode.from_proxy(copy).children["__ipow__"].arg_types[0]


def test_ilshift():
    value = 2
    copy = proxy = tt.ObjectProxy(value)
    value <<= 1
    proxy <<= 1
    assert value == proxy
    assert int in tt.UsageTraceNode.from_proxy(copy).children["__ilshift__"].arg_types[0]


def test_irshift():
    value = 2
    copy = proxy = tt.ObjectProxy(value)
    value >>= 1
    proxy >>= 1
    assert value == proxy
    assert int in tt.UsageTraceNode.from_proxy(copy).children["__irshift__"].arg_types[0]


def test_iand():
    value = 2
    copy = proxy = tt.ObjectProxy(value)
    value &= 1
    proxy &= 1
    assert value == proxy
    assert int in tt.UsageTraceNode.from_proxy(copy).children["__iand__"].arg_types[0]


def test_ixor():
    value = 2
    copy = proxy = tt.ObjectProxy(value)
    value ^= 1
    proxy ^= 1
    assert value == proxy
    assert int in tt.UsageTraceNode.from_proxy(copy).children["__ixor__"].arg_types[0]


def test_ior():
    value = 2
    copy = proxy = tt.ObjectProxy(value)
    value |= 1
    proxy |= 1
    assert value == proxy
    assert int in tt.UsageTraceNode.from_proxy(copy).children["__ior__"].arg_types[0]


def test_neg():
    value = math.pi
    proxy = tt.ObjectProxy(value)
    assert -value == -proxy
    assert tt.UsageTraceNode.from_proxy(proxy).children["__neg__"]


def test_pos():
    value = -math.pi
    proxy = tt.ObjectProxy(value)
    assert +value == +proxy
    assert tt.UsageTraceNode.from_proxy(proxy).children["__pos__"]


def test_abs():
    value = -math.pi
    proxy = tt.ObjectProxy(value)
    assert abs(value) == abs(proxy)
    assert tt.UsageTraceNode.from_proxy(proxy).children["__abs__"]


def test_invert():
    value = 4
    proxy = tt.ObjectProxy(value)
    assert ~value == ~proxy
    assert tt.UsageTraceNode.from_proxy(proxy).children["__invert__"]


@pytest.mark.parametrize("func", [round, int, float, complex])
def test_various_num_methods(func):
    value = math.pi
    proxy = tt.ObjectProxy(value)
    assert func(value) == func(proxy)


def test_getitem_list():
    proxy = tt.ObjectProxy(["entry"])
    element = proxy[0]
    assert element == "entry"
    assert isinstance(element, tt.ObjectProxy)
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__getitem__"].arg_types[0]


def test_getitem_list_slice():
    proxy = tt.ObjectProxy(["a", "b"])
    element = proxy[1:]
    assert element == ["b"]
    assert isinstance(element, tt.ObjectProxy)
    assert slice in tt.UsageTraceNode.from_proxy(proxy).children["__getitem__"].arg_types[0]


def test_getitem_dict():
    proxy = tt.ObjectProxy({"foo": "entry"})
    element = proxy["foo"]
    assert element == "entry"
    assert isinstance(element, tt.ObjectProxy)
    assert str in tt.UsageTraceNode.from_proxy(proxy).children["__getitem__"].arg_types[0]


def test_setitem_list():
    proxy = tt.ObjectProxy(["a", "b"])
    proxy[0] = 42
    element = proxy[0]
    assert element == 42
    assert isinstance(element, tt.ObjectProxy)
    assert int in tt.UsageTraceNode.from_proxy(proxy).children["__setitem__"].arg_types[0]


def test_unwrap():
    foo = object()
    assert tt.unwrap(foo) is foo


def test_unwrap_2():
    foo = object()
    assert tt.unwrap(tt.ObjectProxy(tt.ObjectProxy(foo))) is foo


def test_pretty():
    knowledge = tt.UsageTraceNode("ROOT")
    knowledge.children["foo"].arg_types[0].add(int)
    knowledge.type_checks.add(str)
    assert knowledge.pretty() == "['ROOT', type_checks: {str}]\n└──['foo', arg_types: {0: {int}}]"


def test_getattr():
    proxy = tt.ObjectProxy([1])
    proxy.count(1)
    assert "count" in tt.UsageTraceNode.from_proxy(proxy).children


def test_has_path():
    proxy = tt.ObjectProxy([1])
    proxy.count(1)
    count_call_knowledge = tt.UsageTraceNode.from_proxy(proxy).find_path((
        "count",
        "__call__",
    ))
    assert count_call_knowledge.arg_types[0] == OrderedSet([int])


def test_has_path_no_path():
    proxy = tt.ObjectProxy([1])
    proxy.count(1)
    assert tt.UsageTraceNode.from_proxy(proxy).find_path(("count", "foobar")) is None
