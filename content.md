好的，我们已经完成了核心重构和测试修复，现在底层逻辑和单元测试都已经对齐到新的 `ResourceRegistry` 模型上。

我将生成一个 `[COMMIT]` 计划，将这些变更作为一个完整的逻辑单元提交。

## [COMMIT] refactor(vm): Implement explicit ResourceRegistry injection for observability

### 用户需求
彻底废除 `EventDrivenRunner` 中使用 `functools.partial` 强行注入队列的非正规做法。改用基于 `ResourceRegistry` 的显式依赖注入协议。

### 评论
这是《统一上下文与资源管理路线图》中**阶段 2** 的圆满完成。通过这个改动，我们成功地将物理图的执行（Reactor）与运行环境的资源（Queue）在架构层面实现了真正的解耦。物理函数 `standard_observer` 现在不再被动地接收一个不确定的关键字参数，而是通过一个稳定的、受控的资源注册表接口来主动声明其依赖。这极大地提高了系统的透明度和可测试性。

### 目标
创建一个 Git 提交，记录物理函数调用契约的升级、资源注册表的引入、以及相关的测试对齐。

### 基本原理
我们通过以下三个维度的协同工作实现了这一目标：
1.  **契约升级**：`Reactor` 现在强制向所有物理函数传递第三个参数 `resources`。
2.  **配置中心化**：`EventDrivenRunner` 不再在函数映射阶段干预逻辑，而是在启动前通过 `ResourceRegistry` 预置好所需的“物理环境”。
3.  **引用透明**：`standard_observer` 切换到基于 ID 的资源查找，使其逻辑不依赖于特定的调用闭包。

### 标签
#intent/refine #flow/ready #priority/high #comp/vm #comp/std #concept/executor #scope/core #ai/instruct #task/domain/architecture #task/object/resource-registry #task/action/integration #task/state/end

---

### Script

#### Acts 1: 提交资源注入重构

我们将所有涉及契约变更、实现重构以及修复后的测试文件添加到暂存区。

~~~~~act
git_add
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-std/src/cascade/std/triad/observer.py
packages/cascade-vm/src/cascade/vm/harness.py
packages/cascade-vm/tests/unit/test_reactor.py
packages/cascade-std/tests/unit/triad/test_observer.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(vm): Implement explicit ResourceRegistry injection for observability

This commit replaces the implicit and brittle `functools.partial` injection
mechanism for the observability queue with a formal `ResourceRegistry` model,
as defined in the "Unified Context & Resource Management Roadmap" (Phase 2).

Key Changes:
1. **Reactor API Upgrade**: Updated `Reactor._execute_task` to consistently pass a `resource_registry` instance as the third argument to all physical functions.
2. **Explicit Dependency Injection**: Refactored `EventDrivenRunner` to register the `event_queue` under the stable ID `"system.observer.queue"` within its internal `ResourceRegistry`.
3. **Observer Decoupling**: Updated `standard_observer` to use the standardized `resources.get()` interface, removing its dependence on specific call-site closure injection.
4. **Test Alignment**: Fully synchronized `test_reactor.py` and `test_observer.py` with the new three-argument function signature and registry-based lookup, ensuring a healthy and robust test suite.

This refactoring significantly improves the architectural purity by strictly separating the Graph's logic from its Runtime Environment.
~~~~~

### 下一步建议
我们已经完成了资源管理的第一个闭环。接下来的重心将转向路线图的**阶段 3：统一所有上下文**。

任务如下：
1.  **设计 `ExecutionContext`**: 在 `cascade-spec` 中定义一个新的 `ExecutionContext` 类，它将持有 `InputSpec`、已解析的 `params` 以及我们的 `ResourceRegistry`。
2.  **重构 `Engine`**: 升级 `Engine.run` 的逻辑。它需要：
    *   先扫描图收集所有 `InputSpec`。
    *   结合用户输入的 `params` 环境变量。
    *   构造并填充 `ExecutionContext` 实例。
    *   废除 `cascade.common.context` 中的 `ContextVar` 隐式传递，转而考虑如何将这个显式的 Context 对象注入到 Reactor 的执行流中。

如果你准备好了，我们可以开始设计 `ExecutionContext`。
