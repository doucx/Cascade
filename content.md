好的，我们开始执行 **阶段 3.0：[准备] 公理强制执行与代码协调 (The Great Renaming)**。

你的建议非常正确。对于这种涉及多文件、多符号的全局重构，手动执行一系列 `patch_file` 操作不仅繁琐，而且极易出错。创建一个专门的 Python 脚本来原子化地执行这些重命名，是更稳健、更可靠的工程实践。

我将生成一个计划，该计划会创建、执行并清理一个一次性的重构脚本来完成此任务。

## [WIP] refactor: 执行“The Great Renaming”以对齐哈希命名公理

### 用户需求
启动“Phase 3.0: The Great Renaming”重构任务，通过创建一个健壮的自动化脚本，系统性地修复代码库中所有违反《哈希强制长命名规范》的符号。

### 评论
这是一个至关重要的“概念性重构”步骤。通过用一个自动化的 Python 脚本代替手动 `patch`，我们确保了重构的原子性和一致性，避免了在多个文件中引入不一致状态的风险。此举将彻底消除核心数据结构中的命名歧义，为后续编译器的开发奠定一个清晰、无误的语义基础，是偿还“概念性债务”的关键一步。

### 目标
1.  创建一个名为 `great_renaming.py` 的 Python 脚本。
2.  该脚本将精确地对 `cascade-spec` 和 `cascade-graph` 包中定义及使用核心数据结构的文件执行一系列预定义的重命名操作。
3.  通过 `run_command` 执行此脚本。
4.  执行成功后，删除该脚本，保持代码库的整洁。

### 基本原理
我们将使用 `write_file` 创建一个独立的 Python 脚本。该脚本利用 `pathlib` 库来定位目标文件，并执行一系列精确的字符串替换操作。这些操作被定义在一个清晰的映射表中，确保了重构逻辑的可读性和准确性。执行和清理步骤将通过 `run_command` 和 `delete_file` 来完成，将整个重构过程封装在一个自动化的 Quipu 工作流中。

### 标签
#intent/refine #flow/ready #priority/critical #comp/spec #comp/graph #comp/compiler #concept/state #scope/dx #ai/instruct #task/domain/compiler #task/object/symbol-table #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建重命名脚本

首先，我们创建一个 `great_renaming.py` 脚本。这个脚本包含了所有必要的重命名规则和目标文件路径。

~~~~~act
write_file
great_renaming.py
~~~~~
~~~~~python
#!/usr/bin/env python3
import sys
from pathlib import Path

# 定义重命名规则，顺序很重要，从最具体的开始
RENAMES = {
    # EdgeIR
    "source_id": "source_node_instance_hash",
    "target_id": "target_node_instance_hash",
    # NodeIR
    "id: str": "current_node_instance_hash: str",
    # Node (graph.model)
    "structural_id": "current_node_instance_hash",
}

# 定义目标文件
TARGET_FILES = [
    # 定义模型的文件
    "packages/cascade-spec/src/cascade/spec/ir/models.py",
    "packages/cascade-graph/src/cascade/graph/model.py",
    # 使用这些模型的文件
    "packages/cascade-compiler/src/cascade/compiler/backend.py",
    "packages/cascade-compiler/src/cascade/compiler/frontend.py",
    "packages/cascade-graph/src/cascade/graph/build.py",
    "packages/cascade-graph/src/cascade/graph/serialize.py",
]

def main():
    print("--- Starting The Great Renaming ---")
    total_changes = 0
    project_root = Path.cwd()

    for file_path_str in TARGET_FILES:
        file_path = project_root / file_path_str
        if not file_path.exists():
            print(f"⚠️  File not found, skipping: {file_path_str}", file=sys.stderr)
            continue

        print(f"Processing: {file_path_str}")
        original_content = file_path.read_text()
        content = original_content
        
        file_changes_count = 0
        for old, new in RENAMES.items():
            before_count = content.count(old)
            if before_count > 0:
                content = content.replace(old, new)
                after_count = content.count(new)
                # This logic is simple, might not be perfectly accurate if old/new overlap
                print(f"  - Replaced '{old}' -> '{new}' ({before_count} occurrences)")
                file_changes_count += before_count

        if content != original_content:
            file_path.write_text(content)
            print(f"  ✅ Wrote {file_changes_count} changes to file.")
            total_changes += file_changes_count
        else:
            print(f"  - No changes needed.")

    print(f"\n--- Renaming Complete. Total changes: {total_changes} ---")
    return 0

if __name__ == "__main__":
    sys.exit(main())
~~~~~

#### Acts 2: 赋予脚本执行权限

为了能直接运行，我们为脚本添加可执行权限。

~~~~~act
run_command
~~~~~
~~~~~bash
chmod +x great_renaming.py
~~~~~

#### Acts 3: 执行重命名脚本

现在，我们运行脚本来执行重构。

~~~~~act
run_command
~~~~~
~~~~~bash
./great_renaming.py
~~~~~

#### Acts 4: 清理临时脚本

任务完成，删除这个一次性的脚本。

~~~~~act
delete_file
great_renaming.py
~~~~~

### 下一步建议
我们已经完成了代码的自动化重命名。根据路线图的 **3.0 阶段** 要求，下一步是**验证 (Verification)**。

我建议我们立即运行 `cascade-spec`, `cascade-graph`, 和 `cascade-compiler` 的测试套件，以确保这次纯粹的名称变更没有意外地破坏任何现有逻辑。如果一切正常，我们将正式完成 Phase 3.0。
