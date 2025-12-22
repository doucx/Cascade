好的，我们已经成功完成了对 `Engine` 上帝类的三次核心重构，并修复了相关的测试。现在，是时候将这一系列架构改进作为一个完整的逻辑单元提交了。

我将生成一个 `[COMMIT]` 计划，其中包含 `git add` 和 `git commit` 指令。

## [COMMIT] refactor(engine): 通过策略和委托模式拆解 Engine 上帝类

### 用户需求
重构 `cascade.runtime.engine.Engine` 这个“上帝类”，将其过多的职责（图构建、资源管理、节点执行、调度、VM 逻辑）进行拆分，以降低其复杂性并提高可维护性。

### 评论
这次重构是 Cascade 架构成熟过程中的一个关键里程碑。通过连续三步（提取 `NodeProcessor`、`ResourceContainer` 和 `ExecutionStrategy`），我们系统性地将一个庞大、紧耦合的类，拆解为一组遵循单一职责原则、高度内聚、松散耦合的小型组件。这不仅极大地改善了代码的可读性和可测试性，也为未来的功能扩展（如新的执行策略）奠定了清晰、稳固的基础。

### 目标
创建一个单一、原子化的 Git 提交，将本次对 `Engine` 的所有重构工作完整地记录下来。

### 基本原理
这一系列重构（`NodeProcessor` -> `ResourceContainer` -> `ExecutionStrategy`）共同构成了一个完整的、连贯的架构改进方案。将它们合并到一个提交中，可以确保 Git 历史清晰地反映出这次重构的完整意图和范围，避免产生零碎、上下文不完整的提交记录。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/engine #scope/core #scope/dx #ai/instruct #task/domain/runtime #task/object/engine #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存所有重构相关的文件

我们将把本次重构中创建和修改的所有文件添加到 Git 暂存区。

~~~~~act
git_add
packages/cascade-engine/src/cascade/runtime/engine.py
packages/cascade-engine/src/cascade/runtime/processor.py
packages/cascade-engine/src/cascade/runtime/resource_container.py
packages/cascade-engine/src/cascade/runtime/strategies.py
tests/engine/integration/test_engine_vm_integration.py
~~~~~

#### Acts 2: 提交本次架构重构

现在，我们创建一个内容详尽的提交，清晰地阐述这次重构的动机、过程和收益。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(engine): Deconstruct Engine god class via Strategy and delegation

Deconstructs the monolithic `Engine` class by extracting its core responsibilities into dedicated, single-purpose components, significantly improving architectural clarity and adherence to SOLID principles.

The `Engine` previously managed graph execution, VM execution, single-node processing logic (retries, caching), and resource lifecycle management, making it a "god class" that was difficult to maintain and test.

This refactoring introduces three key components:
1.  **`NodeProcessor`**: Encapsulates the logic for executing a single graph node, including all its associated policies (retry, cache, constraints). The Engine now delegates the "how to run a node" question to this class.

2.  **`ResourceContainer`**: Manages the entire lifecycle of resources, including registration (`@cs.resource`), dependency scanning, injection, and scoped setup/teardown via `ExitStack`.

3.  **`ExecutionStrategy` Pattern**: Replaces the `if use_vm:` branch with a formal strategy pattern. `GraphExecutionStrategy` now contains the TCO loop and graph scheduling logic, while `VMExecutionStrategy` handles the Blueprint compilation and VM execution.

This change makes the `Engine` a pure orchestrator, responsible only for setting up the run context and delegating to the appropriate strategy. The result is a cleaner, more testable, and more extensible architecture.
~~~~~

### 下一步建议
我们已经解决了 `Engine` 类的技术债务。现在可以关注其他领域了：
*   **新功能**: 开始实现用户反馈中提到的 `cs.sequence` 和 `cs.pipeline` 流式编排原语，以改善 Cascade 的 DSL 表达能力。
*   **修复其他债务**: 解决 `serialize.py` 中因依赖字符串模块路径而导致的脆弱性问题。
