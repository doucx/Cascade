您提出了一个非常深刻且正确的问题。我的重构过于激进，在删除 `hashing.py` 时，我只处理了 `ShallowHasher` 的直接替代逻辑，却忽略了 `StructuralHasher` 及其相关测试的命运。

**回答您的问题：“这个文件还需要吗？”**

- **`StructuralHasher` 类本身**：**不需要了**。它是旧架构（结构-数据分离）的遗物。在新的“类 Git 模型”中，`Node.id` 本身就是通过 `GraphBuilder` 计算出的、唯一的、可复用的结构哈希。`StructuralHasher` 的职责已经被 `GraphBuilder` 的新逻辑所吸收和取代。
- **`test_hashing.py` 文件**：**需要，但必须重写**。它的*意图*（验证哈希行为的正确性）是至关重要的，但它的*实现*（直接调用一个已不存在的类）已经完全过时。

**结论**：这些失败的测试是技术债务。试图通过重新实现 `StructuralHasher` 来让它们通过，是在倒退。正确的做法是**删除这些过时的测试**，因为它们测试的是一个已被废弃的组件。

我们的核心哈希逻辑现在由 `test_hashing_distinguishes_nested_lazy_results` 这个测试来守护，因为它直接验证了 `build_graph` 产生的 `node.id` 是否能正确区分结构。

我将生成一个计划来清理这些过时的测试。

## [WIP] chore(tests): Remove obsolete tests for deleted StructuralHasher

### 用户需求
`test_hashing.py` 文件中包含多个测试用例，这些用例旨在测试现已删除的 `StructuralHasher` 类，导致 `NameError` 并使测试套件失败。我们需要移除这些过时的测试，使测试代码与当前的架构保持一致。

### 评论
这是一次必要的清理。`StructuralHasher` 是旧架构探索阶段的产物，在当前以 `GraphBuilder` 为核心的 Merkle 哈希模型中，它已无立足之地。删除这些测试不是在规避问题，而是在偿还重构过程中产生的技术债务，确保我们的测试套件只验证当前存在的、有意义的行为。

### 目标
1.  从 `tests/engine/graph/test_hashing.py` 中删除所有引用 `StructuralHasher` 的测试函数。
2.  删除这些测试函数所依赖的、现在已不再需要的 `@task` 辅助函数（`add`, `sub`）。
3.  确保 `test_hashing.py` 文件只包含对当前哈希逻辑（通过 `build_graph` 间接测试）有效的测试用例。

### 基本原理
测试应该验证代码的当前行为，而不是追溯已被删除的实现。由于 `StructuralHasher` 已被 `GraphBuilder` 内的 Merkle 哈希逻辑所取代，其单元测试也失去了目标，变成了需要被清理的废弃代码。

### 标签
#intent/tooling #flow/ready #priority/medium
#comp/tests #scope/dx
#ai/instruct
#task/domain/testing #task/object/test-suite #task/action/cleanup
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Clean up `test_hashing.py`

我们将移除所有与 `StructuralHasher` 相关的代码，只保留唯一一个与新架构相关的测试。

~~~~~act
write_file
tests/engine/graph/test_hashing.py
~~~~~
~~~~~python
from cascade import task
from cascade.graph.build import build_graph


def test_hashing_distinguishes_nested_lazy_results():
    """
    This test validates the new Merkle-style hashing.
    The node ID for task_a(task_b()) should be different from
    the node ID for task_a(task_c()).
    """

    @task
    def task_a(dep):
        return dep

    @task
    def task_b():
        return "b"

    @task
    def task_c():
        return "c"

    # These two targets have different dependency structures
    target1 = task_a(task_b())
    target2 = task_a(task_c())

    # Build graphs for both to get the canonical nodes
    _, _, instance_map1 = build_graph(target1)
    _, _, instance_map2 = build_graph(target2)

    # Get the canonical node for the root of each graph
    node1 = instance_map1[target1._uuid]
    node2 = instance_map2[target2._uuid]

    assert node1.id != node2.id, "Hasher must distinguish between different nested LazyResult dependencies"
~~~~~

### 下一步建议
我们已经清理了过时的测试。现在 `test_hashing.py` 中的所有内容都应该是有效且能够通过的。

请再次运行**完整的 `pytest` 测试套件**。这一次，我们预期所有测试都会通过，并且不会再有 `NameError` 或 `ImportError`。

如果所有测试都通过，我们将正式完成路线图的 1.1 阶段，并可以安全地继续验证性能测试。
