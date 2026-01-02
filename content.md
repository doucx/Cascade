好的，已进入 Quipu 模式。

这是根据你批准的 Phase 5 迁移路线图，为执行 **任务 5.0.1** 生成的计划。

## [WIP] chore(compiler): 创建 v3.0 编译器目录结构

### 用户需求

根据《Cascade 3.0: Phase 5 迁移总纲与执行路线图》的规定，执行第一项任务 (5.0.1)，为 v3.0 编译器创建清晰的、职责分离的目录结构。这包括在 `packages/cascade-compiler/src/cascade/compiler/` 目录下创建新的 `frontend/` 子目录，并确保其与现有的 `backend/` 目录并存。

### 评论

这是 Phase 5 迁移中一个虽小但至关重要的第一步。通过在文件系统层面物理地分离 `frontend` (用户 API -> IR) 和 `backend` (IR -> 物理图) 的职责，我们为后续的开发工作建立了清晰的边界和上下文，从根本上解决了 v2.0 `cascade-graph` 包职责混乱的问题。

### 目标

1.  在 `packages/cascade-compiler/src/cascade/compiler/` 路径下创建一个名为 `frontend` 的新目录。
2.  在该新目录中创建一个 `__init__.py` 文件，使其成为一个合法的 Python 包。

### 基本原理

我们严格遵循“原子化、非破坏性演进”原则。本次操作仅创建新结构，不修改或删除任何现有文件。现有的 `backend` 目录已经位于正确的位置，因此我们只需创建 `frontend` 目录即可完成此任务。这为下一步（任务 5.0.2: 定义 IR）提供了一个干净、隔离的开发环境。

### 标签

#intent/tooling #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/compiler #task/object/directory-structure #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建 Frontend 目录结构

我们将使用一条命令创建 `frontend` 目录及其 `__init__.py` 文件。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-compiler/src/cascade/compiler/frontend
touch packages/cascade-compiler/src/cascade/compiler/frontend/__init__.py
~~~~~

### 下一步建议

我们已经成功建立了 v3.0 编译器的目录骨架。根据路线图，下一步是 **任务 5.0.2: 定义编译器中间表示 (IR)**。这将在 `cascade-spec` 包中定义连接 Frontend 和 Backend 的核心数据契约，是整个编译流程的通用语言。如果你同意，我将开始准备执行该任务的计划。
