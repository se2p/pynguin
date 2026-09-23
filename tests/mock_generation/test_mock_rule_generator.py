#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the class-level MockRuleGenerator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from pynguin.mock_generation.mock_rule_generator import (
    MockRuleGenerator,
    build_import_map,
    canonical_fqn,
    resolve_target,
    top_level,
)

if TYPE_CHECKING:
    from pathlib import Path


def write_test_file(directory: Path, name: str, source: str) -> Path:
    """Write a test file *name* under *directory* and return the path."""
    path = directory / name
    path.write_text(source, encoding="utf-8")
    return path


def _targets(result: dict) -> set[str]:
    return {entry["target"] for entry in result["targets"]}


# Module-level helpers


def test_top_level_simple():
    assert top_level("requests") == "requests"


def test_top_level_dotted():
    assert top_level("urllib3.util.retry") == "urllib3"


def test_build_import_map_from_import_keeps_full_path():
    assert build_import_map("from requests import Session\n").get("Session") == "requests.Session"


def test_build_import_map_plain_import():
    assert build_import_map("import boto3\n").get("boto3") == "boto3"


def test_build_import_map_dotted_from():
    mapping = build_import_map("from urllib3.util import retry\n")
    assert mapping.get("retry") == "urllib3.util.retry"


# canonical_fqn


def test_canonical_resolves_to_defining_module():
    assert canonical_fqn("requests.Session") == "requests.sessions.Session"


def test_canonical_method_resolves_to_owning_class():
    assert canonical_fqn("requests.sessions.Session.request") == "requests.sessions.Session"


def test_canonical_unresolvable_is_kept():
    assert canonical_fqn("some.unknown.Thing") == "some.unknown.Thing"


def test_resolve_target_kinds():
    assert resolve_target("requests.Session") == ("requests.sessions.Session", "class")
    assert resolve_target("requests.sessions.Session.request") == (
        "requests.sessions.Session",
        "class",
    )
    assert resolve_target("some.unknown.Thing") == ("some.unknown.Thing", "unresolved")


# find_test_files


def test_find_test_files_in_tests_subdir(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_foo.py").write_text("", encoding="utf-8")
    (tests_dir / "bar_test.py").write_text("", encoding="utf-8")
    (tests_dir / "helper.py").write_text("", encoding="utf-8")

    found = {p.name for p in MockRuleGenerator(project_dirs=[]).find_test_files(tmp_path)}
    assert "test_foo.py" in found
    assert "bar_test.py" in found
    assert "helper.py" not in found


def test_find_test_files_nested(tmp_path):
    nested = tmp_path / "tests" / "unit"
    nested.mkdir(parents=True)
    (nested / "test_nested.py").write_text("", encoding="utf-8")
    found = MockRuleGenerator(project_dirs=[]).find_test_files(tmp_path)
    assert any(p.name == "test_nested.py" for p in found)


def test_find_test_files_empty_project(tmp_path):
    assert MockRuleGenerator(project_dirs=[]).find_test_files(tmp_path) == []


# extract_mocked_targets


def test_extract_patch_full_fqn(tmp_path):
    f = write_test_file(tmp_path, "test_x.py", '@patch("requests.Session")\ndef test(): pass\n')
    assert "requests.Session" in MockRuleGenerator(project_dirs=[]).extract_mocked_targets(f)


def test_extract_patch_single_quotes(tmp_path):
    f = write_test_file(tmp_path, "test_x.py", "@patch('boto3.client.Foo')\ndef t(): pass\n")
    assert "boto3.client.Foo" in MockRuleGenerator(project_dirs=[]).extract_mocked_targets(f)


def test_extract_bare_name_is_ignored(tmp_path):
    # "requests" has no dot -> not a class FQN.
    f = write_test_file(tmp_path, "test_x.py", '@patch("requests")\ndef t(): pass\n')
    assert MockRuleGenerator(project_dirs=[]).extract_mocked_targets(f) == set()


def test_extract_mock_spec_dotted(tmp_path):
    f = write_test_file(tmp_path, "test_x.py", "m = MagicMock(spec=redis.StrictRedis)\n")
    assert "redis.StrictRedis" in MockRuleGenerator(project_dirs=[]).extract_mocked_targets(f)


def test_extract_mock_spec_bare_name_resolved_via_import(tmp_path):
    source = "from pymongo import MongoClient\nm = Mock(spec=MongoClient)\n"
    f = write_test_file(tmp_path, "test_x.py", source)
    assert "pymongo.MongoClient" in MockRuleGenerator(project_dirs=[]).extract_mocked_targets(f)


def test_extract_excludes_framework(tmp_path):
    f = write_test_file(tmp_path, "test_x.py", '@patch("unittest.mock.patch")\ndef t(): pass\n')
    assert MockRuleGenerator(project_dirs=[]).extract_mocked_targets(f) == set()


def test_extract_excludes_stdlib(tmp_path):
    f = write_test_file(tmp_path, "test_x.py", '@patch("os.path.exists")\ndef t(): pass\n')
    assert MockRuleGenerator(project_dirs=[]).extract_mocked_targets(f) == set()


def test_extract_empty_file(tmp_path):
    f = write_test_file(tmp_path, "test_x.py", "def test(): pass\n")
    assert MockRuleGenerator(project_dirs=[]).extract_mocked_targets(f) == set()


def test_extract_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        MockRuleGenerator(project_dirs=[]).extract_mocked_targets(tmp_path / "nope.py")


# generate


def test_generate_returns_canonical_target_entries(tmp_path):
    project = tmp_path / "myproject"
    (project / "tests").mkdir(parents=True)
    write_test_file(project / "tests", "test_net.py", '@patch("requests.Session")\ndef t(): pass\n')

    result = MockRuleGenerator(project_dirs=[project]).generate()

    assert "requests.sessions.Session" in _targets(result)  # canonicalised
    entry = next(e for e in result["targets"] if e["target"] == "requests.sessions.Session")
    assert entry["decision"] == "mock"
    assert entry["source"] == "mock-rule-generator"
    # Unified with the classify schema — no extra fields.
    assert set(entry) == {"target", "decision", "reason", "source", "confidence"}


def test_generate_drops_non_class_targets(tmp_path):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    # Patching a module-level constant (a feature flag) is not a class boundary.
    write_test_file(
        project / "tests", "test_flag.py", '@patch("boto3.s3.transfer.HAS_CRT")\ndef t(): pass\n'
    )
    result = MockRuleGenerator(project_dirs=[project]).generate()
    assert "boto3.s3.transfer.HAS_CRT" not in _targets(result)


def test_generate_confidence_grows_with_more_files(tmp_path):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    write_test_file(project / "tests", "test_a.py", '@patch("requests.Session")\ndef t(): pass\n')
    write_test_file(project / "tests", "test_b.py", '@patch("requests.Session")\ndef t(): pass\n')

    result = MockRuleGenerator(project_dirs=[project]).generate()
    entry = next(e for e in result["targets"] if e["target"] == "requests.sessions.Session")
    assert entry["confidence"] == pytest.approx(0.67, abs=0.01)


def test_generate_min_files_threshold_drops_rare_targets(tmp_path):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    sess = '@patch("requests.Session")\ndef t(): pass\n'
    write_test_file(project / "tests", "test_a.py", sess)
    write_test_file(project / "tests", "test_b.py", sess)
    pool = '@patch("urllib3.PoolManager")\ndef t(): pass\n'
    write_test_file(project / "tests", "test_c.py", pool)

    result = MockRuleGenerator(project_dirs=[project], min_files=2).generate()
    targets = _targets(result)
    assert "requests.sessions.Session" in targets
    assert "urllib3.poolmanager.PoolManager" not in targets


def test_generate_skips_missing_project_dir(tmp_path, caplog):
    gen = MockRuleGenerator(project_dirs=[tmp_path / "does_not_exist"])
    with caplog.at_level(logging.WARNING):
        result = gen.generate()
    assert result == {"targets": []}
