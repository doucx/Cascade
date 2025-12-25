好的，测试已通过 (GREEN)。现在我将执行您要求的代码清理，然后创建一个最终的 `[COMMIT]` 计划来完成这项工作。

这是一个中间计划，用于移动测试文件并更新其注释。

## [WIP] chore: Relocate purity model test and update comments

### 用户需求
将 `test_purity_model.py` 文件移动到更合适的规范位置 `tests/engine/graph/`，并将其中的中文注释和文档字符串翻译为英文，以符合项目规范。

### 评论
这是一个良好的重构步骤。将测试用例与其所测试的核心逻辑（图构建和哈希）放在一起，可以提高代码库的可维护性和开发者体验 (DX)。

### 目标
1.  将 `tests/core/test_purity_model.py` 移动到 `tests/engine/graph/test_purity_model.py`。
2.  使用英文重写该文件中的所有文档字符串和注释。
3.  删除现已为空的 `tests/core` 目录。

### 基本原理
我们遵循“测试代码应与被测代码相邻”的原则。任务纯度模型的核心实现在 `cascade-graph` 包中，因此其测试也应归于 `tests/engine/graph` 目录下。

### 标签
#intent/refine #intent/tune #flow/ready #priority/low #comp/tests #scope/dx #ai/instruct #task/domain/core #task/object/task-purity #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: Relocate and Update Test File

首先，我们将测试文件移动到新的位置，并用更新后的、包含英文注释的完整内容覆盖它。

~~~~~act
move_file
tests/core/test_purity_model.py
tests/engine/graph/test_purity_model.py
~~~~~

~~~~~act
write_file
tests/engine/graph/test_purity_model.py
~~~~~
~~~~~python
import pytest
from cascade.spec.task import task
from cascade.graph.build import build_graph


def test_impure_tasks_have_unique_identities():
    """
    Verifies that default tasks (Impure) have unique structural identities.

    Scenario:
    The same task is called twice, even with identical arguments.

    Expected Behavior (CP-006):
    The system should treat them as two separate nodes in the graph, each
    with a different structural_id.

    Previous Behavior (Fixed):
    The system would merge them into a single node via hash-consing.
    """

    @task  # Defaults to pure=False
    def random_int():
        return 42

    # Create two instances
    a = random_int()
    b = random_int()

    # Build graphs for each instance
    graph_a, instance_map_a = build_graph(a)
    graph_b, instance_map_b = build_graph(b)

    node_a = instance_map_a[a._uuid]
    node_b = instance_map_b[b._uuid]

    # Assert: For side-effecting tasks, even if the function and arguments are
    # identical, they are distinct entities.
    assert node_a.structural_id != node_b.structural_id, (
        "Impure tasks (default) must have unique structural IDs to avoid incorrect deduplication."
    )


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

#### Acts 2: Remove Old Directory

现在 `tests/core` 目录是空的，我们将其删除。

~~~~~act
run_command
~~~~~
~~~~~
rm -r tests/core
~~~~~

### 下一步建议
在您执行此计划后，代码库将处于一个干净的状态。请指示我生成最终的 `[COMMIT]` 计划以完成此功能的开发。
