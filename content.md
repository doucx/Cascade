好的，我将生成一个 `[COMMIT]` 计划来固化对 `cs.File` 类的实现。

## [COMMIT] feat(spec): Implement declarative file wrapper `cs.File`

### 用户需求
在 `Cascade` 核心规范中引入 `File` 类，以声明式的方式管理文件路径，并提供便捷的 I/O 方法。

### 评论
`cs.File` 极大地改善了开发者体验 (DX)，它将文件 I/O 逻辑封装起来，使得任务函数可以专注于业务逻辑，同时保持了代码的清晰度和可测试性。该实现严格遵守了架构原则，作为任务参数传递时对核心 `Engine` 无侵入性。

### 目标
创建一个 Git 提交，包含 `File` 类的实现、在顶层包中的导出以及完整的测试用例。

### 基本原理
根据协议，在一个成功的功能实现和测试之后，应使用 `[COMMIT]` 计划为一个逻辑上完整的工作单元创建一个干净、原子化的提交。

### 标签
#intent/build #flow/ready #priority/high #comp/spec #comp/tests #scope/api #scope/dx #ai/instruct #task/domain/core #task/object/file-wrapper #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 提交变更

将 `File` 类的实现文件、API 导出修改和新的测试文件添加到暂存区，并执行提交。

~~~~~act
git_add
src/cascade/spec/file.py
src/cascade/__init__.py
tests/test_spec_file.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(spec): Implement declarative file wrapper `cs.File`

Introduces `cascade.File`, a class that wraps a file path and provides convenience methods for I/O operations like `read_text()` and `write_text()`.

This feature allows users to:
1. Explicitly declare file dependencies in task signatures, enhancing code readability and type safety.
2. Separate file I/O boilerplate from core business logic within tasks.
3. Automatically handle directory creation before writing files, simplifying path management.

A new test module, `tests/test_spec_file.py`, has been added to cover all I/O, path resolution, and task integration scenarios.
~~~~~

### 下一步建议
根据《Cascade 阶段三：增强表现力与动态工作流——执行计划》，下一步是实现**条件工作流 (`.run_if()`)**。这需要修改 `LazyResult`、增强 `GraphBuilder` 引入控制流边，并最重要的是，修改 `Engine` 的核心执行逻辑以实现基于运行时结果的条件剪枝。
