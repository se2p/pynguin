#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the ContextExtractor module."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from pynguin.large_language_model.mock_generation.context_extractor import (
    AttributeAccess,
    ContextExtractor,
    DependencyUsage,
    FunctionContext,
    MethodCall,
)

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract(source: str, deps: list[str]) -> list[FunctionContext]:
    return ContextExtractor(dependencies=deps).extract_from_source(source)


def first(source: str, deps: list[str]) -> FunctionContext:
    results = extract(source, deps)
    assert results, "Expected at least one FunctionContext"
    return results[0]


def dep(ctx: FunctionContext, name: str) -> DependencyUsage:
    for d in ctx.dependencies:
        if d.dependency == name:
            return d
    raise AssertionError(f"Dependency {name!r} not found in context")


# ---------------------------------------------------------------------------
# DataClass field tests
# ---------------------------------------------------------------------------


def test_method_call_fields():
    mc = MethodCall(method_name="get", args_count=1, has_kwargs=False)
    assert mc.method_name == "get"
    assert mc.args_count == 1
    assert mc.has_kwargs is False


def test_attribute_access_fields():
    aa = AttributeAccess(attribute_name="status_code", is_method_call=False)
    assert aa.attribute_name == "status_code"
    assert aa.is_method_call is False


def test_dependency_usage_defaults():
    du = DependencyUsage(dependency="requests")
    assert du.variable_names == []
    assert du.method_calls == []
    assert du.return_value_accesses == []


def test_function_context_fields():
    fc = FunctionContext(function_name="fn", source_code="def fn(): pass")
    assert fc.function_name == "fn"
    assert fc.source_code == "def fn(): pass"
    assert fc.dependencies == []


# ---------------------------------------------------------------------------
# 1. Simple method call
# ---------------------------------------------------------------------------


def test_simple_method_call():
    src = """
def fetch(session):
    session.get("/users")
"""
    ctx = first(src, ["session"])
    d = dep(ctx, "session")
    assert len(d.method_calls) == 1
    mc = d.method_calls[0]
    assert mc.method_name == "get"
    assert mc.args_count == 1
    assert mc.has_kwargs is False


# ---------------------------------------------------------------------------
# 2. Method call with kwargs
# ---------------------------------------------------------------------------


def test_method_call_with_kwargs():
    src = """
def fetch(session):
    session.get("/users", timeout=30)
"""
    ctx = first(src, ["session"])
    mc = dep(ctx, "session").method_calls[0]
    assert mc.method_name == "get"
    assert mc.args_count == 1
    assert mc.has_kwargs is True


# ---------------------------------------------------------------------------
# 3. Attribute access on return value
# ---------------------------------------------------------------------------


def test_attribute_access_on_return_value():
    src = """
def fetch(session):
    response = session.get("/users")
    return response.status_code
"""
    ctx = first(src, ["session"])
    accesses = dep(ctx, "session").return_value_accesses
    names = [a.attribute_name for a in accesses]
    assert "status_code" in names
    # plain attribute read, not a call
    sc = next(a for a in accesses if a.attribute_name == "status_code")
    assert sc.is_method_call is False


# ---------------------------------------------------------------------------
# 4. Method call on return value (.json())
# ---------------------------------------------------------------------------


def test_method_call_on_return_value():
    src = """
def fetch(session):
    response = session.get("/users")
    data = response.json()
    return data
"""
    ctx = first(src, ["session"])
    accesses = dep(ctx, "session").return_value_accesses
    json_acc = next((a for a in accesses if a.attribute_name == "json"), None)
    assert json_acc is not None
    assert json_acc.is_method_call is True


# ---------------------------------------------------------------------------
# 5. Full example from spec
# ---------------------------------------------------------------------------


def test_full_fetch_user_example():
    src = """
def fetch_user(session, user_id):
    response = session.get(f"/users/{user_id}")
    if response.status_code == 200:
        data = response.json()
        return data
    return None
"""
    ctx = first(src, ["session"])
    assert ctx.function_name == "fetch_user"

    d = dep(ctx, "session")
    assert "session" in d.variable_names

    assert len(d.method_calls) == 1
    assert d.method_calls[0].method_name == "get"

    attr_names = [a.attribute_name for a in d.return_value_accesses]
    assert "status_code" in attr_names
    assert "json" in attr_names

    json_acc = next(a for a in d.return_value_accesses if a.attribute_name == "json")
    assert json_acc.is_method_call is True
    sc_acc = next(a for a in d.return_value_accesses if a.attribute_name == "status_code")
    assert sc_acc.is_method_call is False


# ---------------------------------------------------------------------------
# 6. Multiple dependencies in one function
# ---------------------------------------------------------------------------


def test_multiple_dependencies():
    src = """
def save_user_to_db(http_client, db_connection, user_id):
    response = http_client.get(f"/users/{user_id}")
    if response.ok:
        user_data = response.json()
        db_connection.execute("INSERT INTO users VALUES (?)", user_data)
        db_connection.commit()
        return True
    return False
"""
    ctx = first(src, ["http_client", "db_connection"])

    hc = dep(ctx, "http_client")
    assert hc.method_calls[0].method_name == "get"
    attr_names = [a.attribute_name for a in hc.return_value_accesses]
    assert "ok" in attr_names
    assert "json" in attr_names

    db = dep(ctx, "db_connection")
    method_names = [m.method_name for m in db.method_calls]
    assert "execute" in method_names
    assert "commit" in method_names
    execute_call = next(m for m in db.method_calls if m.method_name == "execute")
    assert execute_call.args_count == 2


# ---------------------------------------------------------------------------
# 7. Variable alias (s = session)
# ---------------------------------------------------------------------------


def test_variable_alias():
    src = """
def fetch(session):
    s = session
    s.get("/ping")
"""
    ctx = first(src, ["session"])
    d = dep(ctx, "session")
    assert "s" in d.variable_names
    assert any(m.method_name == "get" for m in d.method_calls)


# ---------------------------------------------------------------------------
# 8. Dependency as function parameter (not imported module)
# ---------------------------------------------------------------------------


def test_dependency_as_parameter():
    src = """
def use_client(requests):
    requests.get("/")
"""
    ctx = first(src, ["requests"])
    assert ctx is not None
    d = dep(ctx, "requests")
    assert d.method_calls[0].method_name == "get"


# ---------------------------------------------------------------------------
# 9. Nested function definitions are not analysed as separate entries
#    but are also not descended into for the outer function
# ---------------------------------------------------------------------------


def test_nested_function_not_analysed_in_outer():
    src = """
def outer(session):
    session.get("/outer")
    def inner():
        session.post("/inner")
"""
    contexts = extract(src, ["session"])
    # Both outer and inner should each produce a context.
    names = [c.function_name for c in contexts]
    assert "outer" in names

    outer_ctx = next(c for c in contexts if c.function_name == "outer")
    outer_calls = [m.method_name for m in dep(outer_ctx, "session").method_calls]
    # "post" lives in inner — must not appear in outer's method calls.
    assert "get" in outer_calls
    assert "post" not in outer_calls


# ---------------------------------------------------------------------------
# 10. Class methods that use dependencies
# ---------------------------------------------------------------------------


def test_class_method_with_dependency():
    src = """
class MyService:
    def fetch(self, session):
        response = session.get("/data")
        return response.text
"""
    contexts = extract(src, ["session"])
    assert any(c.function_name == "fetch" for c in contexts)
    fetch_ctx = next(c for c in contexts if c.function_name == "fetch")
    d = dep(fetch_ctx, "session")
    assert d.method_calls[0].method_name == "get"
    assert any(a.attribute_name == "text" for a in d.return_value_accesses)


# ---------------------------------------------------------------------------
# 11. No tracked dependency used — returns nothing
# ---------------------------------------------------------------------------


def test_no_dependency_returns_empty():
    src = """
def pure_function(x, y):
    return x + y
"""
    results = extract(src, ["session"])
    assert results == []


def test_extract_from_function_returns_none_when_no_dep():
    src = "def fn(x): return x\n"
    tree = ast.parse(src)
    func_node = tree.body[0]
    result = ContextExtractor(dependencies=["session"]).extract_from_function(func_node, src)
    assert result is None


# ---------------------------------------------------------------------------
# 12. Lambda functions — skipped (not FunctionDef nodes)
# ---------------------------------------------------------------------------


def test_lambda_not_extracted():
    src = """
handler = lambda session: session.get("/")
"""
    results = extract(src, ["session"])
    assert results == []


# ---------------------------------------------------------------------------
# 13. Multiple method calls on the same dependency
# ---------------------------------------------------------------------------


def test_multiple_calls_on_same_dependency():
    src = """
def work(db):
    db.begin()
    db.execute("SELECT 1")
    db.commit()
"""
    ctx = first(src, ["db"])
    names = [m.method_name for m in dep(ctx, "db").method_calls]
    assert names == ["begin", "execute", "commit"]


# ---------------------------------------------------------------------------
# 14. Chained call: session.get(url).json()
# ---------------------------------------------------------------------------


def test_chained_call():
    src = """
def fetch(session):
    data = session.get("/api").json()
"""
    ctx = first(src, ["session"])
    d = dep(ctx, "session")
    # session.get() should be captured as a method call
    assert any(m.method_name == "get" for m in d.method_calls)


# ---------------------------------------------------------------------------
# 15. extract_from_file reads the path
# ---------------------------------------------------------------------------


def test_extract_from_file(tmp_path: Path):
    p = tmp_path / "mod.py"
    p.write_text(
        "def fn(session):\n    session.get('/x')\n",
        encoding="utf-8",
    )
    contexts = ContextExtractor(dependencies=["session"]).extract_from_file(p)
    assert len(contexts) == 1
    assert contexts[0].function_name == "fn"


def test_extract_from_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        ContextExtractor(dependencies=["x"]).extract_from_file(tmp_path / "missing.py")


def test_extract_from_file_syntax_error(tmp_path: Path):
    p = tmp_path / "bad.py"
    p.write_text("def broken(\n", encoding="utf-8")
    with pytest.raises(SyntaxError):
        ContextExtractor(dependencies=["x"]).extract_from_file(p)


# ---------------------------------------------------------------------------
# 16. source_code field contains the function text
# ---------------------------------------------------------------------------


def test_source_code_field_contains_function():
    src = """
def fetch(session):
    session.get("/users")
"""
    ctx = first(src, ["session"])
    assert "def fetch" in ctx.source_code
    assert "session.get" in ctx.source_code


# ---------------------------------------------------------------------------
# 17. Untracked dependency in same function is ignored
# ---------------------------------------------------------------------------


def test_untracked_dependency_ignored():
    src = """
def fn(session, logger):
    logger.info("start")
    session.get("/")
"""
    ctx = first(src, ["session"])
    dep_names = [d.dependency for d in ctx.dependencies]
    assert "session" in dep_names
    assert "logger" not in dep_names


# ---------------------------------------------------------------------------
# 18. Async function is extracted
# ---------------------------------------------------------------------------


def test_async_function_extracted():
    src = """
async def fetch(session):
    response = await session.get("/data")
    return response.json()
"""
    contexts = extract(src, ["session"])
    assert any(c.function_name == "fetch" for c in contexts)


# ---------------------------------------------------------------------------
# 19. Empty function body
# ---------------------------------------------------------------------------


def test_empty_function_body():
    src = """
def fn(session):
    pass
"""
    results = extract(src, ["session"])
    assert results == []
