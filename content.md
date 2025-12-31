好的，接下来处理 `cascade-compiler` 包的测试。

这个包的所有测试 (`test_backend.py`, `test_frontend.py`, `test_optimizer.py`) 都属于**单元测试**范畴：
1.  **`test_frontend.py`**: 验证 `Frontend` 将 `LazyResult` 结构转换为 `GraphIR` 的静态逻辑。它不运行任何任务。
2.  **`test_optimizer.py`**: 验证 `Optimizer` 在给定 `GraphIR` 结构下执行拓扑排序和周期检测的纯算法逻辑。它不涉及运行时。
3.  **`test_backend.py`**: 验证 `Backend` 将 `GraphIR` 结构转换为 `Blueprint` (VM 指令集) 的逻辑。它只涉及数据结构转换。

因此，所有文件都将被移动到 `unit/` 目录中。

## [WIP] refactor(tests): 为 cascade-compiler 分离单元测试

### 用户需求

将 `cascade-compiler` 包下的所有测试文件迁移到新创建的 `unit/` 目录中，因为这些测试都是针对编译器组件的静态逻辑验证，不依赖于完整的 Cascade 运行时。

### 评论

`cascade-compiler` 的核心职责是处理静态数据结构 (`LazyResult` -> `GraphIR` -> `ExecutionPlan` -> `Blueprint`)。其测试应严格隔离在单元测试层。由于目前没有集成测试，我们将仅创建 `unit` 目录。

### 目标

1.  在 `packages/cascade-compiler/tests/` 目录下创建 `unit/` 目录。
2.  将所有现有的测试文件 (`test_backend.py`, `test_frontend.py`, `test_optimizer.py`) 移动到 `unit/` 目录中。
3.  删除空的 `packages/cascade-compiler/tests/` 目录下的旧文件。

### 基本原理

如前所述，所有测试都属于对编译器前端、优化器和后端逻辑的隔离验证，符合单元测试的定义。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-structure #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建 Unit 目录

为 `cascade-compiler` 包创建 `unit` 测试目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-compiler/tests/unit
~~~~~

#### Acts 2: 迁移所有测试文件到 Unit 目录

~~~~~act
move_file
packages/cascade-compiler/tests/test_backend.py
packages/cascade-compiler/tests/unit/test_backend.py
~~~~~
~~~~~act
move_file
packages/cascade-compiler/tests/test_frontend.py
packages/cascade-compiler/tests/unit/test_frontend.py
~~~~~
~~~~~act
move_file
packages/cascade-compiler/tests/test_optimizer.py
packages/cascade-compiler/tests/unit/test_optimizer.py
~~~~~

### 下一步建议

我们已经完成了 `cascade-compiler` 的测试结构重构。

接下来我将继续检查其他包的测试结构，下一个目标是 `cascade-graph`。
