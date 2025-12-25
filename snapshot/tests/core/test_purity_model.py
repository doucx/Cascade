import pytest
from cascade.spec.task import task
from cascade.graph.build import build_graph


def test_impure_tasks_have_unique_identities():
    """
    验证默认任务（Impure）是否具有唯一的结构标识。
    
    场景：
    我们调用同一个任务两次，即使参数相同。
    
    期望（CP-006）：
    系统应将它们视为图中的两个独立节点，具有不同的 structural_id。
    
    当前行为（Fail）：
    系统通过 Hash-Consing 将它们合并为一个节点。
    """
    @task  # 默认 pure=False
    def random_int():
        return 42

    # 创建两个实例
    a = random_int()
    b = random_int()

    # 构建图
    # 注意：我们需要一个虚拟的目标来包含这两个节点，或者分别构建
    # 这里为了简单，我们检查构建后的节点 ID
    graph_a, instance_map_a = build_graph(a)
    graph_b, instance_map_b = build_graph(b)
    
    node_a = instance_map_a[a._uuid]
    node_b = instance_map_b[b._uuid]

    # 断言：对于副作用任务，即使函数和参数完全相同，它们也是不同的实体
    assert node_a.structural_id != node_b.structural_id, (
        "Impure tasks (default) must have unique structural IDs to avoid incorrect deduplication."
    )


def test_pure_tasks_are_deduplicated():
    """
    验证纯函数任务（Pure）是否被正确去重。
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

    # 断言：纯函数任务应基于内容寻址（Content-Addressable）
    assert node_a.structural_id == node_b.structural_id, (
        "Pure tasks must be deduplicated based on their content (function + args)."
    )