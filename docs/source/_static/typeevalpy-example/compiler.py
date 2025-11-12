# Author: Yuan Chang
# Copyright: Copyright (C) 2020
# License: MIT
# Email: pyslvs@gmail.com
#
# SPDX-License-Identifier: MIT
#
# -*- coding: utf-8 -*-

"""Compiler functions."""

from __future__ import annotations


__author__ = "Yuan Chang"
__copyright__ = "Copyright (C) 2020"
__license__ = "MIT"
__email__ = "pyslvs@gmail.com"

from collections import defaultdict
from dataclasses import is_dataclass
from enum import Enum
from importlib import import_module
from inspect import getfullargspec
from inspect import isclass
from inspect import isfunction
from inspect import isgenerator
from logging import DEBUG
from logging import basicConfig
from logging import getLogger
from os import getcwd
from os import listdir
from os import mkdir
from os.path import isdir
from os.path import join
from os.path import sep
from pkgutil import walk_packages
from re import search
from re import sub
from sys import exc_info
from sys import modules as sys_modules
from sys import path as sys_path
from sys import stdout
from textwrap import dedent
from traceback import FrameSummary
from traceback import extract_tb
from types import ModuleType
from typing import Any
from typing import Callable
from typing import Dict
from typing import Iterable
from typing import List
from typing import Set
from typing import Tuple
from typing import Type
from typing import cast
from typing import get_type_hints


sys_path.insert(0, getcwd())
unload_modules = set(sys_modules)
basicConfig(stream=stdout, level=DEBUG, format="%(message)s")
logger = getLogger()
LOADED_PATH: Set[str] = set()
INNER_LINKS: Dict[str, str] = {}
ORIG_DOC: Dict[str, str] = {}
ALIAS: Dict[str, str] = {}


class PathModule(ModuleType):
    __path__: List[str]


class PubModule(PathModule):
    __all__: List[str]


class GenericClass(type):  # Protocol
    __orig_bases__: Tuple[type, ...]
    __parameters__: Tuple[Any]


def full_name(parent: Any, obj: Any) -> str:
    """Get full name of an object.
    If m is not a module, return empty string.
    """
    return f"{get_name(parent)}.{get_name(obj)}"


def get_name(obj: Any) -> str:
    """Get a real name from an object."""
    if hasattr(obj, '__name__'):
        if hasattr(obj, '__module__') and not hasattr(obj, '__class__'):
            if obj.__module__ == 'builtins':
                name = obj.__name__
            else:
                name = f"{obj.__module__}.{obj.__name__}"
        else:
            name = obj.__name__
    elif type(obj) is str:
        name = obj
    else:
        name = repr(obj)
    return name


def is_root(m: ModuleType) -> bool:
    """Return true if the module is a root."""
    file_name = m.__file__.rsplit(sep, maxsplit=1)[-1]
    return hasattr(m, '__all__') or file_name == '__init__.py'


def public(names: Iterable[str], init: bool = True) -> Iterable[str]:
    """Yield public names only."""
    for name in names:
        if not name.startswith('_') or (init and name == '__init__'):
            yield name


def local_vars(m: ModuleType) -> Iterable[str]:
    """Get local variables from the module."""
    if hasattr(m, '__all__'):
        yield from cast(PubModule, m).__all__
        return
    for name, obj in m.__dict__.items():
        if (
            get_my_doc(obj, name)
            and not isinstance(obj, ModuleType)
            and hasattr(obj, '__module__')
            and obj.__module__.startswith(m.__name__)
        ):
            if name != get_name(obj):
                ALIAS[name] = get_name(obj)
            yield name


def docstring(obj: Any) -> str:
    """Remove first indent of the docstring."""
    doc = obj.__doc__
    if doc is None or obj.__class__.__doc__ == doc:
        return ""
    doc = cast(str, doc)
    two_parts = doc.split('\n', maxsplit=1)
    if len(two_parts) == 2:
        doc = two_parts[0] + '\n' + dedent(two_parts[1])
    return doc.lstrip().rstrip()


def table_row(*items: Iterable[str]) -> str:
    """Make the rows to a pipe table."""

    def table(_items: Iterable[str], space: bool = True) -> str:
        s = " " if space else ""
        return '|' + s + (s + '|' + s).join(_items) + s + '|\n'

    if len(items) == 0:
        raise ValueError("the number of rows is not enough")
    doc = table(escape(name) for name in items[0])
    if len(items) == 1:
        return doc
    line = (':' + '-' * (len(s) if len(s) > 3 else 3) + ':' for s in items[0])
    doc += table(line, False)
    for item in items[1:]:
        doc += table(escape(name) for name in item)
    return doc


def make_table(obj: Callable) -> str:
    """Make an argument table for function or method."""
    args = getfullargspec(obj)
    hints = defaultdict(lambda: Any, get_type_hints(obj))
    hints['self'] = " "
    args_doc = []
    type_doc = []
    all_args = []
    # Positional arguments
    all_args.extend(args.args)
    # The name of '*'
    if args.varargs is not None:
        new_name = f'**{args.varargs}'
        hints[new_name] = hints.pop(args.varargs, Any)
        all_args.append(new_name)
    elif args.kwonlyargs:
        all_args.append('*')
    # Keyword only arguments
    all_args.extend(args.kwonlyargs or [])
    # The name of '**'
    if args.varkw is not None:
        new_name = f'**{args.varkw}'
        hints[new_name] = hints.pop(args.varkw, Any)
        all_args.append(new_name)
    all_args.append('return')
    for arg in all_args:  # type: str
        args_doc.append(arg)
        type_doc.append(get_name(hints[arg]))
    doc = table_row(args_doc, type_doc)
    df = []
    if args.defaults is not None:
        df.extend([" "] * (len(args.args) - len(args.defaults)))
        df.extend(args.defaults)
    if args.kwonlydefaults is not None:
        df.extend(args.kwonlydefaults.get(arg, " ") for arg in args.kwonlyargs)
    if df:
        df.append(" ")
        doc += table_row([f"{v}" for v in df])
    return doc + '\n'


def is_abstractmethod(obj: Any) -> bool:
    """Return True if it is a abstract method."""
    return hasattr(obj, '__isabstractmethod__')


def is_staticmethod(parent: type, obj: Any) -> bool:
    """Return True if it is a static method."""
    name = get_name(obj)
    if name in parent.__dict__:
        return type(parent.__dict__[name]) is staticmethod
    # Assume it is implemented
    return True


def is_classmethod(parent: type, obj: Any) -> bool:
    """Return True if it is a class method."""
    if not hasattr(obj, '__self__'):
        return False
    return obj.__self__ is parent


def is_property(obj: Any) -> bool:
    """Return True if it is a property."""
    return type(obj) is property


def is_callable(obj: Any) -> bool:
    """Return True if it is a callable object."""
    return callable(obj)


def is_enum(obj: Any) -> bool:
    """Return True if it is enum class."""
    if not isclass(obj):
        return False
    return Enum in mro(obj)


def is_alias(name: str) -> bool:
    """Return True if it is an alias."""
    return name in ALIAS and ALIAS[name] in ORIG_DOC


def parameters(obj: type) -> Tuple[Any, ...]:
    """Get generic parameters."""
    if hasattr(obj, '__parameters__'):
        return cast(GenericClass, obj).__parameters__
    return ()


def mro(obj: type) -> Tuple[type, ...]:
    """Return inherited class."""
    return obj.__mro__


def super_cls(obj: type) -> type:
    """Return super class."""
    return mro(obj)[1]


def linker(name: str) -> str:
    """Return inner link format."""
    return name.lower().replace('.', '')


def escape(s: str) -> str:
    """Valid Markdown name."""
    while True:
        r = sub(r"(?<!\\)([_\[])((?:[a-zA-Z., ]*\\[_\[])*~?[a-zA-Z., ]+[_\]]+)",
                r"\\\1\2", s)
        if r == s:
            return r
        s = r


def interpret_mode(doc: str) -> Iterable[str]:
    """Replace interpreter syntax."""
    keep = False
    lines = doc.split('\n')
    for i, line in enumerate(lines):
        signed = line.startswith(">>> ")
        if signed:
            line = line[len(">>> "):]
            if not keep:
                yield "```python"
                keep = True
        elif keep:
            yield "```\n"
            keep = False
        yield line
        if signed and i == len(lines) - 1:
            yield "```\n"
            keep = False


def get_type_doc(obj: type) -> str:
    """Get the doc string for a type."""
    doc = f"\n\nInherited from `{get_name(super_cls(obj))}`."
    ts = parameters(obj)
    if ts:
        doc += f" Parameters: {', '.join(f'`{t}`' for t in ts)}"
    doc += '\n\n'
    if is_dataclass(obj):
        doc += "Is a data class.\n\n"
    elif is_enum(obj):
        doc += "Is an enum class.\n\n"
        title_doc, value_doc = zip(*[(e.name, f"`{e.value!r}`")
                                     for e in cast(Type[Enum], obj)])
        doc += table_row(title_doc, value_doc) + '\n'
    return doc


def get_method_doc(parent: Any, obj: Any) -> str:
    """Get method's docstring."""
    if not isclass(parent):
        return ""
    doc = ""
    if is_abstractmethod(obj):
        doc += "Is an abstract method.\n\n"
    if is_staticmethod(parent, obj):
        doc += "Is a static method.\n\n"
    if is_classmethod(parent, obj):
        doc += "Is a class method.\n\n"
    return doc


def get_my_doc(obj: Any, name: str) -> str:
    """Return self or stub docstring from PYI or original source."""
    return docstring(obj) or ORIG_DOC.get(name, "")


def get_stub_doc(parent: Any, name: str, level: int, prefix: str = "") -> str:
    """Generate docstring by type."""
    obj = getattr(parent, name)
    if prefix:
        name = f"{prefix}.{name}"
    INNER_LINKS[name] = linker(name)
    doc = '#' * level + f" {escape(name)}"
    sub_doc = []
    if is_alias(name):
        doc += f"\n\nAlias to [{ALIAS[name]}].\n\n"
    elif isfunction(obj) or isgenerator(obj):
        doc += "()\n\n" + make_table(obj) + '\n' + get_method_doc(parent, obj)
    elif isclass(obj):
        doc += get_type_doc(obj)
        hints = get_type_hints(obj)
        if hints:
            for attr in public(hints.keys()):
                INNER_LINKS[f"{name}.{attr}"] = linker(name)
            doc += table_row(
                hints.keys(),
                [get_name(v) for v in hints.values()]
            ) + '\n'
        for attr_name in public(dir(obj), not is_dataclass(obj)):
            if attr_name not in hints:
                sub_doc.append(get_stub_doc(obj, attr_name, level + 1, name))
    elif is_property(obj):
        doc += "\n\nIs a property.\n\n"
    elif is_callable(obj):
        doc += '()\n\n' + make_table(obj)
    else:
        return ""
    doc += '\n'.join(interpret_mode(get_my_doc(obj, name)))
    if sub_doc:
        # The docstring of attributes
        doc += '\n\n' + '\n\n'.join(sub_doc)
    return doc


def cache_orig_doc(parent: Any, name: str, prefix: str = "") -> None:
    """Preload original docstrings to global container "self_doc"."""
    obj = getattr(parent, name)
    if prefix:
        name = f"{prefix}.{name}"
    doc = docstring(obj)
    if doc:
        ORIG_DOC[name] = doc
    if isclass(obj):
        hints = get_type_hints(obj)
        for attr_name in public(dir(obj), not is_dataclass(obj)):
            if attr_name not in hints:
                cache_orig_doc(obj, attr_name, name)


def replace_keywords(doc: str, ignore_module: List[str]) -> str:
    """Replace keywords from docstring."""
    for name in reversed(ignore_module):
        doc = sub(rf"(?<!>>> )(?<!from )({name}\.)", "", doc)
    for word, re_word in (
        ('NoneType', 'None'),
        ('Ellipsis', '...'),
    ):
        doc = doc.replace(word, re_word)
    return doc


def import_from(name: str) -> ModuleType:
    """Import the module from name."""
    try:
        return import_module(name)
    except ImportError:
        logger.warn(f"load module failed: {name}")
        return ModuleType(name)


def load_file(code: str, mod: ModuleType) -> bool:
    """Load file into the module."""
    try:
        exec(compile(code, '', 'exec',
                     flags=annotations.compiler_flag), mod.__dict__)
        sys_modules[get_name(mod)] = mod
    except ImportError:
        return False
    except Exception as e:
        _, _, tb = exc_info()
        stack: FrameSummary = extract_tb(tb)[-1]
        logger.warning(f"In {stack.name}\n{stack.line}\n{e}")
    return True


def load_stubs(m: ModuleType) -> None:
    """Load all pyi files."""
    if not hasattr(m, '__path__'):
        return
    m = cast(PathModule, m)
    root = m.__path__[0]
    if root in LOADED_PATH:
        return
    LOADED_PATH.add(root)
    modules = {}
    for file in listdir(root):
        if not file.endswith('.pyi'):
            continue
        with open(join(root, file), 'r', encoding='utf-8') as f:
            code = f.read()
        modules[get_name(m) + '.' + file[:-len('.pyi')]] = code
    module_names = list(modules)
    counter = 0
    while counter < len(module_names):
        name = module_names.pop()
        logger.debug(f"Load stub: {name}")
        code = modules[name]
        mod = ModuleType(name)
        if not load_file(code, mod):
            module_names.insert(0, name)
            counter += 1
        else:
            counter = 0
        if not module_names:
            break
    else:
        raise ModuleNotFoundError("unsolved module dependencies")
    # Reload root module
    name = get_name(m)
    with open(m.__file__, 'r', encoding='utf-8') as f:
        load_file(f.read(), m)
    sys_modules[name] = m


def get_level(name: str) -> int:
    """Return the level of the module name."""
    return name.count('.')


def load_root(root_name: str, root_module: str) -> str:
    """Root module docstring."""
    m = import_from(root_module)
    modules = {get_name(m): m}
    ignore_module = ['typing', root_module]
    if hasattr(m, '__path__'):
        m = cast(PathModule, m)
        logger.debug(f"Module path: {m.__path__}")
        for info in walk_packages(m.__path__, root_module + '.'):
            m = import_from(info.name)
            name = get_name(m)
            ignore_module.append(name)
            if is_root(m):
                modules[name] = cast(PathModule, m)
    doc = f"# {root_name} API\n\n"
    module_names = sorted(modules, key=get_level)
    for name in reversed(module_names):
        m = modules[name]
        for vname in public(local_vars(m)):
            cache_orig_doc(m, vname)
        load_stubs(m)
    for name in module_names:
        m = modules[name]
        doc += f"## Module `{name}`\n\n{docstring(m)}\n\n"
        doc += replace_keywords('\n\n'.join(
            get_stub_doc(m, name, 3) for name in public(local_vars(m))
        ), ignore_module) + '\n\n'
    return doc.rstrip() + '\n'


def basename(name: str) -> str:
    """Get base name."""
    return name.rsplit('.', maxsplit=1)[-1]


def ref_link(doc: str) -> str:
    """Create the reference and clear the links."""
    ref = ""
    for title, reformat in INNER_LINKS.items():
        if search(rf"(?<!\\)\[{title}]", doc):
            ref += f"[{title}]: #{reformat}\n"
            continue
        title = basename(title)
        if title in INNER_LINKS:
            continue
        if search(rf"(?<!\\)\[{title}]", doc):
            ref += f"[{title}]: #{reformat}\n"
    INNER_LINKS.clear()
    return ref


def gen_api(
    root_names: Dict[str, str],
    prefix: str = 'docs',
    dry: bool = False
) -> None:
    """Generate API. All rules are listed in the readme."""
    if not isdir(prefix):
        logger.debug(f"Create directory: {prefix}")
        mkdir(prefix)
    for name, module in root_names.items():
        path = join(prefix, f"{module.replace('_', '-')}-api.md")
        logger.debug(f"Load root: {module} ({name})")
        doc = sub(r"\n\n+", "\n\n", load_root(name, module))
        ref = ref_link(doc)
        if ref:
            doc += '\n' + ref
        if dry:
            logger.debug(doc)
        else:
            logger.debug(f"Write file: {path}")
            with open(path, 'w+', encoding='utf-8') as f:
                f.write(doc)
        # Unload modules
        for m_name in set(sys_modules) - unload_modules:
            del sys_modules[m_name]
        ALIAS.clear()
        ORIG_DOC.clear()
