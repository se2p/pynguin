#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides analyses for a module's type information."""

from __future__ import annotations

import functools
import inspect
import logging
import re
import types
import typing

from abc import ABC
from abc import abstractmethod
from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field
from itertools import starmap
from typing import Any
from typing import Final
from typing import ForwardRef
from typing import Generic
from typing import TypeVar
from typing import _BaseGenericAlias  # type: ignore[attr-defined]  # noqa: PLC2701
from typing import _eval_type  # type: ignore[attr-defined]  # noqa: PLC2701
from typing import cast
from typing import get_origin
from typing import get_type_hints

import networkx as nx

from networkx.drawing.nx_pydot import to_pydot
from typing_inspect import is_union_type

import pynguin.configuration as config
import pynguin.utils.typetracing as tt

from pynguin.utils import randomness
from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.type_utils import COLLECTIONS
from pynguin.utils.type_utils import PRIMITIVES


if typing.TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence
    from typing import ClassVar

    from pynguin.analyses.module import TypeGuessingStats

_LOGGER = logging.getLogger(__name__)


# The following classes are inspired by
# https://github.com/python/mypy/blob/master/mypy/types.py and most likely incomplete.
# The plan is to gradually expand this type representation.


T = TypeVar("T")


class ProperType(ABC):
    """Base class for all types. Might have to add another layer, like mypy's Type?.

    All subclasses of this class are immutable.
    """

    @abstractmethod
    def accept(self, visitor: TypeVisitor[T]) -> T:
        """Accept a type visitor.

        Args:
            visitor: the visitor
        """

    def __str__(self) -> str:
        return self.accept(TypeStringVisitor())

    def __repr__(self) -> str:
        return self.accept(TypeReprVisitor())

    def __lt__(self, other):
        return str(self) < str(other)

    def __eq__(self, other):
        return isinstance(other, self.__class__)

    def __hash__(self):
        return hash(self.__class__)


class AnyType(ProperType):
    """The Any Type."""

    def accept(self, visitor: TypeVisitor[T]) -> T:  # noqa: D102
        return visitor.visit_any_type(self)


class NoneType(ProperType):
    """The None type."""

    def accept(self, visitor: TypeVisitor[T]) -> T:  # noqa: D102
        return visitor.visit_none_type(self)


class Instance(ProperType):
    """An instance type of form C[T1, ..., Tn].

    C is a class.  Args can be empty.
    """

    def __init__(  # noqa: D107
        self, typ: TypeInfo, args: tuple[ProperType, ...] | None = None
    ):
        assert typ.raw_type is not tuple, "Use TupleType instead!"
        self.type = typ
        self.args: Final[tuple[ProperType, ...]] = args or ()
        self._hash: int | None = None

    def accept(self, visitor: TypeVisitor[T]) -> T:  # noqa: D102
        return visitor.visit_instance(self)

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((self.type, self.args))
        return self._hash

    def __eq__(self, other):
        return isinstance(other, Instance) and self.type == other.type and self.args == other.args


class TupleType(ProperType):
    """Tuple type Tuple[T1, ..., Tn].

    Note that tuple is a special case and intentionally not
    `Instance(TypeInfo(tuple))` because tuple is varargs generic.
    """

    def __init__(  # noqa: D107
        self, args: tuple[ProperType, ...], *, unknown_size: bool = False
    ):
        self.args: Final[tuple[ProperType, ...]] = args
        self.unknown_size: Final[bool] = unknown_size
        self._hash: int | None = None

    def accept(self, visitor: TypeVisitor[T]) -> T:  # noqa: D102
        return visitor.visit_tuple_type(self)

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((self.args, self.unknown_size))
        return self._hash


class UnionType(ProperType):
    """The union type Union[T1, ..., Tn] (at least one type argument)."""

    def __init__(self, items: tuple[ProperType, ...]):  # noqa: D107
        self.items: Final[tuple[ProperType, ...]] = items
        assert len(self.items) > 0
        self._hash: int | None = None

    def accept(self, visitor: TypeVisitor[T]) -> T:  # noqa: D102
        return visitor.visit_union_type(self)

    def __hash__(self):
        if self._hash is None:
            self._hash = hash(self.items)
        return self._hash


class Unsupported(ProperType):
    """Marks an unsupported type in the type system.

    Artificial type which represents a type that is currently not supported by
    our type abstraction. This is purely used for statistic purposes and should not
    be encountered during regular use.
    """

    def accept(self, visitor: TypeVisitor[T]) -> T:  # noqa: D102
        return visitor.visit_unsupported_type(self)


# Static to instances to avoid repeated construction.
ANY = AnyType()
NONE_TYPE = NoneType()
UNSUPPORTED = Unsupported()


class TypeVisitor(Generic[T]):
    """A type visitor.

    Note that the parameter of the visit_* methods is called 'left',
    because it makes the implementations of _SubTypeVisitor and _MaybeSubTypeVisitor
    more clear and Python does not like changing the names of parameters in subclasses,
    thus we renamed them in this class.
    """

    @abstractmethod
    def visit_any_type(self, left: AnyType) -> T:
        """Visit the Any type.

        Args:
            left: the Any type

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_none_type(self, left: NoneType) -> T:
        """Visit the None type.

        Args:
            left: the None type

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_instance(self, left: Instance) -> T:
        """Visit an instance.

        Args:
            left: instance

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_tuple_type(self, left: TupleType) -> T:
        """Visit a tuple type.

        Args:
            left: tuple

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_union_type(self, left: UnionType) -> T:
        """Visit a union.

        Args:
            left: union

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_unsupported_type(self, left: Unsupported) -> T:
        """Visit unsupported type.

        Args:
            left: unsupported

        Returns:
            result of the visit
        """


class _PartialTypeMatch(TypeVisitor[ProperType | None]):
    """A type visitor to check for base type matches."""

    def __init__(self, right: ProperType):
        self.right = right

    def visit_any_type(self, left: AnyType) -> ProperType | None:
        return None

    def visit_none_type(self, left: NoneType) -> ProperType | None:
        return NONE_TYPE if isinstance(self.right, NoneType) else None

    def visit_instance(self, left: Instance) -> ProperType | None:
        return Instance(left.type) if isinstance(self.right, Instance) and left.type == self.right.type else None

    def visit_tuple_type(self, left: TupleType) -> ProperType | None:
        return TupleType(()) if isinstance(self.right, TupleType) else None

    def visit_union_type(self, left: UnionType) -> ProperType | None:
        matches = tuple(
            elem for elem in (_is_partial_type_match(left_elem, self.right) for left_elem in left.items) if elem
        )
        return UnionType(matches) if matches else None

    def visit_unsupported_type(self, left: Unsupported) -> ProperType | None:
        return None


def _is_partial_type_match(left: ProperType, right: ProperType) -> ProperType | None:
    """Is left a partial type match of right?

    This is only useful for statistics purposes, i.e., do we have a fuzzy type match?

    Args:
        left: The guessed type
        right: The ground truth

    Returns:
        The partial match, if Any.
    """
    if isinstance(right, UnionType):
        matches = tuple(
            elem for elem in (_is_partial_type_match(left, right_elem) for right_elem in right.items) if elem is not None
        )
        if matches:
            flattened = {match for match in matches if isinstance(match, UnionType) for match in match.items}
            flattened.update(match for match in matches if not isinstance(match, UnionType))
            return UnionType(tuple(sorted(flattened)))
        return None
    return left.accept(_PartialTypeMatch(right))


class TypeStringVisitor(TypeVisitor[str]):
    """A simple visitor to convert a proper type to a string."""

    def visit_any_type(self, left: AnyType) -> str:  # noqa: D102
        return "Any"

    def visit_none_type(self, left: NoneType) -> str:  # noqa: D102
        return "None"

    def visit_instance(self, left: Instance) -> str:  # noqa: D102
        rep = left.type.name if left.type.module == "builtins" else left.type.full_name
        if left.args:
            rep += "[" + self._sequence_str(left.args) + "]"
        return rep

    def visit_tuple_type(self, left: TupleType) -> str:  # noqa: D102
        rep = "tuple"
        if left.args:
            rep += "[" + self._sequence_str(left.args) + "]"
        return rep

    def visit_union_type(self, left: UnionType) -> str:  # noqa: D102
        return self._sequence_str(left.items, sep=" | ") if len(left.items) > 1 else left.items[0].accept(self)

    def _sequence_str(self, typs: Sequence[ProperType], sep=", ") -> str:
        return sep.join(t.accept(self) for t in typs)

    def visit_unsupported_type(self, left: Unsupported) -> str:  # noqa: D102
        return "<?>"


class TypeReprVisitor(TypeVisitor[str]):
    """A simple visitor to create a repr from a proper type."""

    def visit_any_type(self, left: AnyType) -> str:  # noqa: D102
        return "AnyType()"

    def visit_none_type(self, left: NoneType) -> str:  # noqa: D102
        return "NoneType()"

    def visit_instance(self, left: Instance) -> str:  # noqa: D102
        rep = f"Instance({left.type!r}"
        if left.args:
            rep += "(" + self._sequence_str(left.args) + ")"
        return rep + ")"

    def visit_tuple_type(self, left: TupleType) -> str:  # noqa: D102
        return f"TupleType({self._sequence_str(left.args)})"

    def visit_union_type(self, left: UnionType) -> str:  # noqa: D102
        return f"UnionType({self._sequence_str(left.items)})"

    def _sequence_str(self, typs: Sequence[ProperType]) -> str:
        return ", ".join(t.accept(self) for t in typs)

    def visit_unsupported_type(self, left: Unsupported) -> str:  # noqa: D102
        return "Unsupported()"


class _SubtypeVisitor(TypeVisitor[bool]):
    """A visitor to check the subtyping relationship between two types.

    Checks whether left is a subtype of right.

    There is no need to check 'right' for AnyType, as this is done outside.
    """

    def __init__(
        self,
        graph: TypeSystem,
        right: ProperType,
        sub_type_check: Callable[[ProperType, ProperType], bool],
    ):
        """Create new visitor.

        Args:
            graph: The inheritance graph.
            right: The right type.
            sub_type_check: The subtype check to use
        """
        self.graph = graph
        self.right = right
        self.sub_type_check = sub_type_check

    def visit_any_type(self, left: AnyType) -> bool:
        return True

    def visit_none_type(self, left: NoneType) -> bool:
        return isinstance(self.right, NoneType)

    def visit_instance(self, left: Instance) -> bool:
        if isinstance(self.right, Instance):
            if not self.graph.is_subclass(left.type, self.right.type):
                return False
            if (
                left.type.num_hardcoded_generic_parameters
                == self.right.type.num_hardcoded_generic_parameters
                and left.type.num_hardcoded_generic_parameters is not None
            ):
                return all(
                    self.sub_type_check(left_elem, right_elem)
                    and self.sub_type_check(right_elem, left_elem)
                    for left_elem, right_elem in zip(left.args, self.right.args, strict=True)
                )
            return True
        return False

    def visit_tuple_type(self, left: TupleType) -> bool:
        if isinstance(self.right, TupleType):
            if len(left.args) != len(self.right.args):
                return False
            return all(starmap(self.sub_type_check, zip(left.args, self.right.args, strict=True)))
        return False

    def visit_union_type(self, left: UnionType) -> bool:
        return all(self.sub_type_check(left_elem, self.right) for left_elem in left.items)

    def visit_unsupported_type(self, left: Unsupported) -> bool:
        raise NotImplementedError("This type shall not be used during runtime")


class _MaybeSubtypeVisitor(_SubtypeVisitor):
    """A weaker subtype check, which only checks if left may be a subtype of right.

    For example, tuple[str | int | bytes, str | int | bytes] is not a subtype of
    tuple[int, int], but the actual return value may be.
    """

    def visit_union_type(self, left: UnionType) -> bool:
        return any(self.sub_type_check(left_elem, self.right) for left_elem in left.items)


class _CollectionTypeVisitor(TypeVisitor[bool]):
    # No tuple because it is a separate type.
    Collections: ClassVar[set[type]] = {dict, list, set}

    def visit_any_type(self, left: AnyType) -> bool:
        return False

    def visit_none_type(self, left: NoneType) -> bool:
        return False

    def visit_instance(self, left: Instance) -> bool:
        return left.type.raw_type in _CollectionTypeVisitor.Collections

    def visit_tuple_type(self, left: TupleType) -> bool:
        return True

    def visit_union_type(self, left: UnionType) -> bool:
        return False

    def visit_unsupported_type(self, left: Unsupported) -> bool:
        raise NotImplementedError("This type shall not be used during runtime")


is_collection_type = _CollectionTypeVisitor()


class _PrimitiveTypeVisitor(TypeVisitor[bool]):
    Primitives: ClassVar[set[type]] = {int, str, bool, float, complex, bytes, type}

    def visit_any_type(self, left: AnyType) -> bool:
        return False

    def visit_none_type(self, left: NoneType) -> bool:
        return False

    def visit_instance(self, left: Instance) -> bool:
        return left.type.raw_type in _PrimitiveTypeVisitor.Primitives

    def visit_tuple_type(self, left: TupleType) -> bool:
        return False

    def visit_union_type(self, left: UnionType) -> bool:
        return False

    def visit_unsupported_type(self, left: Unsupported) -> bool:
        raise NotImplementedError("This type shall not be used during runtime")


is_primitive_type = _PrimitiveTypeVisitor()


class TypeInfo:
    """A small wrapper around type, i.e., classes.

    Corresponds 1:1 to a class.
    """

    def __init__(self, raw_type: type):
        """Create type info from the given type.

        Don't use this constructor directly (unless for testing purposes), instead ask
        the inheritance graph to give you a type info for the given raw type.

        Naming in python is somehow misleading, 'type' actually only represents classes,
        but not any more complex types.

        Args:
            raw_type: the raw (class) type
        """
        self.raw_type = raw_type
        self.name = raw_type.__name__
        self.qualname = raw_type.__qualname__
        self.module = raw_type.__module__
        self.full_name = TypeInfo.to_full_name(raw_type)
        self.hash = hash(self.full_name)
        self.is_abstract = inspect.isabstract(raw_type)
        self.instance_attributes: OrderedSet[str] = OrderedSet()
        self.attributes: OrderedSet[str] = OrderedSet()
        self.num_hardcoded_generic_parameters: int | None = (
            2 if raw_type is dict else 1 if raw_type in {set, list} else None
        )

    @staticmethod
    def to_full_name(typ: type) -> str:
        """Get the full name of the given type.

        Args:
            typ: The type for which we want a full name.

        Returns:
            The fully qualified name
        """
        return f"{typ.__module__}.{typ.__qualname__}"

    def __eq__(self, other) -> bool:
        return isinstance(other, TypeInfo) and other.full_name == self.full_name

    def __hash__(self):
        return self.hash

    def __repr__(self):
        return f"TypeInfo({self.full_name})"


class NamedDefaultDict(dict[str, tt.UsageTraceNode]):
    """A default dictionary that automatically creates nodes for keys.

    Default dict which automatically creates a UsageTraceNode for each requested
    and non-existing key.
    """

    def __missing__(self, key):
        res = self[key] = tt.UsageTraceNode(key)
        return res


@dataclass(eq=False, repr=False)
class InferredSignature:
    """Encapsulates the types inferred for a method."""

    signature: inspect.Signature
    original_return_type: ProperType
    original_parameters: dict[str, ProperType]
    usage_trace: dict[str, tt.UsageTraceNode] = field(default_factory=NamedDefaultDict, init=False)
    type_system: TypeSystem
    return_type: ProperType = field(init=False)
    current_guessed_parameters: dict[str, list[ProperType]] = field(init=False, default_factory=dict)
    parameters_for_statistics: dict[str, ProperType] = field(default_factory=dict)
    return_type_for_statistics: ProperType = ANY

    def __post_init__(self):
        self.return_type = self.original_return_type

    def __str__(self):
        return str(self.signature)

    def get_parameter_types(
        self, signature_memo: dict[InferredSignature, dict[str, ProperType]]
    ) -> dict[str, ProperType]:
        if (sig := signature_memo.get(self)) is not None:
            return sig
        res: dict[str, ProperType] = {}
        test_conf = config.configuration.test_creation
        for param_name, orig_type in self.original_parameters.items():
            if len(self.usage_trace[param_name]) > 0:
                self._update_guess(
                    param_name,
                    self._guess_parameter_type(
                        self.usage_trace[param_name],
                        self.signature.parameters[param_name].kind,
                    ),
                )

            choices: list[ProperType] = [NONE_TYPE, ANY]
            weights: list[float] = [test_conf.none_weight, test_conf.any_weight]
            if not isinstance(orig_type, AnyType):
                choices.append(orig_type)
                weights.append(test_conf.original_type_weight)

            if (guessed := self.current_guessed_parameters.get(param_name)) is not None:
                choices.append(UnionType(tuple(sorted(guessed))))
                weights.append(test_conf.type_tracing_weight)

            chosen = randomness.choices(choices, weights)[0]

            if (
                randomness.next_float()
                < config.configuration.test_creation.wrap_var_param_type_probability
            ):
                chosen = self.type_system.wrap_var_param_type(
                    chosen,
                    self.signature.parameters[param_name].kind,
                )
            res[param_name] = chosen
        signature_memo[self] = res
        return res

    def _update_guess(self, name: str, guessed: ProperType | None):
        if guessed is None:
            return

        if (old := self.current_guessed_parameters.get(name)) is None:
            self.current_guessed_parameters[name] = [guessed]
        else:
            if guessed in old:
                return
            if len(old) >= config.configuration.test_creation.type_tracing_kept_guesses:
                old.pop(0)
            old.append(guessed)

    def _guess_parameter_type(self, knowledge: tt.UsageTraceNode, kind) -> ProperType | None:
        match kind:
            case inspect.Parameter.VAR_KEYWORD:
                if (get_item_knowledge := knowledge.children.get("__getitem__")) is not None:
                    return self._guess_parameter_type_from(get_item_knowledge)
            case inspect.Parameter.VAR_POSITIONAL:
                if (iter_knowledge := knowledge.children.get("__iter__")) is not None:
                    return self._guess_parameter_type_from(iter_knowledge)
            case _:
                return self._guess_parameter_type_from(knowledge)
        return None

    _ARGUMENT_ATTRIBUTES = OrderedSet([
        "__eq__",
        "__ne__",
        "__lt__",
        "__le__",
        "__gt__",
        "__ge__",
        "__add__",
        "__radd__",
        "__sub__",
        "__rsub__",
        "__truediv__",
        "__rtruediv__",
        "__floordiv__",
        "__rfloordiv__",
    ])

    _LIST_ELEMENT_ATTRIBUTES = OrderedSet(("__iter__", "__getitem__"))
    _DICT_KEY_ATTRIBUTES = OrderedSet(("__iter__",))
    _DICT_VALUE_ATTRIBUTES = OrderedSet(("__getitem__",))
    _SET_ELEMENT_ATTRIBUTES = OrderedSet(("__iter__",))
    _TUPLE_ELEMENT_ATTRIBUTES = OrderedSet(("__iter__", "__getitem__"))

    _LIST_ELEMENT_FROM_ARGUMENT_TYPES = OrderedSet(("__contains__", "__delitem__"))
    _SET_ELEMENT_FROM_ARGUMENT_TYPES = OrderedSet(("__contains__", "__delitem__"))
    _DICT_KEY_FROM_ARGUMENT_TYPES = OrderedSet((
        "__contains__",
        "__delitem__",
        "__getitem__",
        "__setitem__",
    ))
    _DICT_VALUE_FROM_ARGUMENT_TYPES = OrderedSet(("__setitem__",))
    _TUPLE_ELEMENT_FROM_ARGUMENT_TYPES = OrderedSet(("__contains__",))

    _LIST_ELEMENT_FROM_ARGUMENT_TYPES_PATH: OrderedSet[tuple[str, ...]] = OrderedSet([
        ("append", "__call__"),
        ("remove", "__call__"),
    ])
    _SET_ELEMENT_FROM_ARGUMENT_TYPES_PATH: OrderedSet[tuple[str, ...]] = OrderedSet([
        ("add", "__call__"),
        ("remove", "__call__"),
        ("discard", "__call__"),
    ])
    _EMPTY_SET: OrderedSet[tuple[str, ...]] = OrderedSet()

    def _from_type_check(self, knowledge: tt.UsageTraceNode) -> ProperType | None:
        return self._choose_type_or_negate(
            OrderedSet([self.type_system.to_type_info(randomness.choice(knowledge.type_checks))])
        )

    def _from_attr_table(self, knowledge: tt.UsageTraceNode) -> ProperType | None:
        random_attribute = randomness.choice(list(knowledge.children))
        if (
            random_attribute in InferredSignature._ARGUMENT_ATTRIBUTES
            and knowledge.children[random_attribute].arg_types[0]
            and randomness.next_float() < 0.5
        ):
            random_arg_type = randomness.choice(knowledge.children[random_attribute].arg_types[0])
            return self._choose_type_or_negate(
                OrderedSet([self.type_system.to_type_info(random_arg_type)])
            )
        return self._choose_type_or_negate(self.type_system.find_by_attribute(random_attribute))

    def _guess_parameter_type_from(
        self, knowledge: tt.UsageTraceNode, recursion_depth: int = 0
    ) -> ProperType | None:
        guess_from: list[Callable[[tt.UsageTraceNode], ProperType | None]] = []
        if knowledge.type_checks:
            guess_from.append(self._from_type_check)
        if knowledge.children:
            guess_from.append(self._from_attr_table)

        if not guess_from:
            return None

        guessed_type: ProperType | None = randomness.choice(guess_from)(knowledge)

        if recursion_depth <= 1 and guessed_type and guessed_type.accept(is_collection_type):
            guessed_type = self._guess_generic_type_parameters_for_builtins(
                guessed_type, knowledge, recursion_depth
            )
        return guessed_type

    def _guess_generic_type_parameters_for_builtins(
        self,
        guessed_type: ProperType,
        knowledge: tt.UsageTraceNode,
        recursion_depth: int,
    ):
        if isinstance(guessed_type, Instance):
            args = guessed_type.args
            match guessed_type.type.full_name:
                case "builtins.list":
                    guessed_element_type = self._guess_generic_arguments(
                        knowledge,
                        recursion_depth,
                        InferredSignature._LIST_ELEMENT_ATTRIBUTES,
                        InferredSignature._LIST_ELEMENT_FROM_ARGUMENT_TYPES,
                        InferredSignature._LIST_ELEMENT_FROM_ARGUMENT_TYPES_PATH,
                        argument_idx=0,
                    )
                    args = (guessed_element_type or guessed_type.args[0],)
                case "builtins.set":
                    guessed_element_type = self._guess_generic_arguments(
                        knowledge,
                        recursion_depth,
                        InferredSignature._SET_ELEMENT_ATTRIBUTES,
                        InferredSignature._SET_ELEMENT_FROM_ARGUMENT_TYPES,
                        InferredSignature._SET_ELEMENT_FROM_ARGUMENT_TYPES_PATH,
                        argument_idx=0,
                    )
                    args = (guessed_element_type or guessed_type.args[0],)
                case "builtins.dict":
                    guessed_key_type = self._guess_generic_arguments(
                        knowledge,
                        recursion_depth,
                        InferredSignature._DICT_KEY_ATTRIBUTES,
                        InferredSignature._DICT_KEY_FROM_ARGUMENT_TYPES,
                        InferredSignature._EMPTY_SET,
                        argument_idx=0,
                    )
                    guessed_value_type = self._guess_generic_arguments(
                        knowledge,
                        recursion_depth,
                        InferredSignature._DICT_VALUE_ATTRIBUTES,
                        InferredSignature._DICT_VALUE_FROM_ARGUMENT_TYPES,
                        InferredSignature._EMPTY_SET,
                        argument_idx=1,
                    )
                    args = (
                        guessed_key_type or guessed_type.args[0],
                        guessed_value_type or guessed_type.args[1],
                    )
            guessed_type = Instance(guessed_type.type, args)
        elif isinstance(guessed_type, TupleType):
            num_elements = randomness.next_int(
                1, config.configuration.test_creation.collection_size
            )
            elements = []
            for _ in range(num_elements):
                guessed_element_type = self._guess_generic_arguments(
                    knowledge,
                    recursion_depth,
                    InferredSignature._TUPLE_ELEMENT_ATTRIBUTES,
                    InferredSignature._TUPLE_ELEMENT_FROM_ARGUMENT_TYPES,
                    InferredSignature._EMPTY_SET,
                    argument_idx=0,
                )
                elements.append(guessed_element_type or ANY)
            guessed_type = TupleType(tuple(elements))
        return guessed_type

    def _choose_type_or_negate(self, positive_types: OrderedSet[TypeInfo]) -> ProperType | None:
        if not positive_types:
            return None

        if randomness.next_float() < config.configuration.test_creation.negate_type:
            negated_choices = self.type_system.get_type_outside_of(positive_types)
            if negated_choices:
                return self.type_system.make_instance(randomness.choice(negated_choices))
        return self.type_system.make_instance(randomness.choice(positive_types))

    def _guess_generic_arguments(  # noqa: PLR0917
        self,
        knowledge: tt.UsageTraceNode,
        recursion_depth: int,
        element_attributes: OrderedSet[str],
        argument_attributes: OrderedSet[str],
        argument_attribute_paths: OrderedSet[tuple[str, ...]],
        argument_idx: int,
    ) -> ProperType | None:
        guess_from: list[
            Callable[
                [],
                ProperType | None,
            ]
        ] = []

        if elem_attributes := element_attributes.intersection(knowledge.children.keys()):
            guess_from.append(
                functools.partial(
                    self._guess_parameter_type_from,
                    knowledge.children[randomness.choice(elem_attributes)],
                    recursion_depth + 1,
                )
            )
        if arg_attributes := argument_attributes.intersection(knowledge.children.keys()):
            guess_from.append(
                functools.partial(
                    self._guess_from_argument_types,
                    arg_attributes,
                    knowledge,
                    argument_idx,
                )
            )
        if paths := [
            path for path in argument_attribute_paths if knowledge.find_path(path) is not None
        ]:
            guess_from.append(
                functools.partial(self._guess_from_argument_types_from_path, paths, knowledge)
            )
        guess_from.append(lambda: ANY)

        return randomness.choice(guess_from)()

    def _guess_from_argument_types(
        self,
        arg_attrs: OrderedSet[str],
        knowledge: tt.UsageTraceNode,
        arg_idx: int = 0,
    ) -> ProperType | None:
        arg_types = knowledge.children[randomness.choice(arg_attrs)].arg_types[arg_idx]
        if arg_types:
            return self._choose_type_or_negate(
                OrderedSet([self.type_system.to_type_info(randomness.choice(arg_types))])
            )
        return None

    def _guess_from_argument_types_from_path(
        self,
        paths: list[tuple[str, ...]],
        knowledge: tt.UsageTraceNode,
    ) -> ProperType | None:
        path = randomness.choice(paths)
        path_end = knowledge.find_path(path)
        assert path_end is not None
        arg_types = path_end.children[path[-1]].arg_types[0]
        if arg_types:
            return self._choose_type_or_negate(
                OrderedSet([self.type_system.to_type_info(randomness.choice(arg_types))])
            )
        return None

    def log_stats_and_guess_signature(
        self,
        is_constructor: bool,  # noqa: FBT001
        callable_full_name: str,
        stats: TypeGuessingStats,
    ) -> None:
        sig_info = stats.signature_infos[callable_full_name]

        sig_info.annotated_parameter_types = {
            k: str(v) for k, v in self.parameters_for_statistics.items()
        }
        if not is_constructor:
            sig_info.annotated_return_type = str(self.return_type_for_statistics)
        else:
            stats.number_of_constructors += 1

        parameter_types: dict[str, list[str]] = {}
        compute_partial_matches_for: list[tuple[ProperType, ProperType]] = []
        for param_name, param in self.signature.parameters.items():
            if param_name not in self.original_parameters:
                continue

            top_n_guesses: list[ProperType] = []
            if len(self.usage_trace[param_name]) > 0:
                counter: Counter[ProperType] = Counter()
                for _ in range(100):
                    guess = self._guess_parameter_type(
                        self.usage_trace[param_name],
                        param.kind,
                    )
                    if guess is not None:
                        counter[guess] += 1
                for typ, _ in counter.most_common(
                    config.configuration.statistics_output.type_guess_top_n
                ):
                    top_n_guesses.append(typ)

            for item in top_n_guesses:
                compute_partial_matches_for.append(  # noqa: PERF401
                    (item, self.parameters_for_statistics[param_name])
                )
            parameter_types[param_name] = [str(t) for t in top_n_guesses]
        compute_partial_matches_for.append((
            self.return_type,
            self.return_type_for_statistics,
        ))

        self._compute_partial_matches(compute_partial_matches_for, sig_info)

        return_type = str(self.return_type)
        if not is_constructor and self.return_type != self.original_return_type:
            sig_info.recorded_return_type = str(return_type)
        sig_info.guessed_parameter_types = parameter_types

    @staticmethod
    def _compute_partial_matches(compute_partial_matches_for, sig_info):
        for left, right in compute_partial_matches_for:
            if (match := _is_partial_type_match(left, right)) is not None:
                sig_info.partial_type_matches[f"({left!s}, {right!s})"] = str(match)


class TypeSystem:  # noqa: PLR0904
    """Implements Pynguin's internal type system.

    Provides a simple inheritance graph relating various classes using their subclass
    relationships. Note that parents point to their children.

    This is also the central system to store/handle type information.
    """

    def __init__(self):  # noqa: D107
        self._graph = nx.DiGraph()
        self._types: dict[str, TypeInfo] = {}
        self._attribute_map: dict[str, OrderedSet[TypeInfo]] = defaultdict(OrderedSet)
        self.primitive_proper_types = [self.convert_type_hint(prim) for prim in PRIMITIVES]
        self.collection_proper_types = [self.convert_type_hint(coll) for coll in COLLECTIONS]
        numeric = [complex, float, int, bool]
        self.numeric_tower: dict[Instance, list[Instance]] = cast(
            "dict[Instance, list[Instance]]",
            {
                self.convert_type_hint(typ): [self.convert_type_hint(tp) for tp in numeric[idx:]]
                for idx, typ in enumerate(numeric)
            },
        )

    def enable_numeric_tower(self):
        bool_info = self.to_type_info(bool)
        int_info = self.to_type_info(int)
        float_info = self.to_type_info(float)
        complex_info = self.to_type_info(complex)
        self.add_subclass_edge(super_class=int_info, sub_class=bool_info)
        self.add_subclass_edge(super_class=float_info, sub_class=int_info)
        self.add_subclass_edge(super_class=complex_info, sub_class=float_info)

    def add_subclass_edge(self, *, super_class: TypeInfo, sub_class: TypeInfo) -> None:
        self._graph.add_edge(super_class, sub_class)

    @functools.lru_cache(maxsize=1024)
    def get_subclasses(self, klass: TypeInfo) -> OrderedSet[TypeInfo]:
        if klass not in self._graph:
            return OrderedSet([klass])
        result: OrderedSet[TypeInfo] = OrderedSet(nx.descendants(self._graph, klass))
        result.add(klass)
        return result

    @functools.lru_cache(maxsize=1024)
    def get_superclasses(self, klass: TypeInfo) -> OrderedSet[TypeInfo]:
        if klass not in self._graph:
            return OrderedSet([klass])
        result: OrderedSet[TypeInfo] = OrderedSet(nx.ancestors(self._graph, klass))
        result.add(klass)
        return result

    def get_type_outside_of(self, klasses: OrderedSet[TypeInfo]) -> OrderedSet[TypeInfo]:
        results = OrderedSet(self._types.values())
        for info in klasses:
            results.difference_update(self.get_subclasses(info))
        return results

    @functools.lru_cache(maxsize=16384)
    def is_subclass(self, left: TypeInfo, right: TypeInfo) -> bool:
        return nx.has_path(self._graph, right, left)

    @functools.lru_cache(maxsize=16384)
    def is_subtype(self, left: ProperType, right: ProperType) -> bool:
        if isinstance(right, AnyType):
            return True
        if isinstance(right, UnionType) and not isinstance(left, UnionType):
            return any(self.is_subtype(left, right_elem) for right_elem in right.items)
        return left.accept(_SubtypeVisitor(self, right, self.is_subtype))

    @functools.lru_cache(maxsize=16384)
    def is_maybe_subtype(self, left: ProperType, right: ProperType) -> bool:
        if isinstance(right, AnyType):
            return True
        if isinstance(right, UnionType) and not isinstance(left, UnionType):
            return any(self.is_maybe_subtype(left, right_elem) for right_elem in right.items)
        return left.accept(_MaybeSubtypeVisitor(self, right, self.is_maybe_subtype))

    @property
    def dot(self) -> str:
        dot = to_pydot(self._graph)
        return dot.to_string()

    def to_type_info(self, typ: type) -> TypeInfo:
        found = self._types.get(TypeInfo.to_full_name(typ))
        if found is not None:
            return found
        info = TypeInfo(typ)
        self._types[info.full_name] = info
        self._graph.add_node(info)
        return info

    def find_type_info(self, full_name: str) -> TypeInfo | None:
        return self._types.get(full_name)

    def find_by_attribute(self, attr: str) -> OrderedSet[TypeInfo]:
        return self._attribute_map[attr]

    @functools.lru_cache(maxsize=1)
    def get_all_types(self) -> list[TypeInfo]:
        return list(self._types.values())

    def push_attributes_down(self) -> None:
        reach_in_sets: dict[TypeInfo, set[str]] = defaultdict(set)
        reach_out_sets: dict[TypeInfo, set[str]] = defaultdict(set)

        object_info = self.find_type_info("builtins.object")
        assert object_info is not None
        object_info.attributes.difference_update({
            "__lt__",
            "__le__",
            "__gt__",
            "__ge__",
        })

        work_list = list(self._graph.nodes)
        while work_list:
            current = work_list.pop()
            old_val = set(reach_out_sets[current])
            for pred in self._graph.predecessors(current):
                reach_in_sets[current].update(reach_out_sets[pred])
            current.attributes.difference_update(reach_in_sets[current])
            reach_out_sets[current] = set(reach_in_sets[current])
            reach_out_sets[current].update(current.attributes)
            if old_val != reach_out_sets[current]:
                work_list.extend(self._graph.successors(current))
        for type_info in self._graph.nodes:
            for attribute in type_info.attributes:
                self._attribute_map[attribute].add(type_info)

    def wrap_var_param_type(self, typ: ProperType, param_kind) -> ProperType:
        if param_kind == inspect.Parameter.VAR_POSITIONAL:
            return Instance(self.to_type_info(list), (typ,))
        if param_kind == inspect.Parameter.VAR_KEYWORD:
            return Instance(self.to_type_info(dict), (self.convert_type_hint(str), typ))
        return typ

    def infer_type_info(
        self,
        method: Callable,
        type_inference_strategy=config.TypeInferenceStrategy.TYPE_HINTS,
    ) -> InferredSignature:
        match type_inference_strategy:
            case config.TypeInferenceStrategy.TYPE_HINTS:
                return self.infer_signature(method, self.type_hints_provider)
            case config.TypeInferenceStrategy.NONE:
                return self.infer_signature(method, self.no_type_hints_provider)
            case _:
                raise ConfigurationException(
                    f"Unknown type-inference strategy {type_inference_strategy}"
                )

    @staticmethod
    def no_type_hints_provider(_: Callable) -> dict[str, Any]:
        return {}

    @staticmethod
    def type_hints_provider(method: Callable) -> dict[str, Any]:
        try:
            hints = get_type_hints(method)
        except (AttributeError, NameError, TypeError) as exc:
            _LOGGER.debug("Could not retrieve type hints for %s", method)
            _LOGGER.debug(exc)
            hints = {}
        return hints

    def infer_signature(
        self,
        method: Callable,
        type_hint_provider: Callable[[Callable], dict],
    ) -> InferredSignature:
        try:
            method_signature = inspect.signature(method)
        except ValueError:
            method_signature = inspect.Signature(
                parameters=[
                    inspect.Parameter(
                        name="args",
                        kind=inspect.Parameter.VAR_POSITIONAL,
                        annotation=inspect.Signature.empty,
                    ),
                    inspect.Parameter(
                        name="kwargs",
                        kind=inspect.Parameter.VAR_KEYWORD,
                        annotation=inspect.Signature.empty,
                    ),
                ],
                return_annotation=inspect.Signature.empty,
            )

        hints = type_hint_provider(method)
        parameters: dict[str, ProperType] = {}

        hints_for_statistics: dict = self.type_hints_provider(method)
        parameters_for_statistics: dict[str, ProperType] = {}
        for param_name in method_signature.parameters:
            if param_name == "self":
                continue
            parameters[param_name] = self.convert_type_hint(hints.get(param_name))
            parameters_for_statistics[param_name] = self.convert_type_hint(
                hints_for_statistics.get(param_name), unsupported=UNSUPPORTED
            )

        return_type: ProperType = self.convert_type_hint(hints.get("return"))
        return_type_for_statistics: ProperType = self.convert_type_hint(
            hints_for_statistics.get("return"), unsupported=UNSUPPORTED
        )

        return InferredSignature(
            signature=method_signature,
            original_parameters=parameters,
            original_return_type=return_type,
            type_system=self,
            parameters_for_statistics=parameters_for_statistics,
            return_type_for_statistics=return_type_for_statistics,
        )

    _FIND_DOT_SEPARATED_IDENTIFIERS = re.compile(r"[.a-zA-Z0-9_]+\.[a-zA-Z0-9_]+")

    def try_to_load_type(self, candidate: str, globs) -> ProperType:
        glob: dict[str, Any] = {}
        exec("from typing import *", glob)  # noqa: S102
        glob.update(globs)

        for potential_type in self._FIND_DOT_SEPARATED_IDENTIFIERS.finditer(candidate):
            potential_import = potential_type.group(0).rpartition(".")[0]
            _LOGGER.info("Try to import %s", potential_import)
            try:
                exec("import " + potential_import, glob)  # noqa: S102
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(err)
        try:
            ref = ForwardRef(candidate)
            return self.convert_type_hint(_eval_type(ref, glob, glob))
        except Exception:  # noqa: BLE001
            return ANY

    def convert_type_hint(self, hint: Any, unsupported: ProperType = ANY) -> ProperType:
        if hint is Any or hint is None:
            return ANY
        if hint is type(None):
            return NONE_TYPE
        if hint is tuple:
            return TupleType((ANY,), unknown_size=True)
        if get_origin(hint) is tuple:
            args = self.__convert_args_if_exists(hint, unsupported=unsupported)
            if not args:
                return TupleType((ANY,), unknown_size=True)
            return TupleType(args)
        if is_union_type(hint) or isinstance(hint, types.UnionType):
            return UnionType(
                tuple(sorted(self.__convert_args_if_exists(hint, unsupported=unsupported)))
            )
        if isinstance(hint, _BaseGenericAlias | types.GenericAlias):
            result = Instance(
                self.to_type_info(hint.__origin__),
                self.__convert_args_if_exists(hint, unsupported=unsupported),
            )
            return self._fixup_known_generics(result)

        if isinstance(hint, type):
            return self._fixup_known_generics(Instance(self.to_type_info(hint)))
        _LOGGER.debug("Unknown type hint: %s", hint)
        return unsupported

    def __convert_args_if_exists(
        self, hint: Any, unsupported: ProperType
    ) -> tuple[ProperType, ...]:
        if hasattr(hint, "__args__"):
            return tuple(self.convert_type_hint(t, unsupported=unsupported) for t in hint.__args__)
        return ()

    def make_instance(self, typ: TypeInfo) -> Instance | TupleType | NoneType:
        if typ.full_name == "builtins.tuple":
            return TupleType((ANY,), unknown_size=True)
        if typ.full_name == "builtins.NoneType":
            return NONE_TYPE
        result = Instance(
            typ,
        )
        return self._fixup_known_generics(result)

    @staticmethod
    def _fixup_known_generics(result: Instance) -> Instance:
        if result.type.num_hardcoded_generic_parameters is not None:
            args = tuple(result.args)
            if len(result.args) < result.type.num_hardcoded_generic_parameters:
                args += (ANY,) * (result.type.num_hardcoded_generic_parameters - len(args))
            elif len(result.args) > result.type.num_hardcoded_generic_parameters:
                args = args[: result.type.num_hardcoded_generic_parameters]
            return Instance(result.type, args)
        return result
