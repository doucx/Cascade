好的，我将生成一个 `[COMMIT]` 计划，将这次架构深层重构中的所有相关文件（包括 `Engine`、`Executor`、异常定义、导入修复和所有受影响的测试）提交。

## [COMMIT] refactor(runtime): 解耦 Engine/Executor，增强错误处理，修复导入循环

### 错误分析
本次提交集中解决了三个主要架构问题：
1.  **架构耦合**: `LocalExecutor` 承担了参数解析和图遍历的职责，违反了单一职责原则。
2.  **错误不优雅**: 当控制流（如 `run_if(False)`）跳过任务时，下游任务失败会抛出无上下文信息的 `KeyError`。
3.  **模块依赖**: `LazyResult` 的导入导致了核心模块之间的循环依赖死锁。

### 用户需求
1.  提升运行时错误的可诊断性和优雅性。
2.  为分布式执行器（未来）铺平道路，使 `Executor` 协议只处理纯粹的函数执行。

### 评论
这是一次关键性的架构提交，它将调度逻辑（`Engine`）和执行逻辑（`Executor`）彻底分离。通过将参数解析集中到 `Engine` 中，我们能够：
1.  **抛出语义明确的 `DependencyMissingError`**，极大地提升了调试体验。
2.  **修复了控制流终结时目标节点被跳过的问题**，确保目标缺失也能被正确报告。
3.  **通过引入 `src/cascade/spec/lazy_types.py`，彻底解决了核心模块的循环导入问题**，提升了代码库的稳定性和可维护性。

### 目标
将以下所有结构性更改和修复作为一个原子单元提交：
1.  `src/cascade/runtime/exceptions.py`：定义新的异常。
2.  `src/cascade/spec/lazy_types.py`：隔离 `LazyResult` 和 `MappedLazyResult` 的核心定义。
3.  `Engine` 重构：实现参数解析 (`_resolve_arguments`) 和策略 (`_execute_node_with_policies`) 抽取。
4.  `LocalExecutor` 简化：修改其签名和逻辑，只负责执行。
5.  所有受影响模块的导入路径修复和测试更新。

### 基本原理
遵守 ACA 协议，将所有已通过测试的架构改进提交到版本控制中。

### 标签
#intent/refine #flow/ready #priority/critical #comp/runtime #comp/tests #comp/core #concept/executor #concept/exceptions #scope/core #scope/dx #ai/delegate #task/domain/runtime #task/object/engine-refactor #task/action/decouple #task/state/end #task/status/completed

---

### Script

#### Acts 1: 添加所有变更到 Git 暂存区

~~~~~act
git_add
src/cascade/runtime/exceptions.py
src/cascade/spec/lazy_types.py
src/cascade/runtime/protocols.py
src/cascade/adapters/executors/local.py
src/cascade/runtime/engine.py
src/cascade/runtime/__init__.py
src/cascade/__init__.py
src/cascade/spec/task.py
src/cascade/graph/build.py
src/cascade/graph/serialize.py
src/cascade/spec/routing.py
src/cascade/tools/preview.py
tests/adapters/executors/test_local.py
tests/runtime/test_control_flow.py
~~~~~

#### Acts 2: 执行提交

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(runtime): Decouple Engine/Executor, enhance error reporting, fix circular imports

This commit implements a major structural refactoring to improve error handling, simplify the Executor protocol, and resolve persistent circular dependency issues in the core library.

Key Changes:

1. **Engine/Executor Decoupling**:
   - Argument resolution (handling dependencies, literals, Routers, and Inject objects) is moved from `LocalExecutor` into `Engine._resolve_arguments`.
   - `LocalExecutor` is simplified to a pure function execution wrapper, accepting only pre-resolved `args` and `kwargs`. This prepares the architecture for remote executors.

2. **Improved Error Handling**:
   - Introduced `DependencyMissingError` (`src/cascade/runtime/exceptions.py`) to replace opaque `KeyError` when an upstream task is skipped (`run_if(False)`) and its result is requested downstream.
   - Enhanced `Engine._execute_graph` to correctly check if the *target node itself* was skipped, ensuring a clear `DependencyMissingError` is raised instead of an obscure `KeyError` at the end of the run loop.

3. **Circular Import Fix**:
   - Created `src/cascade/spec/lazy_types.py` to house the fundamental definitions of `LazyResult`, `MappedLazyResult`, and `RetryPolicy`.
   - All high-level modules (`task`, `build`, `engine`, `routing`) now import these types from the lowest common layer (`lazy_types.py`), eliminating the circular dependency cycle.

4. **Test Updates**:
   - `tests/adapters/executors/test_local.py` updated for the new `execute` signature.
   - `tests/runtime/test_control_flow.py` updated to assert `DependencyMissingError` for control flow skips.
~~~~~
