简要回答
所有测试已通过，核心重构已完成。现在我将生成一个 **[COMMIT]** 计划，其中包含所有修改文件的 `git add` 和一个详尽的 `git commit` 信息，以及对未来的建议。

## [COMMIT] feat(core): ParamNode 统一为 TaskNode 子类，修复循环依赖和参数覆盖

### 用户需求
期望 `ParamNode` 能像普通任务一样，由运行时引擎调度执行，并通过标准的参数解析流程处理 `cs.Jump` 带来的参数覆盖。

### 评论
这次重构是 Cascade 运行时核心架构的一个重要里程碑。通过将 `ParamNode` 集成到现有 `TaskNode` 的多态体系中，我们极大地简化了 `ArgumentResolver` 的逻辑，消除了特殊处理的路径，使得 `cs.Param` 在 TCO/Jump 场景下的行为符合预期，并提升了整个系统的健壮性和可维护性。

### 目标
1.  **统一 `ParamNode` 语义**：将 `ParamNode` 重构为 `TaskNode` 的子类，使其拥有 `_callable` 等所有 `TaskNode` 的特性。
2.  **标准化执行流程**：移除 `ArgumentResolver` 中针对 `ParamNode` 的特殊解析和状态写入逻辑，强制 `ParamNode` 走 `Processor` 和 `Executor` 的标准执行路径。
3.  **修复 TCO 参数覆盖**：确保 `cs.Jump` 带来的 `input_overrides` 在 `ArgumentResolver` 中正确应用于 `ParamNode`（通过其 `_callable` 获取值），修复循环依赖时参数不生效的问题。
4.  **提高代码一致性**：删除 `GraphExecutionStrategy` 中遗留的对 `ParamNode` 的跳过逻辑。

### 基本原理
通过彻底移除 `ParamNode` 作为特殊节点的身份，并将其整合到 `TaskNode` 的结构和执行模型中，所有的参数解析和执行都遵循单一、统一的流程。现在，`_get_param_value` 任务作为一个普通任务，其参数（包括通过 `cs.Param` 定义的初始值和通过 `cs.Jump` 传递的覆盖值）都将由 `ArgumentResolver` 的标准机制进行优先级判定和注入。这不仅解决了当前的 `DependencyMissingError`，也消除了潜在的逻辑不一致性，使得未来对任务类型的扩展更加容易。

### 标签
#intent/refine #intent/fix #flow/done #priority/critical #comp/engine #concept/node #concept/execution #concept/parser #concept/state #scope/core #ai/delegate #task/domain/core #task/object/param-node #task/action/unify #task/state/end

---

### Script

#### Acts 1: 添加所有更改到暂存区

~~~~~act
git_add
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
packages/cascade-engine/tests/adapters/executors/test_local.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-graph/src/cascade/graph/model.py
packages/cascade-graph/src/cascade/graph/serialize.py
packages/cascade-graph/tests/test_build.py
packages/cascade-graph/tests/test_serialize.py
packages/cascade-sdk/src/cascade/tools/lisp.py
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~

#### Acts 2: 提交更改

~~~~~act
git_commit
~~~~~
~~~~~text
feat(core): Unify ParamNode as TaskNode subtype, fix TCO and parameter override

Refactored `ParamNode` to inherit from `TaskNode`, unifying its execution model with regular tasks. This change eliminates the special-casing of `ParamNode` within `ArgumentResolver` and `GraphExecutionStrategy`, resolving several critical issues:

-   **Fixes `DependencyMissingError`**: `ParamNode`s are now properly scheduled and executed by the `Executor` via the `_get_param_value` callable, ensuring they produce results in the `StateBackend`.
-   **Enables `cs.Jump` parameter override**: The `ArgumentResolver`'s standard logic for handling `input_overrides` (from `cs.Jump`) now correctly applies to `ParamNode`s, allowing dynamic parameter changes in iterative workflows. Previously, a faulty special branch for `ParamNode` in the resolver incorrectly ignored overrides, leading to infinite loops in TCO tests.
-   **Resolves `AttributeError`**: `ParamNode` now properly exposes `callable_obj` (pointing to `_get_param_value.func`), satisfying API contracts for tools like the CLI generator.
-   **Simplifies Runtime Logic**: Removes redundant and inconsistent code paths, making the core engine more robust and easier to extend.

**Changes Details:**
-   **`cascade-graph/model.py`**: `ParamNode` now inherits from `TaskNode`.
-   **`cascade-graph/build.py`**: Ensures `_callable` (pointing to `_get_param_value.func`) is explicitly set when building `ParamNode`s.
-   **`cascade-graph/serialize.py`**: Updated serialization to handle `ParamNode`'s `_callable`.
-   **`cascade-engine/runtime/resolvers.py`**: Removed the special `if isinstance(ParamNode)` block, relying on the generic argument resolution.
-   **`cascade-engine/runtime/strategies/graph.py`**: Removed the explicit `if node.node_type == "param": continue` line that was preventing `ParamNode` execution.

This refactoring significantly enhances the consistency and reliability of Cascade's core runtime.
~~~~~

### 下一步建议
1.  **文档更新**: 更新任何关于 `ParamNode` 特殊行为的文档，以反映其现在作为 `TaskNode` 子类的统一身份。
2.  **性能审查**: 尽管这次是重构，但仍值得关注对 `ArgumentResolver` 的性能影响，尤其是在大量 ParamNode 的场景下。
3.  **Lisp 转译器审查**: 检查 `packages/cascade-sdk/src/cascade/tools/lisp.py` 是否完全适配了 `ParamNode` 的新结构。本次更改解决了 `AttributeError`，但 Lisp 转译器可能还有其他假设。
