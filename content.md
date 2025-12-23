好的，收到了错误报告。

这是预料之中的连锁反应。我们在上一步的重构中废弃了 `SlotRef` 机制，但未能清理所有引用到它的文件，导致了 `ImportError`。

我将生成一个计划来彻底清除 `SlotRef` 和 `Constant` 的所有残留痕跡，并修复因此损坏的序列化逻辑及其测试。

## [WIP] fix(core): 清理 SlotRef 残留并修复序列化以完成节点模型重构

### 错误分析
-   **现象**: `pytest` 启动时因 `ImportError: cannot import name 'SlotRef'` 而崩溃。
-   **根因**: 上一步重构删除了 `SlotRef` 的定义，但 `build.py`, `serialize.py` 及相关测试文件中仍然存在对它的导入和使用。
-   **影响**: 整个测试套件无法运行，重构处于未完成状态。

### 用户需求
修复 `ImportError`，并更新所有相关代码（特别是序列化模块）以适应新的、自包含的 `Node` 模型，确保系统恢复到可测试、可运行的状态。

### 评论
这是一个典型的重构后清理任务。通过移除所有对 `SlotRef` 和 `Constant` 的引用，我们将彻底完成向自包含 `Node` 模型的转变，使序列化逻辑更简单、更直接。

### 目标
1.  从 `build.py` 中移除悬空的 `SlotRef` 导入。
2.  重构 `serialize.py`，使其直接处理 `Node.input_bindings` 中的字面量值，不再进行 `SlotRef`/`Constant` 的转换。
3.  从 `binding.py` 中彻底移除 `Constant` 类，因为它也已废弃。
4.  修复 `test_serialize.py` 和 `test_build.py` 中的断言，使其验证 `input_bindings` 中的实际值而非类型。

### 基本原理
完成上一步未竟的清理工作。通过确保代码库中不再有任何对 `SlotRef` 或 `Constant` 的引用，我们可以保证 `Node` 模型的一致性和自包含性，从而解决 `ImportError` 并使依赖此模型的其他模块（如序列化）恢复正常。

### 标签
#intent/fix #flow/ready #priority/critical #comp/core #comp/graph #scope/core #ai/instruct #task/domain/architecture #task/object/node-model #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 清理 `build.py` 中的导入

首先解决最直接的 `ImportError` 来源。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
from cascade.spec.task import Task
from cascade.spec.binding import SlotRef
from cascade.spec.resource import Inject

from .registry import NodeRegistry
~~~~~
~~~~~python
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
from cascade.spec.task import Task
from cascade.spec.resource import Inject

from .registry import NodeRegistry
~~~~~

#### Acts 2: 彻底简化 `binding.py`

`Constant` 也已不再使用，将其一并移除。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/binding.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Union, Any

@dataclass(frozen=True)
class Constant:
    """
    Represents a compile-time constant value that is embedded directly in the graph.
    This should be used sparingly, primarily for structural configuration that
    affects the topology itself.
    """
    value: Any

    def __repr__(self):
        return f"Const({self.value!r})"

# A Binding is typically a raw value (Any) or a wrapped Constant.
Binding = Any
~~~~~
~~~~~python
from typing import Any

# A Binding is a raw literal value directly stored in the Node.
Binding = Any
~~~~~

#### Acts 3: 重构序列化逻辑 `serialize.py`

移除所有 `SlotRef` 和 `Constant` 的处理逻辑，直接序列化和反序列化 `input_bindings` 字典。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python
from cascade.spec.lazy_types import RetryPolicy, LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.task import Task
from cascade.spec.binding import SlotRef, Constant


# --- Helpers ---
~~~~~
~~~~~python
from cascade.spec.lazy_types import RetryPolicy, LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.task import Task


# --- Helpers ---
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python
def _node_to_dict(node: Node) -> Dict[str, Any]:
    data = {
        "id": node.id,
        "name": node.name,
        "node_type": node.node_type,
        # Serializing bindings instead of literal_inputs
        "input_bindings": _serialize_bindings(node.input_bindings),
    }

    if node.callable_obj:
~~~~~
~~~~~python
def _node_to_dict(node: Node) -> Dict[str, Any]:
    data = {
        "id": node.id,
        "name": node.name,
        "node_type": node.node_type,
        # input_bindings now contains JSON-serializable literals directly.
        "input_bindings": node.input_bindings,
    }

    if node.callable_obj:
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python
def _serialize_bindings(bindings: Dict[str, Any]) -> Dict[str, Any]:
    """Serializes the input_bindings dictionary."""
    serialized = {}
    for k, v in bindings.items():
        if isinstance(v, SlotRef):
            serialized[k] = {"__slot_ref": v.index}
        elif isinstance(v, Constant):
            serialized[k] = {"__constant": v.value} # Assuming value is JSON serializable
        else:
            # Fallback
            serialized[k] = v
    return serialized


def _edge_to_dict(edge: Edge, router_map: Dict[int, int]) -> Dict[str, Any]:
    data = {
~~~~~
~~~~~python
def _edge_to_dict(edge: Edge, router_map: Dict[int, int]) -> Dict[str, Any]:
    data = {
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python
    # Recover Constraints
    constraints = None
    if "constraints" in data:
        constraints = ResourceConstraint(requirements=data["constraints"])
    
    # Recover Bindings
    input_bindings = _deserialize_bindings(data.get("input_bindings", {}))

    node = Node(
        id=data["id"],
~~~~~
~~~~~python
    # Recover Constraints
    constraints = None
    if "constraints" in data:
        constraints = ResourceConstraint(requirements=data["constraints"])

    node = Node(
        id=data["id"],
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python
        retry_policy=retry_policy,
        constraints=constraints,
        input_bindings=input_bindings, # Use reconstructed bindings
    )
    return node

def _deserialize_bindings(data: Dict[str, Any]) -> Dict[str, Any]:
    deserialized = {}
    for k, v in data.items():
        if isinstance(v, dict) and "__slot_ref" in v:
            deserialized[k] = SlotRef(index=v["__slot_ref"])
        elif isinstance(v, dict) and "__constant" in v:
            deserialized[k] = Constant(value=v["__constant"])
        else:
            deserialized[k] = v
    return deserialized


# --- Main API ---
~~~~~
~~~~~python
        retry_policy=retry_policy,
        constraints=constraints,
        input_bindings=data.get("input_bindings", {}),
    )
    return node


# --- Main API ---
~~~~~

#### Acts 4: 修复相关测试

我们将更新 `test_build.py` 和 `test_serialize.py`，移除对 `SlotRef` 的所有引用，并使断言与新的、自包含的 `Node` 模型保持一致。

##### 4.1: 修复 `test_build.py`

更新 `test_build_graph_with_param_factory` 和 `test_build_graph_with_env_factory` 的断言，以检查 `input_bindings` 中存储的实际字面量值。

~~~~~act
patch_file
tests/engine/graph/test_build.py
~~~~~
~~~~~python
    # 断言它包含正确的 input_bindings (这是内部任务需要的参数)
    assert "name" in p_node.input_bindings
    # The value is now a SlotRef or Constant, we check its existence
    assert p_node.input_bindings["name"] is not None
~~~~~
~~~~~python
    # 断言它包含正确的 input_bindings (这是内部任务需要的参数)
    assert "name" in p_node.input_bindings
    # The value is now the literal string, not a reference
    assert p_node.input_bindings["name"] == "x"
~~~~~

~~~~~act
patch_file
tests/engine/graph/test_build.py
~~~~~
~~~~~python
    e_node = next(n for n in graph.nodes if n.name == "_get_env_var")
    assert e_node.node_type == "task"
    assert "name" in e_node.input_bindings
    assert e_node.input_bindings["name"] is not None
~~~~~
~~~~~python
    e_node = next(n for n in graph.nodes if n.name == "_get_env_var")
    assert e_node.node_type == "task"
    assert "name" in e_node.input_bindings
    assert e_node.input_bindings["name"] == "HOME"
~~~~~

##### 4.2: 修复 `test_serialize.py`

重写 `test_serialize_params` 函数，移除对 `SlotRef` 的导入和断言，改为验证 `input_bindings` 中正确的字面量值。

~~~~~act
patch_file
tests/engine/graph/test_serialize.py
~~~~~
~~~~~python
def test_serialize_params():
    """Test serialization of Param nodes (now standard tasks)."""
    p = cs.Param("env", default="dev", description="Environment")
    target = simple_task(p)
    graph, _, _ = build_graph(target)

    data = graph_to_dict(graph)
    # In v1.3, Param produces a task named '_get_param_value'
    param_node = next(n for n in data["nodes"] if n["name"] == "_get_param_value")

    from cascade.spec.binding import SlotRef

    assert param_node["node_type"] == "task"
    assert "name" in param_node["input_bindings"]
    assert "__slot_ref" in param_node["input_bindings"]["name"]

    # Note: Serialization currently only saves graph structure, not the Context.
    # So deserialized graph will have the node, but not the ParamSpec metadata
    # (which lives in WorkflowContext). This is expected behavior for v1.3.

    # Round trip
    restored = from_json(to_json(graph))
    p_node = next(n for n in restored.nodes if n.name == "_get_param_value")
    assert "name" in p_node.input_bindings
    assert isinstance(p_node.input_bindings["name"], SlotRef)
~~~~~
~~~~~python
def test_serialize_params():
    """Test serialization of Param nodes (now standard tasks)."""
    p = cs.Param("env", default="dev", description="Environment")
    target = simple_task(p)
    graph, _, _ = build_graph(target)

    data = graph_to_dict(graph)
    # In v1.3, Param produces a task named '_get_param_value'
    param_node = next(n for n in data["nodes"] if n["name"] == "_get_param_value")

    assert param_node["node_type"] == "task"
    assert "name" in param_node["input_bindings"]
    assert param_node["input_bindings"]["name"] == "env"
    assert param_node["input_bindings"]["default"] == "dev"

    # Note: Serialization currently only saves graph structure, not the Context.
    # So deserialized graph will have the node, but not the ParamSpec metadata
    # (which lives in WorkflowContext). This is expected behavior for v1.3.

    # Round trip
    restored = from_json(to_json(graph))
    p_node = next(n for n in restored.nodes if n.name == "_get_param_value")
    assert "name" in p_node.input_bindings
    assert p_node.input_bindings["name"] == "env"
    assert p_node.input_bindings["default"] == "dev"
~~~~~

### 下一步建议
清理工作已经完成。请再次运行完整的测试套件。如果全部通过，我们将可以确认 `Node` 模型重构成功，并可以安全地继续进行性能验证。
### 下一步建议
这次清理应该已经解决了 `ImportError`。现在可以重新运行完整的测试套件 (`pytest`)。如果所有测试都通过，就意味着这次重构成功了。接着，我们可以再次运行 `tco_performance.py` 基准测试，以验证性能缓存是否按预期工作。
