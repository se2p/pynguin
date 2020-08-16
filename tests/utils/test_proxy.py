#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import operator
from typing import Any

import pytest

from pynguin.utils.proxy import MagicProxy, Proxy


@pytest.fixture
def int_proxy() -> MagicProxy:
    return MagicProxy(42)


@pytest.fixture
def str_proxy() -> MagicProxy:
    return MagicProxy("Test")


@pytest.fixture
def float_proxy() -> MagicProxy:
    return MagicProxy(2.5)


@pytest.fixture
def none_proxy() -> MagicProxy:
    return MagicProxy(None)


class _Dummy:
    foo = 42


def test_retrieve_obj():
    real = 5
    proxy = MagicProxy(real)
    assert proxy._obj is real


def test_getattribute(int_proxy):
    assert not int_proxy._hasError
    with pytest.raises(AttributeError):
        int_proxy.unknown
    assert int_proxy._hasError


def test_getattribute_of_proxy():

    proxy = Proxy(_Dummy())
    assert proxy.foo == 42


def test_setattr_of_proxy():
    proxy = Proxy(_Dummy())
    assert proxy.foo == 42
    proxy.foo = 43
    assert proxy.foo == 43


def test_str_of_proxy():
    proxy = Proxy(_Dummy())
    assert str(proxy.foo) == "42"


def test_setattribute(int_proxy):
    assert not int_proxy._hasError
    with pytest.raises(AttributeError):
        int_proxy.foo = 42
    assert int_proxy._hasError


def test_set_private_attribute(int_proxy: MagicProxy):
    assert not int_proxy._hasError
    int_proxy._errorCode = 42
    assert int_proxy._errorCode == 42
    assert not int_proxy._hasError


def test_getitem(int_proxy: MagicProxy):
    with pytest.raises(TypeError):
        int_proxy[1]
    assert int_proxy._hasError


def test_add(int_proxy: MagicProxy, str_proxy: MagicProxy):
    with pytest.raises(TypeError):
        int_proxy + str_proxy
    assert int_proxy._hasError
    assert str_proxy._hasError


def test_abs(str_proxy: MagicProxy):
    with pytest.raises(TypeError):
        abs(str_proxy)
    assert str_proxy._hasError


def test_call(int_proxy: MagicProxy):
    def test_callable(fst: int, snd: int = 0) -> int:
        return fst + 2 + snd

    call_proxy = MagicProxy(test_callable)
    with pytest.raises(TypeError):
        int_proxy()
    assert int_proxy._hasError

    result = call_proxy(2)
    assert result == 4
    assert not call_proxy._hasError

    result = call_proxy(2, 2)
    assert result == 6
    assert not call_proxy._hasError


def test_delitem(int_proxy: MagicProxy):
    with pytest.raises(TypeError):
        del int_proxy[1]
    assert int_proxy._hasError


def test_delslice(int_proxy: MagicProxy):
    with pytest.raises(TypeError):
        del int_proxy[1:5]
    assert int_proxy._hasError


def test_getslice(int_proxy: MagicProxy):
    with pytest.raises(TypeError):
        int_proxy[1:3]
    assert int_proxy._hasError


def test_gt(int_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not int_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        int_proxy > str_proxy
    assert int_proxy._hasError
    assert str_proxy._hasError


def test_lt(int_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not int_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        int_proxy < str_proxy
    assert int_proxy._hasError
    assert str_proxy._hasError


def test_ge(int_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not int_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        int_proxy >= str_proxy
    assert int_proxy._hasError
    assert str_proxy._hasError


def test_le(int_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not int_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        int_proxy <= str_proxy
    assert int_proxy._hasError
    assert str_proxy._hasError


def test_mul(float_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not float_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        float_proxy * str_proxy
    assert float_proxy._hasError
    assert str_proxy._hasError


def test_div(int_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not int_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        int_proxy / str_proxy
    assert int_proxy._hasError
    assert str_proxy._hasError


def test_len(int_proxy: MagicProxy):
    assert not int_proxy._hasError
    with pytest.raises(TypeError):
        len(int_proxy)
    assert int_proxy._hasError


def test_ne(int_proxy: MagicProxy):
    assert not int_proxy._hasError
    with pytest.raises(TypeError):
        not int_proxy
    assert int_proxy._hasError


def test_sub(int_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not int_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        int_proxy - str_proxy
    assert int_proxy._hasError
    assert str_proxy._hasError


def test_truediv(int_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not int_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        operator.truediv(int_proxy, str_proxy)
    assert int_proxy._hasError
    assert str_proxy._hasError


def test_floordiv(int_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not int_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        operator.floordiv(int_proxy, str_proxy)
    assert int_proxy._hasError
    assert str_proxy._hasError


def test_eq():
    class Dummy:
        def __eq__(self, other: Any) -> bool:
            return NotImplemented

    dummy_proxy_1 = MagicProxy(Dummy())
    dummy_proxy_2 = MagicProxy(Dummy())
    assert not dummy_proxy_1._hasError
    assert not dummy_proxy_2._hasError
    dummy_proxy_1 == dummy_proxy_2
    assert dummy_proxy_1._hasError
    assert dummy_proxy_2._hasError


def test_mod(float_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not float_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        float_proxy % str_proxy
    assert float_proxy._hasError
    assert str_proxy._hasError


def test_contains(float_proxy: MagicProxy):
    assert not float_proxy._hasError
    with pytest.raises(TypeError):
        "Test" in float_proxy
    assert float_proxy._hasError


def test_none_attr(none_proxy: MagicProxy):
    assert not none_proxy._hasError
    with pytest.raises(AttributeError):
        none_proxy.test()
    assert none_proxy._hasError


def test_none_call(none_proxy: MagicProxy):
    assert not none_proxy._hasError
    with pytest.raises(TypeError):
        none_proxy()
    assert none_proxy._hasError


def test_iter(int_proxy: MagicProxy):
    assert not int_proxy._hasError
    with pytest.raises(TypeError):
        iter(int_proxy)
    assert int_proxy._hasError


def test_next(int_proxy: MagicProxy):
    assert not int_proxy._hasError
    with pytest.raises(TypeError):
        next(int_proxy)
    assert int_proxy._hasError


def test_reversed(int_proxy: MagicProxy):
    assert not int_proxy._hasError
    with pytest.raises(TypeError):
        reversed(int_proxy)
    assert int_proxy._hasError


def test_setitem(int_proxy: MagicProxy):
    assert not int_proxy._hasError
    with pytest.raises(TypeError):
        int_proxy[0] = 42
    assert int_proxy._hasError


def test_pow(float_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not float_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        float_proxy ** str_proxy
    assert float_proxy._hasError
    assert str_proxy._hasError


def test_float(str_proxy: MagicProxy):
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        float(str_proxy)
    assert str_proxy._hasError


def test_int(str_proxy: MagicProxy):
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        int(str_proxy)
    assert str_proxy._hasError


def test_neg(str_proxy: MagicProxy):
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        operator.neg(str_proxy)
    assert str_proxy._hasError


def test_pos(str_proxy: MagicProxy):
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        operator.pos(str_proxy)
    assert str_proxy._hasError


def test_index_hex(str_proxy: MagicProxy):
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        hex(str_proxy)
    assert str_proxy._hasError


def test_index_bin(str_proxy: MagicProxy):
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        bin(str_proxy)
    assert str_proxy._hasError


def test_or(float_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not float_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        operator.or_(float_proxy, str_proxy)
    assert float_proxy._hasError
    assert str_proxy._hasError


def test_lshift(int_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not int_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        operator.lshift(int_proxy, str_proxy)
    assert int_proxy._hasError
    assert str_proxy._hasError


def test_rshift(int_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not int_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        operator.rshift(int_proxy, str_proxy)
    assert int_proxy._hasError
    assert str_proxy._hasError


def test_matmul(float_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not float_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        operator.matmul(float_proxy, str_proxy)
    assert float_proxy._hasError
    assert str_proxy._hasError


def test_and(float_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not float_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        operator.and_(float_proxy, str_proxy)
    assert float_proxy._hasError
    assert str_proxy._hasError


def test_xor(float_proxy: MagicProxy, str_proxy: MagicProxy):
    assert not float_proxy._hasError
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        operator.xor(float_proxy, str_proxy)
    assert float_proxy._hasError
    assert str_proxy._hasError


def test_index_oct(str_proxy: MagicProxy):
    assert not str_proxy._hasError
    with pytest.raises(TypeError):
        oct(str_proxy)
    assert str_proxy._hasError
