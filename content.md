## [WIP] feat(core): 支持资源约束的序列化

### 用户需求
更新图序列化模块，使其能够正确处理 `Node` 对象中的 `constraints` 字段，确保资源约束信息在图的序列化和反序列化过程中不会丢失。

### 评论
这是完成资源约束功能的最后一块拼图。支持序列化意味着带有资源需求的计算图可以被持久化存储、传输到远程节点或由外部工具（如可视化器）正确解析。目前我们主要关注基本类型（如数字、字符串）约束值的序列化，这覆盖了绝大多数静态资源声明场景。

### 目标
1.  修改 `src/cascade/graph/serialize.py`，实现 `ResourceConstraint` 的序列化与反序列化逻辑。
2.  在 `tests/graph/test_serialize.py` 中添加测试用例，验证往返序列化的正确性。

### 基本原理
我们将 `ResourceConstraint` 对象简化为其内部的 `requirements` 字典进行存储。在反序列化时，读取该字典并重新构造 `ResourceConstraint` 对象。这保持了 JSON 结构的简洁性。

### 标签
#intent/build #flow/ready #priority/high #comp/core #concept/solver #task/domain/core #task/object/resource-constraint #task/action/serialization #task/state/continue

---

### Script

#### Acts 1: 修改序列化逻辑

更新 `serialize.py` 以处理 `ResourceConstraint`。

~~~~~act
patch_file
src/cascade/graph/serialize.py
~~~~~
~~~~~python
import importlib
from typing import Any, Dict, Optional
from .model import Graph, Node, Edge
from ..spec.common import Param
from ..spec.routing import Router
from ..spec.task import RetryPolicy, Task
~~~~~
~~~~~python
import importlib
from typing import Any, Dict, Optional
from .model import Graph, Node, Edge
from ..spec.common import Param
from ..spec.constraint import ResourceConstraint
from ..spec.routing import Router
from ..spec.task import RetryPolicy, Task
~~~~~

~~~~~act
patch_file
src/cascade/graph/serialize.py
~~~~~
~~~~~python
            "backoff": node.retry_policy.backoff
        }

    return data

def _edge_to_dict(edge: Edge) -> Dict[str, Any]:
~~~~~
~~~~~python
            "backoff": node.retry_policy.backoff
        }

    if node.constraints:
        data["constraints"] = node.constraints.requirements

    return data

def _edge_to_dict(edge: Edge) -> Dict[str, Any]:
~~~~~

~~~~~act
patch_file
src/cascade/graph/serialize.py
~~~~~
~~~~~python
    # Recover Retry Policy
    retry_policy = None
    if "retry_policy" in data:
        rp = data["retry_policy"]
        retry_policy = RetryPolicy(
            max_attempts=rp["max_attempts"],
            delay=rp["delay"],
            backoff=rp["backoff"]
        )

    node = Node(
        id=data["id"],
        name=data["name"],
        node_type=data["node_type"],
        callable_obj=_load_func_from_path(data.get("callable")),
        mapping_factory=_load_func_from_path(data.get("mapping_factory")),
        param_spec=param_spec,
        retry_policy=retry_policy,
        literal_inputs=data.get("literal_inputs", {})
    )
    return node
~~~~~
~~~~~python
    # Recover Retry Policy
    retry_policy = None
    if "retry_policy" in data:
        rp = data["retry_policy"]
        retry_policy = RetryPolicy(
            max_attempts=rp["max_attempts"],
            delay=rp["delay"],
            backoff=rp["backoff"]
        )

    # Recover Constraints
    constraints = None
    if "constraints" in data:
        constraints = ResourceConstraint(requirements=data["constraints"])

    node = Node(
        id=data["id"],
        name=data["name"],
        node_type=data["node_type"],
        callable_obj=_load_func_from_path(data.get("callable")),
        mapping_factory=_load_func_from_path(data.get("mapping_factory")),
        param_spec=param_spec,
        retry_policy=retry_policy,
        constraints=constraints,
        literal_inputs=data.get("literal_inputs", {})
    )
    return node
~~~~~

#### Acts 2: 添加测试用例

在 `test_serialize.py` 中验证带约束的任务的序列化。

~~~~~act
patch_file
tests/graph/test_serialize.py
~~~~~
~~~~~python
    restored = from_json(to_json(graph))
    t_node = next(n for n in restored.nodes if n.name == "simple_task")
    assert t_node.retry_policy.max_attempts == 5
~~~~~
~~~~~python
    restored = from_json(to_json(graph))
    t_node = next(n for n in restored.nodes if n.name == "simple_task")
    assert t_node.retry_policy.max_attempts == 5

def test_serialize_with_constraints():
    """Test serialization of resource constraints."""
    t = simple_task(x=1).with_constraints(gpu_count=1, memory_gb=16)
    graph = build_graph(t)
    
    data = graph_to_dict(graph)
    task_node = next(n for n in data["nodes"] if n["name"] == "simple_task")
    
    assert "constraints" in task_node
    assert task_node["constraints"]["gpu_count"] == 1
    assert task_node["constraints"]["memory_gb"] == 16
    
    # Round trip
    restored = from_json(to_json(graph))
    t_node = next(n for n in restored.nodes if n.name == "simple_task")
    
    assert t_node.constraints is not None
    assert t_node.constraints.requirements["gpu_count"] == 1
    assert t_node.constraints.requirements["memory_gb"] == 16
~~~~~

### 下一步建议
资源感知调度的基础数据结构工作（模型定义、传递、序列化）已全部完成。现在，我们可以在不影响主线功能的情况下，创建一个新的 Git 提交来封装这些变更。

之后，我们可以转向 **任务映射 (.map)** 的增强，或者开始设计 **Advanced Solver** 的接口，但考虑到 `map` 已经在早期实现中存在但可能需要打磨，检查一下 `map` 功能的完整性也是一个好方向。鉴于用户提到“下一个最具挑战性和基础性的任务是实现资源感知调度”，我们实际上已经完成了核心数据的铺垫。
