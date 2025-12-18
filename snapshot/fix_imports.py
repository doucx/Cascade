import os
import sys
from pathlib import Path

# 定义从旧的、错误的导入路径到新的、正确的导入路径的映射
# 这是本次重构的核心规则集。
REPLACEMENTS = {
    # 规则 1: 'spec' 模块现在直接在 'cascade' 命名空间下
    "from cascade.interfaces.spec": "from cascade.spec",
    "import cascade.interfaces.spec": "import cascade.spec",
    
    # 规则 2: 'graph' 模块现在直接在 'cascade' 命名空间下
    "from cascade.runtime.graph": "from cascade.graph",
    "import cascade.runtime.graph": "import cascade.graph",

    # 规则 3: 'adapters' 模块现在直接在 'cascade' 命名空间下
    "from cascade.runtime.adapters": "from cascade.adapters",
    "import cascade.runtime.adapters": "import cascade.adapters",
}

def fix_imports_in_file(file_path: Path):
    """读取文件，应用所有替换规则，如果文件有变动则写回。"""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content

        for old, new in REPLACEMENTS.items():
            content = content.replace(old, new)

        if content != original_content:
            file_path.write_text(content, encoding="utf-8")
            print(f"✅ Fixed imports in: {file_path}")
            return True
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}", file=sys.stderr)
    return False

def main():
    """主函数，遍历项目目录并修复文件。"""
    project_root = Path(".")
    search_dirs = ["packages", "tests"]
    file_count = 0
    fixed_count = 0

    print("--- Starting import path fixing script ---")

    for search_dir in search_dirs:
        for root, _, files in os.walk(project_root / search_dir):
            for filename in files:
                if filename.endswith(".py"):
                    file_path = Path(root) / filename
                    file_count += 1
                    if fix_imports_in_file(file_path):
                        fixed_count += 1
    
    print("\n--- Script finished ---")
    print(f" scanned {file_count} Python files.")
    print(f" fixed {fixed_count} files.")

if __name__ == "__main__":
    main()