## [WIP] refactor: 修复包结构重构后的引用路径

### 用户需求
完成多包重构的后续清理工作：
1.  移动遗留的 `examples` 目录。
2.  修复因文件移动导致的 `import` 路径断裂（主要是 `runtime` -> `interfaces` 的接口迁移）。
3.  确保 `cascade-cli` 正确暴露入口。

### 评论
代码物理位置的移动只是重构的第一步，逻辑引用的修正才是让系统重新跑起来的关键。特别是 `protocols`、`events` 和 `exceptions` 从 `runtime` 剥离到 `interfaces`，涉及了大量的引用变更。我们需要通过批量替换来高效且准确地完成这一任务。

### 目标
1.  将 `src/cascade/examples` 移动到 `packages/cascade-py/src/cascade/examples`。
2.  在 `packages/cascade-cli/src/cascade/cli/__init__.py` 中导出 `cli` 函数，使其对外可见。
3.  全局批量替换旧的导入路径：
    *   `cascade.runtime.protocols` -> `cascade.interfaces.protocols`
    *   `cascade.runtime.events` -> `cascade.interfaces.events`
    *   `cascade.runtime.exceptions` -> `cascade.interfaces.exceptions`
4.  清理空的 `src` 目录。

### 基本原理
我们利用 `grep` 配合 `sed` 进行精确的字符串替换，确保所有引用了旧路径的文件都被更新为指向新的 `cascade-interfaces` 包。这保证了重构后的代码能够正确解析依赖。

### 标签
#intent/refine #flow/ready #priority/high
#comp/build #concept/refactoring #scope/core
#ai/instruct
#task/domain/runtime #task/object/monorepo #task/action/fix_imports #task/state/continue

---

### Script

#### Acts 1: 移动遗留的 `examples` 目录

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-py/src/cascade/examples
mv src/cascade/examples/* packages/cascade-py/src/cascade/examples/
rm -rf src/cascade/examples
~~~~~

#### Acts 2: 修复 `cascade-cli` 的导出

确保 `from cascade.cli import cli` 可以工作。

~~~~~act
write_file
packages/cascade-cli/src/cascade/cli/__init__.py
~~~~~
~~~~~python
from .main import cli

__all__ = ["cli"]
~~~~~

#### Acts 3: 批量修复导入路径 (Protocols)

将所有对 `cascade.runtime.protocols` 的引用修改为 `cascade.interfaces.protocols`。

~~~~~act
run_command
~~~~~
~~~~~bash
grep -rl "cascade.runtime.protocols" packages tests | xargs sed -i 's/cascade.runtime.protocols/cascade.interfaces.protocols/g'
~~~~~

#### Acts 4: 批量修复导入路径 (Events)

将所有对 `cascade.runtime.events` 的引用修改为 `cascade.interfaces.events`。

~~~~~act
run_command
~~~~~
~~~~~bash
grep -rl "cascade.runtime.events" packages tests | xargs sed -i 's/cascade.runtime.events/cascade.interfaces.events/g'
~~~~~

#### Acts 5: 批量修复导入路径 (Exceptions)

将所有对 `cascade.runtime.exceptions` 的引用修改为 `cascade.interfaces.exceptions`。

~~~~~act
run_command
~~~~~
~~~~~bash
grep -rl "cascade.runtime.exceptions" packages tests | xargs sed -i 's/cascade.runtime.exceptions/cascade.interfaces.exceptions/g'
~~~~~

#### Acts 6: 清理并检查

清理可能残留的空目录。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf src
~~~~~

### 下一步建议
重构工作已基本完成。现在的代码库应该是一个结构清晰的多包 Monorepo。

为了验证重构的正确性，建议运行测试。由于测试文件也被大量修改了引用，运行测试是验证这一系列变更最直接的方法。
运行测试前，可能需要以 editable 模式安装这些新包：
`pip install -e packages/cascade-interfaces -e packages/cascade-runtime -e packages/cascade-py -e packages/cascade-cli`
