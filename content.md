好的，我完全理解。您的分析是正确的，这是一个经典的“灯下黑”问题：测试套件覆盖了所有已知的边界情况，但我们引入了一个全新的、未被预料到的故障模式——**由于哈希算法过于简化而导致的结构性哈HI希冲突**。

性能测试的失败和标准测试的通过，这两者结合在一起，为我们提供了无价的线索。它证明了 `sequence([a(), a()])` 这种“同级”实例唯一性的问题是解决的，但 `a(b(c()))` 这种“纵深”结构的唯一性问题被我们的修改破坏了，并且缺乏测试覆盖。

我将严格遵循 TDD 流程。**此计划的唯一目标是创建一个会失败的测试**，以精确地捕获这个哈希冲突的 bug。在测试“变红”之前，我不会提出任何修复代码的建议。

## [WIP] test: Add failing test for structural hash collision in nested dependencies

### 用户需求
我们的 `ShallowHasher` 在上次修改后，无法区分包含不同 `LazyResult` 子节点的图结构，导致了哈希冲突和伪环的产生。我们需要遵循 TDD 原则，首先创建一个专门的测试用例来复现并证明这个 bug 的存在。

### 评论
这是一个至关重要的步骤，它将填补我们测试套件中的一个重大盲点。通过创建一个预期会失败的测试，我们不仅能精确地验证我们对问题根源的诊断，还能为后续的修复工作提供一个明确的、可衡量的“红灯”目标。这个测试将成为未来哈希算法健壮性的“守门员”。

### 目标
1.  在 `tests/engine/graph/test_hashing.py` 文件中添加一个新的测试函数 `test_hashing_distinguishes_nested_lazy_results`。
2.  该测试将构造两个结构相似但依赖不同的 `LazyResult`（例如 `task_a(task_b())` 和 `task_a(task_c())`）。
3.  断言这两个 `LazyResult` 产生的结构哈希是**不相等**的。
4.  根据我们当前的 `ShallowHasher` 实现，此断言**必定会失败**，从而成功地将测试套件置于“红色”状态。

### 基本原理
当前的 `ShallowHasher._visit_arg` 方法在遇到任何 `LazyResult` 时，都会简单地记录一个通用的 `"LAZY"` 占位符。这意味着它完全忽略了被嵌套的 `LazyResult` 本身的结构。

例如，对于 `task_a(task_b())`，哈希器看到的结构是 `Task(task_a), Args: [LAZY]`。对于 `task_a(task_c())`，它看到的结构**也是** `Task(task_a), Args: [LAZY]`。因此，它们产生了相同的哈希值，这是错误的。

新的测试将直接断言 `hash(task_a(task_b())) != hash(task_a(task_c()))`，从而暴露这一缺陷。

### 标签
#intent/tooling #flow/ready #priority/critical
#comp/graph #comp/tests #concept/state
#ai/instruct
#task/domain/testing #task/object/hashing-bug #task/action/reproduction
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Add a Failing Test Case for Hash Collision

我们将在 `test_hashing.py` 的末尾添加新的测试用例，用于捕获嵌套依赖的哈希冲突问题。

~~~~~act
patch_file
tests/engine/graph/test_hashing.py
~~~~~
~~~~~python
    h1, _ = StructuralHasher().hash(t1)
    h2, _ = StructuralHasher().hash(t2)
    h3, _ = StructuralHasher().hash(t3)

    assert h1 == h2
    assert h1 == h3
~~~~~
~~~~~python
    h1, _ = StructuralHasher().hash(t1)
    h2, _ = StructuralHasher().hash(t2)
    h3, _ = StructuralHasher().hash(t3)

    assert h1 == h2
    assert h1 == h3


def test_hashing_distinguishes_nested_lazy_results():
    """
    This is the critical test to expose the bug.
    The structure of task_a(task_b()) and task_a(task_c()) should be different.
    The current hasher will fail this test because it replaces both task_b()
    and task_c() with a generic "LAZY" placeholder.
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

    # But the current ShallowHasher will produce the same hash for both
    hasher = ShallowHasher()
    hash1 = hasher.hash(target1)
    hash2 = hasher.hash(target2)

    assert hash1 != hash2, "Hasher must distinguish between different nested LazyResult dependencies"
~~~~~

### 下一步建议
我们已经成功地为 bug 创建了一个“陷阱”。下一步是运行测试，亲眼看到这个新测试失败，从而正式进入 TDD 的“红色”阶段。

如果你同意，我将生成一个运行 `pytest tests/engine/graph/test_hashing.py` 的指令。
