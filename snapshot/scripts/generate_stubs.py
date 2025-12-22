#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cascade Provider Stub Generator.

This script scans the workspace for all `pyproject.toml` files, finds the
providers registered under the 'cascade.providers' entry point, dynamically
inspects their function signatures and docstrings, and generates a set of
rich .pyi stub files.

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


PROJECT_ROOT = Path(__file__).parent.parent.resolve()
PACKAGES_DIR = PROJECT_ROOT / "packages"
STUBS_OUTPUT_DIR = PACKAGES_DIR / "cascade-sdk" / "src" / "cascade"

KNOWN_SDK_EXPORTS = {
    # Core Specs
    "task": "cascade.spec.task",
    "LazyResult": "cascade.spec.lazy_types",
    "Router": "cascade.spec.routing",
    "resource": "cascade.spec.resource",
    "inject": "cascade.spec.resource",
    "with_constraints": "cascade.spec.constraint",
    # V1.3 Core Components defined in cascade/__init__.py
    "Param": "cascade",
    "Env": "cascade",
    # Runtime Entrypoint defined in cascade/__init__.py
    "run": "cascade",
    # Other runtime exports
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


def setup_path():
    """Adds all package src directories to sys.path to ensure imports work."""
    # Order matters: deps should be available.
    # We simply add all 'src' folders found in 'packages/'
    for package_dir in PACKAGES_DIR.iterdir():
        if package_dir.is_dir():
            src_dir = package_dir / "src"
            if src_dir.exists():
                sys.path.insert(0, str(src_dir))
    
    # Also add root for good measure
    sys.path.insert(0, str(PROJECT_ROOT))


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


def get_function_signature(target_func: Callable) -> Optional[Tuple[str, str]]:
    """Inspects a function to get its signature and docstring."""
    try:
        sig = inspect.signature(target_func)
        doc = inspect.getdoc(target_func)

        if doc:
            # Indent the docstring so it aligns with the function body
            indented_doc = textwrap.indent(doc, "    ")
            formatted_doc = f'    """\n{indented_doc}\n    """'
        else:
            formatted_doc = ""

        # Handle return annotation
        # Safest bet: force it to simple LazyResult without [Any] to avoid 'Unknown'
        # if the type checker can't resolve the generic or if it's not generic.
        if sig.return_annotation != inspect.Signature.empty:
             # Just replace whatever it is with LazyResult
             sig = sig.replace(return_annotation="LazyResult")
        
        signature_str = str(sig)
        # Remove quotes that might have been added by signature stringification
        signature_str = signature_str.replace("'LazyResult'", "LazyResult")

        return signature_str, formatted_doc
    except Exception as e:
        print(f"⚠️  Could not inspect function '{getattr(target_func, '__name__', 'unknown')}': {e}", file=sys.stderr)
        return None


def get_provider_signature(entry_point: str) -> Optional[Tuple[str, str]]:
    """Dynamically imports a provider and inspects its signature."""
    try:
        module_name, class_name = entry_point.split(":")
        module = importlib.import_module(module_name)
        provider_class = getattr(module, class_name)
        provider_instance = provider_class()
        factory = provider_instance.create_factory()
        target_func = getattr(factory, "func", factory)
        return get_function_signature(target_func)
    except Exception as e:
        print(f"⚠️  Could not load provider entry point '{entry_point}': {e}", file=sys.stderr)
        return None


def build_provider_tree(providers: Dict[str, str]) -> dict:
    """Builds a nested dictionary from a flat dict of dot-separated names."""
    tree = {}
    for name, entry_point in providers.items():
        parts = name.split(".")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = entry_point
    return tree


def generate_stubs(tree: dict, output_dir: Path):
    """Generates the directory structure and .pyi stub files recursively."""
    print(f"\n🗑️  Cleaning up old stubs in {output_dir.relative_to(PROJECT_ROOT)}...")
    if output_dir.exists():
        for item in output_dir.iterdir():
            if item.is_dir() and item.name in tree:
                shutil.rmtree(item)
            elif item.is_file() and item.suffix == ".pyi" and item.name != "__init__.pyi":
                item.unlink()

    output_dir.mkdir(exist_ok=True)
    print("✨ Generating new stubs...")
    _generate_level(tree, output_dir, is_root=True)
    print("\n✅ Stub generation complete!")


def _generate_level(subtree: dict, current_dir: Path, is_root: bool = False):
    """Writes the __init__.pyi for the current level and recurses."""
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
        sdk_natives = {}

        for name, module_path in KNOWN_SDK_EXPORTS.items():
            if module_path == "cascade":
                try:
                    # Now that sys.path is setup, this should work
                    sdk_module = importlib.import_module("cascade")
                    native_func = getattr(sdk_module, name)
                    sdk_natives[name] = native_func
                except Exception as e:
                    # Fallback to Callable if inspection fails, so at least it exists
                    print(f"⚠️  Could not inspect native SDK export '{name}': {e}", file=sys.stderr)
                    content_lines.append(f"{name}: Callable[..., Any]")
            else:
                imports_by_module[module_path].append(name)

        for module_path, names in sorted(imports_by_module.items()):
            content_lines.append(f"from {module_path} import {', '.join(sorted(names))}")
        
        if sdk_natives:
             content_lines.append("\n# --- Locally Defined Exports ---")
             for name, func in sorted(sdk_natives.items()):
                sig_info = get_function_signature(func)
                if sig_info:
                    sig_str, doc_str = sig_info
                    # Use a clean definition with one newline
                    provider_def = f"def {name}{sig_str}:\n{doc_str}"
                    content_lines.append(provider_def)

        content_lines.append("\n# --- Discovered Providers ---")

    for name, value in sorted(subtree.items()):
        if isinstance(value, dict):
            pyi_namespaces.append(name)
            _generate_level(value, current_dir / name)
        else:
            sig_info = get_provider_signature(value)
            if sig_info:
                sig_str, doc_str = sig_info
                provider_def = f"def {name}{sig_str}:\n{doc_str}"
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
    
    # CRITICAL FIX: Ensure all package sources are visible
    setup_path()

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