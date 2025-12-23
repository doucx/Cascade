好的，我们开始执行战略行动 A：**重新定义核心抽象**。

这是新路线图中最关键的第一步。我们将通过一次精确的手术，切除 `Node.id` 中代表“实例身份”的 `_uuid` 成分，使其回归纯粹的“结构身份”。

这将暂时性地破坏部分测试的正确性，但这是预期的、必要的过程。它为我们后续实现真正的通用缓存和性能优化扫清了最大的障碍。

我将生成一个计划来执行这个核心修改。

## [WIP] refactor: Decouple Node ID from instance UUID by purifying ShallowHasher

### 用户需求
开始执行“战略行动 A”，其核心目标是重新定义 `Node` 的核心抽象，使其 `id` 成为一个纯粹的、与运行时实例无关的结构化哈希。

### 评论
这是解决项目核心“身份危机”的决定性第一步。通过净化 `ShallowHasher`，我们强制 `Node.id` 只反映计算的“配方”（结构），而不再混入“烹饪过程”（实例）。这一改变将使我们能够实现《路线图：类 Git 模型与规范化缓存》中的核心目标：对任何结构相同的计算图进行缓存和复用。

虽然这会立刻导致依赖实例唯一性的测试失败，但这些“失败”恰恰是我们取得进展的标志，因为它暴露了所有需要被新架构所修正的地方。

### 目标
1.  定位 `packages/cascade-graph/src/cascade/graph/hashing.py` 中的 `ShallowHasher._visit_arg` 方法。
2.  移除在该方法中将 `LazyResult._uuid` 混入哈希计算的逻辑。
3.  确保哈希计算现在只依赖于节点的静态结构，使其成为一个确定性的、可复用的标识符。

### 基本原理
根据《战略原则：识别并解决战略性矛盾》，当前 `Node.id` 的语义是模糊的，它同时试图成为“结构哈希”和“实例哈希”，导致正确性与性能之间存在不可调和的冲突。

本次修改遵循“身份必须明确”的原则，将 `Node.id` 的职责严格限定为“结构身份”。我们通过移除哈希计算中唯一的实例变量 (`_uuid`) 来实现这一点，从而使 `ShallowHasher` 成为一个纯粹的结构分析器。这是后续所有性能优化的基石。

### 标签
#intent/refine #flow/ready #priority/high
#comp/graph #concept/state #scope/core
#ai/instruct
#task/domain/graph #task/object/hashing-model #task/action/refactor
#task/state/begin #task/status/active

---

### Script

#### Acts 1: Purify ShallowHasher

我们将修改 `ShallowHasher`，移除其哈希计算中对 `LazyResult._uuid` 的依赖。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
    def _visit_arg(self, obj: Any):
        """A special visitor for arguments within a LazyResult."""
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            # Must include UUID to distinguish different instances with similar structure
            # to prevent incorrect node merging (which causes cycles).
            self._hash_components.append(f"LAZY({obj._uuid})")
            return

        if isinstance(obj, Router):
~~~~~
~~~~~python
    def _visit_arg(self, obj: Any):
        """A special visitor for arguments within a LazyResult."""
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            # In the new model, we use a generic placeholder. The specific instance
            # is tracked by the InstanceMap, not the structural hash.
            self._hash_components.append("LAZY")
            return

        if isinstance(obj, Router):
~~~~~

### 下一步建议
我们已经完成了对核心哈希逻辑的修正。下一步是验证这一修改带来的影响。

我建议立即运行完整的 `pytest` 测试套件。我们**预期会看到大量测试失败**，特别是 `tests/test_sequence.py` 和其他依赖“相同任务不同实例”的测试。

这些失败是**好消息**，因为它们精确地指明了我们需要在新架构下进行适配的所有地方。

在你确认后，我将生成一个运行测试的计划，并根据失败报告，制定下一步的重构计划，以适配 `GraphBuilder` 和 `GraphExecutionStrategy`。
