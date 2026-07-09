#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the libcst-based assertion trace/verification observers.

The old ``ExecutionContext``-based observers were rewritten for the libcst
representation:

* :class:`RemoteAssertionTraceObserver` observes the per-statement execution.
  ``after_statement_execution`` receives the executed ``tc.Statement``, the
  shared execution ``namespace`` (a plain ``dict``) and the exception raised by
  that statement (or ``None``).  For exception-free statements that bind a
  variable it delegates to ``_handle`` which fills an ``AssertionTrace``.
* :class:`RemoteAssertionVerificationObserver` re-checks assertions by rendering
  them to source and executing them against the namespace, and validates
  exception-only statements directly against the captured exception.
"""

from __future__ import annotations

import types
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertiontraceobserver as ato
import pynguin.configuration as config
import pynguin.testcase.testcase as tc
from pynguin.utils.naming import get_module_alias
from tests.testcase import _builders as b

# --- helper objects -----------------------------------------------------------


class _Custom:
    """A non-assertable object defined in a non-builtins module."""


class _SizedCustom:
    """A non-assertable Sized object."""

    def __len__(self) -> int:
        return 7


class _SizedRaising:
    """A non-assertable Sized object whose ``__len__`` raises."""

    def __len__(self) -> int:
        raise RuntimeError("no length")


def _assertions_at(observer: ato.RemoteAssertionTraceObserver, position: int) -> list:
    return list(observer.get_trace().trace.get(position, []))


# --- RemoteAssertionTraceObserver: bookkeeping --------------------------------


def test_get_trace_clones():
    observer = ato.RemoteAssertionTraceObserver()
    with mock.patch.object(observer._assertion_local_state, "trace") as trace_mock:
        clone = object()
        trace_mock.clone.return_value = clone
        cloned = observer.get_trace()
        trace_mock.clone.assert_called_once()
        assert cloned is clone


def test_after_test_case_execution_sets_trace():
    observer = ato.RemoteAssertionTraceObserver()
    result = MagicMock()
    with mock.patch.object(observer._assertion_local_state, "trace") as trace_mock:
        clone = object()
        trace_mock.clone.return_value = clone
        observer.after_test_case_execution(MagicMock(), MagicMock(), result)
        assert result.assertion_trace is clone


def test_before_test_case_execution_noop():
    observer = ato.RemoteAssertionTraceObserver()
    # Should not raise and should not record anything.
    observer.before_test_case_execution(MagicMock())


# --- RemoteAssertionTraceObserver: after_statement_execution ------------------


def test_exception_records_exception_assertion():
    observer = ato.RemoteAssertionTraceObserver()
    statement = b.assign("var_0", "0", bound_type=int)
    observer.after_statement_execution(statement, None, {"var_0": 0}, ValueError("boom"))

    recorded = _assertions_at(observer, 0)
    assert len(recorded) == 1
    assert recorded[0] == ass.ExceptionAssertion(
        module="builtins", exception_type_name="ValueError"
    )


def test_no_bound_variable_records_nothing():
    observer = ato.RemoteAssertionTraceObserver()
    statement = b.stmt("print('x')")  # no bound_variable
    observer.after_statement_execution(statement, None, {}, None)
    assert _assertions_at(observer, 0) == []


def test_position_increments_between_statements():
    observer = ato.RemoteAssertionTraceObserver()
    observer.after_statement_execution(b.assign("a", "1", bound_type=int), None, {"a": 1}, None)
    observer.after_statement_execution(b.assign("b", "2", bound_type=int), None, {"b": 2}, None)
    assert isinstance(_assertions_at(observer, 0)[0], ass.ObjectAssertion)
    assert isinstance(_assertions_at(observer, 1)[0], ass.ObjectAssertion)


@pytest.mark.parametrize(
    "value, expected_type, check",
    [
        (46, ass.ObjectAssertion, lambda a: a.object == 46),
        ("hello", ass.ObjectAssertion, lambda a: a.object == "hello"),
        (True, ass.ObjectAssertion, lambda a: a.object is True),
        (1.5, ass.FloatAssertion, lambda a: a.value == 1.5),
    ],
)
def test_primitive_value_records_expected_assertion(value, expected_type, check):
    observer = ato.RemoteAssertionTraceObserver()
    statement = b.assign("var_0", repr(value), bound_type=type(value))
    observer.after_statement_execution(statement, None, {"var_0": value}, None)

    recorded = _assertions_at(observer, 0)
    assert len(recorded) == 1
    assert isinstance(recorded[0], expected_type)
    assert recorded[0].source == "var_0"
    assert check(recorded[0])


def test_assertable_collection_records_object_assertion():
    observer = ato.RemoteAssertionTraceObserver()
    # A list is assertable but is not a primitive and lives in ``builtins``,
    # so it is neither watched nor checked -> no assertion recorded.
    statement = b.assign("var_0", "[1, 2, 3]", bound_type=list)
    observer.after_statement_execution(statement, None, {"var_0": [1, 2, 3]}, None)
    assert _assertions_at(observer, 0) == []


def test_non_builtins_object_records_type_name_assertion():
    observer = ato.RemoteAssertionTraceObserver()
    value = _Custom()
    statement = b.assign("var_0", "object()", bound_type=_Custom)
    observer.after_statement_execution(statement, None, {"var_0": value}, None)

    recorded = _assertions_at(observer, 0)
    assert len(recorded) == 1
    assert isinstance(recorded[0], ass.TypeNameAssertion)
    assert recorded[0].source == "var_0"
    assert recorded[0].qualname == "_Custom"


def test_non_builtins_object_records_isinstance_when_importable():
    observer = ato.RemoteAssertionTraceObserver()
    # Make the object's module the SUT module so isinstance is considered safe.
    config.configuration.module_name = _Custom.__module__
    value = _Custom()
    statement = b.assign("var_0", "object()", bound_type=_Custom)
    observer.after_statement_execution(statement, None, {"var_0": value}, None)

    recorded = _assertions_at(observer, 0)
    assert len(recorded) == 1
    assert isinstance(recorded[0], ass.IsInstanceAssertion)
    assert recorded[0].qualname == "_Custom"


def test_sized_non_assertable_object_records_type_and_length():
    observer = ato.RemoteAssertionTraceObserver()
    value = _SizedCustom()
    statement = b.assign("var_0", "object()", bound_type=_SizedCustom)
    observer.after_statement_execution(statement, None, {"var_0": value}, None)

    recorded = _assertions_at(observer, 0)
    types = {type(a) for a in recorded}
    assert ass.TypeNameAssertion in types
    assert ass.CollectionLengthAssertion in types
    length_assertion = next(a for a in recorded if isinstance(a, ass.CollectionLengthAssertion))
    assert length_assertion.length == 7


def test_sized_object_with_failing_len_is_swallowed():
    observer = ato.RemoteAssertionTraceObserver()
    value = _SizedRaising()
    statement = b.assign("var_0", "object()", bound_type=_SizedRaising)
    observer.after_statement_execution(statement, None, {"var_0": value}, None)

    recorded = _assertions_at(observer, 0)
    # The type-name assertion is still recorded, but no length assertion, as
    # ``len()`` raised and the reference is given up on.
    assert any(isinstance(a, ass.TypeNameAssertion) for a in recorded)
    assert not any(isinstance(a, ass.CollectionLengthAssertion) for a in recorded)


# --- RemoteAssertionTraceObserver: _is_type_importable ------------------------


def test_is_type_importable_builtins_true():
    assert ato.RemoteAssertionTraceObserver._is_type_importable(int) is True


def test_is_type_importable_without_module_attrs_false():
    # An object lacking ``__module__``/``__qualname__`` is not importable.
    assert ato.RemoteAssertionTraceObserver._is_type_importable(3) is False  # type: ignore[arg-type]


def test_is_type_importable_other_module_false():
    config.configuration.module_name = "some.other.module"
    assert ato.RemoteAssertionTraceObserver._is_type_importable(_Custom) is False


def test_is_type_importable_sut_module_true():
    config.configuration.module_name = _Custom.__module__
    assert ato.RemoteAssertionTraceObserver._is_type_importable(_Custom) is True


# --- RemoteAssertionTraceObserver: _should_ignore -----------------------------


@pytest.mark.parametrize(
    "field, value, expected",
    [
        ("_private", 1, True),
        ("__dunder__", 1, True),
        ("public", lambda: None, True),
        ("submodule", types, True),
        ("public", 42, False),
        ("PUBLIC_CONST", "hello", False),
    ],
)
def test_should_ignore(field, value, expected):
    assert ato.RemoteAssertionTraceObserver._should_ignore(field, value) is expected


# --- RemoteAssertionTraceObserver: _resolve_source -----------------------------


def test_resolve_source_flat_hit():
    value = ato.RemoteAssertionTraceObserver._resolve_source({"var_0": 42}, "var_0")
    assert value == 42


def test_resolve_source_dotted_hit():
    module = types.ModuleType("fake_module")
    module.static_state = 5
    value = ato.RemoteAssertionTraceObserver._resolve_source(
        {"module_": module}, "module_.static_state"
    )
    assert value == 5


def test_resolve_source_missing_root_is_unresolved():
    value = ato.RemoteAssertionTraceObserver._resolve_source({}, "missing")
    assert value is ato._UNRESOLVED


def test_resolve_source_missing_attribute_is_unresolved():
    module = types.ModuleType("fake_module")
    value = ato.RemoteAssertionTraceObserver._resolve_source(
        {"module_": module}, "module_.does_not_exist"
    )
    assert value is ato._UNRESOLVED


def test_resolve_source_raising_descriptor_is_unresolved():
    class _Raising:
        @property
        def boom(self):
            raise RuntimeError("nope")

    value = ato.RemoteAssertionTraceObserver._resolve_source({"obj": _Raising()}, "obj.boom")
    assert value is ato._UNRESOLVED


# --- RemoteAssertionTraceObserver: module static-field assertions -------------


def _make_sut_module(**attrs) -> tuple[types.ModuleType, str]:
    module = types.ModuleType("fake_sut_module")
    for name, value in attrs.items():
        setattr(module, name, value)
    config.configuration.module_name = module.__name__
    alias = get_module_alias(module.__name__)
    return module, alias


def test_handle_records_module_field_assertion():
    observer = ato.RemoteAssertionTraceObserver()
    module, alias = _make_sut_module(static_state=0)
    # Module-field enumeration piggybacks on _handle, which only runs for
    # statements that bind a variable (see after_statement_execution); use an
    # unrelated primitive-binding statement to trigger it, like a real
    # SUT-mutating call followed by further statements would.
    namespace = {alias: module, "var_0": 1}

    statement = b.assign("var_0", "1", bound_type=int)
    observer.after_statement_execution(statement, None, namespace, None)

    recorded = _assertions_at(observer, 0)
    assert ass.ObjectAssertion(f"{alias}.static_state", 0) in recorded


def test_handle_ignores_private_dunder_callable_and_submodule_fields():
    observer = ato.RemoteAssertionTraceObserver()
    module, alias = _make_sut_module(
        _private=1,
        __dunder__=2,
        public_func=lambda: None,
        submodule=types,
        visible=3,
    )
    namespace = {alias: module, "var_0": 1}

    statement = b.assign("var_0", "1", bound_type=int)
    observer.after_statement_execution(statement, None, namespace, None)

    recorded = _assertions_at(observer, 0)
    sources = {a.source for a in recorded if isinstance(a, ass.ReferenceAssertion)}
    assert f"{alias}.visible" in sources
    assert f"{alias}._private" not in sources
    assert f"{alias}.__dunder__" not in sources
    assert f"{alias}.public_func" not in sources
    assert f"{alias}.submodule" not in sources


def test_handle_module_field_rechecked_after_every_statement():
    observer = ato.RemoteAssertionTraceObserver()
    module, alias = _make_sut_module(static_state=0)
    namespace = {alias: module, "var_0": 1, "var_1": 2}

    observer.after_statement_execution(
        b.assign("var_0", "1", bound_type=int), None, namespace, None
    )
    module.static_state = 1
    observer.after_statement_execution(
        b.assign("var_1", "2", bound_type=int), None, namespace, None
    )

    assert ass.ObjectAssertion(f"{alias}.static_state", 0) in _assertions_at(observer, 0)
    assert ass.ObjectAssertion(f"{alias}.static_state", 1) in _assertions_at(observer, 1)


def test_handle_no_sut_module_in_namespace_records_nothing_extra():
    observer = ato.RemoteAssertionTraceObserver()
    config.configuration.module_name = "some.module"
    # Namespace does not contain the module alias at all.
    statement = b.assign("var_0", "1", bound_type=int)
    observer.after_statement_execution(statement, None, {"var_0": 1}, None)

    recorded = _assertions_at(observer, 0)
    assert all(
        not (isinstance(a, ass.ReferenceAssertion) and a.source.startswith("some_module_"))
        for a in recorded
    )


# --- RemoteAssertionVerificationObserver: state -------------------------------


def test_verification_state_getter_and_setter():
    observer = ato.RemoteAssertionVerificationObserver()
    original = observer.state["trace"]
    assert original is not None

    new_trace = object()
    observer.state = {"trace": new_trace}
    assert observer.state["trace"] is new_trace


def test_verification_before_test_case_execution_noop():
    observer = ato.RemoteAssertionVerificationObserver()
    observer.before_test_case_execution(MagicMock())


def test_verification_after_test_case_execution_sets_trace():
    observer = ato.RemoteAssertionVerificationObserver()
    result = MagicMock()
    observer.after_test_case_execution(MagicMock(), MagicMock(), result)
    assert result.assertion_verification_trace is observer._state.trace


# --- RemoteAssertionVerificationObserver: exception-only statements -----------


def _exception_statement() -> tc.Statement:
    statement = b.assign("var_0", "0")
    statement.assertions.append(
        ass.ExceptionAssertion(module="builtins", exception_type_name="ValueError")
    )
    return statement


def test_verification_exception_matches_is_clean():
    observer = ato.RemoteAssertionVerificationObserver()
    observer.after_statement_execution(_exception_statement(), None, {}, ValueError())
    assert observer._state.trace.failed == {}
    assert observer._state.trace.error == {}


def test_verification_exception_missing_marks_failed():
    observer = ato.RemoteAssertionVerificationObserver()
    observer.after_statement_execution(_exception_statement(), None, {}, None)
    assert 0 in observer._state.trace.failed
    assert 0 in observer._state.trace.failed[0]
    assert observer._state.trace.error == {}


def test_verification_exception_wrong_type_marks_error():
    observer = ato.RemoteAssertionVerificationObserver()
    observer.after_statement_execution(_exception_statement(), None, {}, KeyError())
    assert 0 in observer._state.trace.error
    assert 0 in observer._state.trace.error[0]
    assert observer._state.trace.failed == {}


# --- RemoteAssertionVerificationObserver: value assertions --------------------


def _value_statement(*assertions: ass.Assertion) -> tc.Statement:
    statement = b.assign("var_0", "0")
    for assertion in assertions:
        statement.assertions.append(assertion)
    return statement


def test_verification_passing_value_assertion_is_clean():
    observer = ato.RemoteAssertionVerificationObserver()
    statement = _value_statement(ass.ObjectAssertion("var_0", 46))
    observer.after_statement_execution(statement, None, {"var_0": 46}, None)
    assert observer._state.trace.failed == {}
    assert observer._state.trace.error == {}


def test_verification_failing_value_assertion_marks_failed():
    observer = ato.RemoteAssertionVerificationObserver()
    statement = _value_statement(ass.ObjectAssertion("var_0", 46))
    observer.after_statement_execution(statement, None, {"var_0": 99}, None)
    assert 0 in observer._state.trace.failed
    assert 0 in observer._state.trace.failed[0]


def test_verification_erroring_value_assertion_marks_error():
    observer = ato.RemoteAssertionVerificationObserver()
    # len() on an int raises TypeError -> recorded as an error, not a failure.
    statement = _value_statement(ass.CollectionLengthAssertion("var_0", 3))
    observer.after_statement_execution(statement, None, {"var_0": 5}, None)
    assert 0 in observer._state.trace.error
    assert 0 in observer._state.trace.error[0]


def test_verification_float_assertion_uses_pytest_namespace():
    observer = ato.RemoteAssertionVerificationObserver()
    statement = _value_statement(ass.FloatAssertion("var_0", 1.5))
    observer.after_statement_execution(statement, None, {"var_0": 1.5, "pytest": pytest}, None)
    assert observer._state.trace.failed == {}
    assert observer._state.trace.error == {}


def test_verification_skips_exception_assertion_in_mixed_statement():
    observer = ato.RemoteAssertionVerificationObserver()
    # Two assertions -> not "only exception", so the loop runs; the exception
    # assertion renders to None and is skipped, the object assertion passes.
    statement = _value_statement(
        ass.ExceptionAssertion(module="builtins", exception_type_name="ValueError"),
        ass.ObjectAssertion("var_0", 46),
    )
    observer.after_statement_execution(statement, None, {"var_0": 46}, None)
    assert observer._state.trace.failed == {}
    assert observer._state.trace.error == {}
