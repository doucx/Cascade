您的观察非常敏锐，这是一个极好的问题。

是的，我们**绝对需要**为这种情况创建一个测试。

您指出的场景测试了一个比我们现有测试更微妙、但同样关键的行为：**不纯性的向上传播 (Impurity Propagation)**。

我们当前的测试只验证了原子行为：
1.  `impure()` vs `impure()` -> **不同**
2.  `pure()` vs `pure()` -> **相同**

您提出的场景 `pure(impure())` vs `pure(impure())` 测试了一个**组合行为**：一个纯函数节点的哈希是否能正确地、可传递地反映其依赖项的不纯性。如果这个逻辑被破坏（例如，哈希器在计算父节点哈希时忘记了包含子节点的哈希），那么即使我们的原子测试全部通过，系统仍然会产生错误的去重。

因此，添加这个测试将使我们的测试套件更加健壮，并确保纯度模型的逻辑是端到端完整的。

我将生成一个计划来添加这个新的测试用例。

## [WIP] test(graph): Add test for impurity propagation

### 用户需求
添加一个新的测试用例，以验证来自上游任务的“不纯性”能够正确地向上传播，即使下游任务被声明为“纯函数”。

### 评论
这是一个关键的集成测试场景。它确保了 `HashingService` 在计算一个节点的结构哈希时，会正确地将其依赖项的唯一哈希值考虑在内。这可以防止一个 Pure 任务错误地去重两个接收了不同 Impure 结果的实例。

### 目标
1.  在 `tests/engine/graph/test_purity_model.py` 文件中增加一个新的测试函数 `test_impurity_propagates_through_pure_functions`。
2.  该测试将断言，两个结构相同但依赖于不同 Impure 任务实例的 Pure 任务，必须生成不同的 `structural_id`。

### 基本原理
通过明确测试这种组合场景，我们为纯度模型的传递性提供了一个强大的回归保障。这确保了无论计算图多么复杂，只要其依赖链的任何部分是不纯的，最终结果的唯一性就能得到保证。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/tests #concept/state #scope/core #ai/instruct #task/domain/core #task/object/task-purity #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: Add Impurity Propagation Test

我们将在 `test_purity_model.py` 文件中追加新的测试函数。

~~~~~act
patch_file
tests/engine/graph/test_purity_model.py
~~~~~
~~~~~python
def test_pure_tasks_are_deduplicated():
    """
    Verifies that pure tasks are correctly deduplicated.
    """

    @task(pure=True)
    def add(x, y):
        return x + y

    a = add(1, 2)
    b = add(1, 2)

    graph_a, instance_map_a = build_graph(a)
    graph_b, instance_map_b = build_graph(b)

    node_a = instance_map_a[a._uuid]
    node_b = instance_map_b[b._uuid]

    # Assert: Pure tasks should be content-addressable.
    assert node_a.structural_id == node_b.structural_id, (
        "Pure tasks must be deduplicated based on their content (function + args)."
    )
~~~~~
~~~~~python
def test_pure_tasks_are_deduplicated():
    """
    Verifies that pure tasks are correctly deduplicated.
    """

    @task(pure=True)
    def add(x, y):
        return x + y

    a = add(1, 2)
    b = add(1, 2)

    graph_a, instance_map_a = build_graph(a)
    graph_b, instance_map_b = build_graph(b)

    node_a = instance_map_a[a._uuid]
    node_b = instance_map_b[b._uuid]

    # Assert: Pure tasks should be content-addressable.
    assert node_a.structural_id == node_b.structural_id, (
        "Pure tasks must be deduplicated based on their content (function + args)."
    )


def test_impurity_propagates_through_pure_functions():
    """
    Verifies that impurity from an upstream task propagates to downstream
    pure tasks, ensuring they also get unique identities.
    """

    @task(pure=False)
    def impure_source():
        return 1

    @task(pure=True)
    def pure_consumer(source):
        return source + 1

    # Create two identical compositions. Because the source is impure,
    # the consuming pure tasks should NOT be deduplicated.
    a = pure_consumer(impure_source())
    b = pure_consumer(impure_source())

    graph_a, instance_map_a = build_graph(a)
    graph_b, instance_map_b = build_graph(b)

    node_a = instance_map_a[a._uuid]
    node_b = instance_map_b[b._uuid]

    # Assert: The two `pure_consumer` nodes must be distinct because their
    # `impure_source` dependencies are distinct.
    assert node_a.structural_id != node_b.structural_id, (
        "Impurity must propagate upwards, preventing deduplication of pure tasks "
        "that consume different impure results."
    )
~~~~~

### 下一步建议
在您批准此计划后，我将执行它。您可以再次运行测试以确认所有三个用例都通过。之后，我们可以重新生成最终的 `[COMMIT]` 计划，将这次的测试改进也包含进去。
