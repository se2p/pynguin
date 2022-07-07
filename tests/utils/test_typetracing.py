#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import inspect
import operator

import pytest

import pynguin.utils.typetracing as tt


def test_isinstance_shim():
    assert inspect.isbuiltin(isinstance)
    with tt.shim_isinstance():
        assert not inspect.isbuiltin(isinstance)
    assert inspect.isbuiltin(isinstance)


def test_non_existing_attribute():
    proxy = tt.ObjectProxy(42)
    with pytest.raises(AttributeError):
        proxy.foo()
    assert "foo" in tt.ProxyKnowledge.from_proxy(proxy).symbol_table


def test_method_called():
    proxy = tt.ObjectProxy("foo")
    assert proxy.startswith("fo")
    assert "startswith" in tt.ProxyKnowledge.from_proxy(proxy).symbol_table
    assert (
        "__call__"
        in tt.ProxyKnowledge.from_proxy(proxy)
        .symbol_table["startswith"][0]
        .symbol_table
    )


def test_loop_over_list():
    proxy = tt.ObjectProxy(["foo", "bar"])
    with tt.shim_isinstance():
        for i, element in enumerate(proxy):
            assert isinstance(element, str)
    # Index 0 is a dummy entry to tell us that __iter__ was accessed.
    assert (
        str
        in tt.ProxyKnowledge.from_proxy(proxy).symbol_table["__iter__"][1].type_checks
    )
    assert (
        str
        in tt.ProxyKnowledge.from_proxy(proxy).symbol_table["__iter__"][2].type_checks
    )


def test_dict():
    proxy = tt.ObjectProxy({"foo": 42})
    assert proxy == {"foo": 42}
    assert (
        dict in tt.ProxyKnowledge.from_proxy(proxy).symbol_table["__eq__"][0].arg_types
    )


def test_isinstance_check():
    proxy = tt.ObjectProxy(42)
    with tt.shim_isinstance():
        assert isinstance(proxy, int)
    assert int in tt.ProxyKnowledge.from_proxy(proxy).type_checks


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
    assert int in tt.ProxyKnowledge.from_proxy(proxy).symbol_table[name][0].arg_types


def test_contains():
    proxy = tt.ObjectProxy([42])
    assert 42 in proxy
    assert (
        int
        in tt.ProxyKnowledge.from_proxy(proxy).symbol_table["__contains__"][0].arg_types
    )


def test_getitem():
    proxy = tt.ObjectProxy(["entry"])
    element = proxy[0]
    assert element == "entry"
    assert isinstance(element, tt.ObjectProxy)
    assert (
        int
        in tt.ProxyKnowledge.from_proxy(proxy).symbol_table["__getitem__"][0].arg_types
    )


def test_len():
    proxy = tt.ObjectProxy(["entry"])
    length = len(proxy)
    assert length == 1
    assert "__len__" in tt.ProxyKnowledge.from_proxy(proxy).symbol_table


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
    assert (
        len(
            tt.ProxyKnowledge.from_proxy(proxy)
            .symbol_table["__contains__"][0]
            .arg_types
        )
        == 0
    )


@pytest.mark.parametrize("func", [round, abs, int])
def test_simple_methods_behave_same(func):
    value = 3.1415
    proxy = tt.ObjectProxy(value)
    assert func(value) == func(proxy)


def test_dont_record_objectproxy_instance_check():
    proxy = tt.ObjectProxy(42)
    with tt.shim_isinstance():
        assert isinstance(proxy, tt.ObjectProxy)
    assert len(tt.ProxyKnowledge.from_proxy(proxy).type_checks) == 0


def test_setattr():
    class Foo:
        def __init__(self):
            self.foo = 42

    proxy = tt.ObjectProxy(Foo())
    proxy.foo = 42
    assert len(tt.ProxyKnowledge.from_proxy(proxy).symbol_table["foo"]) == 1


@pytest.mark.parametrize("obj", [42, "foo", 42.3, {}])
def test_same_dir(obj):
    proxy = tt.ObjectProxy(obj)
    assert dir(proxy) == dir(obj)
