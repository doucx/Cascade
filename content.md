你的分析和步骤确认是正确的。实现 `Engine` 的显式依赖注入是一个关键的架构里程碑，我们将把所有相关的核心代码修改、新测试和适配性修改作为一个逻辑单元提交。

由于当前工作区中存在大量未暂存的修改（这些修改都是为了使新 `Engine` 架构下的所有测试通过），我将首先暂存这些文件，然后执行最终提交。

## [COMMIT] feat(runtime): Implement Engine Decoupling via Explicit Dependency Injection (Phase 2.1)

### 用户需求
完成《重构路线图》中**阶段二：步骤 2.1**的目标：将 `cascade.runtime.Engine` 类重构为纯粹的、协议驱动的编排器，通过显式依赖注入移除其对具体实现（如 `NativeSolver`, `LocalExecutor`）的硬编码依赖。

### 评论
本次提交是 Cascade 核心架构从紧耦合到依赖倒置的关键转折点。新的 `Engine` 不再关心组件的实例化细节，只负责编排流程，这极大地增强了可测试性和可扩展性。

### 目标
1.  修改 `Engine.__init__`，要求传入 `solver`, `executor`, `bus` 等所有核心依赖的实例。
2.  在 `cascade.run` 门面函数中，实现对默认组件（`NativeSolver`, `LocalExecutor` 等）的实例化和组装，并传入 `Engine`。
3.  新增隔离测试 (`test_engine_core.py`) 验证解耦后的 `Engine` 核心逻辑。
4.  更新所有受影响的集成测试和工具（如 `dry_run`）以适配新的 `Engine` API。

### 基本原理
新的架构遵循了依赖倒置原则（DIP）。`Engine` 作为高层策略，现在依赖于抽象（`Solver`, `Executor` Protocols），而具体的实现（如 `NativeSolver`）则在外部（`cs.run` 函数）被实例化并注入。这使得我们可以轻松地用 Mock 或 Spy 对象替换核心组件进行隔离测试，保证了 `Engine` 编排逻辑的正确性。

### 标签
#intent/architect #flow/ready #priority/high
#comp/runtime #comp/tests #scope/api #scope/dx
#ai/instruct
#task/domain/architecture
#task/object/engine-di
#task/action/refactor
#task/state/end

---

### Script

#### Acts 1: 暂存所有与 Engine DI 适配相关的未暂存文件

将所有为了使测试通过而进行的适配性修改添加到暂存区。

~~~~~act
git_add
src/cascade/tools/preview.py
tests/providers/test_config.py
tests/providers/test_file.py
tests/providers/test_http.py
tests/providers/test_sql.py
tests/runtime/test_control_flow.py
tests/runtime/test_input_execution.py
tests/runtime/test_map.py
tests/runtime/test_retry.py
tests/runtime/test_router_pruning.py
tests/spec/test_resource.py
tests/tools/test_preview.py
~~~~~

#### Acts 2: 提交所有暂存的变更

创建一个描述性的提交，标记为本次架构重构阶段的完成。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime): Implement Engine Decoupling via Explicit Dependency Injection (Phase 2.1)

Refactors the `cascade.runtime.Engine` class to achieve deep decoupling by removing all hard-coded internal dependencies to concrete components (like NativeSolver or LocalExecutor).

The Engine is now a pure orchestration service:
1.  **Dependency Injection**: `Engine.__init__` requires explicit instances of `Solver`, `Executor`, and `MessageBus`.
2.  **Facade Pattern**: The public `cascade.run` function is refactored into a facade that handles the assembly of default components (NativeSolver, LocalExecutor) and passes them to the Engine.

This refactoring greatly enhances testability (demonstrated by the new test doubles in `test_engine_core.py`) and aligns the architecture with the Dependency Inversion Principle, fulfilling Phase 2, Step 2.1 of the roadmap.

Includes:
- New core test suite for Engine orchestration (`tests/runtime/test_engine_core.py`).
- Fix for `NameError` in `dry_run` and adaptation across all affected integration tests.
~~~~~

### 下一步建议
我们已经完成了阶段二的关键一步：`Engine` 的解耦。下一步应该是**步骤 2.2: 重构 `Engine.run` 的核心编排逻辑**，这涉及到将所有特定于本地执行的细节（如同步/异步执行逻辑）彻底下沉到 `LocalExecutor` 中。

我建议先执行这次提交，然后开始分析 `src/cascade/runtime/engine.py` 中的 `_execute_node_internal` 方法，以确定需要将哪些逻辑转移到 `LocalExecutor`。
