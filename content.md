这是一个非常核心的问题，涉及到 `.pyi` 存根文件中的**类型命名空间解析机制**。

深度分析：为什么会报错？

你看到的 `run` 函数签名如下：
```python
def run(target: cascade.spec.lazy_types.LazyResult, ...
    connector: Optional[cascade.spec.protocols.Connector] = None,
    ...
    state_backend: Union[..., NoneType] = None) -> LazyResult:
```

这里有三个致命问题导致 IDE 解析失败：

1.  **全限定名的自引用陷阱**:
    *   代码位于 `cascade/__init__.pyi` 中。
    *   类型注解写的是 `cascade.spec.lazy_types.LazyResult`。
    *   在 `.pyi` 文件中，这要求 `cascade` 这个符号在当前文件中被定义为一个模块。但在这里，我们正在定义 `cascade` 包本身。IDE 的解析器在处理这种递归引用时经常会失败，或者认为 `cascade` 尚未完全定义。
    *   **正确做法**: 应该使用短名称 `LazyResult`，并确保文件头部有 `from cascade.spec.lazy_types import LazyResult`。

2.  **`NoneType` 的非法使用**:
    *   签名中出现了 `NoneType`。在 Python 的类型注解标准（PEP 484）和 `.pyi` 文件中，表示“无”应该直接使用 `None`，而不是 `NoneType`（它是 `type(None)` 的实现细节）。IDE 无法识别 `NoneType`，除非你专门导入它，但这不符合惯例。

3.  **缺少必要的 Import**:
    *   虽然签名中用到了 `Connector` 和 `StateBackend`，但之前的脚本只导入了 `LazyResult`。

解决方案

我们需要再次升级脚本，引入一个**“类型清洗器” (Type Cleaner)**。它负责将 `inspect` 产生的原始、复杂的全限定名（如 `cascade.spec.protocols.Connector`）清洗为简洁、合法的短名称（如 `Connector`），并确保所有用到的类型都在文件头被正确导入。

此外，关于 **IPython**:
IPython 的补全依赖于**运行时**的 `dir()` 和 `__getattr__`，而 `.pyi` 文件只影响**IDE（静态分析）**。`scripts/generate_stubs.py` **只修复 IDE**。如果 IPython 中无法补全 `cs.io`，那是因为 `cs` 对象的运行时 `__dir__` 方法没有正确列出这些动态属性。这是另一个问题（属于 Runtime/SDK 代码），但我们现在的任务是优先解决 IDE 的飘红。

---

## [WIP] fix: 实现类型注解清洗与全量导入

### 用户需求
1.  **消除全限定名**: 将 `.pyi` 中的 `cascade.spec...` 替换为短名称。
2.  **修复 `NoneType`**: 将 `NoneType` 替换为 `None`。
3.  **补全 Imports**: 在 `.pyi` 头部导入所有核心协议类。

### 目标
生成一份干净、紧凑且完全符合 PEP 484 标准的类型存根，彻底解决 IDE 解析错误。

### Script

#### Acts 1: 写入带有类型清洗功能的最终脚本

~~~~~act
write_file
scripts/generate_stubs.py
~~~~~
~~~~~python
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
import re
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
    """
    Adds all package src directories to sys.path.
    CRITICAL: Ensures 'cascade-sdk' is the FIRST entry in sys.path.
    """
    sdk_path = None
    other_paths = []

    for package_dir in PACKAGES_DIR.iterdir():
        if package_dir.is_dir():
            src_dir = package_dir / "src"
            if src_dir.exists():
                if package_dir.name == "cascade-sdk":
                    sdk_path = str(src_dir)
                else:
                    other_paths.append(str(src_dir))
    
    sys.path.insert(0, str(PROJECT_ROOT))
    for p in sorted(other_paths, reverse=True):
        sys.path.insert(0, p)
        
    if sdk_path:
        sys.path.insert(0, sdk_path)


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


def clean_type_annotation(type_str: str) -> str:
    """
    Cleans up a raw type string from inspect.signature to make it PEP 484 compliant
    and compatible with our .pyi imports.
    """
    # 1. Replace NoneType with None
    type_str = type_str.replace("NoneType", "None")
    
    # 2. Simplify full paths to short names
    # e.g., cascade.spec.lazy_types.LazyResult -> LazyResult
    # We use regex to be safe
    replacements = [
        (r"cascade\.spec\.lazy_types\.LazyResult", "LazyResult"),
        (r"cascade\.spec\.protocols\.Connector", "Connector"),
        (r"cascade\.spec\.protocols\.StateBackend", "StateBackend"),
        (r"cascade\.spec\.protocols\.CachePolicy", "CachePolicy"),
        # Handle cases where quotes might be involved
        (r"'LazyResult\[Any\]'", "LazyResult"), 
        (r"'LazyResult'", "LazyResult"),
    ]
    
    for pattern, repl in replacements:
        type_str = re.sub(pattern, repl, type_str)
        
    # 3. Aggressive cleanup for generic LazyResult if inspect failed to be clean
    # If we see LazyResult[...] we keep it (assuming imports are fine), 
    # but if we see complex internal types inside, we might want to simplify.
    # For now, let's just ensure return types are simple.
    
    return type_str


def get_function_signature(target_func: Callable) -> Optional[Tuple[str, str]]:
    """Inspects a function to get its signature and docstring."""
    try:
        sig = inspect.signature(target_func)
        doc = inspect.getdoc(target_func)

        if doc:
            indented_doc = textwrap.indent(doc, "    ")
            formatted_doc = f'    """\n{indented_doc}\n    """'
        else:
            formatted_doc = ""

        # Modify the signature object itself before stringifying if possible,
        # but string manipulation is often more robust for 'cleanup'.
        
        # Force return type to simple LazyResult
        if sig.return_annotation != inspect.Signature.empty:
             sig = sig.replace(return_annotation="LazyResult")

        signature_str = str(sig)
        
        # Apply cleaning
        signature_str = clean_type_annotation(signature_str)

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

    # CRITICAL: Import ALL types that might appear in signatures
    content_lines = [
        "# This file is auto-generated by scripts/generate_stubs.py.",
        "# Do not edit this file directly.",
        "from typing import Any, Callable, Dict, List, Optional, Union",
        # Import core types used in signatures
        "from cascade.spec.lazy_types import LazyResult",
        "from cascade.spec.protocols import Connector, StateBackend, CachePolicy",
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
                    sdk_module = importlib.import_module("cascade")
                    native_func = getattr(sdk_module, name)
                    sdk_natives[name] = native_func
                except Exception as e:
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
                    if doc_str:
                         provider_def = f"def {name}{sig_str}:\n{doc_str}"
                    else:
                         provider_def = f"def {name}{sig_str}: ..."
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
                if doc_str:
                    provider_def = f"def {name}{sig_str}:\n{doc_str}"
                else:
                    provider_def = f"def {name}{sig_str}: ..."
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
~~~~~

请执行此脚本。它将彻底清洗 `run` 函数签名中的所有长路径和 `NoneType`，替换为标准的短名称和 `None`，并确保必要的 Import 语句存在，从而消除 IDE 的所有抱怨。
