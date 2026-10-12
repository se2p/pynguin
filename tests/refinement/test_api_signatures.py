#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the API signature summary of a module under test."""

from __future__ import annotations

import importlib
import sys
import types

import pytest

from pynguin.refinement.api_signatures import describe_module_api

_SUT_SOURCE = """\
import abc
import json
from collections import OrderedDict
from pathlib import Path


class Account(abc.ABC):
    def __init__(self, owner: str, balance: int = 0):
        self.owner = owner
        self.balance = balance

    @abc.abstractmethod
    def fee(self) -> int: ...

    def deposit(self, amount: int) -> None:
        self.balance += amount

    def _audit(self):
        pass


class Savings(Account):
    def fee(self) -> int:
        return 0

    @property
    def label(self) -> str:
        return self.owner

    @staticmethod
    def rate(years: int) -> float:
        return 0.01 * years

    @classmethod
    def open(cls, owner: str) -> "Savings":
        return cls(owner)


def transfer(source: Account, target: Account, amount: int) -> None:
    source.balance -= amount
    target.balance += amount


def _helper():
    pass
"""


@pytest.fixture
def sut(tmp_path, monkeypatch):
    (tmp_path / "api_sut.py").write_text(_SUT_SOURCE)
    monkeypatch.syspath_prepend(str(tmp_path))
    module = importlib.import_module("api_sut")
    yield module
    sys.modules.pop("api_sut", None)


def test_describe_module_api_lists_constructor_signatures_without_self(sut):
    summary = describe_module_api(sut)

    assert "class Savings(owner: str, balance: int = 0)" in summary.splitlines()
    assert (
        "def transfer(source: api_sut.Account, target: api_sut.Account, amount: int) -> None"
        in summary.splitlines()
    )


def test_describe_module_api_marks_abstract_classes_with_concrete_subclasses(sut):
    summary = describe_module_api(sut)

    account = next(line for line in summary.splitlines() if line.startswith("class Account"))
    assert "ABSTRACT (abstract methods: fee)" in account
    assert "instantiate a concrete subclass instead: Savings" in account
    savings = next(line for line in summary.splitlines() if line.startswith("class Savings"))
    assert "ABSTRACT" not in savings


def test_describe_module_api_lists_public_methods_including_inherited_ones(sut):
    summary = describe_module_api(sut)

    assert (
        "class Savings(owner: str, balance: int = 0)\n"
        "    fee(self) -> int\n"
        "    label  (property)\n"
        "    @staticmethod rate(years: int) -> float\n"
        "    @classmethod open(owner: str) -> api_sut.Savings\n"
        "    deposit(self, amount: int) -> None\n"
    ) in summary
    assert "_audit" not in summary


def test_describe_module_api_skips_private_and_stdlib_names(sut):
    summary = describe_module_api(sut)

    assert "_helper" not in summary
    assert "OrderedDict" not in summary
    assert "Path" not in summary
    assert "json" not in summary


def test_describe_module_api_respects_dunder_all(sut, monkeypatch):
    monkeypatch.setattr(sut, "__all__", ["transfer"], raising=False)

    assert describe_module_api(sut).startswith("def transfer(")


def test_describe_module_api_lists_own_members_before_imported_ones(sut):
    class Remote:
        def __init__(self, url: str) -> None:
            self.url = url

        def fetch(self) -> str:
            return self.url

    Remote.__module__ = "other"
    sut.Remote = Remote
    try:
        lines = describe_module_api(sut).splitlines()
    finally:
        del sut.Remote

    # Imported classes only show their constructor, after the module's own members.
    assert lines[-1] == "class Remote(url: str)"
    assert not any("fetch" in line for line in lines)


def test_describe_module_api_truncates_to_max_chars(sut):
    full = describe_module_api(sut, max_chars=None)
    first_entry_end = full.index("\nclass Savings")

    truncated = describe_module_api(sut, max_chars=first_entry_end + 1)

    assert truncated == full[:first_entry_end]


def test_describe_module_api_does_not_trigger_module_getattr():
    module = types.ModuleType("lazy_sut")
    calls = []

    def module_getattr(name):
        calls.append(name)
        raise AttributeError(name)

    def run(x: int) -> int:
        return x

    module.__getattr__ = module_getattr
    module.run = run
    module.__all__ = ["run", "lazy_only"]

    assert describe_module_api(module) == "def run(x: int) -> int"
    assert calls == []


def test_describe_module_api_without_public_members_is_empty():
    assert not describe_module_api(types.ModuleType("empty_sut"))
