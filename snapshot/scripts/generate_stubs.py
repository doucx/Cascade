#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cascade Provider Stub Generator.

This script scans the workspace for all `pyproject.toml` files, finds the
providers registered under the 'cascade.providers' entry point, and generates
a set of .pyi stub files.

These stubs provide type hints for the dynamically loaded providers (like `cs.io`,
`cs.shell`, etc.), enabling static analysis tools (like Pyright/Pylance) to
offer autocompletion and type checking, significantly improving developer
experience (DX).

Run this script from the root of the repository after adding or removing providers.
"""

import sys
import shutil
from pathlib import Path
from collections import defaultdict

# tomllib is standard in Python 3.11+. For older versions, we need to import toml.
if sys.version_info < (3, 11):
    try:
        import toml
    except ImportError:
        print(
            "Error: 'toml' library is required for Python < 3.11. "
            "Please run 'pip install toml'",
            file=sys.stderr,
        )
        sys.exit(1)
else:
    import tomllib as toml


# The root directory of the project, assuming the script is in /scripts
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
PACKAGES_DIR = PROJECT_ROOT / "packages"
STUBS_OUTPUT_DIR = PACKAGES_DIR / "cascade-sdk" / "src" / "cascade"

# List of known public exports from cascade-sdk/src/cascade/__init__.py
# This is crucial because a .pyi file completely overrides the module's public
# interface for type checkers. We must re-export the actual API.
KNOWN_SDK_EXPORTS = {
    # Core Specs
    "task": "cascade.spec.task",
    "LazyResult": "cascade.spec.lazy_types",
    "Router": "cascade.spec.routing",
    "resource": "cascade.spec.resource",
    "inject": "cascade.spec.resource",
    "with_constraints": "cascade.spec.constraint",
    # V1.3 Core Components
    "Param": "cascade",
    "Env": "cascade",
    # Runtime
    "run": "cascade",
    "Engine": "cascade.runtime.engine",
    "Event": "cascade.runtime.events",
    "DependencyMissingError": "cascade.runtime.exceptions",
    # Flow control
    "sequence": "cascade.flow",
    "pipeline": "cascade.flow",
    # Tools
    "override_resource": "cascade.testing",
    "dry_run": "cascade.tools.preview",
    "visualize": "cascade.tools.visualize",
    "create_cli": "cascade.tools.cli",
    "to_json": "cascade.graph.serialize",
    "from_json": "cascade.graph.serialize",
    "get_current_context": "cascade.context",
}


def find_provider_names() -> list[str]:
    """Finds all registered provider names from pyproject.toml files."""
    provider_names = []
    toml_files = list(PACKAGES_DIR.glob("**/pyproject.toml"))
    print(f"🔍 Found {len(toml_files)} pyproject.toml files to scan.")

    for toml_file in toml_files:
        try:
            with open(toml_file, "rb") as f:
                data = toml.load(f)

            entry_points = data.get("project", {}).get("entry-points", {})
            providers = entry_points.get("cascade.providers", {})

            if providers:
                print(
                    f"  - Found {len(providers)} providers in {toml_file.relative_to(PROJECT_ROOT)}"
                )
                provider_names.extend(providers.keys())

        except Exception as e:
            print(f"⚠️  Could not parse {toml_file}: {e}", file=sys.stderr)

    return sorted(list(set(provider_names)))


def build_provider_tree(names: list[str]) -> dict:
    """Builds a nested dictionary from a flat list of dot-separated names."""
    tree = {}
    for name in names:
        parts = name.split(".")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        # Mark the last part as a terminal node (a provider function)
        node[parts[-1]] = True
    return tree


def generate_stubs(tree: dict, output_dir: Path):
    """
    Generates the directory structure and .pyi stub files recursively.
    """
    print(f"\n🗑️  Cleaning up old stubs in {output_dir.relative_to(PROJECT_ROOT)}...")
    if output_dir.exists():
        for item in output_dir.iterdir():
            # Be careful: only remove .pyi files and directories that match our tree.
            if item.is_file() and item.suffix == ".pyi":
                if item.name != "__init__.pyi":  # Keep top-level __init__ for now
                    item.unlink()
            elif item.is_dir() and item.name in tree:
                shutil.rmtree(item)

    output_dir.mkdir(exist_ok=True)
    print("✨ Generating new stubs...")

    # Start the recursive generation
    _generate_level(tree, output_dir, is_root=True)
    print("\n✅ Stub generation complete!")


def _generate_level(subtree: dict, current_dir: Path, is_root: bool = False):
    """
    Writes the __init__.pyi for the current level and recurses for sub-namespaces.
    """
    current_dir.mkdir(exist_ok=True)
    # CRITICAL: Ensure the directory is a Python package by adding __init__.py
    (current_dir / "__init__.py").touch()
    init_pyi_path = current_dir / "__init__.pyi"

    # --- Base header for all .pyi files ---
    content_lines = [
        "# This file is auto-generated by scripts/generate_stubs.py.",
        "# Do not edit this file directly.",
    ]

    # --- Lists to hold discovered members ---
    pyi_providers = []
    pyi_namespaces = []

    # --- Re-export known SDK members ONLY in the root __init__.pyi ---
    if is_root:
        content_lines.append("\n# --- Known SDK Exports ---")
        imports_by_module = defaultdict(list)
        for name, module in KNOWN_SDK_EXPORTS.items():
            imports_by_module[module].append(name)

        for module, names in sorted(imports_by_module.items()):
            content_lines.append(f"from {module} import {', '.join(sorted(names))}")
        content_lines.append("\n# --- Discovered Providers ---")

    # --- Separate providers (terminals) from namespaces (sub-trees) ---
    for name, value in sorted(subtree.items()):
        if isinstance(value, dict):
            pyi_namespaces.append(name)
            # Recurse into the sub-directory
            _generate_level(value, current_dir / name)
        else:
            pyi_providers.append(name)

    # --- Assemble the final .pyi content ---

    # 1. Add LazyFactory import only if there are actual providers at this level
    if pyi_providers:
        content_lines.append("from cascade.spec.protocols import LazyFactory")
        content_lines.extend(f"{name}: LazyFactory" for name in pyi_providers)

    # 2. Re-export sub-namespaces to make them discoverable by type checkers
    if pyi_namespaces:
        if pyi_providers:
            content_lines.append("")  # Add a blank line for readability
        content_lines.extend(f"from . import {name}" for name in pyi_namespaces)

    # --- Write the __init__.pyi file for the current level ---
    content = "\n".join(content_lines)
    with open(init_pyi_path, "w", encoding="utf-8") as f:
        f.write(content)
        f.write("\n")  # Ensure trailing newline

    print(f"  - Wrote {init_pyi_path.relative_to(PROJECT_ROOT)}")


def main():
    """Main execution flow."""
    print("--- Cascade Provider Stub Generator ---")

    if not STUBS_OUTPUT_DIR.exists() or not PACKAGES_DIR.exists():
        print("Error: Script must be run from the project root.", file=sys.stderr)
        print(f"Could not find required directory: {STUBS_OUTPUT_DIR}", file=sys.stderr)
        sys.exit(1)

    provider_names = find_provider_names()
    if not provider_names:
        print("No providers found. Exiting.", file=sys.stderr)
        return

    provider_tree = build_provider_tree(provider_names)
    generate_stubs(provider_tree, STUBS_OUTPUT_DIR)

    print(
        "\n💡 Tip: You may need to restart your IDE's language server for changes to take effect."
    )


if __name__ == "__main__":
    main()
