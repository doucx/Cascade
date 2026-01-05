好的，我将创建这个迁移脚本。这是整个重构计划的第一步，也是最关键的一步，它将处理所有代码层面的引用变更。

## [WIP] feat: 创建用于重命名 engine 包的 Stitcher 迁移脚本

### 用户需求

创建 `migrations/001_rename_engine_pkg.py` 文件，该文件包含使用 `stitcher` 将 `cascade.engine` Python 包重构为 `cascade.runtime` 的指令。

### 评论

这是一个正确的开端。我们首先在代码的命名空间层面进行重构，让 Stitcher 这样的语义工具来处理所有复杂的跨包引用更新。在这一步完成并验证后，再进行物理目录和构建配置的修改，可以最大限度地降低风险。

### 目标

1.  创建 `migrations` 目录（如果尚不存在）。
2.  在 `migrations` 目录下创建 `001_rename_engine_pkg.py` 文件，并写入指定的重构逻辑。

### 基本原理

该计划使用 `run_command` 创建目录，然后使用 `write_file` 创建迁移脚本。脚本本身利用 Stitcher 的 `MoveDir` 操作，这是处理整个 Python 包重命名的理想方式，因为它会自动推断符号 FQN（完全限定名称）的变化，并更新整个代码库中的所有引用点。

### 标签

#intent/build #flow/ready #priority/high #comp/build #concept/parser #scope/dx #ai/instruct #task/domain/refactoring #task/object/stitcher-script #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建迁移脚本

我们将首先确保 `migrations` 目录存在，然后创建 `001_rename_engine_pkg.py` 文件。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p migrations
~~~~~

~~~~~act
write_file
migrations/001_rename_engine_pkg.py
~~~~~
~~~~~
from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, MoveDir

def upgrade(spec: MigrationSpec):
    """
    将 cascade.engine 包重命名为 cascade.runtime。
    Stitcher 会自动处理所有跨包引用更新。
    """
    
    # 定义源路径和目标路径 (相对于 Monorepo 根目录)
    # 注意：我们暂时还在 packages/cascade-engine 目录下操作
    src_path = Path("packages/cascade-engine/src/cascade/engine")
    dest_path = Path("packages/cascade-engine/src/cascade/runtime")

    # 执行目录移动
    # 这将触发隐式的 Rename 操作：cascade.engine.* -> cascade.runtime.*
    spec.add(MoveDir(src_path, dest_path))
~~~~~

### 下一步建议

脚本已创建。下一步是执行它来进行重构。我强烈建议首先使用 `--dry-run` 标志来预览所有即将发生的变更，确保一切都符合预期。

你可以执行以下命令来预览：
`stitcher refactor apply migrations/001_rename_engine_pkg.py --dry-run`

如果你对预览结果满意，就可以移除 `--dry-run` 标志来正式应用变更。
