#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides analyses for the subject module, based on the module and its AST."""
from __future__ import annotations

import ast
import dataclasses
import enum
import importlib
import inspect
import itertools
import json
import logging
import queue
import sys
import typing
from collections import namedtuple
from statistics import mean, median
from types import (
    BuiltinFunctionType,
    FunctionType,
    MethodDescriptorType,
    ModuleType,
    WrapperDescriptorType,
)
from typing import Any, Callable, NamedTuple, get_args

from ordered_set import OrderedSet
from typing_inspect import is_union_type

from pynguin.analyses.modulecomplexity import mccabe_complexity
from pynguin.analyses.syntaxtree import (
    FunctionDescription,
    get_all_classes,
    get_all_functions,
    get_function_descriptions,
)
from pynguin.analyses.types import (
    InheritanceGraph,
    TypeInferenceStrategy,
    TypeWrapper,
    infer_type_info,
)
from pynguin.instrumentation.instrumentation import CODE_OBJECT_ID_KEY
from pynguin.utils import randomness, type_utils
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
    GenericConstructor,
    GenericEnum,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.statistics.runtimevariable import RuntimeVariable
from pynguin.utils.type_utils import (
    COLLECTIONS,
    PRIMITIVES,
    extract_non_generic_class,
    get_class_that_defined_method,
)

if typing.TYPE_CHECKING:
    import pynguin.ga.computations as ff
    import pynguin.generation.algorithms.archive as arch
    from pynguin.testcase.execution import KnownData
    from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject

LOGGER = logging.getLogger(__name__)
ASTFunctionNodes = ast.FunctionDef | ast.AsyncFunctionDef

# A set of modules that shall be blacklisted from analysis (keep them sorted!!!):
# The modules that are listed here are not prohibited from execution, but Pynguin will
# not consider any classes or functions from these modules for generating inputs to
# other routines
MODULE_BLACKLIST = frozenset(
    (
        "__future__",
        "_thread",
        "abc",
        "argparse",
        "asyncio",
        "atexit",
        "builtins",
        "cmd",
        "code",
        "codeop",
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
    )
)


def _is_blacklisted(element: Any) -> bool:
    """Checks if the given element belongs to the blacklist.

    Args:
        element: The element to check

    Returns:
        Is the element blacklisted?
    """
    if inspect.ismodule(element):
        return element.__name__ in MODULE_BLACKLIST
    if inspect.isclass(element):
        return element.__module__ in MODULE_BLACKLIST
    if inspect.isfunction(element):
        # Some modules can be run standalone using a main function or provide a small
        # set of tests ('test'). We don't want to include those functions.
        return element.__module__ in MODULE_BLACKLIST or element.__name__ in (
            "main",
            "test",
        )
    # Something that is not supported yet.
    return False


class _ParseResult(NamedTuple):
    """A data wrapper for an imported and parsed module."""

    linenos: int
    module_name: str
    module: ModuleType
    syntax_tree: ast.AST | None
    type_inference_strategy: TypeInferenceStrategy


class _ArgumentAnnotationRemovalVisitor(ast.NodeTransformer):
    """Removes argument annotations from an AST."""

    # pylint: disable=missing-function-docstring
    def visit_arg(self, node: ast.arg) -> Any:
        node.annotation = ast.Name(id="Any", ctx=ast.Load())
        return node


class _ArgumentReturnAnnotationReplacementVisitor(ast.NodeTransformer):
    """Replaces type-annotations by typing.Any.

    An unannotated type is the same as `Any` hence, we replace it
    by the `Any` value.
    """

    class FindTypingAnyImportVisitor(ast.NodeVisitor):
        """A visitor checking for the existence of an ``from typing import Any``."""

        def __init__(self) -> None:
            self.__is_any_imported = False

        # pylint: disable=missing-function-docstring, invalid-name
        def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
            if node.module == "typing":
                for alias in node.names:
                    assert isinstance(alias, ast.alias)
                    if alias.name == "Any":
                        self.__is_any_imported = True
            return node

        @property
        def is_any_imported(self) -> bool:
            """Returns, whether ``Any`` is already imported.

            Returns:
                Whether ``Any`` is already imported
            """
            return self.__is_any_imported

    # pylint: disable=missing-function-docstring, invalid-name
    def visit_Module(self, node: ast.Module) -> Any:
        # Check whether there is an `from typing import Any` somewhere
        visitor = self.FindTypingAnyImportVisitor()
        visitor.visit(node)
        # Insert an `from typing import Any` to the module if there is not yet one
        if not visitor.is_any_imported:
            import_node = ast.ImportFrom(module="typing", names=[ast.alias(name="Any")])
            ast.copy_location(import_node, node)
            ast.fix_missing_locations(import_node)
            node.body.insert(0, import_node)

        return self.generic_visit(node)

    # pylint: disable=missing-function-docstring
    def visit_arg(self, node: ast.arg) -> Any:
        if node.annotation is None:
            node.annotation = ast.Name(id="Any", ctx=ast.Load())
        return self.generic_visit(node)

    # pylint: disable=missing-function-docstring, invalid-name
    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        if node.returns is None:
            node.returns = ast.Name(id="Any", ctx=ast.Load())
        return self.generic_visit(node)


def parse_module(
    module_name: str,
    type_inference: TypeInferenceStrategy = TypeInferenceStrategy.TYPE_HINTS,
) -> _ParseResult:
    """Parses a module and extracts its module-type and AST.

    If the source code is not available it is not possible to build an AST.  In this
    case the respective field of the :py:class:`_ParseResult` will contain the value
    ``None``.  This is the case, for example, for modules written in native code,
    for example, in C.

    Args:
        module_name: The fully-qualified name of the module
        type_inference: The type-inference strategy to use

    Returns:
        A tuple of the imported module type and its optional AST
    """
    module = importlib.import_module(module_name)

    try:
        source_file = inspect.getsourcefile(module)
        source_code = inspect.getsource(module)
        syntax_tree = ast.parse(
            source_code,
            filename=source_file if source_file is not None else "",
            type_comments=type_inference is not TypeInferenceStrategy.NONE,
            feature_version=sys.version_info[1],
        )
        if type_inference is TypeInferenceStrategy.NONE:
            # The parameter type_comments of the AST library's parse function does not
            # prevent that the annotation is present in the AST.  Thus, we explicitly
            # remove it if we do not want the types to be extracted.
            # This is a hack, maybe I do not understand how to use ast.parse properly...
            annotation_remover = _ArgumentAnnotationRemovalVisitor()
            annotation_remover.visit(syntax_tree)
        # Replace all occurrences of `object` or no type annotation by `Any`
        annotation_replacer = _ArgumentReturnAnnotationReplacementVisitor()
        annotation_replacer.visit(syntax_tree)
        syntax_tree = ast.fix_missing_locations(syntax_tree)
        linenos = len(source_code.splitlines())
    except OSError as error:
        LOGGER.warning(
            f"Could not retrieve source code for module {module_name} ({error}). "
            f"Cannot derive syntax tree to allow Pynguin using more precise analysis."
        )
        syntax_tree = None
        linenos = -1
    return _ParseResult(
        linenos=linenos,
        module_name=module_name,
        module=module,
        syntax_tree=syntax_tree,
        type_inference_strategy=type_inference,
    )


class ModuleTestCluster:
    """A test cluster for a module.

    Contains all methods/constructors/functions and all required transitive
    dependencies.
    """

    def __init__(self, linenos: int) -> None:
        self.__linenos = linenos
        self.__generators: dict[type, OrderedSet[GenericAccessibleObject]] = {}
        self.__modifiers: dict[type, OrderedSet[GenericAccessibleObject]] = {}
        self.__accessible_objects_under_test: OrderedSet[
            GenericAccessibleObject
        ] = OrderedSet()
        self.__function_data_for_accessibles: dict[
            GenericAccessibleObject, _CallableData
        ] = {}
        self.__inheritance_graph = InheritanceGraph()

    @property
    def inheritance_graph(self) -> InheritanceGraph:
        """Provides the inheritance graph.

        Returns:
            The inheritance graph.
        """
        return self.__inheritance_graph

    @property
    def linenos(self) -> int:
        """Provide the number of source code lines.

        Returns:
            The number of source code lines
        """
        return self.__linenos

    def add_generator(self, generator: GenericAccessibleObject) -> None:
        """Add the given accessible as a generator.

        Args:
            generator: The accessible object
        """
        generated_type = generator.generated_type()
        if (
            generated_type is None
            or type_utils.is_none_type(generated_type)
            or type_utils.is_primitive_type(generated_type)
        ):
            return
        if generated_type in self.__generators:
            self.__generators[generated_type].add(generator)
        else:
            self.__generators[generated_type] = OrderedSet([generator])

    def add_accessible_object_under_test(
        self, objc: GenericAccessibleObject, data: _CallableData
    ) -> None:
        """Add accessible object to the objects under test.

        Args:
            objc: The accessible object
            data: The function-description data
        """
        self.__accessible_objects_under_test.add(objc)
        self.__function_data_for_accessibles[objc] = data

    def add_modifier(self, type_: type, obj: GenericAccessibleObject) -> None:
        """Add a modifier.

        A modifier is something that can be used to modify the given type,
        for example, a method.

        Args:
            type_: The type that can be modified
            obj: The accessible that can modify
        """
        if type_ in self.__modifiers:
            self.__modifiers[type_].add(obj)
        else:
            self.__modifiers[type_] = OrderedSet([obj])

    @property
    def accessible_objects_under_test(self) -> OrderedSet[GenericAccessibleObject]:
        """Provides all accessible objects under test.

        Returns:
            The set of all accessible objects under test
        """
        return self.__accessible_objects_under_test

    @property
    def function_data_for_accessibles(
        self,
    ) -> dict[GenericAccessibleObject, _CallableData]:
        """Provides all function data for all accessibles.

        Returns:
            A dictionary of accessibles to their function data
        """
        return self.__function_data_for_accessibles

    def num_accessible_objects_under_test(self) -> int:
        """Provide the number of accessible objects under test.

        Useful to check whether there is even something to test.

        Returns:
            The number of all accessibles under test
        """
        return len(self.__accessible_objects_under_test)

    def get_generators_for(self, type_: type) -> OrderedSet[GenericAccessibleObject]:
        """Retrieve all known generators for the given type.

        Args:
            type_: The type we want to have the generators for

        Returns:
            The set of all generators for that type
        """
        if type_ is typing.Any:
            return OrderedSet(itertools.chain.from_iterable(self.__generators.values()))
        if (non_generic_type := extract_non_generic_class(type_)) is not None:
            generators: OrderedSet[GenericAccessibleObject] = OrderedSet()
            for subtype in self.__inheritance_graph.get_subtypes(
                TypeWrapper.from_type(non_generic_type)
            ):
                if subtype.raw_type in self.__generators:
                    generators.update(self.__generators[subtype.raw_type])
            return generators
        return self.__generators.get(type_, OrderedSet())

    def get_modifiers_for(self, type_: type) -> OrderedSet[GenericAccessibleObject]:
        """Get all known modifiers for a type.

        TODO: Incorporate inheritance

        Args:
            type_: The type

        Returns:
            The set of all accessibles that can modify the type
        """
        if type_ is typing.Any:
            return OrderedSet(itertools.chain.from_iterable(self.__modifiers.values()))
        if (non_generic_type := extract_non_generic_class(type_)) is not None:
            modifiers: OrderedSet[GenericAccessibleObject] = OrderedSet()
            for super_type in self.__inheritance_graph.get_supertypes(
                TypeWrapper.from_type(non_generic_type)
            ):
                if super_type.raw_type in self.__modifiers:
                    modifiers.update(self.__modifiers[super_type.raw_type])
            return modifiers
        return self.__modifiers.get(type_, OrderedSet())

    @property
    def generators(self) -> dict[type, OrderedSet[GenericAccessibleObject]]:
        """Provides all available generators.

        Returns:
            A dictionary of types and their generating accessibles
        """
        return self.__generators

    @property
    def modifiers(self) -> dict[type, OrderedSet[GenericAccessibleObject]]:
        """Provides all available modifiers.

        Returns:
            A dictionary of types and their modifying accessibles
        """
        return self.__modifiers

    def get_random_accessible(self) -> GenericAccessibleObject | None:
        """Provides a random accessible of the unit under test.

        Returns:
            A random accessible, or None if there is none
        """
        if self.num_accessible_objects_under_test() == 0:
            return None
        return randomness.choice(self.__accessible_objects_under_test)

    def get_random_call_for(self, type_: type) -> GenericAccessibleObject:
        """Get a random modifier for the given type.

        Args:
            type_: The type

        Returns:
            A random modifier for that type

        Raises:
            ConstructionFailedException: if no modifiers for the type exist
        """
        accessible_objects = self.get_modifiers_for(type_)
        if len(accessible_objects) == 0:
            raise ConstructionFailedException(f"No modifiers for {type_}")
        return randomness.choice(accessible_objects)

    def get_all_generatable_types(self) -> list[type]:
        """Provides all types that can be generated.

        This includes primitives and collections.

        Returns:
            A list of all types that can be generated
        """
        generatable = OrderedSet(self.__generators.keys())
        generatable.update(PRIMITIVES)
        generatable.update(COLLECTIONS)
        return list(generatable)

    def select_concrete_type(self, type_: type | None) -> type | None:
        """Select a concrete type from the given type.

        This is required, for example, when handling union types.  Currently, only
        unary types, Any, and Union are handled.

        Args:
            type_: An optional type

        Returns:
            An optional type
        """
        if type_ == Any:  # pylint: disable=comparison-with-callable
            return randomness.choice(self.get_all_generatable_types())
        if is_union_type(type_):
            candidates = get_args(type_)
            if candidates is not None and len(candidates) > 0:
                return randomness.choice(candidates)
            return None
        return type_

    def track_statistics_values(
        self, tracking_fun: Callable[[RuntimeVariable, Any], None]
    ) -> None:
        """Track statistics values from the test cluster and its items.

        Args:
            tracking_fun: The tracking function as a callback.
        """
        tracking_fun(
            RuntimeVariable.AccessibleObjectsUnderTest,
            self.num_accessible_objects_under_test(),
        )
        tracking_fun(
            RuntimeVariable.GeneratableTypes, len(self.get_all_generatable_types())
        )

        cyclomatic_complexity = self.__compute_cyclomatic_complexities(
            self.function_data_for_accessibles.values()
        )
        if cyclomatic_complexity is not None:
            tracking_fun(RuntimeVariable.McCabeMin, cyclomatic_complexity.min)
            tracking_fun(RuntimeVariable.McCabeMean, cyclomatic_complexity.mean)
            tracking_fun(RuntimeVariable.McCabeMedian, cyclomatic_complexity.median)
            tracking_fun(RuntimeVariable.McCabeMax, cyclomatic_complexity.max)
            tracking_fun(RuntimeVariable.LineNos, self.__linenos)

    CyclomaticComplexity = namedtuple("CyclomaticComplexity", "min mean median max")

    @staticmethod
    def __compute_cyclomatic_complexities(
        callable_data: typing.Iterable[_CallableData],
    ) -> CyclomaticComplexity | None:
        # Collect complexities only for callables that had an AST.  Their minimal
        # complexity is 1, the value None symbolises a callable that had no AST present,
        # either because there is none or because it is an implicitly added function,
        # such as a default constructor or the constructor of a base class.
        complexities = [
            item.cyclomatic_complexity
            for item in callable_data
            if item.cyclomatic_complexity is not None
        ]
        if len(complexities) == 0:
            return None
        return ModuleTestCluster.CyclomaticComplexity(
            min=min(complexities),
            mean=mean(complexities),
            median=median(complexities),
            max=max(complexities),
        )


class FilteredModuleTestCluster(ModuleTestCluster):
    """A test cluster wrapping another test cluster.

    Delegates most methods to the wrapped delegate.  This cluster filters out
    accessible objects under test that are already fully covered, in order to focus
    the search on areas that are not yet fully covered.
    """

    def __init__(
        self,
        delegate: ModuleTestCluster,
        archive: arch.Archive,
        known_data: KnownData,
        targets: OrderedSet[ff.TestCaseFitnessFunction],
    ) -> None:
        super().__init__(linenos=delegate.linenos)
        self.__delegate = delegate
        self.__known_data = known_data
        self.__code_object_id_to_accessible_objects: dict[
            int, GenericCallableAccessibleObject
        ] = {
            json.loads(acc.callable.__code__.co_consts[0])[  # type: ignore
                CODE_OBJECT_ID_KEY
            ]: acc
            for acc in delegate.accessible_objects_under_test
            if isinstance(acc, GenericCallableAccessibleObject)
            and hasattr(acc.callable, "__code__")
        }
        # Checking for __code__ is necessary, because the __init__ of a class that
        # does not define __init__ points to some internal CPython stuff.

        self.__accessible_to_targets: dict[
            GenericCallableAccessibleObject, OrderedSet
        ] = {
            acc: OrderedSet()
            for acc in self.__code_object_id_to_accessible_objects.values()
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
                acc := self.__code_object_id_to_accessible_objects.get(
                    code_object_id, None
                )
            ) is not None:
                return acc
            code_object_id = self.__known_data.existing_code_objects[
                code_object_id
            ].parent_code_object_id
        return None

    def on_target_covered(self, target: ff.TestCaseFitnessFunction) -> None:
        """A callback function to get informed by an archive when a target is covered

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
                    "Removed %s from test cluster because all targets within it have "
                    "been covered.",
                    acc,
                )

    @property
    def accessible_objects_under_test(self) -> OrderedSet[GenericAccessibleObject]:
        accessibles = self.__accessible_to_targets.keys()
        if len(accessibles) == 0:
            # Should never happen, just in case everything is already covered?
            return self.__delegate.accessible_objects_under_test
        return OrderedSet(accessibles)

    def num_accessible_objects_under_test(self) -> int:
        return self.__delegate.num_accessible_objects_under_test()

    def get_generators_for(self, type_: type) -> OrderedSet[GenericAccessibleObject]:
        return self.__delegate.get_generators_for(type_)

    def get_modifiers_for(self, type_: type) -> OrderedSet[GenericAccessibleObject]:
        return self.__delegate.get_modifiers_for(type_)

    @property
    def generators(self) -> dict[type, OrderedSet[GenericAccessibleObject]]:
        return self.__delegate.generators

    @property
    def modifiers(self) -> dict[type, OrderedSet[GenericAccessibleObject]]:
        return self.__delegate.modifiers

    def get_random_accessible(self) -> GenericAccessibleObject | None:
        accessibles = self.__accessible_to_targets.keys()
        if len(accessibles) == 0:
            return self.__delegate.get_random_accessible()
        return randomness.choice(OrderedSet(accessibles))

    def get_random_call_for(self, type_: type) -> GenericAccessibleObject:
        return self.__delegate.get_random_call_for(type_)

    def get_all_generatable_types(self) -> list[type]:
        return self.__delegate.get_all_generatable_types()

    def select_concrete_type(self, type_: type | None) -> type | None:
        return self.__delegate.select_concrete_type(type_)


def __get_function_node_from_ast(
    tree: ast.AST | None, name: str
) -> ASTFunctionNodes | None:
    if tree is None:
        return None
    for func in get_all_functions(tree):
        if func.name == name:
            return func
    return None


def __get_class_node_from_ast(tree: ast.AST | None, name: str) -> ast.ClassDef | None:
    if tree is None:
        return None
    for class_ in get_all_classes(tree):
        if class_.name == name:
            return class_
    return None


def __get_function_description_from_ast(
    tree: ASTFunctionNodes | None,
) -> FunctionDescription | None:
    if tree is None:
        return None

    def filter_for_tree_defining_function_name(desc: FunctionDescription) -> bool:
        return getattr(tree, "name", None) == desc.name

    # Filter the resulting function descriptions for the one represented by the `tree`
    # AST node.  There might be more than one function description, e.g., for nested
    # functions, where we are still only interested in the top-level functions and
    # not in the closures.
    description = list(
        filter(filter_for_tree_defining_function_name, get_function_descriptions(tree))
    )
    assert len(description) == 1
    return description[0]


def __get_mccabe_complexity(tree: ast.AST | None) -> int | None:
    if tree is None:
        return None
    return mccabe_complexity(tree)


def __is_constructor(method_name: str) -> bool:
    return method_name == "__init__"


def __is_protected(method_name: str) -> bool:
    return method_name.startswith("_") and not method_name.startswith("__")


def __is_private(method_name: str) -> bool:
    return method_name.startswith("__") and not method_name.endswith("__")


def __is_method_defined_in_class(class_: type, method: object) -> bool:
    return class_ == get_class_that_defined_method(method)


@dataclasses.dataclass
class _CallableData:
    accessible: GenericAccessibleObject
    tree: ast.AST | None
    description: FunctionDescription | None
    cyclomatic_complexity: int | None


def __analyse_function(
    *,
    func_name: str,
    func: FunctionType,
    type_inference_strategy: TypeInferenceStrategy,
    syntax_tree: ast.AST | None,
    test_cluster: ModuleTestCluster,
    add_to_test: bool,
) -> None:
    if __is_private(func_name) or __is_protected(func_name):
        LOGGER.debug("Skipping function %s from analysis", func_name)
        return
    if inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func):
        if add_to_test:
            raise ValueError("Pynguin cannot handle Coroutine in SUT. Stopping.")
        # Coroutine outside the SUT are not problematic, just exclude them.
        LOGGER.debug("Skipping coroutine %s outside of SUT", func_name)
        return

    LOGGER.debug("Analysing function %s", func_name)
    inferred_signature = infer_type_info(func, type_inference_strategy)
    func_ast = __get_function_node_from_ast(syntax_tree, func_name)
    description = __get_function_description_from_ast(func_ast)
    raised_exceptions = description.raises if description is not None else set()
    cyclomatic_complexity = __get_mccabe_complexity(func_ast)
    generic_function = GenericFunction(
        func, inferred_signature, raised_exceptions, func_name
    )
    function_data = _CallableData(
        accessible=generic_function,
        tree=func_ast,
        description=description,
        cyclomatic_complexity=cyclomatic_complexity,
    )
    test_cluster.add_generator(generic_function)
    if add_to_test:
        test_cluster.add_accessible_object_under_test(generic_function, function_data)


def __analyse_class(  # pylint: disable=too-many-arguments
    *,
    class_name: str,
    class_: type,
    type_inference_strategy: TypeInferenceStrategy,
    syntax_tree: ast.AST | None,
    test_cluster: ModuleTestCluster,
    add_to_test: bool,
) -> None:
    assert inspect.isclass(class_)
    LOGGER.debug("Analysing class %s", class_name)
    class_ast = __get_class_node_from_ast(syntax_tree, class_name)
    constructor_ast = __get_function_node_from_ast(class_ast, "__init__")
    description = __get_function_description_from_ast(constructor_ast)
    raised_exceptions = description.raises if description is not None else set()
    cyclomatic_complexity = __get_mccabe_complexity(constructor_ast)

    if issubclass(class_, enum.Enum):
        generic: GenericEnum | GenericConstructor = GenericEnum(class_)
        if isinstance(generic, GenericEnum) and len(generic.names) == 0:
            LOGGER.debug(
                "Skipping enum %s from test cluster, it has no fields.",
                class_name,
            )
            return
    else:
        generic = GenericConstructor(
            class_, infer_type_info(class_, type_inference_strategy), raised_exceptions
        )

    method_data = _CallableData(
        accessible=generic,
        tree=constructor_ast,
        description=description,
        cyclomatic_complexity=cyclomatic_complexity,
    )
    if not inspect.isabstract(class_):
        # TODO adding an abstract class constructor makes no sense?
        test_cluster.add_generator(generic)
        if add_to_test:
            test_cluster.add_accessible_object_under_test(generic, method_data)

    for method_name, method in inspect.getmembers(class_, inspect.isfunction):
        __analyse_method(
            class_name=class_name,
            class_=class_,
            method_name=method_name,
            method=method,
            type_inference_strategy=type_inference_strategy,
            syntax_tree=class_ast,
            test_cluster=test_cluster,
            add_to_test=add_to_test,
        )


def __analyse_method(  # pylint: disable=too-many-arguments
    *,
    class_name: str,
    class_: type,
    method_name: str,
    method: (
        FunctionType
        | BuiltinFunctionType
        | WrapperDescriptorType
        | MethodDescriptorType
    ),
    type_inference_strategy: TypeInferenceStrategy,
    syntax_tree: ast.AST | None,
    test_cluster: ModuleTestCluster,
    add_to_test: bool,
) -> None:
    if (
        __is_private(method_name)
        or __is_protected(method_name)
        or __is_constructor(method_name)
        or not __is_method_defined_in_class(class_, method)
    ):
        LOGGER.debug("Skipping method %s from analysis", method_name)
        return
    if inspect.iscoroutinefunction(method) or inspect.isasyncgenfunction(method):
        if add_to_test:
            raise ValueError("Pynguin cannot handle Coroutine in SUT. Stopping.")
        # Coroutine outside the SUT are not problematic, just exclude them.
        LOGGER.debug("Skipping coroutine %s outside of SUT", method_name)
        return

    LOGGER.debug("Analysing method %s.%s", class_name, method_name)
    inferred_signature = infer_type_info(method, type_inference_strategy)
    method_ast = __get_function_node_from_ast(syntax_tree, method_name)
    description = __get_function_description_from_ast(method_ast)
    raised_exceptions = description.raises if description is not None else set()
    cyclomatic_complexity = __get_mccabe_complexity(method_ast)
    generic_method = GenericMethod(
        class_, method, inferred_signature, raised_exceptions, method_name
    )
    method_data = _CallableData(
        accessible=generic_method,
        tree=method_ast,
        description=description,
        cyclomatic_complexity=cyclomatic_complexity,
    )
    test_cluster.add_generator(generic_method)
    test_cluster.add_modifier(class_, generic_method)
    if add_to_test:
        test_cluster.add_accessible_object_under_test(generic_method, method_data)


def __resolve_dependencies(
    root_module: ModuleType,
    type_inference_strategy: TypeInferenceStrategy,
    syntax_tree: ast.AST | None,
    test_cluster: ModuleTestCluster,
) -> None:

    # Provide a set of seen modules, classes and functions for fixed-point iteration
    seen_modules: set[ModuleType] = set()
    seen_classes: set[Any] = set()
    seen_functions: set[Any] = set()

    # Start with root module, i.e., the module under test.
    wait_list: queue.SimpleQueue = queue.SimpleQueue()
    wait_list.put(root_module)

    while not wait_list.empty():
        current_module = wait_list.get()
        if current_module in seen_modules:
            # Skip the module, we have already analysed it before
            continue
        if _is_blacklisted(current_module):
            # Don't include anything from the blacklist
            continue

        tree = None
        if current_module == root_module:
            # Currently, the syntax tree is only available for the root module,
            # i.e., the SUT.
            tree = syntax_tree

        # Analyze all classes found in the current module
        __analyse_included_classes(
            module=current_module,
            root_module_name=root_module.__name__,
            type_inference_strategy=type_inference_strategy,
            test_cluster=test_cluster,
            seen_classes=seen_classes,
            syntax_tree=tree,
        )

        # Analyze all functions found in the current module
        __analyse_included_functions(
            module=current_module,
            root_module_name=root_module.__name__,
            type_inference_strategy=type_inference_strategy,
            test_cluster=test_cluster,
            seen_functions=seen_functions,
            syntax_tree=tree,
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


def __analyse_included_classes(
    *,
    module: ModuleType,
    root_module_name: str,
    type_inference_strategy: TypeInferenceStrategy,
    test_cluster: ModuleTestCluster,
    syntax_tree: ast.AST | None,
    seen_classes: set,
) -> None:
    work_list = list(
        filter(
            lambda x: inspect.isclass(x) and not _is_blacklisted(x),
            vars(module).values(),
        )
    )

    while len(work_list) > 0:
        current = work_list.pop(0)
        if current in seen_classes:
            continue
        seen_classes.add(current)

        __analyse_class(
            class_name=current.__qualname__,
            class_=current,
            type_inference_strategy=type_inference_strategy,
            syntax_tree=syntax_tree,
            test_cluster=test_cluster,
            add_to_test=current.__module__ == root_module_name,
        )

        # TODO(fk) apply blacklist on bases?
        wrapper = TypeWrapper.from_type(current)
        test_cluster.inheritance_graph.add_type(wrapper)
        if hasattr(current, "__bases__"):
            for base in current.__bases__:
                base_wrapper = TypeWrapper.from_type(base)
                test_cluster.inheritance_graph.add_type(base_wrapper)
                test_cluster.inheritance_graph.add_edge(
                    super_type=base_wrapper, sub_type=wrapper
                )
                work_list.append(base)


def __analyse_included_functions(
    *,
    module: ModuleType,
    root_module_name: str,
    type_inference_strategy: TypeInferenceStrategy,
    test_cluster: ModuleTestCluster,
    syntax_tree: ast.AST | None,
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
            type_inference_strategy=type_inference_strategy,
            syntax_tree=syntax_tree,
            test_cluster=test_cluster,
            add_to_test=current.__module__ == root_module_name,
        )


def analyse_module(parsed_module: _ParseResult) -> ModuleTestCluster:
    """Analyses a module to build a test cluster.

    Args:
        parsed_module: The parsed module

    Returns:
        A test cluster for the module
    """
    test_cluster = ModuleTestCluster(linenos=parsed_module.linenos)
    __resolve_dependencies(
        root_module=parsed_module.module,
        type_inference_strategy=parsed_module.type_inference_strategy,
        syntax_tree=parsed_module.syntax_tree,
        test_cluster=test_cluster,
    )
    return test_cluster


def generate_test_cluster(
    module_name: str,
    type_inference_strategy: TypeInferenceStrategy = TypeInferenceStrategy.TYPE_HINTS,
) -> ModuleTestCluster:
    """Generates a new test cluster from the given module.

    Args:
        module_name: The name of the module
        type_inference_strategy: Which type-inference strategy to use

    Returns:
        A new test cluster for the given module
    """
    return analyse_module(parse_module(module_name, type_inference_strategy))
