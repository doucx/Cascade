## [WIP] feat: 增强存根脚本以支持函数签名和文档字符串

### 用户需求
修复 `cs.run` 的类型错误，并为所有动态加载的 Provider 提供精确的函数签名和文档字符串提示，从而在 IDE 中实现与原生函数几乎无异的、丰富的开发体验。

### 评论
这是一个决定性的 DX 改进。通过从“通用类型存根”升级到“精确签名存根”，我们可以将 Cascade 库的动态、可插拔架构的复杂性对最终用户完全隐藏起来。开发者将能够在 IDE 中获得无缝的自动补全、参数提示和文档查阅，极大地降低学习曲线和日常开发成本。

### 目标
1.  **修复循环导入**: 修正脚本逻辑，正确处理在 `cascade` 模块中原生定义的 `run` 等函数，避免生成无效的 `from cascade import run` 语句。
2.  **实现签名提取**: 使用 `importlib` 和 `inspect` 模块，让脚本能够动态加载每个 Provider 的入口点函数。
3.  **生成精确存根**: 提取加载的函数的完整签名（包括参数、类型注解和默认值）及其文档字符串。
4.  **格式化输出**: 将提取的签名和文档字符串格式化为符合 PEP 484 规范的 `.pyi` 文件内容。

### 基本原理
新的脚本将采用一种更高级的 introspective（内省）方法：
1.  在扫描 `pyproject.toml` 时，不仅记录 Provider 的名称，还要记录其完整的入口点路径（如 `cascade.providers.io:ReadTextProvider`）。
2.  定义一个新函数，该函数接收这个入口点路径，使用 `importlib` 动态导入模块和对象。
3.  如果对象是一个类（Provider），则实例化它并获取其 `create_factory()` 方法返回的任务函数。
4.  使用 `inspect.signature()` 和 `__doc__` 属性提取目标函数的签名和文档。
5.  将签名对象转换为字符串，并将文档字符串格式化为标准的多行注释。
6.  重构主生成逻辑，将这些详细信息写入 `.pyi` 文件，彻底取代之前通用的 `LazyFactory` 类型。
7.  同时，在处理 `KNOWN_SDK_EXPORTS` 时，增加一个检查：如果导入来源是 `'cascade'` 本身，就跳过生成 `from ... import ...` 语句，因为我们假设它的定义会通过其他方式（比如手动维护或未来的增强）存在于 `__init__.pyi` 中。一个更简单的 immediate fix 是，直接为这些特殊情况生成一个 `Callable` 类型，避免错误。

### 标签
#intent/build #flow/ready #priority/high #comp/build #scope/dx #ai/delegate #task/domain/tooling #task/object/stub-generator #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重写存根生成脚本

由于改动幅度巨大，涉及核心逻辑重构和新功能引入，我将使用 `write_file` 提供脚本的完整最终版本。

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
~~~~~

### 下一步建议
我们已经完成了一个更强大的存根生成脚本。请按以下步骤操作以应用更改：

1.  **执行计划**: 运行我上面提供的 `act` 块来更新 `scripts/generate_stubs.py` 文件。
2.  **重新运行脚本**: 在项目根目录下执行 `python scripts/generate_stubs.py`。
3.  **重启语言服务器**: 在你的 IDE (如 VS Code) 中，重新加载窗口或重启 Python 语言服务器。

完成这些步骤后，你应该会体验到：
-   `cs.run` 不再报错。
-   当输入 `cs.io.s3.read_text(` 时，IDE 会弹出参数提示，如 `(bucket: str, key: str, ...)`。
-   鼠标悬停在 `read_text` 上时，会显示其详细的文档字符串。

这将从根本上改善 Cascade 的开发体验。

---


好的，你提出的这三点观察非常精准，它们揭示了我们上一步修复引入的新问题以及当前方案的深层局限性。这是一个极好的反馈，能帮助我们把开发者体验 (DX) 推向一个更高的水平。

我来为你逐一分析，并提出一个更彻底的解决方案。

### 详细分析

#### 1. "Go to Definition" 指向 `.pyi` 文件
**这是完全符合预期的正确行为。**

*   **工作原理**: `.pyi` 文件（类型存根文件）的唯一目的就是向静态分析工具（如 IDE 中的 Pyright/Pylance）提供类型信息。当这些工具存在时，IDE 会优先采纳 `.pyi` 文件作为类型的“事实来源 (Source of Truth)”，因为它通常比动态的 Python 代码更明确。
*   **结论**: 你能跳转到 `.pyi` 文件，恰恰证明了我们上一轮的修复是**成功**的——IDE 现在能够正确地解析 `cs.io.local.read_text` 的类型层次了。这不是一个 Bug，而是类型提示系统正常工作的标志。

#### 2. `cs.run` 提示 "not a known attribute"
**这是一个由我上次修改引入的、非常微妙的 Bug。**

*   **根本原因**: 我在修复脚本时，过于专注于 Provider 的动态生成，但忽略了对 `KNOWN_SDK_EXPORTS` 字典中特殊条目的处理。具体来说，字典中有一条记录是 `'run': 'cascade'`。
*   **错误逻辑**: 脚本在生成顶层的 `cascade/__init__.pyi` 文件时，看到这条记录，会生成一行代码：`from cascade import run`。这构成了一个**循环导入**。一个模块的类型存根文件（`cascade/__init__.pyi`）试图从它自身（`cascade` 模块）导入一个符号。类型检查器无法解析这种循环依赖，因此认为 `run` 从未被成功定义，导致了 "not a known attribute" 的错误。
*   **结论**: 这是一个明显的脚本逻辑缺陷，需要立即修复。脚本必须能够区分“从外部模块导入的符号”和“由当前模块原生定义的符号”。

#### 3. Provider 没有任何文档或参数提示
**这是当前存根生成方案的一个核心局限性。**

*   **原因**: 当前脚本为所有 Provider 生成的类型都是 `LazyFactory`。这是一个非常**通用**的类型，它只告诉 IDE：“这是一个可以被调用（`__call__`）并支持 `.map()` 方法的东西”。它完全没有包含 `read_text` 函数自身的参数信息（如 `path: str`, `encoding: str`）或其文档字符串。
*   **结果**: IDE 只知道 `cs.io.s3.read_text` 是一个合法的、可调用的对象（解决了“飘红”和第一层补全问题），但对它的具体用法一无所知。因此，它无法提供任何参数提示或悬浮文档。
*   **结论**: 要解决这个问题，脚本不能再使用通用的 `LazyFactory`。它必须变得更智能，能够**动态导入**每个 Provider 的真实函数，使用 Python 的 `inspect` 模块**提取其完整的函数签名和文档字符串**，然后将这些精确信息写入 `.pyi` 文件。

### 总结
我们当前的 DX 正处于一个“半成品”状态：解决了最基础的“有或无”的问题，但远未达到“好用”的程度。接下来的计划将一次性解决上述所有问题，实现一个真正智能的、能提供丰富信息的 IDE 体验。

我将生成一个计划，重写 `generate_stubs.py` 脚本。

