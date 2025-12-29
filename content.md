## [WIP] fix: 改进重复模块检查脚本以支持命名空间包

### 用户需求
当前的 `check_duplicate_modules.py` 脚本过于严格，将合法的 Python 命名空间包（Namespace Packages，例如多个包共享 `cascade` 顶级目录）误报为冲突。用户需要一个更智能的脚本，能够区分“合法的命名空间合并”和“非法的模块覆盖”。

### 评论
在现代 Python 开发中，尤其是 monorepo 环境下，命名空间包是常态。如果不改进此逻辑，该工具将无法在实际项目中使用。我们需要引入对 `__init__.py` 内容的简单静态分析，以忽略那些仅包含命名空间声明样板代码的文件。

### 目标
1.  修改 `scripts/check_duplicate_modules.py`。
2.  **策略调整**：
    *   对于非 `__init__.py` 的 `.py` 文件：保持严格的唯一性检查。任何重复都是错误。
    *   对于 `__init__.py` 文件：检查其内容。如果文件为空，或仅包含标准的 `pkgutil` 命名空间声明代码（忽略注释和空行），则将其视为“非实质性定义”。
3.  **冲突判定**：只有当同一个模块存在多个“实质性定义”时，才报告为冲突。如果多个包都定义了同一个命名空间（例如 `cascade`），但它们都只是声明了命名空间而没有业务逻辑，则不视为冲突。

### 基本原理
Python 的 `pkgutil` 风格命名空间包允许不同目录下的 `__init__.py` 文件共存，只要它们都包含扩展 `__path__` 的样板代码。真正的冲突发生在该文件包含特定的初始化逻辑（如变量定义、特定导入）时，因为 Python 解释器只会加载其中一个（取决于 `sys.path`顺序），从而导致不可预测的行为。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/tooling #task/object/validation-script #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 更新检查脚本

我们将重写 `find_duplicate_modules` 函数的核心逻辑，加入对 `__init__.py` 内容的分析。

~~~~~act
write_file
scripts/check_duplicate_modules.py
~~~~~
~~~~~python
#!/usr/bin/env python3
import sys
import re
from collections import defaultdict
from pathlib import Path

# Standard namespace package declaration patterns
NAMESPACE_PATTERNS = [
    re.compile(r"^__path__\s*=\s*__import__\(['\"]pkgutil['\"]\)\.extend_path\(__path__,\s*__name__\)\s*$"),
    re.compile(r"^__import__\(['\"]pkg_resources['\"]\)\.declare_namespace\(__name__\)\s*$"),
]

def is_namespace_package_boilerplate(file_path):
    """
    Checks if an __init__.py file contains only namespace declaration boilerplate,
    comments, or whitespace.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        # If we can't read it, assume it's substantive (better safe than sorry)
        return False

    has_code = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        
        # If we find a line of code, check if it matches known boilerplate
        matched = False
        for pattern in NAMESPACE_PATTERNS:
            if pattern.match(stripped):
                matched = True
                break
        
        if not matched:
            # Found a line of code that isn't boilerplate
            return False
            
    # If we get here, all code lines were boilerplate (or there were no code lines)
    return True

def find_duplicate_modules(root_dir="."):
    """
    Scans the 'packages' directory to find modules defined in multiple packages.
    Distinguishes between strict file conflicts and namespace package merges.
    """
    packages_dir = Path(root_dir) / "packages"
    if not packages_dir.is_dir():
        print(f"Error: Directory not found: {packages_dir}", file=sys.stderr)
        return 1

    # Map of module_name -> list of (package_name, is_substantive)
    definitions = defaultdict(list)
    package_dirs = [d for d in packages_dir.iterdir() if d.is_dir()]

    for package_path in package_dirs:
        package_name = package_path.name
        src_path = package_path / "src"

        if not src_path.is_dir():
            continue

        for path in src_path.rglob("*"):
            module_name = None
            is_substantive = True

            # Case 1: It's a package directory (contains __init__.py)
            if path.is_file() and path.name == "__init__.py":
                module_parts = path.parent.relative_to(src_path).parts
                module_name = ".".join(module_parts)
                # Check if it's just a namespace placeholder
                if is_namespace_package_boilerplate(path):
                    is_substantive = False
            
            # Case 2: It's a module file (.py)
            elif path.is_file() and path.suffix == ".py":
                # Exclude __init__.py files as they are handled above
                if path.stem == "__init__":
                    continue
                
                module_parts = list(path.relative_to(src_path).parts)
                module_parts[-1] = path.stem # remove .py extension
                module_name = ".".join(module_parts)
                # Regular .py files are always substantive definitions
                is_substantive = True
            
            if module_name:
                definitions[module_name].append({
                    "package": package_name,
                    "is_substantive": is_substantive,
                    "path": str(path)
                })

    conflicts = {}

    for module, defs in definitions.items():
        # Filter for substantive definitions (those containing actual code)
        substantive_defs = [d for d in defs if d["is_substantive"]]
        
        # Conflict Condition 1: Multiple packages define substantive logic for the same module/package
        if len(substantive_defs) > 1:
            conflicts[module] = {
                "reason": "Multiple substantive definitions (logic collision)",
                "sources": [f"{d['package']} ({'substantive' if d['is_substantive'] else 'namespace'})" for d in defs]
            }
        # Conflict Condition 2: Regular module file (.py) vs Package dir (__init__.py)
        # This is implicitly handled because one would be 'foo' and the other 'foo'
        # But we need to make sure we don't have a file 'foo.py' and a dir 'foo/' both substantive.
        # (The script logic above maps them to the same dotted name, so len > 1 catches this too)

    if conflicts:
        print("❌ Found duplicate module definitions:", file=sys.stderr)
        print("-------------------------------------", file=sys.stderr)
        sorted_conflicts = sorted(conflicts.items())
        for module, info in sorted_conflicts:
            print(f"- Module: {module}", file=sys.stderr)
            print(f"  Reason: {info['reason']}", file=sys.stderr)
            print(f"  Defined in:", file=sys.stderr)
            for src in info['sources']:
                print(f"    * {src}", file=sys.stderr)
            print("", file=sys.stderr)
        return 1
    else:
        print("✅ No duplicate module definitions found.")
        return 0

if __name__ == "__main__":
    # Assuming the script is run from the repository root
    repo_root = Path(__file__).parent.parent.resolve()
    sys.exit(find_duplicate_modules(repo_root))
~~~~~

### 下一步建议
再次运行脚本进行验证：
```bash
./scripts/check_duplicate_modules.py
```
这次应该会忽略所有的命名空间包声明，只报告真正的代码冲突（如果有的话）。
