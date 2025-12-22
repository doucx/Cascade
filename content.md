你的决定非常正确。在黑暗中摸索不仅效率低下，而且容易引入新的回归问题。我们需要建立一个**反馈回路**：生成 -> 验证（测试） -> 修正。

 错误根因分析 (Post-Mortem)

根据你提供的最新输出，我们可以明确识别出导致 IDE 解析失败的**语法错误**：

1.  **非法默认值语法**:
    *   生成代码: `def Param(..., type: Any = <class 'str'>, ...)`
    *   错误: `<class 'str'>` 是 Python 对象在内存中的 `repr()` 表示，这不是合法的 Python 代码。Python 语法解析器在 `.pyi` 文件中看到 `<` 就会报错。
    *   正确做法: 应该生成 `str` 或者 `...`。

2.  **未导入的符号**:
    *   生成代码: `def recv(..., connector: Connector = Inject(...))`
    *   错误: `Inject` 在文件头部**没有被导入**。这会导致 `NameError`，使整行定义无效。
    *   正确做法: 将所有复杂的默认值替换为 `...` (Ellipsis)，因为在类型存根中，默认值的具体实现细节并不重要，重要的是“它有默认值”这个事实。

 解决方案：引入自动化测试与清洗逻辑

我们将分两步走：
1.  **创建测试工具**: 编写 `scripts/test_stubs.py`，使用 Python 内置的 `ast` 模块解析生成的 `.pyi` 文件。如果存在语法错误，它会立即报告。
2.  **修复生成脚本**: 修改 `generate_stubs.py`，增加对**函数参数默认值**的清洗逻辑。任何非基础类型（int, str, bool, None）的默认值都将被替换为 `...`。

## [WIP] test: 创建存根验证工具并修复生成逻辑

### 用户需求
1.  **停止猜测**: 提供一个脚本来验证生成的 `.pyi` 文件是否合法。
2.  **修复语法错误**: 消除 `<class 'str'>` 和未定义的 `Inject` 等错误。
3.  **验证结果**: 确保生成的存根能被 Python 解析器接受。

### 目标
1.  创建 `scripts/test_stubs.py`。
2.  升级 `scripts/generate_stubs.py` 以包含参数清洗逻辑。
3.  执行验证。

### 标签
#intent/tooling #flow/ready #priority/critical #comp/build #scope/dx #ai/delegate #task/domain/testing #task/object/stub-validator #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建存根验证脚本

这个脚本会尝试编译生成的 `.pyi` 文件。如果文件包含语法错误（如 `<class...`），编译将失败并打印行号。

~~~~~act
write_file
scripts/test_stubs.py
~~~~~
~~~~~python
#!/usr/bin/env python3
import sys
import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
STUBS_DIR = PROJECT_ROOT / "packages" / "cascade-sdk" / "src" / "cascade"

def test_stubs():
    print(f"🔍 Verifying stubs in {STUBS_DIR}...")
    
    if not STUBS_DIR.exists():
        print(f"❌ Stubs directory not found: {STUBS_DIR}")
        sys.exit(1)

    has_errors = False
    
    # Recursively find all .pyi files
    for pyi_file in STUBS_DIR.glob("**/*.pyi"):
        try:
            with open(pyi_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Attempt to parse the file into an Abstract Syntax Tree
            # This catches SyntaxErrors like "<class 'str'>" or invalid indents
            ast.parse(content, filename=str(pyi_file))
            print(f"✅ [PASS] {pyi_file.relative_to(PROJECT_ROOT)}")
            
        except SyntaxError as e:
            has_errors = True
            print(f"❌ [FAIL] {pyi_file.relative_to(PROJECT_ROOT)}")
            print(f"   Line {e.lineno}: {e.text.strip() if e.text else ''}")
            print(f"   Error: {e.msg}")
        except Exception as e:
            has_errors = True
            print(f"❌ [FAIL] {pyi_file.relative_to(PROJECT_ROOT)}: {e}")

    if has_errors:
        print("\n🚫 Verification failed. Please fix the stub generator.")
        sys.exit(1)
    else:
        print("\n🎉 All stubs are valid Python syntax!")

if __name__ == "__main__":
    test_stubs()
~~~~~

#### Acts 2: 修复生成脚本 (引入参数清洗)

我将更新 `get_function_signature` 函数，使其遍历参数签名，并将所有复杂的默认值替换为 `...`。

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
    """Adds all package src directories to sys.path, prioritizing cascade-sdk."""
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


def clean_type_str(type_str: str) -> str:
    """Cleans up raw type strings."""
    # Handle NoneType
    type_str = type_str.replace("NoneType", "None")
    
    # Simplify full paths to short names
    replacements = [
        (r"cascade\.spec\.lazy_types\.LazyResult", "LazyResult"),
        (r"cascade\.spec\.protocols\.Connector", "Connector"),
        (r"cascade\.spec\.protocols\.StateBackend", "StateBackend"),
        (r"cascade\.spec\.protocols\.CachePolicy", "CachePolicy"),
        # Handle quotes
        (r"'LazyResult\[Any\]'", "LazyResult"), 
        (r"'LazyResult'", "LazyResult"),
    ]
    
    for pattern, repl in replacements:
        type_str = re.sub(pattern, repl, type_str)
        
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

        # --- PARAMETER SANITIZATION ---
        new_params = []
        for param in sig.parameters.values():
            # 1. Clean Type Annotation
            new_annotation = inspect.Parameter.empty
            if param.annotation != inspect.Parameter.empty:
                # Convert to string and clean
                # Note: This is a simplification; complex nested types might need AST parsing,
                # but string cleaning covers 90% of our cases.
                type_name = str(param.annotation)
                # If it's a class object (like <class 'str'>), get its name
                if isinstance(param.annotation, type):
                    type_name = param.annotation.__name__
                
                clean_name = clean_type_str(str(type_name))
                # For safety, if cleaning didn't resolve <class '...'>, fallback to Any
                if "<class" in clean_name:
                    clean_name = "Any"
                new_annotation = clean_name

            # 2. Clean Default Value
            new_default = inspect.Parameter.empty
            if param.default != inspect.Parameter.empty:
                # Keep simple literals, replace everything else with Ellipsis (...)
                if param.default is None:
                    new_default = None
                elif isinstance(param.default, (int, float, bool, str)):
                    new_default = param.default
                else:
                    # e.g. Inject(...), or custom classes.
                    # We use Ellipsis to signify "some default value" in stub files
                    new_default = ... 

            # Reconstruct parameter
            # We can't pass string as annotation to Parameter constructor directly if using `inspect.Signature`
            # to render. So we construct the string manually to avoid inspect's validation logic
            # confusing our clean strings.
            
            param_str = param.name
            if new_annotation != inspect.Parameter.empty:
                param_str += f": {new_annotation}"
            
            if new_default != inspect.Parameter.empty:
                if new_default is ...:
                    param_str += " = ..."
                elif new_default is None:
                    param_str += " = None"
                else:
                    param_str += f" = {repr(new_default)}"
            
            new_params.append(param_str)

        # Reconstruct signature string manually
        signature_str = f"({', '.join(new_params)})"

        # Handle Return Type
        if sig.return_annotation != inspect.Signature.empty:
             signature_str += " -> LazyResult"
        else:
             signature_str += " -> LazyResult" # Default for providers

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

### 下一步建议

1.  运行 `python scripts/generate_stubs.py` 生成新存根。
2.  **立即运行验证**: `python scripts/test_stubs.py`。
    *   你应该会看到 `🎉 All stubs are valid Python syntax!`。
3.  重启 IDE 窗口。

这次，所有的默认值（如 `Inject(...)`）都会被转化为 `...`，所有非法的类表示（如 `<class 'str'>`）都会被修复。这是保证存根合法性的关键。
