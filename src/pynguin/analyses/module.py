#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides analyses for the subject module, based on the module and its AST."""

from __future__ import annotations

import abc
import builtins
import dataclasses
import enum
import functools
import importlib
import inspect
import itertools
import json
import logging
import queue
import types
import typing
from collections import defaultdict
from pathlib import Path
from types import (
    BuiltinFunctionType,
    FunctionType,
    GenericAlias,
    MethodDescriptorType,
    ModuleType,
    WrapperDescriptorType,
)
from typing import Any

import astroid
from astroid.nodes import Assign, AsyncFunctionDef, ClassDef, FunctionDef, Lambda, Module

import pynguin.configuration as config
import pynguin.utils.statistics.stats as stat
import pynguin.utils.typetracing as tt
from pynguin.analyses.type_inference import (
    ANY_STR,
    HintInference,
    InferenceProvider,
    LLMInference,
    NoInference,
)
from pynguin.utils.llm import LLMProvider

if config.configuration.pynguinml.ml_testing_enabled or typing.TYPE_CHECKING:
    import pynguin.utils.pynguinml.ml_testing_resources as tr

from pynguin.analyses.modulecomplexity import mccabe_complexity
from pynguin.analyses.syntaxtree import (
    FunctionDescription,
    astroid_to_ast,
    get_class_node_from_ast,
    get_function_description,
    get_function_node_from_ast,
)
from pynguin.analyses.typesystem import (
    ANY,
    AnyType,
    Instance,
    NoneType,
    ProperType,
    TupleType,
    TypeInfo,
    TypeSystem,
    TypeVisitor,
    UnionType,
    Unsupported,
    is_primitive_type,
)
from pynguin.configuration import TypeInferenceStrategy
from pynguin.utils import randomness
from pynguin.utils.exceptions import (
    ConstraintValidationError,
    ConstructionFailedException,
    CoroutineFoundException,
)
from pynguin.utils.generic.genericaccessibleobject import (
    GenericAccessibleObject,
    GenericCallableAccessibleObject,
    GenericConstructor,
    GenericEnum,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.statistics.runtimevariable import RuntimeVariable
from pynguin.utils.type_utils import COLLECTIONS, PRIMITIVES, get_class_that_defined_method
from pynguin.utils.typeevalpy_json_schema import provide_json

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    import pynguin.ga.algorithms.archive as arch
    import pynguin.ga.computations as ff
    from pynguin.instrumentation.tracer import SubjectProperties
    from pynguin.utils.pynguinml.mlparameter import MLParameter

AstroidFunctionDef: typing.TypeAlias = AsyncFunctionDef | FunctionDef

LOGGER = logging.getLogger(__name__)


# A set of modules that shall be blacklisted from analysis (keep them sorted to ease
# future manipulations or looking up module names of this set!!!):
# The modules that are listed here are not prohibited from execution, but Pynguin will
# not consider any classes or functions from these modules for generating inputs to
# other routines
MODULE_BLACKLIST = frozenset((
    "__future__",
    "_frozen_importlib",
    "_thread",
    "abc",
    "argparse",
    "asyncio",
    "atexit",
    "builtins",
    "cmd",
    "code",
    "codeop",
    "collections.abc",
    "compileall",
    "concurrent",
    "concurrent.futures",
    "configparser",
    "contextlib",
    "contextvars",
    "copy",
    "copyreg",
    "csv",
    "ctypes",
    "dbm",
    "dis",
    "filecmp",
    "fileinput",
    "fnmatch",
    "functools",
    "gc",
    "getopt",
    "getpass",
    "glob",
    "importlib",
    "io",
    "itertools",
    "linecache",
    "logging",
    "logging.config",
    "logging.handlers",
    "marshal",
    "mmap",
    "multiprocessing",
    "multiprocessing.shared_memory",
    "netrc",
    "operator",
    "os",
    "os.path",
    "pathlib",
    "pickle",
    "pickletools",
    "plistlib",
    "py_compile",
    "queue",
    "random",
    "reprlib",
    "sched",
    "secrets",
    "select",
    "selectors",
    "shelve",
    "shutil",
    "signal",
    "six",  # Not from STDLIB
    "socket",
    "sre_compile",
    "sre_parse",
    "ssl",
    "stat",
    "subprocess",
    "sys",
    "tarfile",
    "tempfile",
    "threading",
    "timeit",
    "trace",
    "traceback",
    "tracemalloc",
    "types",
    "typing",
    "warnings",
    "weakref",
))

# Blacklist for methods.
METHOD_BLACKLIST = frozenset(("time.sleep",))


def _is_blacklisted(element: Any) -> bool:
    """Checks if the given element belongs to the blacklist.

    Args:
        element: The element to check

    Returns:
        Is the element blacklisted?
    """
    module_blacklist = set(MODULE_BLACKLIST).union(config.configuration.ignore_modules)
    method_blacklist = set(METHOD_BLACKLIST).union(config.configuration.ignore_methods)

    try:
        if inspect.ismodule(element):
            return element.__name__ in module_blacklist
        if inspect.isclass(element):
            if element.__module__ == "builtins" and (
                element in PRIMITIVES or element in COLLECTIONS
            ):
                # Allow some builtin types
                return False
            return element.__module__ in module_blacklist
        if inspect.isfunction(element):
            # Some modules can be run standalone using a main function or provide a small
            # set of tests ('test'). We don't want to include those functions.
            # Importing certain modules such as inspect, that use or import C-functions can
            # lead to __module__ being None. We want to exclude these functions as well.
            return (
                element.__module__ is None
                or element.__module__ in module_blacklist
                or element.__qualname__.startswith((
                    "main",
                    "test",
                ))
                or f"{element.__module__}.{element.__qualname__}" in method_blacklist
            )
    except Exception:  # noqa: BLE001
        LOGGER.warning(
            "Could not check if %s is blacklisted. Assuming it is not.", element, exc_info=True
        )
    # Something that is not supported yet.
    return False


C_MODULE_WHITELIST = frozenset((
    # === Basic C modules (interpreter startup) ===
    "abc",
    "ast",
    "codecs",
    "collections",
    "enum",
    "functools",
    "imp",
    "io",
    "locale",
    "operator",
    "signal",
    "sitebuiltins",
    "stat",
    "thread",
    "tracemalloc",
    "weakref",
    "builtins",
    "errno",
    "marshal",
    "sys",
    "time",
    "sre",
    "symtable",
    "warnings",
    "string",
    "re",
    "inspect",
    "tokenize",
    # === Common Data Structures & Algorithms ===
    "array",
    "bisect",
    "heapq",
    "itertools",
    # === Math & Random ===
    "math",
    "random",
    "statistics",
    # === Data Serialization & Formats ===
    "csv",
    "json",
    "pickle",
    "struct",
    "elementtree",
    "pyexpat",
    "binascii",
    # === Hashing & Cryptography ===
    "hashlib",
    "ssl",
    "blake2",
    "md5",
    "sha3",
    "unicodedata",
    # === Compression ===
    "zlib",
    "bz2",
    "lzma",
    # === Concurrency & Interoperability ===
    # "multiprocessing", # Explicitly not included
    # "ctypes",  # Explicitly not included
    # "asyncio",  # Explicitly not included
    # === Networking ===
    "socket",
    "select",
    # === Database ===
    "sqlite3",
    # === GUI ===
    "tkinter",
    # === Introspection & Debugging ===
    "gc",
    "faulthandler",
    # === Platform: POSIX/Unix-like ===
    "posix",
    # "posixsubprocess", # Explicitly not included
    "fcntl",
    "grp",
    "pwd",
    "resource",
    "termios",
    # === Platform: Windows ===
    "winapi",
    "msvcrt",
    # === Platform: macOS ===
    "scproxy",
    # === Platform: Cross-platform ===
    "mmap",
    # --- Other ---
    "queue",
    "decimal",
    "uuid",
    "datetime",
    "zoneinfo",
    "shlex",
    "calendar",
    "yaml",
    "email",
    "syslog",
    "dataclasses",
    "pprint",
    "difflib",
    "cmath",
    "hmac",
))


def _c_is_whitelisted(element: ModuleType) -> bool:
    """Checks if the given element belongs to the C module whitelist.

    Args:
        element: The element to check

    Returns:
        Is the element whitelisted?
    """
    c_module_whitelist = set(C_MODULE_WHITELIST)

    try:
        module_name = element.__name__
        top_level = module_name.split(".")[0]
        public_top_level = top_level.lstrip("_")
        return public_top_level in c_module_whitelist
    except Exception:  # noqa: BLE001
        LOGGER.warning(
            "Could not check if %s is whitelisted. Assuming it is not.", element, exc_info=True
        )
    # Something that is not supported yet.
    return False


def _handle_c_modules(
    c_extensions: set[str],
) -> None:
    """Handles the C extensions in the subject module.

    Args:
        c_extensions: The set of C extensions.
    """
    subprocess_mode_recommended = len(c_extensions) > 0
    if config.configuration.subprocess_if_recommended:
        config.configuration.subprocess = subprocess_mode_recommended
        LOGGER.info(
            "Subprocess mode is set to %s because the subject module uses "
            "the following C extensions: %s. ",
            config.configuration.subprocess,
            ", ".join(sorted(c_extensions)),
        )
    elif not config.configuration.subprocess and subprocess_mode_recommended:
        LOGGER.warning(
            "You are using threaded execution mode, but the subject module "
            "uses the following C extensions: %s. "
            "This may lead to unexpected behavior, consider using "
            "subprocess mode instead.",
            ", ".join(sorted(c_extensions)),
        )

    # Store the discovered C extensions in the statistics
    stat.track_output_variable(RuntimeVariable.CExtensionModules, str(sorted(c_extensions)))
    stat.track_output_variable(RuntimeVariable.SubprocessMode, str(config.configuration.subprocess))


@dataclasses.dataclass
class _ModuleParseResult:
    """A data wrapper for an imported and parsed module."""

    linenos: int
    module_name: str
    module: ModuleType
    syntax_tree: Module | None


def import_module(module_name: str) -> ModuleType:
    """Imports a module by name.

    Unlike the built-in :py:func:`importlib.import_module`, this function also supports
    importing module aliases.

    Args:
        module_name: The fully-qualified name of the module

    Returns:
        The imported module
    """
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        try:
            package_name, submodule_name = module_name.rsplit(".", 1)
        except ValueError as e:
            raise error from e

        try:
            package = import_module(package_name)
        except ModuleNotFoundError as e:
            raise error from e

        try:
            submodule = getattr(package, submodule_name)
        except AttributeError as e:
            raise error from e

        if not inspect.ismodule(submodule):
            raise error

        return submodule


def read_module_ast(module_path: str, module_name: str) -> tuple[Module, str]:
    """Reads the AST of the module and returns it along with its source code.

    Args:
        module_path: The path of the module.
        module_name: The name of the module.

    Raises:
        OSError: if the module file cannot be read.
        AstroidError: if an error occurs during the creation of the AST.

    Returns:
        A tuple containing the AST and the source code.
    """
    source_code = Path(module_path).read_text(encoding="utf-8")
    syntax_tree = astroid.parse(code=source_code, module_name=module_name, path=module_path)
    return syntax_tree, source_code


def parse_module(module_name: str) -> _ModuleParseResult:
    """Parses a module and extracts its module-type and AST.

    If the source code is not available it is not possible to build an AST.  In this
    case the respective field of the :py:class:`_ModuleParseResult` will contain the
    value ``None``.  This is the case, for example, for modules written in native code,
    for example, in C.

    Args:
        module_name: The fully-qualified name of the module

    Returns:
        A tuple of the imported module type and its optional AST
    """
    module = import_module(module_name)
    syntax_tree: Module | None = None
    linenos: int = -1
    try:
        module_path = inspect.getsourcefile(module)
        assert module_path is not None, f"Could not determine the path of module {module}"
        syntax_tree, source_code = read_module_ast(module_path, module_name)
    except (
        TypeError,  # from `inspect.getsourcefile`
        AssertionError,  # from `assert`
        OSError,
        astroid.AstroidError,
    ) as error:
        LOGGER.debug(
            f"Could not retrieve source code for module {module_name} "  # noqa: G004
            f"({error}). "
            f"Cannot derive syntax tree to allow Pynguin using more precise analysis."
        )
    else:
        linenos = len(source_code.splitlines())

    return _ModuleParseResult(
        linenos=linenos,
        module_name=module_name,
        module=module,
        syntax_tree=syntax_tree,
    )


class TestCluster(abc.ABC):  # noqa: PLR0904
    """Interface for a test cluster."""

    @property
    @abc.abstractmethod
    def type_system(self) -> TypeSystem:
        """Provides the inheritance graph."""

    @property
    @abc.abstractmethod
    def linenos(self) -> int:
        """Provide the number of source code lines."""

    @abc.abstractmethod
    def log_cluster_statistics(self) -> None:
        """Log the signatures of all seen callables."""

    @abc.abstractmethod
    def add_generator(self, generator: GenericAccessibleObject) -> None:
        """Add the given accessible as a generator.

        Args:
            generator: The accessible object
        """

    @abc.abstractmethod
    def add_accessible_object_under_test(
        self, objc: GenericAccessibleObject, data: CallableData
    ) -> None:
        """Add accessible object to the objects under test.

        Args:
            objc: The accessible object
            data: The function-description data
        """

    @abc.abstractmethod
    def add_modifier(self, typ: TypeInfo, obj: GenericAccessibleObject) -> None:
        """Add a modifier.

        A modifier is something that can be used to modify the given type,
        for example, a method.

        Args:
            typ: The type that can be modified
            obj: The accessible that can modify
        """

    @property
    @abc.abstractmethod
    def accessible_objects_under_test(self) -> OrderedSet[GenericAccessibleObject]:
        """Provides all accessible objects under test."""

    @property
    @abc.abstractmethod
    def function_data_for_accessibles(
        self,
    ) -> dict[GenericAccessibleObject, CallableData]:
        """Provides all function data for all accessibles."""

    @abc.abstractmethod
    def add_ml_data(self, obj: GenericAccessibleObject, data: MLCallableData) -> None:
        """Provides ML data for a accessible."""

    @abc.abstractmethod
    def get_ml_data_for(self, generic_accessible: GenericAccessibleObject) -> MLCallableData | None:
        """Provides ML data for a accessible."""

    @abc.abstractmethod
    def num_accessible_objects_under_test(self) -> int:
        """Provide the number of accessible objects under test.

        Useful to check whether there is even something to test.
        """

    @abc.abstractmethod
    def get_generators_for(
        self, typ: ProperType
    ) -> tuple[OrderedSet[GenericAccessibleObject], bool]:
        """Retrieve all known generators for the given type.

        Args:
            typ: The type we want to have the generators for

        Returns:
            The set of all generators for that type, as well as a boolean
              that indicates if all generators have been matched through Any.
              # noqa: DAR202
        """

    @abc.abstractmethod
    def get_modifiers_for(self, typ: ProperType) -> OrderedSet[GenericAccessibleObject]:
        """Get all known modifiers for a type.

        Args:
            typ: The type

        Returns:
            The set of all accessibles that can modify the type  # noqa: DAR202
        """

    @property
    @abc.abstractmethod
    def generators(self) -> dict[ProperType, OrderedSet[GenericAccessibleObject]]:
        """Provides all available generators."""

    @property
    @abc.abstractmethod
    def modifiers(self) -> dict[TypeInfo, OrderedSet[GenericAccessibleObject]]:
        """Provides all available modifiers."""

    @abc.abstractmethod
    def get_random_accessible(self) -> GenericAccessibleObject | None:
        """Provides a random accessible of the unit under test.

        Returns:
            A random accessible, or None if there is none  # noqa: DAR202
        """

    @abc.abstractmethod
    def get_random_call_for(self, typ: ProperType) -> GenericAccessibleObject:
        """Get a random modifier for the given type.

        Args:
            typ: The type

        Returns:
            A random modifier for that type  # noqa: DAR202

        Raises:
            ConstructionFailedException: if no modifiers for the type
                exist# noqa: DAR402
        """

    @abc.abstractmethod
    def get_all_generatable_types(self) -> list[ProperType]:
        """Provides all types that can be generated.

        This includes primitives and collections.

        Returns:
            A list of all types that can be generated  # noqa: DAR202
        """

    @abc.abstractmethod
    def select_concrete_type(self, typ: ProperType) -> ProperType:
        """Select a concrete type from the given type.

        This is required, for example, when handling union types.  Currently, only
        unary types, Any, and Union are handled.

        Args:
            typ: An optional type

        Returns:
            An optional type  # noqa: DAR202
        """

    @abc.abstractmethod
    def track_statistics_values(self, tracking_fun: Callable[[RuntimeVariable, Any], None]) -> None:
        """Track statistics values from the test cluster and its items.

        Args:
            tracking_fun: The tracking function as a callback.
        """

    @abc.abstractmethod
    def update_return_type(
        self, accessible: GenericCallableAccessibleObject, new_type: ProperType
    ) -> None:
        """Update the return for the given accessible to the new seen type.

        Args:
            accessible: the accessible that was observed
            new_type: the new return type
        """

    @abc.abstractmethod
    def update_parameter_knowledge(
        self,
        accessible: GenericCallableAccessibleObject,
        param_name: str,
        knowledge: tt.UsageTraceNode,
    ) -> None:
        """Update the knowledge about the parameter of the given accessible.

        Args:
            accessible: the accessible that was observed.
            param_name: the parameter name for which we have new information.
            knowledge: the new information.
        """


@dataclasses.dataclass
class SignatureInfo:
    """Another utility class to group information per callable."""

    # A dictionary mapping parameter names and to their developer annotated parameters
    # types.
    # Does not include self, etc.
    annotated_parameter_types: dict[str, str] = dataclasses.field(default_factory=dict)

    # Similar to above, but with guessed parameters types.
    # Contains multiples type guesses.
    guessed_parameter_types: dict[str, list[str]] = dataclasses.field(default_factory=dict)

    # Needed to compute top-n accuracy in the evaluation.
    # Elements are of form (A,B); A is a guess, B is an annotated type.
    # (A,B) is only present, when A is a base type match of B.
    # If it is present, it points to the partial type match between A and B.
    partial_type_matches: dict[str, str] = dataclasses.field(default_factory=dict)

    # Annotated return type, if Any.
    # Does not include constructors.
    annotated_return_type: str | None = None

    # Recorded return type, if Any.
    recorded_return_type: str | None = None


@dataclasses.dataclass
class TypeGuessingStats:
    """Class to gather some type guessing related statistics."""

    # Number of constructors in the MUT.
    number_of_constructors: int = 0

    # Maps names of callables to a signature info object.
    signature_infos: dict[str, SignatureInfo] = dataclasses.field(
        default_factory=lambda: defaultdict(SignatureInfo)
    )


def _serialize_helper(obj):
    """Utility to deal with non-serializable types.

    Args:
        obj: The object to serialize

    Returns:
        A serializable object.
    """
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, SignatureInfo):
        return dataclasses.asdict(obj)
    return obj


class ModuleTestCluster(TestCluster):  # noqa: PLR0904
    """A test cluster for a module.

    Contains all methods/constructors/functions and all required transitive
    dependencies.
    """

    def __init__(self, linenos: int) -> None:  # noqa: D107
        self.__type_system = TypeSystem()
        self.__linenos = linenos
        self.__generators: dict[ProperType, OrderedSet[GenericAccessibleObject]] = defaultdict(
            OrderedSet
        )

        # Modifier belong to a certain class, not type.
        self.__modifiers: dict[TypeInfo, OrderedSet[GenericAccessibleObject]] = defaultdict(
            OrderedSet
        )
        self.__accessible_objects_under_test: OrderedSet[GenericAccessibleObject] = OrderedSet()
        self.__function_data_for_accessibles: dict[GenericAccessibleObject, CallableData] = {}
        self.__ml_data_for_accessibles: dict[GenericAccessibleObject, MLCallableData] = {}

        # Keep track of all callables, this is only for statistics purposes.
        self.__callables: OrderedSet[GenericCallableAccessibleObject] = OrderedSet()

    def log_cluster_statistics(self) -> None:  # noqa: D102
        stats = TypeGuessingStats()
        for accessible in self.__accessible_objects_under_test:
            if isinstance(accessible, GenericCallableAccessibleObject):
                accessible.inferred_signature.log_stats_and_guess_signature(
                    accessible.is_constructor(), str(accessible), stats
                )
        stat.track_output_variable(
            RuntimeVariable.SignatureInfos,
            json.dumps(
                stats.signature_infos,
                default=_serialize_helper,
            ),
        )
        stat.track_output_variable(
            RuntimeVariable.NumberOfConstructors,
            str(stats.number_of_constructors),
        )
        self.__write_type_eval_py_output(stats)

    def __write_type_eval_py_output(self, stats: TypeGuessingStats):
        # Create a folder for the inferred types
        signatures_folder = Path(config.configuration.statistics_output.report_dir) / "signatures"
        signatures_folder.mkdir(parents=True, exist_ok=True)
        project_folder = signatures_folder / config.configuration.statistics_output.project_name
        project_folder.mkdir(parents=True, exist_ok=True)
        module_folder = project_folder / config.configuration.module_name.split(".")[-1]
        module_folder.mkdir(parents=True, exist_ok=True)

        # Dump the captured type information to a JSON file
        types_json = (
            module_folder / f"{config.configuration.module_name.split('.')[-1]}_result.json"
        )

        types_json.write_text(
            provide_json(
                f"{config.configuration.module_name.split('.')[-1]}.py",
                self.__accessible_objects_under_test,
                self.__function_data_for_accessibles,
                stats,
            ),
            encoding="utf-8",
        )

    def _drop_generator(self, accessible: GenericCallableAccessibleObject):
        gens = self.__generators.get(accessible.generated_type())
        if gens is None:
            return

        gens.discard(accessible)
        if len(gens) == 0:
            self.__generators.pop(accessible.generated_type())

    @staticmethod
    def _add_or_make_union(
        old_type: ProperType, new_type: ProperType, max_size: int = 5
    ) -> UnionType:
        if isinstance(old_type, UnionType):
            items = old_type.items
            if len(items) >= max_size or new_type in items:
                return old_type
            new_type = UnionType(tuple(sorted((*items, new_type))))
        elif old_type in {ANY, new_type}:
            new_type = UnionType((new_type,))
        else:
            new_type = UnionType(tuple(sorted((old_type, new_type))))
        return new_type

    def update_return_type(  # noqa: D102
        self, accessible: GenericCallableAccessibleObject, new_type: ProperType
    ) -> None:
        # Loosely map runtime type to proper type
        old_type = accessible.inferred_signature.return_type

        new_type = self._add_or_make_union(old_type, new_type)
        if old_type == new_type:
            # No change
            return
        self._drop_generator(accessible)
        # Must invalidate entire cache, because subtype relationship might also change
        # the return values which are not new_type or old_type.
        self.get_generators_for.cache_clear()
        self.get_all_generatable_types.cache_clear()
        accessible.inferred_signature.return_type = new_type
        self.__generators[new_type].add(accessible)

    def update_parameter_knowledge(  # noqa: D102
        self,
        accessible: GenericCallableAccessibleObject,
        param_name: str,
        knowledge: tt.UsageTraceNode,
    ) -> None:
        # Store new data
        accessible.inferred_signature.usage_trace[param_name].merge(knowledge)

    @property
    def type_system(self) -> TypeSystem:
        """Provides the type system.

        Returns:
            The type system.
        """
        return self.__type_system

    @property
    def linenos(self) -> int:  # noqa: D102
        return self.__linenos

    def add_generator(self, generator: GenericAccessibleObject) -> None:  # noqa: D102
        if isinstance(generator, GenericCallableAccessibleObject):
            self.__callables.add(generator)

        generated_type = generator.generated_type()
        if isinstance(generated_type, NoneType) or generated_type.accept(is_primitive_type):
            return
        self.__generators[generated_type].add(generator)

    def add_accessible_object_under_test(  # noqa: D102
        self, objc: GenericAccessibleObject, data: CallableData
    ) -> None:
        self.__accessible_objects_under_test.add(objc)
        self.__function_data_for_accessibles[objc] = data

    def add_modifier(  # noqa: D102
        self, typ: TypeInfo, obj: GenericAccessibleObject
    ) -> None:
        if isinstance(obj, GenericCallableAccessibleObject):
            self.__callables.add(obj)

        self.__modifiers[typ].add(obj)

    @property
    def accessible_objects_under_test(  # noqa: D102
        self,
    ) -> OrderedSet[GenericAccessibleObject]:
        return self.__accessible_objects_under_test

    @property
    def function_data_for_accessibles(  # noqa: D102
        self,
    ) -> dict[GenericAccessibleObject, CallableData]:
        return self.__function_data_for_accessibles

    def add_ml_data(self, obj: GenericAccessibleObject, data: MLCallableData) -> None:  # noqa: D102
        self.__ml_data_for_accessibles[obj] = data

    def get_ml_data_for(self, obj: GenericAccessibleObject) -> MLCallableData | None:  # noqa: D102
        return self.__ml_data_for_accessibles.get(obj)

    def num_accessible_objects_under_test(self) -> int:  # noqa: D102
        return len(self.__accessible_objects_under_test)

    @functools.lru_cache(maxsize=1024)
    def get_generators_for(  # noqa: D102
        self, typ: ProperType
    ) -> tuple[OrderedSet[GenericAccessibleObject], bool]:
        if isinstance(typ, AnyType):
            # Just take everything when it's Any.
            return (
                OrderedSet(itertools.chain.from_iterable(self.__generators.values())),
                False,
            )

        results: OrderedSet[GenericAccessibleObject] = OrderedSet()
        only_any = True
        for gen_type, generators in self.__generators.items():
            if self.__type_system.is_maybe_subtype(gen_type, typ):
                results.update(generators)
                # Set flag to False as soon as we encounter a generator that is not
                # for Any.
                only_any &= gen_type == ANY

        return results, only_any

    class _FindModifiers(TypeVisitor[OrderedSet[GenericAccessibleObject]]):
        """A visitor to find all modifiers for the given type."""

        def __init__(self, cluster: TestCluster):
            self.cluster = cluster

        def visit_any_type(self, left: AnyType) -> OrderedSet[GenericAccessibleObject]:
            # If it's Any just take everything.
            return OrderedSet(itertools.chain.from_iterable(self.cluster.modifiers.values()))

        def visit_none_type(self, left: NoneType) -> OrderedSet[GenericAccessibleObject]:
            return OrderedSet()

        def visit_instance(self, left: Instance) -> OrderedSet[GenericAccessibleObject]:
            result: OrderedSet[GenericAccessibleObject] = OrderedSet()
            for type_info in self.cluster.type_system.get_superclasses(left.type):
                result.update(self.cluster.modifiers[type_info])
            return result

        def visit_tuple_type(self, left: TupleType) -> OrderedSet[GenericAccessibleObject]:
            return OrderedSet()

        def visit_union_type(self, left: UnionType) -> OrderedSet[GenericAccessibleObject]:
            result: OrderedSet[GenericAccessibleObject] = OrderedSet()
            for element in left.items:
                result.update(element.accept(self))  # type: ignore[arg-type]
            return result

        def visit_unsupported_type(self, left: Unsupported) -> OrderedSet[GenericAccessibleObject]:
            raise NotImplementedError("This type shall not be used during runtime")

    def get_modifiers_for(  # noqa: D102
        self, typ: ProperType
    ) -> OrderedSet[GenericAccessibleObject]:
        return typ.accept(self._FindModifiers(self))

    @property
    def generators(  # noqa: D102
        self,
    ) -> dict[ProperType, OrderedSet[GenericAccessibleObject]]:
        return self.__generators

    @property
    def modifiers(  # noqa: D102
        self,
    ) -> dict[TypeInfo, OrderedSet[GenericAccessibleObject]]:
        return self.__modifiers

    def get_random_accessible(self) -> GenericAccessibleObject | None:  # noqa: D102
        if self.num_accessible_objects_under_test() == 0:
            return None
        return randomness.choice(self.__accessible_objects_under_test)

    def get_random_call_for(  # noqa: D102
        self, typ: ProperType
    ) -> GenericAccessibleObject:
        accessible_objects = self.get_modifiers_for(typ)
        if len(accessible_objects) == 0:
            raise ConstructionFailedException(f"No modifiers for {typ}")
        return randomness.choice(accessible_objects)

    @functools.lru_cache(maxsize=128)
    def get_all_generatable_types(self) -> list[ProperType]:  # noqa: D102
        generatable = OrderedSet(self.__generators.keys())
        generatable.update(self.type_system.primitive_proper_types)
        generatable.update(self.type_system.collection_proper_types)
        return list(generatable)

    def select_concrete_type(self, typ: ProperType) -> ProperType:  # noqa: D102
        if isinstance(typ, AnyType):
            typ = randomness.choice(self.get_all_generatable_types())
        if isinstance(typ, UnionType):
            typ = self.select_concrete_type(randomness.choice(typ.items))
        return typ

    def track_statistics_values(  # noqa: D102
        self, tracking_fun: Callable[[RuntimeVariable, Any], None]
    ) -> None:
        tracking_fun(
            RuntimeVariable.AccessibleObjectsUnderTest,
            self.num_accessible_objects_under_test(),
        )
        tracking_fun(RuntimeVariable.GeneratableTypes, len(self.get_all_generatable_types()))

        cyclomatic_complexities = self.__compute_cyclomatic_complexities(
            self.function_data_for_accessibles.values()
        )
        if cyclomatic_complexities is not None:
            tracking_fun(RuntimeVariable.McCabeAST, json.dumps(cyclomatic_complexities))
            tracking_fun(RuntimeVariable.LineNos, self.__linenos)

    @staticmethod
    def __compute_cyclomatic_complexities(
        callable_data: typing.Iterable[CallableData],
    ) -> list[int]:
        # Collect complexities only for callables that had an AST.  Their minimal
        # complexity is 1, the value None symbolises a callable that had no AST present,
        # either because there is none or because it is an implicitly added function,
        # such as a default constructor or the constructor of a base class.
        return [
            item.cyclomatic_complexity
            for item in callable_data
            if item.cyclomatic_complexity is not None
        ]


class FilteredModuleTestCluster(TestCluster):  # noqa: PLR0904
    """A test cluster wrapping another test cluster.

    Delegates most methods to the wrapped delegate.  This cluster filters out
    accessible objects under test that are already fully covered, in order to focus
    the search on areas that are not yet fully covered.
    """

    @property
    def type_system(self) -> TypeSystem:  # noqa: D102
        return self.__delegate.type_system

    def update_return_type(  # noqa: D102
        self, accessible: GenericCallableAccessibleObject, new_type: ProperType
    ) -> None:
        self.__delegate.update_return_type(accessible, new_type)

    def update_parameter_knowledge(  # noqa: D102
        self,
        accessible: GenericCallableAccessibleObject,
        param_name: str,
        knowledge: tt.UsageTraceNode,
    ) -> None:
        self.__delegate.update_parameter_knowledge(accessible, param_name, knowledge)

    @property
    def linenos(self) -> int:  # noqa: D102
        return self.__delegate.linenos

    def log_cluster_statistics(self) -> None:  # noqa: D102
        self.__delegate.log_cluster_statistics()

    def add_generator(self, generator: GenericAccessibleObject) -> None:  # noqa: D102
        self.__delegate.add_generator(generator)

    def add_accessible_object_under_test(  # noqa: D102
        self, objc: GenericAccessibleObject, data: CallableData
    ) -> None:
        self.__delegate.add_accessible_object_under_test(objc, data)

    def add_modifier(  # noqa: D102
        self, typ: TypeInfo, obj: GenericAccessibleObject
    ) -> None:
        self.__delegate.add_modifier(typ, obj)

    @property
    def function_data_for_accessibles(  # noqa: D102
        self,
    ) -> dict[GenericAccessibleObject, CallableData]:
        return self.__delegate.function_data_for_accessibles

    def add_ml_data(self, obj: GenericAccessibleObject, data: MLCallableData) -> None:  # noqa: D102
        self.__delegate.add_ml_data(obj, data)

    def get_ml_data_for(self, obj: GenericAccessibleObject) -> MLCallableData | None:  # noqa: D102
        return self.__delegate.get_ml_data_for(obj)

    def track_statistics_values(  # noqa: D102
        self, tracking_fun: Callable[[RuntimeVariable, Any], None]
    ) -> None:
        self.__delegate.track_statistics_values(tracking_fun)

    def __init__(  # noqa: D107
        self,
        delegate: ModuleTestCluster,
        archive: arch.Archive,
        subject_properties: SubjectProperties,
        targets: OrderedSet[ff.TestCaseFitnessFunction],
    ) -> None:
        self.__delegate = delegate
        self.__subject_properties = subject_properties

        existing_code_objects = {
            metadata.code_object: code_object_id
            for code_object_id, metadata in subject_properties.existing_code_objects.items()
        }

        self.__code_object_id_to_accessible_objects = {
            existing_code_objects[acc.callable.__code__]: acc
            for acc in delegate.accessible_objects_under_test
            if isinstance(acc, GenericCallableAccessibleObject)
            and hasattr(acc.callable, "__code__")
            and acc.callable.__code__ in existing_code_objects
        }
        # Checking for __code__ is necessary, because the __init__ of a class that
        # does not define __init__ points to some internal CPython stuff.

        self.__accessible_to_targets: dict[GenericCallableAccessibleObject, OrderedSet] = {
            acc: OrderedSet() for acc in self.__code_object_id_to_accessible_objects.values()
        }
        for target in targets:
            if (acc := self.__get_accessible_object_for_target(target)) is not None:
                targets_for_acc = self.__accessible_to_targets[acc]
                targets_for_acc.add(target)

        # Get informed by archive when a target is covered
        archive.add_on_target_covered(self.on_target_covered)

    def __get_accessible_object_for_target(
        self, target: ff.TestCaseFitnessFunction
    ) -> GenericCallableAccessibleObject | None:
        code_object_id: int | None = target.code_object_id
        while code_object_id is not None:
            if (
                acc := self.__code_object_id_to_accessible_objects.get(code_object_id, None)
            ) is not None:
                return acc
            code_object_id = self.__subject_properties.existing_code_objects[
                code_object_id
            ].parent_code_object_id
        return None

    def on_target_covered(self, target: ff.TestCaseFitnessFunction) -> None:
        """A callback function to get informed by an archive when a target is covered.

        Args:
            target: The newly covered target
        """
        acc = self.__get_accessible_object_for_target(target)
        if acc is not None:
            targets_for_acc = self.__accessible_to_targets.get(acc)
            assert targets_for_acc is not None
            targets_for_acc.remove(target)
            if len(targets_for_acc) == 0:
                self.__accessible_to_targets.pop(acc)
                LOGGER.debug(
                    "Removed %s from test cluster because all targets within it have been covered.",
                    acc,
                )

    @property
    def accessible_objects_under_test(  # noqa: D102
        self,
    ) -> OrderedSet[GenericAccessibleObject]:
        accessibles = self.__accessible_to_targets.keys()
        if len(accessibles) == 0:
            # Should never happen, just in case everything is already covered?
            return self.__delegate.accessible_objects_under_test
        return OrderedSet(accessibles)

    def num_accessible_objects_under_test(self) -> int:  # noqa: D102
        return self.__delegate.num_accessible_objects_under_test()

    def get_generators_for(  # noqa: D102
        self, typ: ProperType
    ) -> tuple[OrderedSet[GenericAccessibleObject], bool]:
        return self.__delegate.get_generators_for(typ)

    def get_modifiers_for(  # noqa: D102
        self, typ: ProperType
    ) -> OrderedSet[GenericAccessibleObject]:
        return self.__delegate.get_modifiers_for(typ)

    @property
    def generators(  # noqa: D102
        self,
    ) -> dict[ProperType, OrderedSet[GenericAccessibleObject]]:
        return self.__delegate.generators

    @property
    def modifiers(  # noqa: D102
        self,
    ) -> dict[TypeInfo, OrderedSet[GenericAccessibleObject]]:
        return self.__delegate.modifiers

    def get_random_accessible(self) -> GenericAccessibleObject | None:  # noqa: D102
        accessibles = self.__accessible_to_targets.keys()
        if len(accessibles) == 0:
            return self.__delegate.get_random_accessible()
        return randomness.choice(OrderedSet(accessibles))

    def get_random_call_for(  # noqa: D102
        self, typ: ProperType
    ) -> GenericAccessibleObject:
        return self.__delegate.get_random_call_for(typ)

    def get_all_generatable_types(self) -> list[ProperType]:  # noqa: D102
        return self.__delegate.get_all_generatable_types()

    def select_concrete_type(self, typ: ProperType) -> ProperType:  # noqa: D102
        return self.__delegate.select_concrete_type(typ)


def __get_mccabe_complexity(tree: AstroidFunctionDef | None) -> int | None:
    if tree is None:
        return None
    try:
        return mccabe_complexity(astroid_to_ast(tree))
    except SyntaxError:
        return None


def __is_constructor(method_name: str) -> bool:
    return method_name == "__init__"


def __is_annotate(method_name: str) -> bool:
    return method_name == "__annotate_func__"


def __is_protected(method_name: str) -> bool:
    return method_name.startswith("_") and not method_name.startswith("__")


def __is_private(method_name: str) -> bool:
    return method_name.startswith("__") and not method_name.endswith("__")


def __is_method_defined_in_class(class_: type | types.UnionType, method: object) -> bool:
    return class_ == get_class_that_defined_method(method)


@dataclasses.dataclass
class CallableData:
    """Provides all information on callables.

    While the accessible is available for every callable, the other fields are only
    filled for methods that are available in (Python) source code because their
    information is retrieved from the abstract syntax tree.

    Attributes:
        accessible: the accessible object itself
        tree: the AST of the callable, if any
        description: the function description of the callable, if any
        cyclomatic_complexity: the McCabe cyclomatic complexity of the callable, if any
    """

    accessible: GenericAccessibleObject
    tree: AstroidFunctionDef | None
    description: FunctionDescription | None
    cyclomatic_complexity: int | None


@dataclasses.dataclass
class MLCallableData:
    """Provides ML-specific information on callables.

    Attributes:
        parameters: A dictionary of parameters, if any
        generation_order: The generation order of the callable (can be empty)
    """

    parameters: dict[str, MLParameter | None]
    generation_order: list[str]


def _get_lambda_assigned_name(module_tree, lambda_lineno) -> str | None:
    """Retrieve the variable name of a lambda assignment.

    Example:
        For a lambda defined at line 10:
            y = lambda: 42
        this function will return "y" if the lambda node starts at line 10.
    """
    for node in module_tree.body:
        if isinstance(node, Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if (
                hasattr(target, "name")
                and isinstance(node.value, Lambda)
                and node.value.lineno == lambda_lineno
            ):
                return target.name
    return None


def __analyse_function(
    *,
    func_name: str,
    func: FunctionType,
    type_inference_provider: InferenceProvider,
    module_tree: Module | None,
    test_cluster: ModuleTestCluster,
    add_to_test: bool,
) -> None:
    if __is_private(func_name) or __is_protected(func_name):
        LOGGER.debug("Skipping function %s from analysis", func_name)
        return
    if inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func):
        if add_to_test:
            raise CoroutineFoundException("Found coroutine in SUT: %s", func_name)
        # Coroutine outside the SUT are not problematic, just exclude them.
        LOGGER.debug("Skipping coroutine %s outside of SUT", func_name)
        return

    LOGGER.debug("Analysing function %s", func_name)
    inferred_signature = test_cluster.type_system.infer_type_info(
        func,
        type_inference_provider=type_inference_provider,
    )
    func_ast = get_function_node_from_ast(module_tree, func_name)
    description = get_function_description(func_ast)
    raised_exceptions = description.raises if description is not None else set()
    cyclomatic_complexity = __get_mccabe_complexity(func_ast)
    if getattr(func, "__name__", None) == "<lambda>":
        if lambda_assigned_name := _get_lambda_assigned_name(
            module_tree, func.__code__.co_firstlineno
        ):
            func_name = lambda_assigned_name
            func.__name__ = lambda_assigned_name
        else:
            # If the lambda itself has no name, we must not add it to the test cluster
            # or else it will cause an exception during test export.
            return

    generic_function = GenericFunction(func, inferred_signature, raised_exceptions, func_name)

    if config.configuration.pynguinml.ml_testing_enabled and module_tree is not None:
        parameters: dict[str, MLParameter | None] = {}
        generation_order: list[str] = []

        try:
            parameters, generation_order = tr.load_and_process_constraints(
                module_tree.name, func_name, list(inferred_signature.original_parameters.keys())
            )
        except ConstraintValidationError as e:
            LOGGER.warning("ConstraintValidationError occurred: %s. Skipping.", e)

        ml_data = MLCallableData(
            parameters=parameters,
            generation_order=generation_order,
        )
        test_cluster.add_ml_data(generic_function, ml_data)

    function_data = CallableData(
        accessible=generic_function,
        tree=func_ast,
        description=description,
        cyclomatic_complexity=cyclomatic_complexity,
    )
    test_cluster.add_generator(generic_function)
    if add_to_test:
        test_cluster.add_accessible_object_under_test(generic_function, function_data)


def __analyse_class(
    *,
    type_info: TypeInfo,
    type_inference_provider: InferenceProvider,
    module_tree: Module | None,
    test_cluster: ModuleTestCluster,
    add_to_test: bool,
) -> None:
    LOGGER.debug("Analysing class %s", type_info)
    class_ast = get_class_node_from_ast(module_tree, type_info.name)
    __add_symbols(class_ast, type_info)
    if type_info.raw_type is tuple:
        # Tuple is problematic...
        return

    constructor_ast = get_function_node_from_ast(class_ast, "__init__")
    description = get_function_description(constructor_ast)
    raised_exceptions = description.raises if description is not None else set()
    cyclomatic_complexity = __get_mccabe_complexity(constructor_ast)

    if issubclass(type_info.raw_type, enum.Enum):  # type: ignore[arg-type]
        generic: GenericEnum | GenericConstructor = GenericEnum(type_info)
        if isinstance(generic, GenericEnum) and len(generic.names) == 0:
            LOGGER.debug(
                "Skipping enum %s from test cluster, it has no fields.",
                type_info.full_name,
            )
            return
    else:
        generic = GenericConstructor(
            type_info,
            test_cluster.type_system.infer_type_info(
                type_info.raw_type.__init__,  # type: ignore[misc]
                type_inference_provider=type_inference_provider,
            ),
            raised_exceptions,
        )
        generic.inferred_signature.return_type = test_cluster.type_system.convert_type_hint(
            type_info.raw_type
        )

    if (
        config.configuration.pynguinml.ml_testing_enabled
        and type_info.raw_type.__module__ != "builtins"
        and not isinstance(generic, GenericEnum)
    ):
        parameters: dict[str, MLParameter | None] = {}
        generation_order: list[str] = []

        try:
            parameters, generation_order = tr.load_and_process_constraints(
                type_info.module,
                type_info.name,
                list(generic.inferred_signature.original_parameters.keys()),
            )
        except ConstraintValidationError as e:
            LOGGER.warning("ConstraintValidationError occurred: %s. Skipping.", e)

        ml_data = MLCallableData(
            parameters=parameters,
            generation_order=generation_order,
        )
        test_cluster.add_ml_data(generic, ml_data)

    method_data = CallableData(
        accessible=generic,
        tree=constructor_ast,
        description=description,
        cyclomatic_complexity=cyclomatic_complexity,
    )
    if not (
        type_info.is_abstract
        or type_info.raw_type in COLLECTIONS
        or type_info.raw_type in PRIMITIVES
    ):
        # Don't add constructors for abstract classes and for builtins. We generate
        # the latter ourselves.
        test_cluster.add_generator(generic)
        if add_to_test:
            test_cluster.add_accessible_object_under_test(generic, method_data)

    try:
        methods_with_names = inspect.getmembers(type_info.raw_type, inspect.isfunction)
    except Exception as ex:  # noqa: BLE001
        LOGGER.error("Could not get members for class %s: %s", type_info.full_name, str(ex))
        return

    for method_name, method in methods_with_names:
        __analyse_method(
            type_info=type_info,
            method_name=method_name,
            method=method,
            type_inference_provider=type_inference_provider,
            class_tree=class_ast,
            test_cluster=test_cluster,
            add_to_test=add_to_test,
        )


# Some symbols are not interesting for us.
IGNORED_SYMBOLS: set[str] = {
    "__new__",
    "__init__",
    "__del__",
    "__repr__",
    "__str__",
    "__sizeof__",
    "__getattribute__",
    "__getattr__",
}


def __add_symbols(class_ast: ClassDef | None, type_info: TypeInfo) -> None:
    """Tries to infer what symbols can be found on an instance of the given class.

    We also try to infer what attributes are defined in '__init__'.

    Args:
        class_ast: The AST Node of the class.
        type_info: The type info.
    """
    if class_ast is not None:
        type_info.instance_attributes.update(tuple(class_ast.instance_attrs))
    type_info.attributes.update(type_info.instance_attributes)
    type_info.attributes.update(tuple(vars(type_info.raw_type)))
    type_info.attributes.difference_update(IGNORED_SYMBOLS)


def __analyse_method(
    *,
    type_info: TypeInfo,
    method_name: str,
    method: (FunctionType | BuiltinFunctionType | WrapperDescriptorType | MethodDescriptorType),
    type_inference_provider: InferenceProvider,
    class_tree: ClassDef | None,
    test_cluster: ModuleTestCluster,
    add_to_test: bool,
) -> None:
    if (
        __is_annotate(method_name)
        or __is_private(method_name)
        or __is_protected(method_name)
        or __is_constructor(method_name)
        or not __is_method_defined_in_class(type_info.raw_type, method)
    ):
        LOGGER.debug("Skipping method %s from analysis", method_name)
        return
    if inspect.iscoroutinefunction(method) or inspect.isasyncgenfunction(method):
        if add_to_test:
            raise CoroutineFoundException("Found coroutine in SUT: %s", method_name)
        # Coroutine outside the SUT are not problematic, just exclude them.
        LOGGER.debug("Skipping coroutine %s outside of SUT", method_name)
        return

    LOGGER.debug("Analysing method %s.%s", type_info.full_name, method_name)
    inferred_signature = test_cluster.type_system.infer_type_info(
        method,
        type_inference_provider=type_inference_provider,
    )
    method_ast = get_function_node_from_ast(class_tree, method_name)
    description = get_function_description(method_ast)
    raised_exceptions = description.raises if description is not None else set()
    cyclomatic_complexity = __get_mccabe_complexity(method_ast)
    generic_method = GenericMethod(
        type_info, method, inferred_signature, raised_exceptions, method_name
    )

    if config.configuration.pynguinml.ml_testing_enabled:
        parameters: dict[str, MLParameter | None] = {}
        generation_order: list[str] = []

        callable_name = type_info.name + "." + method_name
        try:
            parameters, generation_order = tr.load_and_process_constraints(
                type_info.module, callable_name, list(inferred_signature.original_parameters.keys())
            )
        except ConstraintValidationError as e:
            LOGGER.warning("ConstraintValidationError occurred: %s. Skipping.", e)

        ml_data = MLCallableData(
            parameters=parameters,
            generation_order=generation_order,
        )
        test_cluster.add_ml_data(generic_method, ml_data)

    method_data = CallableData(
        accessible=generic_method,
        tree=method_ast,
        description=description,
        cyclomatic_complexity=cyclomatic_complexity,
    )
    test_cluster.add_generator(generic_method)
    test_cluster.add_modifier(type_info, generic_method)
    if add_to_test:
        test_cluster.add_accessible_object_under_test(generic_method, method_data)


class _ParseResults(dict):  # noqa: FURB189
    def __missing__(self, key):
        # Parse module on demand
        res = self[key] = parse_module(key)
        return res


def __resolve_dependencies(
    root_module: _ModuleParseResult,
    type_inference_provider: InferenceProvider,
    test_cluster: ModuleTestCluster,
) -> None:
    parse_results: dict[str, _ModuleParseResult] = _ParseResults()
    parse_results[root_module.module_name] = root_module

    # Provide a set of seen modules, classes and functions for fixed-point iteration
    seen_modules: set[ModuleType] = set()
    seen_classes: set[Any] = set()
    seen_functions: set[Any] = set()

    # Set of C-extension modules that are not whitelisted
    dangerous_c_modules: set[str] = set()

    # Always analyse builtins
    __analyse_included_classes(
        module=builtins,
        root_module_name=root_module.module_name,
        type_inference_provider=type_inference_provider,
        test_cluster=test_cluster,
        seen_classes=seen_classes,
        parse_results=parse_results,
    )
    test_cluster.type_system.enable_numeric_tower()

    # Start with root module, i.e., the module under test.
    wait_list: queue.SimpleQueue[ModuleType] = queue.SimpleQueue()
    wait_list.put(root_module.module)

    while not wait_list.empty():
        current_module = wait_list.get()
        if current_module in seen_modules:
            # Skip the module, we have already analysed it before
            continue
        if _is_blacklisted(current_module):
            # Don't include anything from the blacklist
            continue

        # Check if the module contains c extensions that are not whitelisted
        dangerous_c_modules.update(
            __check_c_modules(
                module=current_module,
            )
        )

        # Analyze all classes found in the current module
        __analyse_included_classes(
            module=current_module,
            root_module_name=root_module.module_name,
            type_inference_provider=type_inference_provider,
            test_cluster=test_cluster,
            seen_classes=seen_classes,
            parse_results=parse_results,
        )

        # Analyze all functions found in the current module
        __analyse_included_functions(
            module=current_module,
            root_module_name=root_module.module_name,
            type_inference_provider=type_inference_provider,
            test_cluster=test_cluster,
            seen_functions=seen_functions,
            parse_results=parse_results,
        )

        # Collect the modules that are included by this module and add
        # them for further processing.
        for included_module in filter(inspect.ismodule, vars(current_module).values()):
            wait_list.put(included_module)

        # Take care that we know for future iterations that we have already analysed
        # this module before
        seen_modules.add(current_module)
    LOGGER.info("Analyzed project to create test cluster")
    LOGGER.info("Modules:   %5i", len(seen_modules))
    LOGGER.info("Functions: %5i", len(seen_functions))
    LOGGER.info("Classes:   %5i", len(seen_classes))
    _handle_c_modules(dangerous_c_modules)

    test_cluster.type_system.push_attributes_down()


def __analyse_included_classes(
    *,
    module: ModuleType,
    root_module_name: str,
    type_inference_provider: InferenceProvider,
    test_cluster: ModuleTestCluster,
    parse_results: dict[str, _ModuleParseResult],
    seen_classes: set[type],
) -> None:
    values = list(vars(module).values())
    work_list = list(
        filter(
            lambda x: inspect.isclass(x) and not _is_blacklisted(x),
            values,
        )
    )

    # TODO(fk) inner classes?
    while len(work_list) > 0:
        current = work_list.pop(0)
        if current in seen_classes:
            continue
        seen_classes.add(current)

        type_info = test_cluster.type_system.to_type_info(current)

        # Skip if the class is _ObjectProxyMethods, as it is broken
        # since __module__ is not well defined on it.
        if isinstance(current.__module__, property):
            LOGGER.info("Skipping class that has a property __module__: %s", current)
            continue

        # Skip some C-extension modules that are not publicly accessible.
        try:
            results = parse_results[current.__module__]
        except ModuleNotFoundError as error:
            if getattr(current, "__file__", None) is None or Path(current.__file__).suffix in {
                ".so",
                ".pyd",
            }:
                LOGGER.info("C-extension module not found: %s", current.__module__)
                continue
            raise error

        __analyse_class(
            type_info=type_info,
            type_inference_provider=type_inference_provider,
            module_tree=results.syntax_tree,
            test_cluster=test_cluster,
            add_to_test=current.__module__ == root_module_name,
        )

        if hasattr(current, "__bases__"):
            for base in current.__bases__:
                # TODO(fk) base might be an instance.
                #  Ignored for now.
                #  Probably store Instance in graph instead of TypeInfo?
                if isinstance(base, GenericAlias):
                    base = base.__origin__  # noqa: PLW2901

                base_info = test_cluster.type_system.to_type_info(base)
                test_cluster.type_system.add_subclass_edge(
                    super_class=base_info, sub_class=type_info
                )
                work_list.append(base)


def __analyse_included_functions(
    *,
    module: ModuleType,
    root_module_name: str,
    type_inference_provider: InferenceProvider,
    test_cluster: ModuleTestCluster,
    parse_results: dict[str, _ModuleParseResult],
    seen_functions: set,
) -> None:
    for current in filter(
        lambda x: inspect.isfunction(x) and not _is_blacklisted(x),
        vars(module).values(),
    ):
        if current in seen_functions:
            continue
        seen_functions.add(current)
        __analyse_function(
            func_name=current.__qualname__,
            func=current,
            type_inference_provider=type_inference_provider,
            module_tree=parse_results[current.__module__].syntax_tree,
            test_cluster=test_cluster,
            add_to_test=current.__module__ == root_module_name,
        )


def __check_c_modules(
    *,
    module: ModuleType,
) -> set[str]:
    """Return the names of modules containing non-whitelisted C extensions.

    Args:
        module: The module to check

    Returns:
        A set of module names with non-whitelisted C code.
    """
    non_whitelisted_modules = set()

    # If the whole module file looks like a binary extension:
    module_file = getattr(module, "__file__", "")
    if module_file and Path(module_file).suffix in {".so", ".pyd"}:
        if not _c_is_whitelisted(module):
            non_whitelisted_modules.add(module.__name__)
        return non_whitelisted_modules

    # If the module is Python, inspect its members too:
    for element in vars(module).values():
        if inspect.isfunction(element) or inspect.isclass(element):
            try:
                inspect.getsource(element)
                # Source is available => likely pure Python.
            except Exception:  # noqa: BLE001
                # No source => likely compiled or builtin.
                if not _c_is_whitelisted(module):
                    non_whitelisted_modules.add(module.__name__)

    return non_whitelisted_modules


def analyse_module(
    parsed_module: _ModuleParseResult,
    type_inference_strategy: TypeInferenceStrategy = TypeInferenceStrategy.TYPE_HINTS,
) -> ModuleTestCluster:
    """Analyses a module to build a test cluster.

    Args:
        parsed_module: The parsed module
        type_inference_strategy: The type inference strategy to use.

    Returns:
        A test cluster for the module
    """
    test_cluster = ModuleTestCluster(linenos=parsed_module.linenos)

    type_provider = get_type_provider(
        type_inference_strategy, parsed_module.module, test_cluster.type_system
    )

    __resolve_dependencies(
        root_module=parsed_module,
        type_inference_provider=type_provider,
        test_cluster=test_cluster,
    )
    collect_provider_metrics(type_provider)
    return test_cluster


def generate_test_cluster(
    module_name: str,
    type_inference_strategy: TypeInferenceStrategy = TypeInferenceStrategy.TYPE_HINTS,
) -> ModuleTestCluster:
    """Generates a new test cluster from the given module.

    Args:
        module_name: The name of the root module
        type_inference_strategy: Which type-inference strategy to use

    Returns:
        A new test cluster for the given module
    """
    return analyse_module(parse_module(module_name), type_inference_strategy)


def get_type_provider(
    type_inference_strategy: TypeInferenceStrategy, module: ModuleType, type_system: TypeSystem
) -> InferenceProvider:
    """Get the initialised inference provider for the given strategy.

    Args:
        type_inference_strategy: The type inference strategy to use
        module: The module to analyse (only needed for LLM-based inference)
        type_system: The type system to use

    Returns:
        The type inference provider for the given strategy
    """
    match type_inference_strategy:
        case TypeInferenceStrategy.LLM:
            callables = _collect_public_callables(module)
            return LLMInference(callables, LLMProvider.OPENAI, type_system)
        case TypeInferenceStrategy.TYPE_HINTS:
            return HintInference()
        case TypeInferenceStrategy.NONE:
            return NoInference()
        case _:
            LOGGER.error(
                "Unknown type inference strategy: '%s'. Falling back to NoInference.",
                type_inference_strategy,
            )
            return NoInference()


def _collect_public_callables(module: ModuleType) -> Sequence[Callable[..., Any]]:
    """Collects a list of all public accessibles in a module."""
    callables = []
    seen = set()

    def add(obj):
        if id(obj) not in seen:
            callables.append(obj)
            seen.add(id(obj))

    for name, obj in vars(module).items():
        if name.startswith("_") and name != "__init__":
            continue
        if inspect.isfunction(obj) and obj.__module__ == module.__name__:
            add(obj)

    for cls_name, cls in vars(module).items():
        if (
            cls_name.startswith("_")
            or not inspect.isclass(cls)
            or cls.__module__ != module.__name__
        ):
            continue
        for meth_name, member in inspect.getmembers(cls, predicate=inspect.isfunction):
            if not meth_name.startswith("_"):
                add(member)

    return callables


def collect_provider_metrics(typ_provider: InferenceProvider):
    """Collects metrics from the given type inference provider.

    currently, this only works for LLM-based providers.

    When using an LLM-based provider, collect the raw inferred
    parameter strings per callable and the annotated parameter strings
    as JSON and store in the LLMInferredSignatures runtime variable.

    Other providers default all metrics to zero.
    """
    metrics = typ_provider.get_metrics()
    stat.track_output_variable(
        RuntimeVariable.TypeInferenceInferredParameters, metrics.get("successful_inferences", 0)
    )
    stat.track_output_variable(
        RuntimeVariable.TypeInferenceFailedParameters, metrics.get("failed_inferences", 0)
    )
    stat.track_output_variable(
        RuntimeVariable.TypeInferenceLLMCalls, metrics.get("sent_requests", 0)
    )
    stat.track_output_variable(
        RuntimeVariable.TypeInferenceLLMTime, metrics.get("total_setup_time", 0.0)
    )

    if isinstance(typ_provider, LLMInference):
        try:
            inferred_signatures: dict[str, dict] = {}

            inference_map = typ_provider.get_inference_map()
            callables = typ_provider.get_callables()

            for func in callables:
                # Build a stable key: module.qualname when possible
                module_part = getattr(func, "__module__", "")
                qualname_part = getattr(func, "__qualname__", None)
                key = str(func) if qualname_part is None else f"{module_part}.{qualname_part}"

                # Annotated parameter strings (prior), fallback to typing.Any
                try:
                    prior = typ_provider.prior_types_for(func)
                except (
                    Exception  # noqa: BLE001
                ) as exc:  # narrow catch for unexpected provider failures
                    LOGGER.debug("Could not obtain prior types for %s: %s", func, exc)
                    prior = {}

                guessed_raw = inference_map.get(func, {})

                params = set(prior.keys()) | set(guessed_raw.keys())

                annotated_parameter_types: dict[str, str] = {}
                guessed_parameter_types: dict[str, list[str]] = {}

                for p in params:
                    if p in {"*args", "**kwargs"}:
                        annotated_parameter_types[p] = ANY_STR
                    else:
                        annotated_parameter_types[p] = prior.get(p, ANY_STR)

                    guess = guessed_raw.get(p, "")
                    if isinstance(guess, str) and guess.strip():
                        guessed_parameter_types[p] = [guess.strip()]
                    else:
                        guessed_parameter_types[p] = []

                inferred_signatures[key] = {
                    "annotated_parameter_types": annotated_parameter_types,
                    "guessed_parameter_types": guessed_parameter_types,
                    "partial_type_matches": {},
                    "annotated_return_type": None,
                    "recorded_return_type": None,
                }

            stat.track_output_variable(
                RuntimeVariable.LLMInferredSignatures, json.dumps(inferred_signatures)
            )
        except Exception as exc:  # Catch at top-level to ensure metrics don't break analysis
            LOGGER.exception("Could not collect LLM inferred signatures: %s", exc)
    else:
        LOGGER.warning(
            "Type inference provider is not LLM-based, skipping inferred signatures collection."
        )
