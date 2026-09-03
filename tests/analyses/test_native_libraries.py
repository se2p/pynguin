#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for native libraries handling and C-extension support in TestCluster."""

from __future__ import annotations

import json
import math
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

import pytest

import pynguin.analyses.module as pm
import pynguin.configuration as config
from pynguin.analyses import ast_utils
from pynguin.analyses.module import (
    analyse_module,
    parse_module,
)
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


@pytest.fixture
def clean_config():
    """Reset configuration after test execution."""
    old_subprocess = config.configuration.subprocess
    old_subprocess_if_rec = config.configuration.subprocess_if_recommended
    yield
    config.configuration.subprocess = old_subprocess
    config.configuration.subprocess_if_recommended = old_subprocess_if_rec


def test_c_is_whitelisted():
    """Verify that whitelisted stdlib modules are recognized and non-whitelisted are not."""
    assert pm._c_is_whitelisted(math)
    assert pm._c_is_whitelisted(json)

    # Fake non-whitelisted module
    fake_mod = types.ModuleType("some_native_c_mod")
    assert not pm._c_is_whitelisted(fake_mod)


def test_c_is_whitelisted_exception():
    """Verify that non-module or broken objects return False without crashing."""

    class BrokenModule:
        @property
        def __name__(self):  # noqa: PLW3201
            raise RuntimeError("boom")

    assert not pm._c_is_whitelisted(BrokenModule())  # type: ignore[arg-type]


def test_check_c_modules_binary_extension():
    """Verify check_c_modules detects binary extensions with .so, .pyd, and .dylib."""
    for ext in [".so", ".pyd", ".dylib"]:
        mod = types.ModuleType("my_c_lib")
        mod.__file__ = f"/path/to/my_c_lib{ext}"
        detected = pm.__check_c_modules(module=mod)
        assert "my_c_lib" in detected


def test_check_c_modules_whitelisted_binary():
    """Verify check_c_modules does not flag whitelisted modules even with binary extension."""
    mod = types.ModuleType("math")
    mod.__file__ = "/path/to/math.so"
    detected = pm.__check_c_modules(module=mod)
    assert len(detected) == 0


def test_check_c_modules_pure_python():
    """Verify pure python module has no detected C extensions."""
    detected = pm.__check_c_modules(module=ast_utils)
    assert len(detected) == 0


def test_check_c_modules_with_builtin_routine():
    """Verify check_c_modules detects modules with non-whitelisted C routines."""
    mod = types.ModuleType("custom_c_module")
    # math.sin is a built-in function (inspect.isbuiltin == True, inspect.isfunction == False)
    mod.native_sin = math.sin  # type: ignore[attr-defined]
    detected = pm.__check_c_modules(module=mod)
    assert "custom_c_module" in detected


@pytest.mark.usefixtures("clean_config")
def test_handle_c_modules_recommended_enabled():
    """Verify subprocess mode is enabled when C extensions are present and recommended."""
    config.configuration.subprocess_if_recommended = True
    config.configuration.subprocess = False

    with patch("pynguin.utils.statistics.stats.track_output_variable") as mock_track:
        pm._handle_c_modules({"numpy", "my_c_ext"})
        assert config.configuration.subprocess is True
        mock_track.assert_any_call(
            RuntimeVariable.CExtensionModules, str(sorted({"numpy", "my_c_ext"}))
        )
        mock_track.assert_any_call(RuntimeVariable.SubprocessMode, "True")


@pytest.mark.usefixtures("clean_config")
def test_handle_c_modules_recommended_disabled():
    """Verify subprocess mode is disabled when no C extensions are present and recommended."""
    config.configuration.subprocess_if_recommended = True
    config.configuration.subprocess = True

    with patch("pynguin.utils.statistics.stats.track_output_variable") as mock_track:
        pm._handle_c_modules(set())
        assert config.configuration.subprocess is False
        mock_track.assert_any_call(RuntimeVariable.CExtensionModules, "[]")
        mock_track.assert_any_call(RuntimeVariable.SubprocessMode, "False")


@pytest.mark.usefixtures("clean_config")
def test_handle_c_modules_not_recommended_warning():
    """Verify warning is logged when subprocess_if_recommended is False and subprocess is False."""
    config.configuration.subprocess_if_recommended = False
    config.configuration.subprocess = False

    with patch("pynguin.analyses.module.LOGGER.warning") as mock_warn:
        pm._handle_c_modules({"numpy"})
        assert config.configuration.subprocess is False
        mock_warn.assert_called_once()


def test_is_blacklisted_class_invalid_module():
    """Verify classes with None, non-string, or empty __module__ are blacklisted."""

    class ClassNoneMod:
        pass

    ClassNoneMod.__module__ = None  # type: ignore[assignment]
    assert pm._is_blacklisted(ClassNoneMod)

    class ClassEmptyMod:
        pass

    ClassEmptyMod.__module__ = ""
    assert pm._is_blacklisted(ClassEmptyMod)

    class ClassNonStringMod:
        pass

    ClassNonStringMod.__module__ = 123  # type: ignore[assignment]
    assert pm._is_blacklisted(ClassNonStringMod)


def test_is_blacklisted_function_invalid_module():
    """Verify functions with None, non-string, or empty __module__ are blacklisted."""

    def func_none():
        pass

    func_none.__module__ = None  # type: ignore[assignment]
    assert pm._is_blacklisted(func_none)

    def func_empty():
        pass

    func_empty.__module__ = ""
    assert pm._is_blacklisted(func_empty)

    def func_non_str():
        pass

    func_non_str.__module__ = 456  # type: ignore[assignment]
    assert pm._is_blacklisted(func_non_str)


def _get_accessible_name(obj) -> str:
    """Extract readable symbol name from GenericAccessibleObject."""
    if hasattr(obj, "function_name"):
        return obj.function_name
    if hasattr(obj, "method_name"):
        return obj.method_name
    if hasattr(obj, "owner"):
        return obj.owner.name
    return str(obj)


def test_test_cluster_with_numpy_module():
    """Verify that TestCluster generation succeeds on a module using NumPy."""
    pytest.importorskip("numpy")

    with tempfile.TemporaryDirectory() as tmpdir:
        sys.path.insert(0, tmpdir)
        try:
            mod_file = Path(tmpdir) / "sut_np_cluster.py"
            mod_file.write_text(
                "import numpy as np\n\n"
                "def array_mean(a: np.ndarray) -> float:\n"
                "    return float(np.mean(a))\n\n"
                "class ArrayContainer:\n"
                "    def __init__(self, arr: np.ndarray):\n"
                "        self.arr = arr\n\n"
                "    def size(self) -> int:\n"
                "        return int(self.arr.size)\n"
            )
            parsed = parse_module("sut_np_cluster")
            cluster = analyse_module(parsed)

            assert len(cluster.accessible_objects_under_test) == 3
            obj_names = {_get_accessible_name(obj) for obj in cluster.accessible_objects_under_test}
            assert "array_mean" in obj_names
            assert "ArrayContainer" in obj_names
            assert "size" in obj_names
        finally:
            if tmpdir in sys.path:
                sys.path.remove(tmpdir)


def test_test_cluster_with_numpy_subclass():
    """Verify TestCluster generation succeeds for a class subclassing a native type."""
    pytest.importorskip("numpy")

    with tempfile.TemporaryDirectory() as tmpdir:
        sys.path.insert(0, tmpdir)
        try:
            mod_file = Path(tmpdir) / "sut_np_subclass.py"
            mod_file.write_text(
                "import numpy as np\n\n"
                "class CustomArray(np.ndarray):\n"
                "    def custom_norm(self) -> float:\n"
                "        return float(np.linalg.norm(self))\n"
            )
            parsed = parse_module("sut_np_subclass")
            cluster = analyse_module(parsed)

            obj_names = {_get_accessible_name(obj) for obj in cluster.accessible_objects_under_test}
            assert "CustomArray" in obj_names
            assert "custom_norm" in obj_names
        finally:
            if tmpdir in sys.path:
                sys.path.remove(tmpdir)


def test_test_cluster_with_c_modules_and_builtins():
    """Verify TestCluster generation with SUT importing C modules and built-in functions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sys.path.insert(0, tmpdir)
        try:
            mod_file = Path(tmpdir) / "sut_c_builtins.py"
            mod_file.write_text(
                "import math\n"
                "import _json\n"
                "import _csv\n\n"
                "def compute_sin(val: float) -> float:\n"
                "    return math.sin(val)\n\n"
                "def encode_str(s: str) -> str:\n"
                "    return _json.encode_basestring_ascii(s)\n"
            )
            parsed = parse_module("sut_c_builtins")
            cluster = analyse_module(parsed)

            obj_names = {_get_accessible_name(obj) for obj in cluster.accessible_objects_under_test}
            assert "compute_sin" in obj_names
            assert "encode_str" in obj_names
        finally:
            if tmpdir in sys.path:
                sys.path.remove(tmpdir)


def test_test_cluster_unimportable_c_extension_function():
    """Verify TestCluster generation does not crash on functions from unimportable C modules."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sys.path.insert(0, tmpdir)
        try:
            mod_file = Path(tmpdir) / "sut_unimportable.py"
            mod_file.write_text(
                "def helper():\n"
                "    return 42\n"
                "helper.__module__ = 'non_existent_c_extension'\n\n"
                "def actual_sut_func() -> int:\n"
                "    return helper()\n"
            )
            parsed = parse_module("sut_unimportable")
            cluster = analyse_module(parsed)

            obj_names = {_get_accessible_name(obj) for obj in cluster.accessible_objects_under_test}
            assert "actual_sut_func" in obj_names
        finally:
            if tmpdir in sys.path:
                sys.path.remove(tmpdir)


def test_test_cluster_unimportable_c_extension_class():
    """Verify TestCluster generation does not crash on classes from unimportable C modules."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sys.path.insert(0, tmpdir)
        try:
            mod_file = Path(tmpdir) / "sut_unimportable_cls.py"
            mod_file.write_text(
                "class ExternalCClass:\n"
                "    pass\n"
                "ExternalCClass.__module__ = 'non_existent_c_extension'\n\n"
                "class SUTClass:\n"
                "    def __init__(self, obj: ExternalCClass):\n"
                "        self.obj = obj\n"
            )
            parsed = parse_module("sut_unimportable_cls")
            cluster = analyse_module(parsed)

            obj_names = {_get_accessible_name(obj) for obj in cluster.accessible_objects_under_test}
            assert "SUTClass" in obj_names
        finally:
            if tmpdir in sys.path:
                sys.path.remove(tmpdir)
