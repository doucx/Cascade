太好了！第二阶段的架构重构也顺利完成。现在我们将这个清晰的职责分离作为一个原子提交来保存。

## [COMMIT] refactor(arch): Isolate graph logic into dedicated cascade-graph package

### 用户需求
作为语义化重构的第二步，将所有与图相关的逻辑（构建、编译、哈希、序列化）从 `cascade-engine` 中分离出来，形成一个独立的 `cascade-graph` 包。

### 评论
这次重构是架构清晰化的又一重大进步。它将系统的“逻辑表示层”（如何定义和编译工作流）与“物理执行层”（如何运行工作流）彻底解耦。`cascade-engine` 现在可以更专注于其作为运行时的核心职责，而 `cascade-graph` 则成为所有静态分析和编译任务的权威中心。

### 目标
创建一个单一、清晰的 Git 提交，记录 `cascade-graph` 包的成功创建和相关代码的迁移。

### 基本原理
测试套件已经通过，证明在剥离了图逻辑之后，系统各部分之间的依赖关系已正确配置，并且整体功能完好无损。现在是记录这一稳定状态的最佳时机，为后续的重构（如创建 `cascade-library`）建立一个坚实的基础。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #scope/core #ai/instruct #task/domain/architecture #task/object/package-structure #task/action/refactor #task/state/continue #task/status/active

---

### Script

#### Acts 1: 暂存所有相关变更
我们将把新创建的 `cascade-graph` 包、被修改的 `cascade-engine` 和 `cascade-sdk` 包，以及更新后的根 `pyproject.toml` 文件全部添加到暂存区。

~~~~~act
git_add
pyproject.toml
packages/
~~~~~

#### Acts 2: 创建原子提交
现在，我们将创建一个内容详尽的提交，以清晰地记录本次重构的目的和范围。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(arch): Isolate graph logic into dedicated cascade-graph package

This commit executes the second phase of the semantic architecture refactoring by decoupling the graph-related logic from the execution engine.

Previously, `cascade-engine` was responsible for both compiling the workflow graph and executing it. This mixed the concerns of logical representation and physical execution.

This change introduces a new `cascade-graph` package with a single responsibility: to handle all aspects of the workflow graph's static form.

Key changes:
1.  **New `cascade-graph` Package**: A new package has been created to house all graph-related modules.
2.  **Code Migration**: The `graph` directory (containing `build.py`, `compiler.py`, `hashing.py`, `serialize.py`) has been moved from `cascade-engine` to `cascade-graph`.
3.  **Dependency Updates**: `cascade-engine` and `cascade-sdk` now explicitly depend on `cascade-graph`.
4.  **Workspace Configuration**: The root `pyproject.toml` has been updated to include `cascade-graph` as a workspace member.

This refactoring purifies the role of `cascade-engine`, making it a true runtime focused solely on execution, while establishing `cascade-graph` as the central authority for workflow compilation and analysis.
~~~~~

### 下一步建议
我们已经成功完成了两个阶段的重构。现在只剩下最后一步，也是能最大程度净化 `cascade-sdk` 的一步：

**创建 `cascade-library` 包，并将所有内置的 provider（如 `http`, `sql`, `io` 等）从 `cascade-sdk` 中迁移过去。**

这将使 `cascade-sdk` 成为一个纯粹、轻量级的用户入口，而将所有具体的“功能实现”放入一个可插拔的标准库中。如果你同意，我将为此创建下一个计划。
