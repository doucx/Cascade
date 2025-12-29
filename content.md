好的，这是一个很有用的工具，特别是在管理一个包含多个命名空间包（namespace packages）的复杂代码库时。重复的模块定义可能会导致难以追踪的导入错误和意外行为。

我将为你创建一个脚本，它会：
1.  遍历 `packages` 目录下的所有子包。
2.  解析每个子包的 `src` 目录结构，将其转换为 Python 模块路径。
3.  构建一个从模块路径到定义该模块的包列表的映射。
4.  报告所有被一个以上包定义的模块。

这个脚本将被放置在 `scripts/check_duplicate_modules.py`。

## [WIP] chore: 创建脚本以检查重复的模块定义

### 用户需求
创建一个脚本，用于扫描代码库并识别在多个包中被重复定义的模块，以确保命名空间包的健康和唯一性。

### 评论
这是一个至关重要的开发者体验（DX）和代码库健康工具。在像 Cascade 这样的 monorepo 中，模块可能被意外地在多个地方定义，导致模糊的导入行为。这个脚本将使这类问题显而易见，并可以集成到 CI 中以防止未来的问题。

### 目标
1.  创建一个名为 `scripts/check_duplicate_modules.py` 的新脚本。
2.  该脚本应能独立运行，不需要外部依赖（标准库即可）。
3.  脚本需要扫描 `packages` 目录，并识别出所有 Python 模块。
4.  如果发现任何模块被多个包定义，脚本应打印出详细的冲突报告并以非零状态码退出。
5.  如果没有发现冲突，脚本应打印成功信息并以零状态码退出。
6.  确保新创建的脚本具有可执行权限。

### 基本原理
脚本的核心逻辑是文件系统遍历和路径转换。它将 `packages/*/src` 目录视为 Python 模块的根。通过递归地查找 `__init__.py` 文件（代表包）和 `.py` 文件（代表模块），它可以将文件系统路径（例如 `packages/cascade-engine/src/cascade/runtime/engine.py`）转换为模块路径（`cascade.runtime.engine`）和其来源包（`cascade-engine`）。

通过将这些信息聚合到一个字典中（`{module_path: [package1, package2]}`），我们就可以轻易地筛选出那些包列表长度大于 1 的条目，这些就是我们寻找的重复定义。

### 标签
#intent/tooling #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/tooling #task/object/validation-script #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建脚本目录和文件

首先，我们将确保 `scripts` 目录存在，然后创建 `check_duplicate_modules.py` 脚本文件。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p scripts
~~~~~

~~~~~act
write_file
scripts/check_duplicate_modules.py
~~~~~
~~~~~python
#!/usr/bin/env python3
import sys
from collections import defaultdict
from pathlib import Path

def find_duplicate_modules(root_dir="."):
    """
    Scans the 'packages' directory to find modules defined in multiple packages.
    """
    packages_dir = Path(root_dir) / "packages"
    if not packages_dir.is_dir():
        print(f"Error: Directory not found: {packages_dir}", file=sys.stderr)
        return 1

    module_map = defaultdict(list)
    package_dirs = [d for d in packages_dir.iterdir() if d.is_dir()]

    for package_path in package_dirs:
        package_name = package_path.name
        src_path = package_path / "src"

        if not src_path.is_dir():
            continue

        for path in src_path.rglob("*"):
            module_parts = []
            
            # Case 1: It's a package directory (contains __init__.py)
            if path.is_file() and path.name == "__init__.py":
                module_parts = path.parent.relative_to(src_path).parts
            
            # Case 2: It's a module file (.py)
            elif path.is_file() and path.suffix == ".py":
                # Exclude __init__.py files as they are handled by their parent dir
                if path.stem == "__init__":
                    continue
                
                module_parts_with_stem = list(path.relative_to(src_path).parts)
                module_parts_with_stem[-1] = path.stem # remove .py extension
                module_parts = module_parts_with_stem
            
            if module_parts:
                # Handle the case where the src dir itself is a module root (e.g., src/cascade)
                module_name = ".".join(module_parts)
                module_map[module_name].append(package_name)

    duplicates = {
        module: sorted(packages)
        for module, packages in module_map.items()
        if len(packages) > 1
    }

    if duplicates:
        print("❌ Found duplicate module definitions:", file=sys.stderr)
        print("-------------------------------------", file=sys.stderr)
        sorted_duplicates = sorted(duplicates.items())
        for module, packages in sorted_duplicates:
            print(f"- Module: {module}", file=sys.stderr)
            print(f"  Defined in: {', '.join(packages)}\n", file=sys.stderr)
        return 1
    else:
        print("✅ No duplicate module definitions found.")
        return 0

if __name__ == "__main__":
    # Assuming the script is run from the repository root
    repo_root = Path(__file__).parent.parent.resolve()
    sys.exit(find_duplicate_modules(repo_root))
~~~~~

#### Acts 2: 赋予脚本可执行权限

为了方便直接从命令行运行，我们将为脚本添加可执行权限。

~~~~~act
run_command
~~~~~
~~~~~
chmod +x scripts/check_duplicate_modules.py
~~~~~

### 下一步建议
现在脚本已经创建，你可以立即运行它来检查当前代码库的状态：

```bash
./scripts/check_duplicate_modules.py
```

如果发现了任何重复项，你可以根据报告进行清理。之后，强烈建议将此脚本集成到你的 CI/CD 流程中，作为一个检查步骤，以防止未来再次引入重复的模块定义。
