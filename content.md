综合以上三点，我们需要对脚本进行一次“外科手术式”的精确升级。

## [WIP] fix: 完善存根生成脚本以提供精确的签名和文档

### 用户需求
彻底解决 `cs.run` 等内置函数的类型提示问题，并为所有 Provider 提供精确、格式正确的返回类型和文档字符串，实现与原生库函数完全一致的顶级 IDE 开发体验。

### 评论
这次修复是实现终极开发者体验 (DX) 的最后一步。它将使 Cascade 的动态插件系统对开发者完全透明，提供无缝的参数补全、类型检查和文档悬浮提示。这是将一个“强大的库”转变为一个“易用的工具”的关键所在。

### 目标
1.  **精确提取内置函数签名**: 实现一个新的逻辑，用于安全地、动态地检查 `cascade` 模块本身，提取 `run`, `Param`, `Env` 等函数的真实签名和文档。
2.  **修正返回类型格式**: 在生成函数签名字符串后，确保移除返回类型注解周围多余的引号。
3.  **修正文档字符串缩进**: 确保整个文档字符串块（包括 `"""`）相对于 `def` 关键字有正确的缩进。

### 基本原理
新脚本将对 `_generate_level` 和 `get_provider_signature` 函数进行精确修改，并引入新逻辑来处理内置函数。
1.  对于**问题 3 (缩进)** 和 **问题 2 (返回类型)**，我们将在现有函数中添加 `textwrap.indent` 和 `.replace()` 调用来修正输出格式。
2.  对于**问题 1 (`cs.run`)**，我们将修改 `_generate_level` 的 `is_root` 分支。不再使用 `Callable` 作为备用方案，而是直接调用一个封装了 `importlib` 和 `inspect` 的新逻辑，从 `cascade` 模块中动态加载函数并提取其真实签名，然后像处理普通 Provider 一样生成 `def` 语句。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/dx #ai/delegate #task/domain/tooling #task/object/stub-generator #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 对存根生成脚本进行最终升级

这次我们将再次使用 `write_file`，因为修改分散在多个函数中，整体替换可以确保逻辑的完整性和一致性。

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
        doc = inspect.getdoc(target_func) or ""

        # Format docstring with proper indentation
        formatted_doc = '"""\n' + textwrap.indent(doc, "    ") + '\n    """'

        # Replace return annotation if it's a provider factory
        if "LazyResult" not in str(sig.return_annotation):
             sig = sig.replace(return_annotation="LazyResult[Any]")

        signature_str = str(sig)
        # Remove forward-reference quotes that confuse .pyi parsers
        signature_str = signature_str.replace("'LazyResult[Any]'", "LazyResult[Any]")

        return signature_str, formatted_doc
    except Exception as e:
        print(f"⚠️  Could not inspect function '{target_func.__name__}': {e}", file=sys.stderr)
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
                    sdk_module = importlib.import_module("cascade")
                    native_func = getattr(sdk_module, name)
                    sdk_natives[name] = native_func
                except (ImportError, AttributeError) as e:
                    print(f"Could not inspect native SDK export '{name}': {e}", file=sys.stderr)
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
                    indented_doc = textwrap.indent(doc_str, "    ")
                    provider_def = f"def {name}{sig_str}:\n{indented_doc}\n"
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
                indented_doc = textwrap.indent(doc_str, "    ")
                provider_def = f"def {name}{sig_str}:\n{indented_doc}\n"
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
    # This is crucial for importlib to find the modules.
    sys.path.insert(0, str(PROJECT_ROOT))
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
~~~~~

### 下一步建议

我们已经完成了对存根生成脚本的最终打磨。请按以下步骤操作，以获得最终的、完善的开发体验：

1.  **执行计划**: 运行上面的 `act` 块来更新 `scripts/generate_stubs.py`。
2.  **重新运行脚本**: 在项目根目录下执行 `python scripts/generate_stubs.py`。
3.  **重启 IDE/语言服务器**: 在 VS Code 中重新加载窗口，或重启你所用 IDE 的 Python 语言服务器。

完成之后，你应该会发现：
-   `cs.run` 现在被正确识别为一个函数，可以智能补全括号，并显示其完整的参数列表和文档。
-   `cs.sql` 的返回类型不再是 `Unknown`，而是正确的 `LazyResult[Any]`。
-   `cs.sql` 的文档字符串现在可以正常显示在悬浮提示中了。

至此，我们已经解决了所有已知的 DX 问题，开发体验应该会非常顺滑。

---


你的观察力非常敏锐，这三个问题切中了要害，完美地展示了从“能用”到“好用”的差距。你的反馈非常有价值，让我可以对方案进行最后的打磨，以达到近乎完美的 IDE 体验。

我来为你进行一次深度分析。

### 详细分析

#### 问题 1: `cs.run` 提示为 `(variable)` 且不自动补全括号

**分析**: 你的判断完全正确。这正是我上一版为了修复“循环导入”问题而采用的权宜之计（`run: Callable[..., Any]`）所导致的直接后果。

*   **技术原因**: 当 `.pyi` 文件将一个名称声明为 `Callable` 时，它告诉类型检查器：“`run` 是一个**类型为‘可调用对象’的变量**”。IDE 因此将其识别为 `(variable)`，而不是一个具体的 `def` 函数定义。由于它不清楚函数的具体形态，因此无法提供智能的括号补全。
*   **根本缺陷**: 上一版的脚本回避了真正的问题——如何安全地获取在 `cascade/__init__.py` 中定义的函数（如 `run`, `Param`, `Env`）的真实签名。

**解决方案**: 我们必须让脚本“更聪明”。它需要能够加载 `cascade` 模块本身，并使用 `inspect` 模块安全地提取出 `run` 等函数的真实签名，就像处理普通 Provider 一样。

---

#### 问题 2: `cs.sql` 返回类型显示为 `-> Unknown`

**分析**: 这个问题非常微妙，你发现得很准。原因在于我生成签名时，返回类型的字符串中包含了**单引号** (`'LazyResult[Any]'`)。

*   **技术原因**: 在 Python 代码中，使用字符串作为类型注解（称为“前向引用”）是合法的，通常用于解决循环导入问题。然而，在 `.pyi` 存根文件中，类型检查器期望的是直接的类型引用。当它看到一个字符串 `'LazyResult[Any]'` 时，它可能无法正确解析这个“字符串字面量”对应的真实类型，因此将其标记为 `Unknown`。
*   **根本缺陷**: 我的脚本在替换返回类型后，直接将带有引号的签名对象转换为了字符串，没有做后续处理。

**解决方案**: 这是一个简单的字符串处理问题。在生成签名字符串后，我们只需将多余的单引号移除即可。

---

#### 问题 3: `cs.sql` 文档显示不正常（缩进问题）

**分析**: 你的怀疑是正确的，这确实是一个**缩进问题**。

*   **技术原因**: PEP 257 (Docstring Conventions) 规定，一个函数的文档字符串 `"""..."""` 块本身，应该和函数体内的第一行代码一样，进行**缩进**。我上一版的脚本 `f"def {name}{sig_str}:\n{doc_str}\n"` 将 `doc_str`（包含 `"""`）直接拼接在了换行符后面，导致 `"""` 总是从第 0 列开始，这不符合规范，导致 IDE 解析异常。
*   **根本缺陷**: 脚本只缩进了文档字符串的*内容*，而没有缩进文档字符串的*整个块*。

**解决方案**: 在将 `doc_str` 拼接到最终函数定义之前，需要使用 `textwrap.indent()` 对其整体进行一次 4 空格的缩进。

---

