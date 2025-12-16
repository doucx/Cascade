简要回答：
我们将修改 `src/cascade/graph/serialize.py`，实现 `EdgeType` 的序列化与反序列化，并确保所有边缘元数据（包括重试策略和约束）在往返过程中保持完整性。

## [WIP] refactor(graph): 增强图序列化以支持 EdgeType 和 Router 元数据

### 用户需求
增强图序列化模块 (`src/cascade/graph/serialize.py`)，使其能够正确处理并持久化 `EdgeType` 枚举和 `Router` 边缘元数据。

### 评论
图序列化是实现分布式执行、工作流持久化和高级调试工具（如外部可视化器）的基础。引入 `EdgeType` 后，我们必须同步更新序列化逻辑，以确保图模型能够无损地进行往返操作，这是下一步平台演进的关键。

### 目标
1.  修改 `serialize.py`，导入并使用 `EdgeType`。
2.  在 `_edge_to_dict` 中将 `EdgeType` 转换为字符串名称。
3.  在 `graph_from_dict` 中将字符串名称转换回 `EdgeType` 枚举。
4.  更新 `tests/graph/test_serialize.py`，增加对 `EdgeType` 往返测试的覆盖。
5.  在 `serialize.py` 中添加关于 `Router` 重建的技术债务注释，明确当前阶段的限制。

### 基本原理
由于 `EdgeType` 是一个 Python 枚举，它无法被原生 JSON 序列化。我们将采用标准的序列化策略：将枚举值存储为它们的名称字符串，并在反序列化时通过名称查找重新构造枚举对象。

### 标签
#intent/refine #flow/ready #priority/high #comp/graph #comp/tests #concept/serialization #scope/core #scope/dx #ai/delegate #task/domain/graph #task/object/serialization #task/action/refinement #task/state/continue

---

### Script

#### Acts 1: 更新 Graph 序列化逻辑 (`serialize.py`)

修改 `src/cascade/graph/serialize.py` 以支持 `EdgeType` 的序列化和反序列化，并添加必要的 `EdgeType` 导入。

~~~~~act
patch_file
src/cascade/graph/serialize.py
~~~~~
~~~~~python
import json
import importlib
from typing import Any, Dict, Optional
from .model import Graph, Node, Edge
from ..spec.common import Param
from ..spec.constraint import ResourceConstraint
from ..spec.lazy_types import RetryPolicy  # NEW
from ..spec.task import Task
~~~~~
~~~~~python
import json
import importlib
from typing import Any, Dict, Optional
from .model import Graph, Node, Edge, EdgeType
from ..spec.common import Param
from ..spec.constraint import ResourceConstraint
from ..spec.lazy_types import RetryPolicy
from ..spec.task import Task
~~~~~

~~~~~act
patch_file
src/cascade/graph/serialize.py
~~~~~
~~~~~python
def _edge_to_dict(edge: Edge) -> Dict[str, Any]:
    data = {
        "source_id": edge.source.id,
        "target_id": edge.target.id,
        "arg_name": edge.arg_name,
    }
    if edge.router:
        # Router is complex, but for the edge we just need to mark it or verify consistency
        # In current model, router object is attached to edge.
        # We need to serialize enough info to reconstruct the Router logic if needed,
        # but the Router spec object itself is mostly build-time.
        # Runtime logic depends on the edge structure.
        # For now, we simply flag it.
        data["router_present"] = True
    return data
~~~~~
~~~~~python
def _edge_to_dict(edge: Edge) -> Dict[str, Any]:
    data = {
        "source_id": edge.source.id,
        "target_id": edge.target.id,
        "arg_name": edge.arg_name,
        "edge_type": edge.edge_type.name,
    }
    if edge.router:
        # We flag the presence of a Router, but the object itself is not serialized 
        # (Router reconstruction requires full graph context not available here).
        # This is a known limitation for MVP serialization.
        data["router_present"] = True
    return data
~~~~~

~~~~~act
patch_file
src/cascade/graph/serialize.py
~~~~~
~~~~~python
    # 2. Reconstruct Edges
    for ed in edges_data:
        source = node_map.get(ed["source_id"])
        target = node_map.get(ed["target_id"])
        if source and target:
            # Note: We are losing the original 'Router' spec object here.
            # If runtime requires the Router object on the edge, we might need to rethink.
            # Checking `LocalExecutor`: it checks `edge.router`.
            # If `edge.router` is None, dynamic routing fails.
            # So we MUST reconstruct a Router object if `router_present` is True.

            # However, the `Router` object in spec needs `routes` dict and `selector` LazyResult.
            # Reconstructing that from a flat edge list is hard.
            # BUT, look at `LocalExecutor`: it uses `edge.router.routes` to find the implementation node.
            # This implies the graph structure already contains the routes.
            # The Executor uses `edge.router` mainly as a marker and a lookup table for `routes`.

            # For this MVP, we will revive the Edge.
            # TODO: Fully restoring Router object requires matching the "implicit_dependency" edges
            # back to the routes dict. This is complex.
            # For basic serialization (visualization/inspection), omitting Router object is fine.
            # For Distributed Execution, we will need full reconstruction.
            # Let's leave a TODO for Router reconstruction and support basic edges.

            edge = Edge(source=source, target=target, arg_name=ed["arg_name"])
            # If we marked it as having a router, we might want to attach a placeholder or
            # address this in a future PR for distributed routing.
            graph.add_edge(edge)
        else:
            raise ValueError(f"Edge references unknown node: {ed}")
~~~~~
~~~~~python
    # 2. Reconstruct Edges
    for ed in edges_data:
        source = node_map.get(ed["source_id"])
        target = node_map.get(ed["target_id"])
        if source and target:
            edge_type_name = ed.get("edge_type", "DATA")
            edge_type = EdgeType[edge_type_name]
            
            # Note: We are losing the original 'Router' spec object here.
            # Reconstructing the complex Router object is a technical debt item 
            # required for distributed execution, but not for visualization/inspection.
            
            # The Edge object itself is restored.
            edge = Edge(
                source=source, 
                target=target, 
                arg_name=ed["arg_name"], 
                edge_type=edge_type
            )
            
            # Current limitation: We cannot restore the `edge.router` object, 
            # making the deserialized graph unsuitable for execution that relies 
            # on dynamic routing (i.e., LocalExecutor will fail to resolve inputs 
            # for tasks downstream of a Router).
            if ed.get("router_present"):
                # We retain the flag but cannot set the object.
                # TODO: Implement full Router object reconstruction in a future PR.
                pass 

            graph.add_edge(edge)
        else:
            raise ValueError(f"Edge references unknown node: {ed}")
~~~~~

#### Acts 2: 增强序列化测试用例 (`test_serialize.py`)

在 `tests/graph/test_serialize.py` 中添加测试，确保所有新的 `EdgeType` 都能正确地进行序列化往返。

~~~~~act
patch_file
tests/graph/test_serialize.py
~~~~~
~~~~~python
    p_node = next(n for n in restored.nodes if n.node_type == "param")
    assert p_node.param_spec.name == "env"


def test_serialize_with_retry():
    """Test serialization of retry policy."""
    t = simple_task(x=1).with_retry(max_attempts=5, delay=1.0)
    graph = build_graph(t)

    data = graph_to_dict(graph)
    task_node = next(n for n in data["nodes"] if n["name"] == "simple_task")

    assert task_node["retry_policy"]["max_attempts"] == 5
    assert task_node["retry_policy"]["delay"] == 1.0

    # Round trip
    restored = from_json(to_json(graph))
    t_node = next(n for n in restored.nodes if n.name == "simple_task")
    assert t_node.retry_policy.max_attempts == 5
~~~~~
~~~~~python
    p_node = next(n for n in restored.nodes if n.node_type == "param")
    assert p_node.param_spec.name == "env"


def test_serialize_with_retry():
    """Test serialization of retry policy including backoff."""
    t = simple_task(x=1).with_retry(max_attempts=5, delay=1.0, backoff=2.0)
    graph = build_graph(t)

    data = graph_to_dict(graph)
    task_node = next(n for n in data["nodes"] if n["name"] == "simple_task")

    assert task_node["retry_policy"]["max_attempts"] == 5
    assert task_node["retry_policy"]["delay"] == 1.0
    assert task_node["retry_policy"]["backoff"] == 2.0

    # Round trip
    restored = from_json(to_json(graph))
    t_node = next(n for n in restored.nodes if n.name == "simple_task")
    assert t_node.retry_policy.max_attempts == 5
    assert t_node.retry_policy.backoff == 2.0


def test_serialize_edge_types():
    """Test serialization and deserialization of various EdgeType instances."""
    
    @cs.task
    def t_condition(): return True
    
    @cs.task
    def t_dynamic_constraint(val): return val
    
    @cs.task
    def t_target(x): return x

    # 1. Condition edge
    target_condition = t_target(t_dynamic_constraint(1)).run_if(t_condition())
    
    # 2. Constraint edge (dynamic)
    target = target_condition.with_constraints(cpu=t_dynamic_constraint(1))
    
    graph = build_graph(target)
    json_str = to_json(graph)
    restored_graph = from_json(json_str)

    # We only need to check the edges pointing to t_target (the target node of the chains)
    target_node = next(n for n in restored_graph.nodes if n.name == "t_target")
    
    data_edges = [e for e in restored_graph.edges if e.target == target_node and e.edge_type == cs.graph.model.EdgeType.DATA]
    condition_edges = [e for e in restored_graph.edges if e.target == target_node and e.edge_type == cs.graph.model.EdgeType.CONDITION]
    constraint_edges = [e for e in restored_graph.edges if e.target == target_node and e.edge_type == cs.graph.model.EdgeType.CONSTRAINT]

    assert len(data_edges) == 1
    assert len(condition_edges) == 1
    assert len(constraint_edges) == 1
    
    # Verify the restored types are correct
    assert condition_edges[0].edge_type is cs.graph.model.EdgeType.CONDITION
    assert constraint_edges[0].edge_type is cs.graph.model.EdgeType.CONSTRAINT
~~~~~
