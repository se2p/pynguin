#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides analyses for a module's type information."""
from __future__ import annotations

import functools
import inspect
import logging
import types
import typing
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Generic, Sequence, TypeVar, get_type_hints

import networkx as nx
from networkx.drawing.nx_pydot import to_pydot
from ordered_set import OrderedSet
from typing_inspect import is_union_type

import pynguin.configuration as config
import pynguin.utils.typetracing as tt
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.type_utils import COLLECTIONS, PRIMITIVES

_LOGGER = logging.getLogger(__name__)


# The following classes are inspired by
# https://github.com/python/mypy/blob/master/mypy/types.py and most likely incomplete.
# The plan is to gradually expand this type representation.


T = TypeVar("T")


class ProperType(ABC):
    """Base class for all types. Might have to add another layer, like mypy's Type?."""

    @abstractmethod
    def accept(self, visitor: TypeVisitor) -> T:
        """Accept a type visitor

        Args:
            visitor: the visitor
        """

    def __str__(self) -> str:
        return self.accept(TypeStringVisitor())

    def __repr__(self) -> str:
        return self.accept(TypeReprVisitor())


class AnyType(ProperType):
    """The Any Type"""

    def accept(self, visitor: TypeVisitor[T]) -> T:
        return visitor.visit_any_type(self)

    def __hash__(self):
        return hash(AnyType)

    def __eq__(self, other):
        return isinstance(other, AnyType)


class NoneType(ProperType):
    """The None type"""

    def accept(self, visitor: TypeVisitor[T]) -> T:
        return visitor.visit_none_type(self)

    def __hash__(self):
        return hash(NoneType)

    def __eq__(self, other):
        return isinstance(other, NoneType)


class Instance(ProperType):
    """An instance type of form C[T1, ..., Tn].
    C is a class.
    Args can be empty."""

    def __init__(self, typ: TypeInfo, args: tuple[ProperType, ...] = None):
        assert typ.raw_type is not tuple, "Use TupleType instead!"
        self.type = typ
        if args is None:
            args = ()
        self.args = tuple(args)
        # Cached hash value
        self._hash: int | None = None

    def accept(self, visitor: TypeVisitor[T]) -> T:
        return visitor.visit_instance(self)

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((self.type, self.args))
        return self._hash

    def __eq__(self, other):
        if not isinstance(other, Instance):
            return False
        return self.type == other.type and self.args == other.args


class TupleType(ProperType):
    """Tuple type Tuple[T1, ..., Tn]. At least one argument."""

    # TODO(fk) this is a bit problematic. Merge with instance?
    #  i.e., there can be TupleType(unknown_size=True) and Instance(TypeInfo(tuple))
    #  tuple is special because it is varargs generic.
    def __init__(self, args: tuple[ProperType, ...], unknown_size: bool = False):
        self.args = args
        self.unknown_size = unknown_size
        # Cached hash value
        self._hash: int | None = None

    def accept(self, visitor: TypeVisitor[T]) -> T:
        return visitor.visit_tuple_type(self)

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((self.args, self.unknown_size))
        return self._hash

    def __eq__(self, other):
        return (
            isinstance(other, TupleType)
            and self.args == other.args
            and self.unknown_size == other.unknown_size
        )


class UnionType(ProperType):
    """The union type Union[T1, ..., Tn] (at least one type argument)."""

    def __init__(self, items: tuple[ProperType, ...]):
        self.items = items
        # TODO(fk) think about flattening Unions, also order should not matter.
        assert len(self.items) > 0
        # Cached hash value
        self._hash: int | None = None

    def accept(self, visitor: TypeVisitor[T]) -> T:
        return visitor.visit_union_type(self)

    def __hash__(self):
        if self._hash is None:
            self._hash = hash(self.items)
        return self._hash

    def __eq__(self, other):
        return isinstance(other, UnionType) and self.items == other.items


class TypeVisitor(Generic[T]):
    """A type visitor"""

    @abstractmethod
    def visit_any_type(self, left: AnyType) -> T:
        """Visit the Any type

        Args:
            left: the Any type

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_none_type(self, left: NoneType) -> T:
        """Visit the None type

        Args:
            left: the None type

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_instance(self, left: Instance) -> T:
        """Visit an instance

        Args:
            left: instance

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_tuple_type(self, left: TupleType) -> T:
        """Visit a tuple type

        Args:
            left: tuple

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_union_type(self, left: UnionType) -> T:
        """Visit a union

        Args:
            left: union

        Returns:
            result of the visit
        """


class TypeStringVisitor(TypeVisitor[str]):
    """A simple visitor to convert a proper type to a string."""

    def visit_any_type(self, left: AnyType) -> str:
        return "Any"

    def visit_none_type(self, left: NoneType) -> str:
        return "None"

    def visit_instance(self, left: Instance) -> str:
        rep = left.type.name
        if len(left.args) > 0:
            rep += "[" + self._sequence_str(left.args) + "]"
        return rep

    def visit_tuple_type(self, left: TupleType) -> str:
        return f"tuple[{self._sequence_str(left.args)}]"

    def visit_union_type(self, left: UnionType) -> str:
        if len(left.items) == 1:
            return left.items[0].accept(self)
        return f"{self._sequence_str(left.items, sep=' | ')}"

    def _sequence_str(self, typs: Sequence[ProperType], sep=", ") -> str:
        return sep.join(t.accept(self) for t in typs)


class TypeReprVisitor(TypeVisitor[str]):
    """A simple visitor to create a repr from a proper type."""

    def visit_any_type(self, left: AnyType) -> str:
        return "AnyType()"

    def visit_none_type(self, left: NoneType) -> str:
        return "NoneType()"

    def visit_instance(self, left: Instance) -> str:
        rep = f"Instance({left.type!r}"
        if len(left.args) > 0:
            rep += "(" + self._sequence_str(left.args) + ")"
        return rep + ")"

    def visit_tuple_type(self, left: TupleType) -> str:
        return f"TupleType({self._sequence_str(left.args)})"

    def visit_union_type(self, left: UnionType) -> str:
        return f"UnionType({self._sequence_str(left.items)})"

    def _sequence_str(self, typs: Sequence[ProperType]) -> str:
        return ", ".join(t.accept(self) for t in typs)


class _SubtypeVisitor(TypeVisitor[bool]):
    """A visitor to check the subtyping relationship between two types, i.e.,
    is left a subtype of right?

    There is no need to check 'right' for AnyType, as this is done outside.
    """

    def __init__(
        self,
        graph: TypeSystem,
        right: ProperType,
        sub_type_check: Callable[[ProperType, ProperType], bool],
    ):
        """Create new visitor

        Args:
            graph: The inheritance graph.
            right: The right type.
            sub_type_check: The subtype check to use
        """
        self.graph = graph
        self.right = right
        self.sub_type_check = sub_type_check

    def visit_any_type(self, left: AnyType) -> bool:  # pylint:disable=unused-argument
        # Any wins always
        return True

    def visit_none_type(self, left: NoneType) -> bool:  # pylint:disable=unused-argument
        # None cannot be subtyped
        # TODO(fk) handle protocols, e.g., hashable.
        return isinstance(left, NoneType)

    def visit_instance(self, left: Instance) -> bool:
        if isinstance(self.right, Instance):
            if not self.graph.is_subclass(left.type, self.right.type):
                return False
            if (
                left.type.num_hardcoded_generic_parameters
                == self.right.type.num_hardcoded_generic_parameters
                is not None
            ):
                # TODO(fk) handle generics properly :(
                # We only check hard coded generics for now and treat them as invariant,
                # i.e., A <: B and B <: A
                return all(
                    self.sub_type_check(left_elem, right_elem)
                    and self.sub_type_check(right_elem, left_elem)
                    for left_elem, right_elem in zip(left.args, self.right.args)
                )
            return True
        return False

    def visit_tuple_type(self, left: TupleType) -> bool:
        if isinstance(self.right, TupleType):
            if len(left.args) != len(self.right.args):
                # TODO(fk) Handle unknown size.
                return False
            return all(
                self.sub_type_check(left_elem, right_elem)
                for left_elem, right_elem in zip(left.args, self.right.args)
            )
        return False

    def visit_union_type(self, left: UnionType) -> bool:
        return all(
            self.sub_type_check(left_elem, self.right) for left_elem in left.items
        )


class _MaybeSubtypeVisitor(_SubtypeVisitor):
    """A weaker subtype check, which only checks if left may be a subtype of right.
    For example, tuple[str | int | bytes, str | int | bytes] is not a subtype of
    tuple[int, int], but the actual return value may be."""

    def visit_union_type(self, left: UnionType) -> bool:
        return any(
            self.sub_type_check(left_elem, self.right) for left_elem in left.items
        )


class _CollectionTypeVisitor(TypeVisitor[bool]):

    Collections = {dict, list, set}  # No tuple because it is a separate type.

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


is_collection_type = _CollectionTypeVisitor()


class _PrimitiveTypeVisitor(TypeVisitor[bool]):

    Primitives = {int, str, bool, float, complex, bytes}

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


is_primitive_type = _PrimitiveTypeVisitor()


# pylint:disable=too-many-instance-attributes
class TypeInfo:
    """A small wrapper around type, i.e., classes.
    Corresponds 1:1 to a class."""

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
        self.is_abstract = inspect.isabstract(raw_type)
        # TODO(fk) store more information on attributes
        self.instance_attributes: OrderedSet[str] = OrderedSet()
        self.symbols: OrderedSet[str] = OrderedSet()

        # TODO(fk) properly implement generics!
        # For now we just store the number of generic parameters for set, dict and list.
        self.num_hardcoded_generic_parameters: int | None = (
            2 if raw_type is dict else 1 if raw_type in (set, list) else None
        )

    @staticmethod
    def to_full_name(typ: type) -> str:
        """Get the full name of the given type

        Args:
            typ: The type for which we want a full name.

        Returns:
            The fully qualified name
        """
        return f"{typ.__module__}.{typ.__qualname__}"

    def __eq__(self, other) -> bool:
        if not isinstance(other, TypeInfo):
            return False
        return other.full_name == self.full_name

    def __hash__(self):
        return hash(self.full_name)

    def __repr__(self):
        return f"TypeInfo({self.full_name})"


@dataclass(eq=False)
class InferredSignature:
    """Encapsulates the types inferred for a method."""

    # Signature inferred from inspect, only useful to get non-type related information
    # on parameters
    signature: inspect.Signature
    # The return type
    original_return_type: ProperType
    # A dict mapping every parameter name to its type
    original_parameters: dict[str, ProperType]

    # Proxy knowledge learned from executions
    knowledge: dict[str, tt.ProxyKnowledge] = field(
        default_factory=lambda: defaultdict(lambda: tt.ProxyKnowledge("ROOT")),
        init=False,
    )

    # Reference to the used type system.
    type_system: TypeSystem

    # Return type might be updated, which is stored here.
    return_type: ProperType = field(init=False)

    # The currently guessed parameter types. Guessing will never result as that is
    # not a useful guess.
    current_guessed_parameters: dict[str, UnionType] = field(
        init=False, default_factory=dict
    )

    def __post_init__(self):
        self.return_type = self.original_return_type

    def get_parameter_types(
        self, signature_memo: dict[InferredSignature, dict[str, ProperType]]
    ) -> dict[str, ProperType]:
        """Get a possible type signature for the parameters.
        This method may choose a random type signature, or return the original one or
        create one based on the observed knowledge.

        Args:
            signature_memo: A memo that stores already chosen signatures, so that
                we don't choose another signature in the same run. This is required for
                certain operations in the test factory to be consistent.

        Returns:
            A dict of chosen parameter types for each parameter.
        """
        if (sig := signature_memo.get(self)) is not None:
            # We already chose a signature
            return sig
        res: dict[str, ProperType] = {}
        test_conf = config.configuration.test_creation
        for param_name, orig_type in self.original_parameters.items():
            if param_name in self.knowledge:
                # If we have information from proxies, update guess.
                self._update_guess(
                    param_name,
                    self._guess_parameter_type(
                        self.knowledge[param_name],
                        self.signature.parameters[param_name].kind,
                    ),
                )

            # Choose from:
            # - Reusing developer annotated types
            # - Guessed types from proxies
            # - NoneType
            # - AnyType, i.e., disregard type
            # TODO(fk) add choices from other source here, e.g., DeepTyper.
            choices: list[ProperType] = [NoneType(), AnyType(), orig_type]
            weights: list[float] = [
                test_conf.none_weight,
                test_conf.any_weight,
                test_conf.original_type_weight,
            ]
            if (guessed := self.current_guessed_parameters.get(param_name)) is not None:
                choices.append(guessed)
                weights.append(test_conf.type_tracing_weight)
            # Make sure var-positional or var-keyword are wrapped in list/dict
            res[param_name] = self.type_system.wrap_var_param_type(
                randomness.choices(choices, weights)[0],
                self.signature.parameters[param_name].kind,
            )
        signature_memo[self] = res
        return res

    def _update_guess(self, name: str, guessed: ProperType | None):
        if guessed is None:
            return

        if (old := self.current_guessed_parameters.get(name)) is None:
            self.current_guessed_parameters[name] = UnionType((guessed,))
        else:
            if guessed in old.items:
                return
            if len(old.items) >= 5:
                # Drop first guess and append current.
                self.current_guessed_parameters[name] = UnionType(
                    old.items[1:] + (guessed,)
                )
            else:
                self.current_guessed_parameters[name] = UnionType(
                    old.items + (guessed,)
                )

    # pylint:disable=too-many-return-statements
    def _guess_parameter_type(
        self, knowledge: tt.ProxyKnowledge, kind
    ) -> ProperType | None:
        """Guess a type for a parameter.

        Args:
            knowledge: The name of the parameter.
            kind: the kind of parameter.

        Returns:
            A guessed type for the given parameter name, or None, if no educated guess
                can be made.
        """
        match kind:
            case inspect.Parameter.VAR_KEYWORD:
                # Case for **kwargs parameter
                # We know that it is always dict[str, ?].
                # We can guess the unknown type by looking at the knowledge of
                # __getitem__ of the proxy.
                if (
                    get_item_knowledge := knowledge.symbol_table.get("__getitem__")
                ) is not None:
                    return self._guess_parameter_type_from(get_item_knowledge)
            case inspect.Parameter.VAR_POSITIONAL:
                # Case for *args parameter
                # We know that it is always list[?]
                # Similar to above.
                if (
                    iter_knowledge := knowledge.symbol_table.get("__iter__")
                ) is not None:
                    return self._guess_parameter_type_from(iter_knowledge)
            case _:
                return self._guess_parameter_type_from(knowledge)
        return None

    # If one of these methods was called on a proxy, we can use the argument type
    # to make guesses.
    _ARGUMENT_SYMBOLS = OrderedSet(
        [
            "__eq__",
            "__ne__",
            "__lt__",
            "__le__",
            "__gt__",
            "__ge__",
        ]
    )

    # We can guess the element type by looking at the knowledge from these
    _LIST_ELEMENT_SYMBOLS = OrderedSet(("__iter__", "__getitem__"))
    _DICT_KEY_SYMBOLS = OrderedSet(("__iter__",))
    _DICT_VALUE_SYMBOLS = OrderedSet(("__getitem__",))
    _SET_ELEMENT_SYMBOLS = OrderedSet(("__iter__",))

    # We can guess generic type(s) from the argument type(s) of these methods:
    _LIST_ELEMENT_FROM_ARGUMENT_TYPES = OrderedSet(("__contains__", "__delitem__"))
    _SET_ELEMENT_FROM_ARGUMENT_TYPES = OrderedSet(("__contains__", "__delitem__"))
    _DICT_KEY_FROM_ARGUMENT_TYPES = OrderedSet(
        (
            "__contains__",
            "__delitem__",
            "__getitem__",
            "__setitem__",
        )
    )
    _DICT_VALUE_FROM_ARGUMENT_TYPES = OrderedSet(("__setitem__",))

    def _from_type_check(self, knowledge: tt.ProxyKnowledge) -> ProperType | None:
        # Type checks is not empty here.
        return self._choose_type_or_negate(
            OrderedSet(
                [
                    self.type_system.to_type_info(
                        randomness.choice(knowledge.type_checks)
                    )
                ]
            )
        )

    def _from_symbol_table(self, knowledge: tt.ProxyKnowledge) -> ProperType | None:
        random_symbol = randomness.choice(list(knowledge.symbol_table))
        if (
            random_symbol in InferredSignature._ARGUMENT_SYMBOLS
            and knowledge.symbol_table[random_symbol].arg_types[0]
            and randomness.next_float() < 0.5
        ):
            random_arg_type = randomness.choice(
                knowledge.symbol_table[random_symbol].arg_types[0]
            )
            return self._choose_type_or_negate(
                OrderedSet([self.type_system.to_type_info(random_arg_type)])
            )
        return self._choose_type_or_negate(
            self.type_system.find_by_symbol(random_symbol)
        )

    # pylint:disable=too-many-return-statements
    def _guess_parameter_type_from(
        self, knowledge: tt.ProxyKnowledge, recursion_depth: int = 0
    ) -> ProperType | None:
        guess_from: list[Callable[[tt.ProxyKnowledge], ProperType | None]] = []
        if knowledge.type_checks:
            guess_from.append(self._from_type_check)
        if knowledge.symbol_table:
            guess_from.append(self._from_symbol_table)

        if not guess_from:
            return None

        guessed_type: ProperType | None = randomness.choice(guess_from)(knowledge)

        if (
            recursion_depth <= 1
            and guessed_type
            and guessed_type.accept(is_collection_type)
        ):
            guessed_type = self._guess_generic_parameters_for_builtins(
                guessed_type, knowledge, recursion_depth
            )
        return guessed_type

    def _guess_generic_parameters_for_builtins(
        self,
        guessed_type: ProperType,
        knowledge: tt.ProxyKnowledge,
        recursion_depth: int,
    ):
        # If it is a builtin collection, we may be able to make further guesses on
        # the generic types.
        if isinstance(guessed_type, Instance):
            args = guessed_type.args
            match guessed_type.type.full_name:
                case "builtins.list":
                    guessed_element_type = self._guess_generic_arguments(
                        knowledge,
                        recursion_depth,
                        InferredSignature._LIST_ELEMENT_SYMBOLS,
                        InferredSignature._LIST_ELEMENT_FROM_ARGUMENT_TYPES,
                        argument_idx=0,
                    )
                    args = (
                        guessed_element_type
                        if guessed_element_type
                        else guessed_type.args[0],
                    )
                case "builtins.set":
                    guessed_element_type = self._guess_generic_arguments(
                        knowledge,
                        recursion_depth,
                        InferredSignature._SET_ELEMENT_SYMBOLS,
                        InferredSignature._SET_ELEMENT_FROM_ARGUMENT_TYPES,
                        argument_idx=0,
                    )
                    args = (
                        guessed_element_type
                        if guessed_element_type
                        else guessed_type.args[0],
                    )
                case "builtins.dict":
                    guessed_key_type = self._guess_generic_arguments(
                        knowledge,
                        recursion_depth,
                        InferredSignature._DICT_KEY_SYMBOLS,
                        InferredSignature._DICT_KEY_FROM_ARGUMENT_TYPES,
                        argument_idx=0,
                    )
                    guessed_value_type = self._guess_generic_arguments(
                        knowledge,
                        recursion_depth,
                        InferredSignature._DICT_VALUE_SYMBOLS,
                        InferredSignature._DICT_VALUE_FROM_ARGUMENT_TYPES,
                        argument_idx=1,
                    )
                    args = (
                        guessed_key_type if guessed_key_type else guessed_type.args[0],
                        guessed_value_type
                        if guessed_value_type
                        else guessed_type.args[1],
                    )
            guessed_type = Instance(guessed_type.type, args)
        elif isinstance(guessed_type, TupleType):
            # TODO(fk) think about tuples.
            pass
        return guessed_type

    def _choose_type_or_negate(
        self, positive_types: OrderedSet[TypeInfo]
    ) -> ProperType | None:
        if not positive_types:
            return None

        if randomness.next_float() < config.configuration.test_creation.negate_type:
            negated_choices = self.type_system.get_type_outside_of(positive_types)
            if len(negated_choices) > 0:
                return self.type_system.make_instance(
                    randomness.choice(negated_choices)
                )
        return self.type_system.make_instance(randomness.choice(positive_types))

    # pylint:disable-next=too-many-arguments
    def _guess_generic_arguments(
        self,
        knowledge: tt.ProxyKnowledge,
        recursion_depth: int,
        element_symbols: OrderedSet[str],
        argument_symbols: OrderedSet[str],
        argument_idx: int,
    ) -> ProperType | None:
        guess_from: list[
            Callable[
                [],
                ProperType | None,
            ]
        ] = []
        if elem_symbols := element_symbols.intersection(knowledge.symbol_table.keys()):
            guess_from.append(
                functools.partial(
                    self._guess_parameter_type_from,
                    knowledge.symbol_table[randomness.choice(elem_symbols)],
                    recursion_depth + 1,
                )
            )
        if arg_symbols := argument_symbols.intersection(knowledge.symbol_table.keys()):
            guess_from.append(
                functools.partial(
                    self._guess_from_argument_types,
                    arg_symbols,
                    knowledge,
                    argument_idx,
                )
            )

        if guess_from:
            return randomness.choice(guess_from)()
        return None

    def _guess_from_argument_types(
        self, arg_symbols: Sequence[str], knowledge: tt.ProxyKnowledge, arg_idx: int = 0
    ) -> ProperType | None:
        arg_types = knowledge.symbol_table[randomness.choice(arg_symbols)].arg_types[
            arg_idx
        ]
        if arg_types:
            return self._choose_type_or_negate(
                OrderedSet(
                    [self.type_system.to_type_info(randomness.choice(arg_types))]
                )
            )
        return None

    def format_guessed_signature(self) -> str:
        """Provide a formatted signature

        Returns:
            The formatted signature.
        """
        parameters = []
        for name, param in self.signature.parameters.items():
            if name not in self.original_parameters:
                # e.g., 'self' is not in original parameters.
                parameters.append(param.replace(annotation=inspect.Parameter.empty))
            elif (guessed := self.current_guessed_parameters.get(name)) is not None:
                parameters.append(param.replace(annotation=str(guessed)))
            else:
                parameters.append(
                    param.replace(annotation=str(self.original_parameters[name]))
                )
        return_type = str(self.return_type)
        return str(
            self.signature.replace(parameters=parameters, return_annotation=return_type)
        )


class TypeSystem:
    """Provides a simple inheritance graph relating various classes using their subclass
    relationships. Note that parents point to their children.

    This is also the central system to store/handle type information.
    """

    def __init__(self):
        self._graph = nx.DiGraph()
        # Maps all known types from their full name to their type info.
        self._types: dict[str, TypeInfo] = {}
        # Maps symbols to type which have that symbol
        self._symbol_map: dict[str, OrderedSet[TypeInfo]] = defaultdict(OrderedSet)
        # These types are intrinsic for Pynguin, i.e., we can generate them ourselves
        # without needing a generator. We store them here, so we don't have to generate
        # them all the time.
        self.primitive_proper_types = [
            self.convert_type_hint(prim) for prim in PRIMITIVES
        ]
        self.collection_proper_types = [
            self.convert_type_hint(coll) for coll in COLLECTIONS
        ]

    def add_subclass_edge(self, *, super_class: TypeInfo, sub_class: TypeInfo) -> None:
        """Add a subclass edge between two types.

        Args:
            super_class: superclass
            sub_class: subclass
        """
        self._graph.add_edge(super_class, sub_class)

    @lru_cache(maxsize=1024)
    def get_subclasses(self, klass: TypeInfo) -> OrderedSet[TypeInfo]:
        """Provides all descendants of the given type. Includes klass.

        Args:
            klass: The class whose subtypes we want to query.

        Returns:
            All subclasses including klass
        """
        if klass not in self._graph:
            return OrderedSet([klass])
        result: OrderedSet[TypeInfo] = OrderedSet(nx.descendants(self._graph, klass))
        result.add(klass)
        return result

    @lru_cache(maxsize=1024)
    def get_superclasses(self, klass: TypeInfo) -> OrderedSet[TypeInfo]:
        """Provides all ancestors of the given class.

        Args:
            klass: The class whose supertypes we want to query.

        Returns:
            All superclasses including klass
        """
        if klass not in self._graph:
            return OrderedSet([klass])
        result: OrderedSet[TypeInfo] = OrderedSet(nx.ancestors(self._graph, klass))
        result.add(klass)
        return result

    def get_type_outside_of(
        self, klasses: OrderedSet[TypeInfo]
    ) -> OrderedSet[TypeInfo]:
        """Find a type that does not belong to the given types or any subclasses.

        Args:
            klasses: The classes to exclude

        Returns:
            A set of klasses that don't belong the given ones.
        """
        results = OrderedSet(self._types.values())
        for info in klasses:
            results.difference_update(self.get_subclasses(info))
        return results

    @lru_cache(maxsize=4096)
    def is_subclass(self, left: TypeInfo, right: TypeInfo) -> bool:
        """Is 'left' a subclass of 'right'?

        Args:
            left: left type info
            right: right type info

        Returns:
            True, if there is a subclassing path from left to right.
        """
        return nx.has_path(self._graph, right, left)

    @lru_cache(maxsize=4096)
    def is_subtype(self, left: ProperType, right: ProperType) -> bool:
        """Is 'left' a subtype of 'right'?

        This check is more than incomplete, but it takes into account
        that anything is a subtype of AnyType.

        See https://peps.python.org/pep-0483/ and https://peps.python.org/pep-0484/
        for more details

        Args:
            left: The left type
            right: The right type

        Returns:
            True, if left is a subtype of right.
        """
        if isinstance(right, AnyType):
            # trivial case
            return True
        if isinstance(right, UnionType) and not isinstance(left, UnionType):
            # Case that would be duplicated for each type, so we put it here.
            return any(self.is_subtype(left, right_elem) for right_elem in right.items)
        return left.accept(_SubtypeVisitor(self, right, self.is_subtype))

    @lru_cache(maxsize=4096)
    def is_maybe_subtype(self, left: ProperType, right: ProperType) -> bool:
        """Is 'left' maybe a subtype of 'right'?

        This is a more lenient check than is_subtype. Consider a function that
        returns tuple[str | int | bytes, str | int | bytes]. Strictly speaking, we
        cannot use such a value as an argument for a function that requires an argument
        of type tuple[int, int]. However, it may be possible that the returned
        value is tuple[int, int], in which case it does work.
        This check only differs from is_subtype in how it handles Unions.
        Instead of requiring every type to be a subtype, it is sufficient that one
        type of the Union is a subtype.

        Args:
            left: The left type
            right: The right type

        Returns:
            True, if left may be a subtype of right.
        """
        if isinstance(right, AnyType):
            # trivial case
            return True
        if isinstance(right, UnionType) and not isinstance(left, UnionType):
            # Case that would be duplicated for each type, so we put it here.
            return any(
                self.is_maybe_subtype(left, right_elem) for right_elem in right.items
            )
        return left.accept(_MaybeSubtypeVisitor(self, right, self.is_maybe_subtype))

    @property
    def dot(self) -> str:
        """Create dot representation of this graph.

        Returns:
            A dot string.
        """
        dot = to_pydot(self._graph)
        return dot.to_string()

    def to_type_info(self, typ: type) -> TypeInfo:
        """Find or create type info for the given type.

        Args:
            typ: The raw type we want to convert.

        Returns:
            A type info object.
        """
        # TODO(fk) what to do when we encounter a new type?
        found = self._types.get(TypeInfo.to_full_name(typ))
        if found is not None:
            return found
        info = TypeInfo(typ)
        self._types[info.full_name] = info
        self._graph.add_node(info)
        return info

    def find_type_info(self, full_name: str) -> TypeInfo | None:
        """Find typeinfo for the given name.

        Args:
            full_name: The name to search for.

        Returns:
            Type info, if any.
        """
        return self._types.get(full_name)

    def find_by_symbol(self, symbol: str) -> OrderedSet[TypeInfo]:
        """Search for all types that have the given symbol.

        Args:
            symbol: the symbol to search for.

        Returns:
            All types (or supertypes thereof) who have the given symbol.
        """
        return self._symbol_map[symbol]

    def push_symbols_down(self) -> None:
        """We don't want to see symbols multiple times, e.g., in subclasses, so only the
        first class in the hierarchy which adds the symbol should have it listed as a
        symbol, i.e., when searching for a class with that symbol we only want to
        retrieve the top-most class(es) in the hierarchy which define it, and not every
        (sub)class that inherited it.
        """
        reach_in_sets: dict[TypeInfo, set[str]] = defaultdict(set)
        reach_out_sets: dict[TypeInfo, set[str]] = defaultdict(set)

        # While object sits at the top, it is not particularly useful, so we delete
        # all of its symbols.
        # TODO(fk) does this make sense?
        object_info = self.find_type_info("builtins.object")
        assert object_info is not None
        object_info.symbols.clear()

        # Use fix point iteration with reach-in/out to push elements down.
        work_list = list(self._graph.nodes)
        while len(work_list) > 0:
            current = work_list.pop()
            old_val = set(reach_out_sets[current])
            for pred in self._graph.predecessors(current):
                reach_in_sets[current].update(reach_out_sets[pred])
            current.symbols.difference_update(reach_in_sets[current])
            reach_out_sets[current] = set(reach_in_sets[current])
            reach_out_sets[current].update(current.symbols)
            if old_val != reach_out_sets[current]:
                work_list.extend(self._graph.successors(current))
        for type_info in self._graph.nodes:
            for symbol in type_info.symbols:
                self._symbol_map[symbol].add(type_info)

    def wrap_var_param_type(self, typ: ProperType, param_kind) -> ProperType:
        """Wrap the parameter type of *args and **kwargs in List[...] or Dict[str, ...],
        respectively.

        Args:
            typ: The type to be wrapped.
            param_kind: the kind of parameter.

        Returns:
            The wrapped type, or the original type, if no wrapping is required.
        """
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
        """Infers the type information for a callable.

        Args:
            method: The callable we try to infer type information for
            type_inference_strategy: Whether to incorporate type annotations

        Returns:
            The inference result

        Raises:
            ConfigurationException: in case an unknown type-inference strategy was
                selected
        """
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
        """Provides no type hints.

        Args:
            _: Ignored.

        Returns:
            An empty dict.
        """
        return {}

    @staticmethod
    def type_hints_provider(method: Callable) -> dict[str, Any]:
        """Provides PEP484-style type information, if available.

        Args:
            method: The method for which we want type hints.

        Returns:
            A dict mapping parameter names to type hints.
        """
        try:
            hints = get_type_hints(method)
            # Sadly there is no guarantee that resolving the type hints actually works.
            # If the developers annotated something with an erroneous type hint we fall
            # back to no type hints, i.e., use Any.
            # The import used in the type hint could also be conditional on
            # typing.TYPE_CHECKING, e.g., to avoid circular imports, in which case this
            # also fails.
        except NameError:
            hints = {}
        return hints

    def infer_signature(
        self, method: Callable, type_hint_provider: Callable[[Callable], dict]
    ) -> InferredSignature:
        """Infers the method signature using the given type hint provider.

        Args:
            method: The callable
            type_hint_provider: A method that provides type hints for the given method.

        Returns:
            The inference result
        """
        if inspect.isclass(method) and hasattr(method, "__init__"):
            return self.infer_signature(getattr(method, "__init__"), type_hint_provider)

        method_signature = inspect.signature(method)
        hints = type_hint_provider(method)
        parameters: dict[str, ProperType] = {}
        for param_name in method_signature.parameters:
            if param_name == "self":
                # TODO(fk) does not necessarily work, can be named anything,
                #  for example cls for @classmethod.
                continue
            hint: ProperType = self.convert_type_hint(hints.get(param_name))
            parameters[param_name] = hint

        return_type: ProperType = self.convert_type_hint(hints.get("return"))

        return InferredSignature(
            signature=method_signature,
            original_parameters=parameters,
            original_return_type=return_type,
            type_system=self,
        )

    def convert_type_hint(
        self,
        hint: Any,
    ) -> ProperType:
        # pylint:disable=too-many-return-statements
        """Python's builtin functionality makes handling types during runtime really
        hard, because 1) this is not intended to be used at runtime and 2) there are a
        lot of different notations, due to the constantly evolving type hint system.
        We also cannot easily use mypy's type abstraction because it is 1) strongly
        encapsulated and not part of mypy's public API and 2) is designed to be used
        for static type checking. This method tries to translate type hints into our
        own type abstraction in order to make handling types less painful.

        This conversion is naive when compared to what sophisticated type checkers like
        mypy do, but it is hopefully sufficient for our purposes.
        This method only handles a very small subset of the types that we may
        encounter in the wild, but at least it allows use to better reason about types.
        This should be extended in the future to handle more cases.

        Args:
            hint: The type hint

        Returns:
            A proper type.
        """
        # We must handle a lot of special cases, so try to give an example for each one.

        if hint is typing.Any or hint is None:
            # typing.Any or empty
            return AnyType()
        if hint is type(None):  # noqa: E721
            # None
            return NoneType()
        if hint is tuple:
            # tuple
            # TODO(fk) Tuple without size. Should use tuple[Any, ...] ?
            #  But ... (ellipsis) is not a type.
            return TupleType((AnyType(),), unknown_size=True)
        if typing.get_origin(hint) is tuple:
            # tuple[int, str] or typing.Tuple[int, str]
            return TupleType(tuple(self.convert_type_hint(t) for t in hint.__args__))
        if is_union_type(hint) or isinstance(hint, types.UnionType):
            # int | str or typing.Union[int, str]
            return UnionType(tuple(self.convert_type_hint(t) for t in hint.__args__))
        if isinstance(
            hint, (typing._BaseGenericAlias, types.GenericAlias)  # type:ignore
        ):
            # list[int, str] or List[int, str] or Dict[int, str] or set[str]
            result = Instance(
                self.to_type_info(hint.__origin__),
                tuple(self.convert_type_hint(t) for t in hint.__args__),
            )
            # TODO(fk) remove this one day.
            #  Hardcoded support generic dict, list and set.
            return self._fixup_known_generics(result)

        if isinstance(hint, type):
            # int or str or MyClass
            return self._fixup_known_generics(Instance(self.to_type_info(hint)))
        # TODO(fk) log unknown hints to so we can better understand what
        #  we should add next
        _LOGGER.debug("Unknown type hint: %s", hint)
        # Should raise an error in the future.
        return AnyType()

    def make_instance(self, typ: TypeInfo) -> Instance | TupleType:
        """Create an instance from the given type.

        Args:
            typ: The type info.

        Returns:
            An instance or TupleType
        """
        if typ.full_name == "builtins.tuple":
            return TupleType((AnyType(),), unknown_size=True)
        result = Instance(
            typ,
        )
        return self._fixup_known_generics(result)

    @staticmethod
    def _fixup_known_generics(result: Instance) -> Instance:
        if result.type.num_hardcoded_generic_parameters is not None:
            args = tuple(result.args)
            if len(result.args) < result.type.num_hardcoded_generic_parameters:
                # Fill with AnyType if to small
                args = args + (AnyType(),) * (
                    result.type.num_hardcoded_generic_parameters - len(args)
                )
            elif len(result.args) > result.type.num_hardcoded_generic_parameters:
                # Remove excessive args.
                args = args[: result.type.num_hardcoded_generic_parameters]
            return Instance(result.type, args)
        return result
