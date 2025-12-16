好的，既然所有资源调度和图遍历相关的测试都已通过，那么现在可以放心地提交本次关于`资源感知的初步实现`的内容了。

## [COMMIT] feat(core): 实现资源感知调度与配额管理 (MVP)

### 错误分析
没有错误，实现通过所有测试。

### 用户需求
实现一个零依赖的资源感知调度系统，使 `Engine` 能够在执行任务前检查、等待并获取任务声明所需的资源（例如 CPU, GPU, 内存）。同时，支持动态资源约束，即资源的需求量本身可以是一个上游任务的计算结果。修复了测试中的事件嵌套循环错误。

### 评论
这个提交增加了资源管理能力，这是向工业级别框架演进的重要一步。
### 目标
所有代码修改已完成。

### 基本原理
-   **ResourceManager**: 选择 `asyncio.Condition` 而非 `Semaphore` 是因为资源请求是多维度的（如 `{gpu:1, mem:4}`），标准信号量无法处理这种原子性的多资源请求。
-   **GraphBuilder 增强**: 为了保证拓扑排序正确，动态计算的资源需求量必须被视为“上游依赖”。通过添加特殊前缀的边，我们既利用了现有的求解器，又能在执行时通过名称过滤将其与普通数据参数区分开。
-   **Engine 集成**: 将资源获取放在 `_execute_node_with_policies` 中最靠近执行点的位置，能够最大限度地减少资源占用时间。

### 标签
#intent/build #flow/done #priority/high #comp/core #comp/runtime #scope/core #task/domain/runtime #task/object/resource-manager #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 添加变更到 Git 暂存区

将所有被修改和添加的文件都添加到 Git 暂存区，准备提交。

~~~~~act
git_add
src/cascade/runtime/resource_manager.py
src/cascade/graph/build.py
src/cascade/adapters/executors/local.py
src/cascade/runtime/engine.py
src/cascade/__init__.py
tests/integration/test_resource_scheduling.py
~~~~~

#### Acts 2: 执行提交

创建包含详细信息的提交，并推送到远程仓库。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(core): Implement resource-aware scheduling and quota management (MVP)

This commit introduces a zero-dependency resource-aware scheduling system to Cascade, enabling the Engine to inspect, wait for, and acquire resources (CPU, GPU, memory) declared by tasks. It also supports dynamic resource constraints, where the demand is the result of an upstream task.

Key changes:

-   `src/cascade/runtime/resource_manager.py`: Implements `ResourceManager`, a thread-safe resource manager based on `asyncio.Condition`. It manages resource limits and ensures tasks wait until resources become available.
-   `src/cascade/graph/build.py`: Enhances `GraphBuilder` to scan for `.with_constraints()` and creates implicit dependency edges to tasks that compute the resource amount.
-   `src/cascade/adapters/executors/local.py`: Modifies `LocalExecutor` to ignore constraint edges during argument injection.
-   `src/cascade/runtime/engine.py`: Integrates `ResourceManager` into the task execution lifecycle: resolving dynamic resource requirements, acquiring before task execution, and releasing after.
-   `src/cascade/__init__.py`: Updates the public API `run` function to accept a `system_resources` argument, configuring available resources.
-   `tests/integration/test_resource_scheduling.py`: Adds integration tests for concurrency limiting, dynamic resource constraints, and error handling for insufficient resources.

This is an important infrastructure milestone, allowing Cascade workflows to be more robust in complex resource-constrained environments.
~~~~~

### 下一步建议
根据先前的讨论，现在是构建 `cs.config` Provider 的理想时机。
