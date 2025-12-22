## [WIP] fix(build): 修复文件结构嵌套并完成 spec 迁移

### 用户需求
修复 `cascade-spec` 包中错误的文件嵌套结构。目前代码被错误地放置在 `packages/cascade-spec/cascade-interfaces/src` 下，导致 Python 无法找到 `cascade.spec.task` 等模块。需要将这些文件正确合并到 `packages/cascade-spec/src` 中。

### 评论
这个错误可能是由于之前的复制操作不当（例如在目标目录已存在时使用了 `cp -r`）导致的。使用 Python 脚本进行递归合并是解决“目录非空”错误的最佳方案，同时可以优雅地处理 `__pycache__` 等干扰项。

### 目标
1.  编写并执行 `scripts/fix_spec_structure.py`。
2.  该脚本将递归合并 `packages/cascade-spec/cascade-interfaces/src/cascade` 到 `packages/cascade-spec/src/cascade`。
3.  脚本将清理残留的 `cascade-interfaces` 目录。
4.  脚本将自动删除 `__pycache__` 目录以避免冲突。

### 基本原理
利用 Python 的 `os` 和 `shutil` 模块，我们可以编写一个具有原子性（针对单个文件）的合并逻辑，它能遍历源目录树，将文件移动到目标位置（如有冲突则覆盖），从而修复分裂的目录结构。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #scope/core #ai/instruct #task/domain/architecture #task/object/package-structure #task/action/cleanup #task/state/continue #task/status/active

---

### Script

#### Acts 1: 创建并执行结构修复脚本
我们将编写一个专门的 Python 脚本来处理这个棘手的目录合并问题，特别是要处理目录非空和缓存文件的情况。

~~~~~act
write_file
scripts/fix_spec_structure.py
~~~~~
~~~~~python
import os
import shutil

def merge_directories(src_dir, dst_dir):
    """
    Recursively moves contents from src_dir to dst_dir.
    Overwrites files if they exist in dst_dir.
    Merges directories.
    """
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
        print(f"Created directory: {dst_dir}")
    
    for item in os.listdir(src_dir):
        if item == "__pycache__":
            continue
            
        s = os.path.join(src_dir, item)
        d = os.path.join(dst_dir, item)
        
        if os.path.isdir(s):
            merge_directories(s, d)
        else:
            if os.path.exists(d):
                os.remove(d)
                print(f"Overwriting {d}")
            shutil.move(s, d)
            print(f"Moved {item} -> {dst_dir}")

def main():
    root_dir = os.getcwd()
    # The accidentally nested directory
    nested_root = os.path.join(root_dir, "packages/cascade-spec/cascade-interfaces")
    nested_src = os.path.join(nested_root, "src/cascade")
    
    # The correct destination
    target_dst = os.path.join(root_dir, "packages/cascade-spec/src/cascade")
    
    print(f"Checking for nested structure at: {nested_src}")
    
    if os.path.exists(nested_src):
        print(f"Found nested content. Merging into {target_dst}...")
        try:
            merge_directories(nested_src, target_dst)
            print("Merge successful.")
            
            print(f"Removing source: {nested_root}")
            shutil.rmtree(nested_root)
        except Exception as e:
            print(f"Error during merge: {e}")
            exit(1)
    else:
        print("No nested content found. Directory structure might already be correct.")

if __name__ == "__main__":
    main()
~~~~~

~~~~~act
run_command
~~~~~
~~~~~
python3 scripts/fix_spec_structure.py
~~~~~

### 下一步建议
脚本执行成功后，文件结构应当已修复。请再次运行测试以验证模块是否可以被正确加载：
```bash
pytest
```
如果测试通过（或者至少不再报 ModuleNotFoundError），我们将可以继续后续的重构工作（如清理旧的接口引用）。
