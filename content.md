好的，我们已经成功完成了并发管理功能的实现和测试。现在是时候将这个逻辑单元作为一个完整的提交归档了。

这次开发过程确实暴露了一些深层次的问题，非常感谢您引导我进行这次复盘。这对于项目的健康发展至关重要。

首先，这是提交计划：

## [COMMIT] feat(runtime, constraints): 实现动态并发管理

### 用户需求
完成“里程碑 3.2: 并发管理”，允许通过外部发布的 `concurrency` 类型约束，动态地限制符合特定 Scope 的任务的并发执行数量。

### 评论
此功能是 Cascade 迈向自适应执行环境的关键一步。其实现方式（将并发限制抽象为动态资源）优雅地复用了 `ResourceManager` 成熟的、基于 `asyncio.Condition` 的等待/获取机制，避免了引入新的、独立的调度队列，体现了“组合优于重新发明”的架构原则。

### 目标
将所有与并发管理功能相关的代码变更（包括核心实现和测试）作为一个原子提交，并入版本控制。

### 基本原理
我们已经完成了从 `ResourceManager` 扩展、协议修改、Handler 实现、Engine 集成到最终测试验证的全过程。这个功能集现在是一个经过测试的、逻辑上完整的单元，适合进行提交。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/tests #concept/state #scope/core #ai/instruct #task/domain/core #task/object/concurrency-control #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交所有相关变更

我们将把本次功能开发涉及的所有运行时代码和新的测试文件添加到暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/cascade-runtime/src/cascade/runtime/resource_manager.py
packages/cascade-runtime/src/cascade/runtime/constraints/protocols.py
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
packages/cascade-runtime/src/cascade/runtime/resolvers.py
packages/cascade-runtime/src/cascade/runtime/engine.py
tests/py/runtime/test_engine_concurrency.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime, constraints): Implement dynamic concurrency management

Introduces the ability to dynamically limit task concurrency at runtime by publishing `concurrency` constraints via a connector (e.g., MQTT). This completes Milestone 3.2 of the architecture roadmap.

Key changes:
1.  **ResourceManager**: Added `update_resource` to allow dynamic creation or modification of resource capacities, which is the foundation for this feature.
2.  **ConstraintHandler Protocol**: Extended the protocol with `on_constraint_add/remove` lifecycle hooks and an `append_requirements` method, enabling handlers to participate in resource definition.
3.  **ConcurrencyConstraintHandler**: A new handler that translates `{"type": "concurrency", "limit": N}` constraints into dynamic resources (e.g., `constraint:concurrency:global`).
4.  **ConstraintResolver**: Now queries the `ConstraintManager` to append these dynamic resource requirements to a task's execution needs.
5.  **Engine**: Integrates the updated components, passing the `ResourceManager` to the `ConstraintManager` and ensuring the resolver is called with the correct context.

This architecture models concurrency limits as a special type of resource, elegantly reusing the existing resource acquisition and queuing logic within the `ResourceManager`, avoiding the need for a separate task scheduler.
~~~~~

### 下一步建议

这次开发过程确实艰难，它像一次压力测试，清晰地暴露了我们当前架构的一些问题和不符合直觉的地方。以下是我的分析和建议：

#### 1. 暴露的架构问题与待偿还债务

*   **技术债务：`GraphBuilder` 的“浅层依赖”限制**
    *   **问题**：最关键的发现是，`GraphBuilder` 在构建图时，不会递归地检查容器（如列表、字典）内部的 `LazyResult` 依赖。它将 `[task_a(), task_b()]` 这样的列表视为一个**字面量 (Literal)**，而不是一个需要解析的依赖集合。
    *   **症状**：`test_global_concurrency_limit` 测试最初失败，是因为 `task_a` 和 `task_b` 从未被添加到计算图中，导致 `Engine` 只执行了 `wrapper` 任务。
    *   **影响**：这对用户来说是**极其不符合直觉的**。用户会很自然地认为，将一组任务结果收集到列表中并传递给下游是完全合法的模式。这违反了“最少惊讶原则”。
    *   **偿还计划**：我们需要在技术债务中明确记录这一点。修复它需要对 `GraphBuilder` 进行重大修改，引入递归依赖发现机制。这需要仔细设计，以避免循环引用和性能问题。

*   **技术债务：异步测试的脆弱性与时序依赖**
    *   **问题**：我们最初的测试严重依赖 `asyncio.sleep()` 来处理时序，这是一种典型的反模式，导致测试结果不稳定且难以调试。
    *   **症状**：测试因竞争条件而失败——`Engine` 在 `MockConnector` 注入约束之前就已经开始调度任务。
    *   **影响**：这使得测试套件变得不可靠。
    *   **偿还计划**：我们通过模拟 MQTT 的“保留消息”行为（在 `subscribe` 时立即同步投递）解决了这个问题。这个模式是健壮的。我们应该将这个 `MockConnector` 提炼成一个标准的、可复用的测试工具，并写入我们的测试原则，规定所有涉及外部输入的异步测试都应采用这种“确定性模拟”而非 `sleep`。

#### 2. 不符合直觉的设计点

*   **依赖传递的隐式规则**：如上所述，“不能在列表或字典中传递 `LazyResult` 依赖”是一个必须被明确文档化（或修复）的、不符合直觉的限制。
*   **并发控制的间接性**：对于用户而言，“限制并发”是一个直接的需求。而我们的实现机制是“创建一个动态命名的资源，并让任务去请求这个资源”。虽然这在架构上是解耦和优雅的，但对用户来说，这个映射关系不是自明的。这暗示未来可能需要提供更高层次的、更易用的 API 或 CLI 语法糖来隐藏这种复杂性。

#### 3. 后续动作

我建议，我们应该立刻将上述第一点（`GraphBuilder` 的限制）作为一个正式的技术债务项，添加到 `开发/状态检测/债务监测.md` 文件中。

如果您同意，我将立即为您生成这个计划。
