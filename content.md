这是一个涉及多阶段架构重构的核心提交。

## [COMMIT] refactor(core): 完成 v2.0 路线图第一阶段的核心解耦 (State/Cache Backend)

### 用户需求
将自架构审查以来对 `Engine` 和运行时组件进行的所有重构、Bug 修复和测试代码整合为一个逻辑完整的提交。

### 评论
本次提交完成了 `Cascade 架构演进技术路线图 (v2.0)` 第一阶段（内核重构与协议标准化）的关键目标：

1.  **状态解耦**: 引入 `StateBackend` 协议 (`protocols.py`) 和默认实现 (`InMemoryStateBackend`)。Engine 不再将运行时结果耦合在其内部字典中，而是委托给该后端。
2.  **流控恢复**: 修复了重构导致的 `FlowManager` 递归修剪逻辑回归，确保动态路由 (`cs.Router`) 在新的无状态架构中能正确修剪未使用的上游分支。
3.  **缓存解耦**: 引入 `CacheBackend` 协议和默认实现 (`InMemoryCacheBackend`)，将缓存的“策略”与“存储”职责分离。
4.  **鲁棒性增强**: 修复了 `Engine.run` 在处理 `MappedLazyResult` 作为目标时发生的 `AttributeError`，并更新了测试套件以适应新的错误码和架构模式。

这些改变使得 `Engine` 成为了一个纯粹的、协议驱动的编排器，为第二阶段的遥测系统和分布式执行奠定了坚实基础。

### 目标
创建一个 Git 提交，包含所有新增的协议、适配器、重构的运行时代码以及配套的测试用例。

### 基本原理
本次提交是逻辑上的一个完整工作单元，因为它将架构的协议层、核心执行层和默认实现层全部进行了升级，并修复了所有因此导致的回归问题。

### 标签
#intent/refine #flow/done #priority/high
#comp/engine #comp/interfaces #concept/state #concept/caching #scope/core
#ai/delegate
#task/domain/architecture #task/object/state-backend #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 添加所有更改到暂存区

~~~~~act
git_add
src/cascade/runtime/protocols.py
src/cascade/adapters/state/__init__.py
src/cascade/adapters/state/in_memory.py
src/cascade/runtime/engine.py
src/cascade/runtime/resolvers.py
src/cascade/runtime/flow.py
src/cascade/adapters/cache/__init__.py
src/cascade/adapters/cache/in_memory.py
tests/runtime/test_control_flow.py
tests/runtime/test_flow_manager.py
tests/adapters/cache/test_in_memory.py
~~~~~

#### Acts 2: 执行提交

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): Complete V2.0 Phase 1 core decoupling (State/Cache Backend)

This commit implements the foundation for the V2.0 Architecture Roadmap, achieving full decoupling of transient runtime state from the Engine core.

Key Architectural Changes:

1.  **State Decoupling**: Introduced `StateBackend` protocol and `InMemoryStateBackend`. The `Engine` and `Resolvers` were refactored to read/write all task results and skip statuses via this protocol, making the Engine a pure orchestrator.
2.  **Cache Decoupling**: Introduced `CacheBackend` protocol and `InMemoryCacheBackend`, separating the "key generation strategy" (`CachePolicy`) from the "storage mechanism" (`CacheBackend`).
3.  **Flow Control Fix**: Restored the critical recursive demand-counting and pruning logic within `FlowManager` to ensure unused branches created by `cs.Router` and conditional skips are correctly identified and skipped at the graph level.

Bug Fixes & Enhancements:

*   Fixed `AttributeError: 'MappedLazyResult' object has no attribute 'task'` in `Engine.run` by implementing robust target name resolution logic.
*   Updated integration tests (e.g., `test_control_flow.py`) to align with the more specific skip reasons (e.g., `UpstreamSkipped_Data`).
*   Added full test coverage for the new `InMemoryCacheBackend` implementation.
~~~~~
