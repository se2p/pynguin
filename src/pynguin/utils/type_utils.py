#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides utilities when working with types."""

from __future__ import annotations

import ast
import contextlib
import copy
import enum
import functools
import inspect
import numbers
import pickle  # noqa: S403
import sys
import textwrap
import types
import typing
import weakref
from inspect import isclass
from typing import Any

import libcst as cst

if sys.version_info >= (3, 14):
    import annotationlib

import pynguin.configuration as config
from pynguin.utils.naming import get_module_alias
from pynguin.utils.orderedset import OrderedSet

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from pynguin.analyses.typesystem import InferredSignature

PRIMITIVES = OrderedSet([int, str, bytes, bool, float, complex])
COLLECTIONS = OrderedSet([list, set, tuple, dict])
IGNORABLE_TYPES = OrderedSet(["builtins.generator", "builtins.async_generator"])


def is_primitive_type(typ: type | None) -> bool:
    """Check if the given type is a primitive.

    Args:
        typ: a given type

    Returns:
        Whether the type is a primitive type
    """
    return typ in PRIMITIVES


def is_collection_type(typ: type | None) -> bool:
    """Check if the given type is a collection type.

    Args:
        typ: a given type

    Returns:
        Whether the type is a collection type
    """
    return typ in COLLECTIONS or typing.get_origin(typ) in COLLECTIONS


def is_ignorable_type(typ: type) -> bool:
    """Check if the given type is ignorable.

    These are types that are exposed as a runtime type, although they are not
    directly usable.  Consider the following example:
    >>> def foo_gen():
    ...     for i in range(10):
    ...         yield i
    ...
    >>> def test_foo():
    ...     gen = foo_gen()
    ...     print(f"{type(gen).__module__}.{type(gen).__name__}")
    ...
    >>> test_foo()
    builtins.generator

    Such a type leads to erroneous behaviour and crashes the assertion generation
    that tracks all seen types.  Thus, we do not track these types as we cannot
    reasonably handle them or generate an assertion for them.

    Args:
        typ: a given type

    Returns:
        Whether the type is ignorable
    """
    return f"{typ.__module__}.{typ.__name__}" in IGNORABLE_TYPES


def is_type_picklable(typ: Any) -> bool:
    """Check if a type can be safely pickled and referenced by name.

    In Python, types and classes are pickled by their global name:
    (module, qualname). If a type is an internal C-extension type (such as
    `_json.Scanner`) or not accessible as an attribute on its defining module,
    it cannot be looked up during pickling or unpickling and cannot be imported
    in generated test cases.

    Args:
        typ: The object or type to check.

    Returns:
        True if the type can be safely pickled by reference, False otherwise.
    """
    try:
        pickle.dumps(typ)
        return True
    except Exception:  # noqa: BLE001
        return False


def is_none_type(typ: type | None) -> bool:
    """Is the given type NoneType?

    Args:
        typ: a type to check

    Returns:
        Whether or not the given type is NoneType
    """
    return typ is type(None)


def is_numeric(value: Any) -> bool:
    """Check if the given value is numeric.

    Args:
        value: an arbitrary value

    Returns:
        Whether or not the given value is numeric
    """
    return isinstance(value, numbers.Number)


def is_string(value: Any) -> bool:
    """Check if the given value is a string.

    Args:
        value: an arbitrary value

    Returns:
        Whether or not the given value is a string
    """
    return isinstance(value, str)


def is_bytes(value: Any) -> bool:
    """Check if the given value is a bytes or bytearray.

    Args:
        value: an arbitrary value

    Returns:
        Whether or not the given value is of type bytes or bytearray
    """
    return isinstance(value, bytes | bytearray)


def is_list(typ: type) -> bool:
    """Check if the given value is a list.

    Args:
        typ: a type

    Returns:
        Whether the given value is of type list.
    """
    return typ is list


def is_set(typ: type) -> bool:
    """Check if the given value is a set.

    Args:
        typ: a type

    Returns:
        Whether the given value is of type set.
    """
    return typ is set


def is_dict(typ: type) -> bool:
    """Check if the given value is a dict.

    Args:
        typ: a type

    Returns:
        Whether the given value is of type dict.
    """
    return typ is dict


def is_tuple(typ: type) -> bool:
    """Check if the given value is a tuple.

    Args:
        typ: a type

    Returns:
        Whether the given value is of type tuple.
    """
    return typ is tuple


def is_enum(value: Any) -> bool:
    """Check if the given value is an enum.

    Args:
        value: an arbitrary value

    Returns:
        Whether the given value is of type enum.
    """
    return issubclass(value, enum.Enum)


def _build_eval_namespace(namespace: dict[str, Any] | None) -> dict[str, Any]:
    eval_ns: dict[str, Any] = {"__builtins__": __builtins__}
    mod_name = config.configuration.module_name
    alias = get_module_alias(mod_name) if mod_name else None

    if namespace is not None:
        eval_ns.update({k: v for k, v in namespace.items() if not k.startswith("_")})
        if alias and alias in namespace:
            eval_ns[alias] = namespace[alias]
        return eval_ns

    if not mod_name or mod_name not in sys.modules:
        return eval_ns

    mod = sys.modules[mod_name]
    if alias:
        eval_ns[alias] = mod
    for name in dir(mod):
        if not name.startswith("_") and name != alias:
            with contextlib.suppress(Exception):
                eval_ns[name] = getattr(mod, name)
    return eval_ns


def is_repr_assertable(obj: Any, namespace: dict[str, Any] | None = None) -> bool:
    """Check whether an object can be asserted on by recreating it from its __repr__.

    An object fulfills the __repr__ contract if:
    1. It implements a custom __repr__ (not inherited from object.__repr__).
    2. It implements a custom __eq__ (not inherited from object.__eq__).
    3. Its repr() produces a valid Python expression parseable by libcst.
    4. The object can be copied with copy.deepcopy.
    5. Evaluating repr() in the given namespace (or test export namespace) recreates
       an object of the same type that compares equal to the original object.

    Args:
        obj: The object to check.
        namespace: Optional execution namespace.

    Returns:
        True if the object can be asserted on via its repr.
    """
    tp_ = type(obj)
    if tp_.__repr__ is object.__repr__ or tp_.__eq__ is object.__eq__:
        return False

    try:
        repr_str = repr(obj)
    except Exception:  # noqa: BLE001
        return False

    if not repr_str.strip() or (repr_str.startswith("<") and repr_str.endswith(">")):
        return False

    try:
        cst.parse_expression(repr_str)
    except Exception:  # noqa: BLE001
        return False

    try:
        copy.deepcopy(obj)
    except Exception:  # noqa: BLE001
        return False

    eval_ns = _build_eval_namespace(namespace)
    try:
        recreated = eval(repr_str, eval_ns)  # noqa: S307
    except Exception:  # noqa: BLE001
        return False

    try:
        if type(recreated) is not tp_:
            return False
        if not (recreated == obj and obj == recreated):
            return False
    except Exception:  # noqa: BLE001
        return False

    return True


def is_assertable(
    obj: Any,
    recursion_depth: int = 0,
) -> bool:
    """Returns whether we can generate an assertion using an exact comparison value.

    Primitives (except float) are assertable.
    Enum values are assertable.
    List, sets, dicts and tuples composed only of assertable objects are also
    assertable.

    Objects that are accepted by this function must be constructable in
    `pynguin.assertion.assertion_to_ast._value_to_cst`

    Args:
        obj: The object to check for assertability.
        recursion_depth: Avoid endless recursion for nested structures.

    Returns:
        True, if we can assert on the given value.
    """
    if recursion_depth > 4:
        # Object is possibly nested to deep to make a sensible assertion on.
        return False
    if isinstance(obj, float):
        # Creating exact assertions on float values is usually not desirable.
        return False

    tp_ = type(obj)
    if is_enum(tp_) or is_primitive_type(tp_) or is_none_type(tp_):
        return True
    if is_set(tp_) or is_list(tp_) or is_tuple(tp_):
        return all(is_assertable(elem, recursion_depth + 1) for elem in obj)
    if is_dict(tp_):
        return all(
            is_assertable(key, recursion_depth + 1) and is_assertable(value, recursion_depth + 1)
            for key, value in obj.items()
        )
    return False


def get_class_that_defined_method(method: object) -> object | None:
    """Retrieves the class that defines a method.

    Taken from https://stackoverflow.com/a/25959545/4293396

    Args:
        method: The method

    Returns:
        The class that defines the method
    """
    with contextlib.suppress(Exception):
        method = inspect.unwrap(method)  # type: ignore[arg-type]
    if inspect.ismethod(method):
        assert isinstance(method, types.MethodType)
        for cls in inspect.getmro(method.__self__.__class__):
            if cls.__dict__.get(method.__name__) is method:
                return cls
        method = method.__func__  # fallback to __qualname__ parsing
    if inspect.isfunction(method):
        assert isinstance(method, types.FunctionType)
        module = inspect.getmodule(method)
        attribute_name = method.__qualname__.split(".<locals>", 1)[0].rsplit(".", 1)[0]
        target_cls: Any = module
        for part in attribute_name.split("."):
            target_cls = getattr(target_cls, part, None)
            if target_cls is None:
                break
        if isinstance(target_cls, type):
            return target_cls
    return getattr(method, "__objclass__", None)  # handle special descriptor objs


def get_method_for_signature(method: Callable) -> Callable:
    """Get the object of the given method if it is a non-Python __init__ method.

    inspect.signature(object.__init__) returns <Signature (self, /, *args, **kwargs)>.
    Thus, Pynguin will later try to create object with an *args parameter, which results
    in a failing test. The object itself returns the correct signature <Signature ()>
    (inspect.signature(object)). Thus we replace the method with the object if it is a
    non-Python __init__ method.

    When the class of the given method or a parent class does not define a __init__
    method, the object.__init__ method is used as fallback.

    Args:
         method: The method to check.

    Returns:
        The original method if it is not a non-Python __init__ method, otherwise the
        object of the __init__ method.
    """
    method_for_signature = method
    if method_for_signature.__name__.startswith("__init__"):
        clazz = get_class_that_defined_method(method_for_signature)
        is_python = True
        try:
            # Source is available => likely pure Python.
            inspect.getsource(method_for_signature)
        except Exception:  # noqa: BLE001
            # No source => likely compiled or builtin.
            is_python = False
        if not is_python:
            method_for_signature = clazz  # type: ignore[assignment]
    return method_for_signature


if sys.version_info >= (3, 14):
    # The source of each annotation and whether it failed, and whether inspect.signature
    # failed, per function. The entries only hold strings, so they are freed with the
    # function, e.g., when the SUT is reloaded, and leave the SUT's functions untouched.
    # Only plain functions are keys, which are hashed and compared by identity, so
    # looking them up runs no code of the SUT.
    _ANNOTATIONS = "annotations"
    _SIGNATURE_FAILED = "signature_failed"
    _CACHE: weakref.WeakKeyDictionary[types.FunctionType, dict[str, Any]] = (
        weakref.WeakKeyDictionary()
    )

    def _cached(func: types.FunctionType, key: str) -> Any:
        # An entry only belongs to the code it was stored with, as __code__ can be
        # replaced.
        entry = _CACHE.get(func, {}).get(key)
        if entry is not None and entry[0] is func.__code__:
            return entry[1]
        return None

    def _cache(func: types.FunctionType, key: str, value: Any) -> None:
        _CACHE.setdefault(func, {})[key] = (func.__code__, value)

    def _annotation_sources(func: Any) -> dict[str, str]:
        sources: dict[str, str] | None = None
        with contextlib.suppress(Exception):
            sources = annotationlib.get_annotations(func, format=annotationlib.Format.STRING)
        if sources is not None:
            # Format.STRING drops the quotes of a quoted annotation, such as "int", which
            # Format.FORWARDREF keeps as a string.
            with contextlib.suppress(Exception):
                values = annotationlib.get_annotations(func, format=annotationlib.Format.FORWARDREF)
                return {
                    name: repr(values[name]) if isinstance(values.get(name), str) else source
                    for name, source in sources.items()
                }
        # Format.STRING still evaluates operations on literals, such as "int" | None, so
        # read the annotations from the source code instead.
        from_code = _annotation_sources_from_code(func)
        if from_code is not None and (sources is None or from_code.keys() == sources.keys()):
            return from_code
        return sources or {}

    def _annotation_sources_from_code(obj: Any) -> dict[str, str] | None:
        if not inspect.isfunction(obj) and not inspect.isclass(obj):
            return None
        try:
            tree = ast.parse(textwrap.dedent(inspect.getsource(obj)))
        except (OSError, TypeError, SyntaxError):
            return None
        # The source only covers the object, so its first definition is the object,
        # whatever its __name__ is.
        if inspect.isclass(obj):
            class_node = next(
                (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)), None
            )
            if class_node is None:
                return None
            return {
                statement.target.id: ast.unparse(statement.annotation)
                for statement in class_node.body
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
            }
        node = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            ),
            None,
        )
        if node is None:
            return None
        args = node.args
        parameters = [*args.posonlyargs, *args.args, *args.kwonlyargs]
        parameters.extend(arg for arg in (args.vararg, args.kwarg) if arg is not None)
        sources = {
            parameter.arg: ast.unparse(parameter.annotation)
            for parameter in parameters
            if parameter.annotation is not None
        }
        if node.returns is not None:
            sources["return"] = ast.unparse(node.returns)
        return sources

    def _annotation_scope(func: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        # Like get_type_hints, take the globals of the function wrapped by decorators,
        # as a wrapper from functools.wraps has the globals of the decorator's module.
        try:
            unwrapped = inspect.unwrap(func)
        except ValueError:
            unwrapped = func
        globals_ = getattr(unwrapped, "__globals__", None)
        if globals_ is None:
            module = sys.modules.get(getattr(func, "__module__", None) or "")
            globals_ = vars(module) if module is not None else {}
        # The annotations of a method or a nested function can also use names from the
        # class body or the enclosing functions, which their annotate function holds.
        locals_: dict[str, Any] = {}
        class_dict: Any = {}
        annotate = getattr(func, "__annotate__", None)
        code = getattr(annotate, "__code__", None)
        closure = getattr(annotate, "__closure__", None) or ()
        if code is not None:
            for name, cell in zip(code.co_freevars, closure, strict=False):
                try:
                    value = cell.cell_contents
                except ValueError:
                    continue
                if name == "__classdict__":
                    class_dict = value
                else:
                    locals_[name] = value
        with contextlib.suppress(TypeError, ValueError):
            locals_.update(class_dict)
        return globals_, locals_

    def _evaluate_annotation(
        source: str, globals_: dict[str, Any], locals_: dict[str, Any], *, eval_str: bool
    ) -> Any:
        try:
            value = eval(source, globals_, locals_)  # noqa: S307
        except Exception:  # noqa: BLE001
            return annotationlib.ForwardRef(source)
        # A quoted annotation, such as "int", which is read as is from the source code.
        # Like inspect.signature, only evaluate it with eval_str.
        if not isinstance(value, str) or not eval_str:
            return value
        try:
            return eval(value, globals_, locals_)  # noqa: S307
        except Exception:  # noqa: BLE001
            return annotationlib.ForwardRef(value)

    def get_annotations_one_by_one(obj: Any, *, eval_str: bool = True) -> dict[str, Any]:
        """Evaluate each annotation of an object on its own.

        On Python 3.14, annotations are deferred (PEP 649) and evaluated all at once, so
        a single annotation that cannot be evaluated, e.g., a type imported only for type
        checking or ``"int" | None``, makes all of them unavailable. Here, such an
        annotation becomes a forward reference to its source text, while the others are
        evaluated as usual, in the same scope as the annotations themselves. The forward
        references have no owner, so they neither show memory addresses nor prevent
        copying. Which annotations fail is cached per function, so they are evaluated
        once, and each call returns new forward references, as evaluating one, e.g., by
        get_type_hints, stores code on it, which cannot be pickled.

        Args:
            obj: The object whose annotations are evaluated.
            eval_str: Whether to evaluate quoted annotations, see inspect.signature.

        Returns:
            The annotations of the object.
        """
        func = getattr(obj, "__func__", obj)
        is_function = inspect.isfunction(func)
        globals_, locals_ = _annotation_scope(func)
        if is_function and (cached := _cached(func, _ANNOTATIONS)) is not None:
            return {
                name: _evaluate_annotation(source, globals_, locals_, eval_str=eval_str)
                if evaluates
                else annotationlib.ForwardRef(source)
                for name, (source, evaluates) in cached.items()
            }
        sources = _annotation_sources(func)
        annotations = {
            name: _evaluate_annotation(source, globals_, locals_, eval_str=eval_str)
            for name, source in sources.items()
        }
        if is_function:
            # Only an annotation whose source fails is not evaluated again.
            _cache(
                func,
                _ANNOTATIONS,
                {
                    name: (
                        source,
                        not (
                            isinstance(annotations[name], annotationlib.ForwardRef)
                            and annotations[name].__forward_arg__ == source
                        ),
                    )
                    for name, source in sources.items()
                },
            )
        return annotations

    def with_annotations_one_by_one(obj: Any, *, eval_str: bool = True) -> Any:
        """Build a stand-in for obj whose signature does not evaluate annotations.

        Args:
            obj: A function, method, class, functools.partial or callable instance
                whose signature failed.
            eval_str: Whether to evaluate quoted annotations, see inspect.signature.

        Returns:
            A stand-in with the same signature as obj, but annotations evaluated one by
            one, or None if obj is not supported.
        """
        if isinstance(obj, types.MethodType):
            func = with_annotations_one_by_one(obj.__func__, eval_str=eval_str)
            return None if func is None else types.MethodType(func, obj.__self__)
        if inspect.isclass(obj):
            return _class_with_annotations_one_by_one(obj, eval_str=eval_str)
        if isinstance(obj, functools.partial):
            func = with_annotations_one_by_one(obj.func, eval_str=eval_str)
            return None if func is None else functools.partial(func, *obj.args, **obj.keywords)
        if (call := _instance_call(obj)) is not None:
            return with_annotations_one_by_one(types.MethodType(call, obj), eval_str=eval_str)
        func = _unwrapped_function(obj)
        if func is None:
            return None
        stand_in = types.FunctionType(
            func.__code__, func.__globals__, func.__name__, func.__defaults__, func.__closure__
        )
        stand_in.__kwdefaults__ = func.__kwdefaults__
        stand_in.__qualname__ = func.__qualname__
        stand_in.__annotations__ = get_annotations_one_by_one(func, eval_str=eval_str)
        return stand_in

    def _instance_call(obj: Any) -> types.FunctionType | None:
        # The __call__ method of a callable instance, which inspect.signature uses.
        if inspect.isroutine(obj) or isinstance(obj, type):
            return None
        call = inspect.getattr_static(type(obj), "__call__", None)
        return call if inspect.isfunction(call) else None

    def _unwrapped_function(obj: Any) -> types.FunctionType | None:
        if not inspect.isfunction(obj):
            return None
        # Like inspect.signature, follow functions wrapped by decorators.
        func = inspect.unwrap(obj, stop=lambda f: hasattr(f, "__signature__"))
        return func if inspect.isfunction(func) else None

    def _constructor(cls: type) -> tuple[str, Any] | None:
        # Mirrors how inspect.signature picks the constructor of a class.
        for metaclass in inspect.getmro(type(cls)):
            if metaclass not in {type, object} and "__call__" in vars(metaclass):
                return None
        for base in cls.__mro__:
            if base is object:
                break
            for name in ("__new__", "__init__"):
                if name in vars(base):
                    method = vars(base)[name]
                    return name, getattr(method, "__func__", method)
        return None

    def _class_with_annotations_one_by_one(cls: type, *, eval_str: bool) -> type | None:
        constructor = _constructor(cls)
        if constructor is None:
            return None
        name, method = constructor
        stand_in = with_annotations_one_by_one(method, eval_str=eval_str)
        if stand_in is None:
            return None
        if name == "__new__":
            stand_in = staticmethod(stand_in)
        return type(cls.__name__, (), {name: stand_in})

    def _signature_function(obj: Any) -> types.FunctionType | None:
        # The function whose annotations inspect.signature evaluates for obj.
        with contextlib.suppress(Exception):
            if isinstance(obj, types.MethodType):
                return _signature_function(obj.__func__)
            if inspect.isclass(obj):
                constructor = _constructor(obj)
                return None if constructor is None else _signature_function(constructor[1])
            if isinstance(obj, functools.partial):
                return _signature_function(obj.func)
            if (call := _instance_call(obj)) is not None:
                return _signature_function(call)
            return _unwrapped_function(obj)
        return None

    def _get_signature_tolerantly(obj: Callable, *, eval_str: bool) -> inspect.Signature:
        func = _signature_function(obj)
        # With eval_str, string annotations are evaluated too, so the signature can fail
        # for one value of eval_str and work for the other.
        failed_key = f"{_SIGNATURE_FAILED}_{eval_str}"
        if func is not None and _cached(func, failed_key):
            # Avoid evaluating the annotations again, which fails the same way.
            with contextlib.suppress(Exception):
                return inspect.signature(
                    with_annotations_one_by_one(obj, eval_str=eval_str), eval_str=eval_str
                )
        try:
            return inspect.signature(obj, eval_str=eval_str)
        except Exception as error:
            stand_in = with_annotations_one_by_one(obj, eval_str=eval_str)
            signature = None
            if stand_in is not None:
                with contextlib.suppress(Exception):
                    signature = inspect.signature(stand_in, eval_str=eval_str)
            if signature is None:
                if isinstance(error, TypeError | ValueError):
                    raise
                # An annotation that cannot be evaluated, e.g., of a functools.partial.
                raise ValueError(f"Cannot get the signature of {obj!r}: {error!r}") from error
            if func is not None:
                _cache(func, failed_key, value=True)
            return signature


def get_signature(obj: Callable, *, eval_str: bool = False) -> inspect.Signature:
    """Get the signature of a callable, even if its annotations cannot be evaluated.

    On Python 3.14, annotations are deferred (PEP 649) and only evaluated when the
    signature is requested. If this fails for a function, method or class, each
    annotation is evaluated on its own, see get_annotations_one_by_one.
    annotation_format=Format.FORWARDREF of inspect.signature is no replacement: it
    still fails on operations on literals, such as "int" | None, and its forward
    references hold their module, so the signature can be neither copied nor pickled.

    Args:
        obj: The callable to inspect.
        eval_str: Whether to evaluate string annotations, see inspect.signature.

    Returns:
        The signature of the callable.

    Raises:
        ValueError: If no signature can be provided.
        TypeError: If the object is not supported by inspect.signature.
    """
    if sys.version_info >= (3, 14):
        return _get_signature_tolerantly(obj, eval_str=eval_str)
    return inspect.signature(obj, eval_str=eval_str)


def is_optional_parameter(inf_sig: InferredSignature, parameter_name: str) -> bool:
    """Returns, whether a parameter is optional.

    There are some parameter types (*args, **kwargs, parameters with default) that
    are optional.

    This is a simple utility method to check if the given parameter is optional.

    Args:
        inf_sig: the inferred signature
        parameter_name: the name of the parameter

    Returns:
        Whether or not this parameter is optional.
    """
    parameter: inspect.Parameter = inf_sig.signature.parameters[parameter_name]
    # parameter.kind might not be hashable
    return (
        parameter.kind == inspect.Parameter.VAR_POSITIONAL  # noqa: PLR1714
        or parameter.kind == inspect.Parameter.VAR_KEYWORD
        or parameter.default is not inspect.Parameter.empty
    )


def is_arg_or_kwarg(inf_sig: InferredSignature, parameter_name: str) -> bool:
    """Returns, whether a parameter is *args or **kwarg.

    Args:
        inf_sig: the inferred signature
        parameter_name: the name of the parameter

    Returns:
        Whether this parameter is *arg or **kwarg.
    """
    parameter: inspect.Parameter = inf_sig.signature.parameters[parameter_name]
    # parameter.kind might not be hashable
    return (
        parameter.kind == inspect.Parameter.VAR_POSITIONAL  # noqa: PLR1714
        or parameter.kind == inspect.Parameter.VAR_KEYWORD
    )


def given_exception_matches(err, exc) -> bool:
    """Returns whether a raised exception matches an exception class.

    This is a naive approach to figure out if an exception matches, similar to
    what CPython does here:
    https://github.com/python/cpython/blob/ae3c66acb89a6104fcd0eea760f80a0287327cc4/Python/errors.c#L231.

    Args:
        err: The raised exception
        exc: The matching exception class

    Returns:
        True, iff the exception matches.
    """
    if err is None or exc is None:
        return False
    if not isclass(err):
        err = type(err)
    return issubclass(err, exc)


def string_distance(string1: str, string2: str) -> float:
    """Returns the distance between two strings.

    Unlike the Levenshtein distance, this calculates not just the
    number of edits, but the character distance for left aligned strings.
    Since we count each missing character as distance 1, character distances
    are normalised in [0,1].
    """
    if string1 == string2:
        return 0.0

    min_length = min(len(string1), len(string2))
    max_length = max(len(string1), len(string2))
    differences: float = max_length - min_length

    for pos in range(min_length):
        if string1[pos] != string2[pos]:
            difference = abs(ord(string1[pos]) - ord(string2[pos]))
            differences += difference / (difference + 1.0)

    return differences


def string_lt_distance(string1: str, string2: str) -> int:
    """Returns the strict ordered distance between two strings."""
    if string1 < string2:
        return 0

    min_length = min(len(string1), len(string2))

    for pos in range(min_length):
        if string1[pos] > string2[pos]:
            return ord(string1[pos]) - ord(string2[pos]) + 1

    return 1


def string_le_distance(string1: str, string2: str) -> int:
    """Returns the ordered distance between two strings."""
    if string1 <= string2:
        return 0

    min_length = min(len(string1), len(string2))

    for pos in range(min_length):
        if string1[pos] > string2[pos]:
            return ord(string1[pos]) - ord(string2[pos])

    return 1
