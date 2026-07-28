# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Discovery of the modules to evaluate (bundled examples or rundefinition XML)."""

from __future__ import annotations

import importlib.util
import xml.etree.ElementTree as ET  # noqa: S405
from dataclasses import dataclass
from pathlib import Path

from . import console, err_console

# quick_eval lives at <repo>/utils/_quick_eval/tasks.py, so parents[2] is the repo root
# (pynguin-4) and its sibling is the pynguin-experiments checkout that holds the
# rundefinition XMLs and project sources.
_REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = _REPO_ROOT.parent / "pynguin-experiments"
RUNDEFINITIONS_DIR = EXPERIMENTS_DIR / "rundefinitions"
DEFAULT_PROJECTS_DIR = EXPERIMENTS_DIR / "projects"

# Bundled example subjects — small packages installed in the project venv.
# Each entry: (project_name, top_level_package, [module_names_to_test])
BUNDLED_EXAMPLES: list[tuple[str, str, list[str]]] = [
    ("codetiming", "codetiming", ["codetiming._timers"]),
    ("first", "first", ["first"]),
    ("python-slugify", "slugify", ["slugify.slugify"]),
    ("tzlocal", "tzlocal", ["tzlocal.unix"]),
    ("untangle", "untangle", ["untangle"]),
]


@dataclass
class ModuleTask:
    """Input specification for one Pynguin run."""

    project: str
    module: str
    project_path: str


def _find_package_path(top_level_package: str) -> str | None:
    """Return the parent dir of an installed package, suitable as --project-path."""
    spec = importlib.util.find_spec(top_level_package)
    if spec is None:
        return None
    if spec.origin:
        origin = Path(spec.origin)
        if origin.name == "__init__.py":
            # Package: origin is pkg/__init__.py, so site-packages is two levels up.
            return str(origin.parent.parent)
        # Top-level single-file module: origin sits directly in site-packages.
        return str(origin.parent)
    if spec.submodule_search_locations:
        locs = list(spec.submodule_search_locations)
        if locs:
            return str(Path(locs[0]).parent)
    return None


def bundled_tasks() -> list[ModuleTask]:
    """Build a ModuleTask list from the bundled example subjects."""
    tasks: list[ModuleTask] = []
    for project, top_pkg, modules in BUNDLED_EXAMPLES:
        path = _find_package_path(top_pkg)
        if path is None:
            console.print(f"[yellow][warn][/yellow] Cannot locate '{top_pkg}', skipping.")
            continue
        tasks.extend(
            ModuleTask(project=project, module=module, project_path=path) for module in modules
        )
    return tasks


def resolve_rundefinition(value: str) -> str:
    """Resolve a rundefinition path or bare name.

    Accepts a full/relative path, or a bare name (with or without the ``.xml``
    suffix) which is looked up in ``../pynguin-experiments/rundefinitions/``.
    Falls back to the given value unchanged so downstream parsing raises a clear
    error when nothing matches.
    """
    if Path(value).exists():
        return value
    for candidate in (RUNDEFINITIONS_DIR / value, RUNDEFINITIONS_DIR / f"{value}.xml"):
        if candidate.exists():
            return str(candidate)
    return value


def xml_tasks(
    rundefinition: str, projects_dir: str, modules_filter: list[str] | None
) -> list[ModuleTask]:
    """Build a ModuleTask list by parsing a rundefinition XML file."""
    tree = ET.parse(rundefinition)  # noqa: S314
    root = tree.getroot()
    tasks: list[ModuleTask] = []
    for project_elem in root.findall("project"):
        sources = project_elem.findtext("sources", "")
        project_name = project_elem.findtext("name", "")
        project_path = str(Path(projects_dir) / sources)
        for mod_elem in project_elem.findall("modules/module"):
            module_name = mod_elem.text or ""
            if modules_filter and module_name not in modules_filter:
                continue
            tasks.append(
                ModuleTask(project=project_name, module=module_name, project_path=project_path)
            )
    return tasks


def resolve_tasks(
    *,
    use_bundled: bool,
    rundefinition: str | None,
    projects_dir: str | None,
    modules: list[str] | None,
) -> list[ModuleTask] | None:
    """Resolve the task list, applying pynguin-experiments convenience defaults.

    A bare ``rundefinition`` name is resolved against the experiments checkout and,
    when ``projects_dir`` is omitted, it defaults to ``../pynguin-experiments/projects``.
    """
    if use_bundled:
        tasks = bundled_tasks()
        if modules:
            tasks = [t for t in tasks if t.module in modules]
    elif rundefinition:
        rundef_path = resolve_rundefinition(rundefinition)
        base_dir = projects_dir or str(DEFAULT_PROJECTS_DIR)
        tasks = xml_tasks(rundef_path, base_dir, modules)
    else:
        err_console.print("Error: specify --use-bundled-examples or --rundefinition")
        return None
    if not tasks:
        err_console.print("No tasks found.")
        return None
    return tasks
