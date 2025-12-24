好的，我们开始执行“第二阶段：修复测试套件”。

根据战略分析，失败的根源在于 `test_flow_manager_pruning_logic` 测试用例本身是同步的，但它调用的 `FlowManager` 和 `InMemoryStateBackend` 方法现在是异步的。我们将通过将此测试转换为异步测试来解决这个问题。

## [WIP] fix(tests): 将 test_flow_manager 迁移至异步以适配 IO 边界

### 错误分析
测试 `test_flow_manager_pruning_logic` 失败，并伴有 `RuntimeWarning`。
*   **原因**: 测试函数是同步的 (`def test_...`)，但它调用的 `state_backend.put_result`, `manager.register_result` 和 `state_backend.get_skip_reason` 都已重构为异步方法 (`async def`)。
*   **后果**:
    1.  `put_result` 和 `register_result` 的协程从未被 `await`，导致其逻辑从未执行，状态后端没有被更新。
    2.  断言 `assert state_backend.get_skip_reason(...)` 正在比较一个未执行的协程对象和一个字符串，这永远不会相等。

### 用户需求
修复 `test_flow_manager.py` 中失败的测试，完成“StateBackend 异步化”重构的第二阶段。

### 评论
这是预料之中的失败，是重构的最后一步。通过修复这个测试，我们不仅能让 CI 恢复绿灯，还能创建一个如何正确测试核心异步组件的范例，巩固了我们的架构原则。

### 目标
1.  将 `test_flow_manager_pruning_logic` 测试用例转换为异步测试。
2.  在所有对异步方法的调用前添加 `await` 关键字。
3.  确保测试断言能够正确验证剪枝逻辑。

### 基本原理
使用 `pytest.mark.asyncio` 装饰器，并将测试函数签名改为 `async def`，允许我们在测试体内使用 `await`。这是使用 `pytest-asyncio` 插件测试异步代码的标准模式，它确保了测试执行环境能够正确地运行和管理协程。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #concept/state #scope/core #ai/instruct #task/domain/core #task/object/state-backend #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `test_flow_manager.py`

我们将重写整个文件，将其中的测试用例转换为异步，并添加 `await` 关键字。

~~~~~act
write_file
tests/engine/runtime/test_flow_manager.py
~~~~~
~~~~~python
from unittest.mock import MagicMock
import pytest

from cascade.graph.model import Node, Edge, EdgeType
from cascade.spec.routing import Router
from cascade.spec.lazy_types import LazyResult
from cascade.runtime.flow import FlowManager
from cascade.adapters.state.in_memory import InMemoryStateBackend


def create_mock_node(name: str) -> Node:
    """Creates a mock Node with structural_id == name."""
    return Node(structural_id=name, name=name, template_id=f"t_{name}")


def create_mock_lazy_result(node_id: str) -> LazyResult:
    """Creates a mock LazyResult whose UUID matches the node ID for mapping."""
    lr = MagicMock(spec=LazyResult)
    lr._uuid = node_id
    return lr


@pytest.mark.asyncio
async def test_flow_manager_pruning_logic():
    """
    Test that FlowManager correctly prunes downstream nodes recursively.

    Graph Topology:
    S (Selector) -> chooses "a" or "b"

    Routes:
    - "a": A
    - "b": B -> B_UP (B depends on B_UP)

    Consumer C depends on Router(S)

    If S chooses "a":
    1. Route "b" (Node B) is not selected.
    2. B should be pruned.
    3. B_UP (only used by B) should be recursively pruned.
    """

    # 1. Setup Nodes
    nodes = [create_mock_node(n) for n in ["S", "A", "B", "B_UP", "C"]]
    n_map = {n.structural_id: n for n in nodes}

    # 2. Setup Router Objects
    lr_s = create_mock_lazy_result("S")
    lr_a = create_mock_lazy_result("A")
    lr_b = create_mock_lazy_result("B")

    router_obj = Router(selector=lr_s, routes={"a": lr_a, "b": lr_b})

    # 3. Setup Edges
    edges = [
        Edge(
            n_map["S"],
            n_map["C"],
            arg_name="x",
            edge_type=EdgeType.DATA,
            router=router_obj,
        ),
        Edge(n_map["B_UP"], n_map["B"], arg_name="dep", edge_type=EdgeType.DATA),
        Edge(
            n_map["A"], n_map["C"], arg_name="_route_a", edge_type=EdgeType.ROUTER_ROUTE
        ),
        Edge(
            n_map["B"], n_map["C"], arg_name="_route_b", edge_type=EdgeType.ROUTER_ROUTE
        ),
    ]

    graph = MagicMock()
    graph.nodes = nodes
    graph.edges = edges

    # Create a mock instance_map for the test
    instance_map = {
        lr_s._uuid: n_map["S"],
        lr_a._uuid: n_map["A"],
        lr_b._uuid: n_map["B"],
    }

    # 4. Initialize Manager & Backend
    manager = FlowManager(graph, target_node_id="C", instance_map=instance_map)
    state_backend = InMemoryStateBackend(run_id="test_run")

    # Initial state check
    assert manager.downstream_demand["B_UP"] == 1
    assert manager.downstream_demand["B"] == 1

    # 5. Simulate S completing and choosing "a"
    await state_backend.put_result("S", "a")
    await manager.register_result("S", "a", state_backend)

    # 6. Verify Pruning
    # Route "b" (Node B) was not selected and should be pruned.
    assert await state_backend.get_skip_reason("B") == "Pruned"
    # Node B_UP, which only B depends on, should be recursively pruned.
    assert await state_backend.get_skip_reason("B_UP") == "Pruned"
~~~~~

### 下一步建议
我们已经完成了对内核和测试套件的修复。现在，整个代码库应该与新的异步 `StateBackend` 契约保持一致。

我建议您现在运行完整的测试套件。如果所有测试都通过，我们可以认为这次针对“架构缺陷 B”的重构已经成功完成。届时，我将为您生成一个 `[COMMIT]` 计划来最终提交这些更改。
