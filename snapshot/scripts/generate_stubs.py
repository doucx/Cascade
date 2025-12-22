#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cascade Provider Stub Generator.

This script scans the workspace for all `pyproject.toml` files, finds the
providers registered under the 'cascade.providers' entry point, dynamically
inspects their function signatures and docstrings, and generates a set of
rich .pyi stub files.

These stubs provide precise type hints for dynamically loaded providers (like
`cs.io`, `cs.shell`, etc.), enabling static analysis tools (like Pyright/
Pylance) to offer full autocompletion, parameter info, and docstrings,
significantly improving developer experience (DX).

Run this script from the root of the repository after adding or removing providers.
"""

import sys
import shutil
import inspect
import textwrap
import importlib
from pathlib import Path
from collections import defaultdict
from typing import Any, Callable, Dict, List, Tuple, Optional

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
    "Param": "cascade", # Special case, defined in __init__.py
    "Env": "cascade",   # Special case, defined in __init__.py
    # Runtime
    "run": "cascade",   # Special case, defined in __init__.py
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


def find_providers() -> Dict[str, str]:
    """Finds all registered providers and their entry points."""
    providers = {}
    toml_files = list(PACKAGES_DIR.glob("**/pyproject.toml"))
    print(f"🔍 Found {len(toml_files)} pyproject.toml files to scan.")

    for toml_file in toml_files:
        try:
            with open(toml_file, "rb") as f:
                data = toml.load(f)

            entry_points = data.get("project", {}).get("entry-points", {})
            provider_eps = entry_points.get("cascade.providers", {})

            if provider_eps:
                print(
                    f"  - Found {len(provider_eps)} providers in {toml_file.relative_to(PROJECT_ROOT)}"
                )
                providers.update(provider_eps)

        except Exception as e:
            print(f"⚠️  Could not parse {toml_file}: {e}", file=sys.stderr)

    return dict(sorted(providers.items()))


def get_provider_signature(entry_point: str) -> Optional[Tuple[str, str]]:
    """
    Dynamically imports a provider and inspects its signature and docstring.
    """
    try:
        module_name, class_name = entry_point.split(":")
        module = importlib.import_module(module_name)
        provider_class = getattr(module, class_name)

        # Instantiate the provider to get its factory
        provider_instance = provider_class()
        factory = provider_instance.create_factory()

        # The factory might be a Task object, which holds the original function
        target_func = getattr(factory, "func", factory)

        # Get signature and docstring
        sig = inspect.signature(target_func)
        doc = inspect.getdoc(target_func) or ""

        # Format docstring
        formatted_doc = '"""\n' + textwrap.indent(doc, "    ") + '\n    """'

        # Format signature
        # Replace return type annotation with LazyResult for accuracy
        sig = sig.replace(return_annotation="LazyResult[Any]")
        signature_str = str(sig)

        return signature_str, formatted_doc

    except Exception as e:
        print(f"⚠️  Could not inspect provider '{entry_point}': {e}", file=sys.stderr)
        return None


def build_provider_tree(providers: Dict[str, str]) -> dict:
    """Builds a nested dictionary from a flat dict of dot-separated names."""
    tree = {}
    for name, entry_point in providers.items():
        parts = name.split(".")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        # Store the entry point at the terminal node
        node[parts[-1]] = entry_point
    return tree


def generate_stubs(tree: dict, output_dir: Path):
    """
    Generates the directory structure and .pyi stub files recursively.
    """
    print(f"\n🗑️  Cleaning up old stubs in {output_dir.relative_to(PROJECT_ROOT)}...")
    # A more robust cleanup: remove all .pyi files and known subdirectories
    if output_dir.exists():
        for item in output_dir.iterdir():
            if item.is_dir() and item.name in tree:
                shutil.rmtree(item)
            elif item.is_file() and item.suffix == ".pyi" and item.name != "__init__.pyi":
                item.unlink()

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
    (current_dir / "__init__.py").touch()
    init_pyi_path = current_dir / "__init__.pyi"

    content_lines = [
        "# This file is auto-generated by scripts/generate_stubs.py.",
        "# Do not edit this file directly.",
        "from typing import Any, Callable, Dict, List, Optional, Union",
        "from cascade.spec.lazy_types import LazyResult",
    ]

    pyi_providers = []
    pyi_namespaces = []

    if is_root:
        content_lines.append("\n# --- Known SDK Exports ---")
        imports_by_module = defaultdict(list)
        special_cases = []

        for name, module in KNOWN_SDK_EXPORTS.items():
            if module == "cascade":  # Fix for circular import
                special_cases.append(name)
            else:
                imports_by_module[module].append(name)

        for module, names in sorted(imports_by_module.items()):
            content_lines.append(f"from {module} import {', '.join(sorted(names))}")
        
        # Handle special cases with a generic Callable to avoid errors
        if special_cases:
             content_lines.append("\n# --- Locally Defined Exports ---")
             for name in sorted(special_cases):
                 content_lines.append(f"{name}: Callable[..., Any]")

        content_lines.append("\n# --- Discovered Providers ---")

    for name, value in sorted(subtree.items()):
        if isinstance(value, dict):  # It's a namespace
            pyi_namespaces.append(name)
            _generate_level(value, current_dir / name)
        else:  # It's a terminal node (a provider function)
            signature_info = get_provider_signature(value)
            if signature_info:
                sig_str, doc_str = signature_info
                provider_def = f"def {name}{sig_str}:\n{doc_str}\n"
                pyi_providers.append(provider_def)

    if pyi_providers:
        content_lines.extend(pyi_providers)

    if pyi_namespaces:
        if pyi_providers:
            content_lines.append("")
        content_lines.extend(f"from . import {name} as {name}" for name in pyi_namespaces)

    content = "\n".join(content_lines)
    with open(init_pyi_path, "w", encoding="utf-8") as f:
        f.write(content)
        f.write("\n")

    print(f"  - Wrote {init_pyi_path.relative_to(PROJECT_ROOT)}")


def main():
    """Main execution flow."""
    print("--- Cascade Provider Stub Generator ---")
    
    # Add project packages to path to allow inspection
    sys.path.insert(0, str(PACKAGES_DIR / "cascade-spec" / "src"))
    sys.path.insert(0, str(PACKAGES_DIR / "cascade-sdk" / "src"))
    sys.path.insert(0, str(PACKAGES_DIR / "cascade-library" / "src"))


    if not STUBS_OUTPUT_DIR.exists() or not PACKAGES_DIR.exists():
        print("Error: Script must be run from the project root.", file=sys.stderr)
        sys.exit(1)

    providers = find_providers()
    if not providers:
        print("No providers found. Exiting.", file=sys.stderr)
        return

    provider_tree = build_provider_tree(providers)
    generate_stubs(provider_tree, STUBS_OUTPUT_DIR)

    print(
        "\n💡 Tip: You may need to restart your IDE's language server (e.g., 'Developer: Reload Window' in VS Code) for changes to take effect."
    )


if __name__ == "__main__":
    main()