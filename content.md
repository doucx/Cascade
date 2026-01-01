这是 **Phase 4.5** 的第二步。我们将遵循 TDD 流程：首先定义 Spec 并创建测试用例，使系统进入 **RED** 状态。

## [WIP] feat(spec): 定义 `EnvironmentDef` 并添加 Builder 资源管理测试

### 用户需求
1.  **定义 `EnvironmentDef`**: 在 Spec 层形式化“环境”的概念，使其包含资源定义（`ResourceDef`），从而剥离 Compiler 凭空创造资源的能力。
2.  **创建测试**: 编写针对 `Builder` 的新测试，验证其能够接受 `EnvironmentDef`，根据环境创建资源节点，并正确处理资源缺失的情况（抛出异常）。

### 评论
此计划引入了 `EnvironmentDef`，这是物理场中的“边界条件”。这标志着我们从“按需分配”的乌托邦模型转向了“资源受限”的现实物理模型。

由于这是一个 TDD 的 **RED** 阶段，新创建的测试 `test_builder_environment.py` 将会失败，因为 `Builder.build` 方法尚未更新以接受 `environment` 参数。这是预期的行为。

### 目标
1.  创建 `cascade.spec.environment` 模块。
2.  创建 `tests/unit/backend/test_builder_environment.py`，定义预期的 Builder 行为。

### 基本原理
我们必须先定义数据结构（Spec），然后定义行为契约（Test），最后才实现逻辑。
*   `EnvironmentDef` 是一个纯数据类，定义了物理场中存在的客观资源。
*   新的测试用例将强制 `Builder` 实现逻辑：仅当资源在环境中定义时才创建物理节点，否则报错。

### 标签
#intent/architect #flow/draft #priority/high #comp/spec #comp/compiler #concept/resources #scope/core #ai/instruct #task/domain/refactoring #task/object/environment #task/action/define #task/state/continue

---

### Script

#### Acts 1: 定义 `EnvironmentDef` Spec
创建新的 Spec 文件，定义 `ResourceDef` 和 `EnvironmentDef`。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/environment.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class ResourceDef:
    name: str
    capacity: int = 1
    """The total available units of this resource in the environment."""


@dataclass(frozen=True)
class EnvironmentDef:
    resources: List[ResourceDef] = field(default_factory=list)
    """The set of all resources objectively available in this physical field."""
~~~~~

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/environment.stitcher.yaml
~~~~~
~~~~~yaml
"EnvironmentDef": |-
  Defines the boundary conditions and objective reality of the physical field.
  It lists all available resources and their capacities.
  The Compiler uses this to instantiate D_res nodes.
"ResourceDef": |-
  Defines a single resource type available in the environment.
~~~~~

#### Acts 2: 导出新 Spec
更新 `__init__.py` 以暴露新类。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~
~~~~~python.old
from .triad import BleachNode, WorkerNode, StainNode, ObservabilityNode
from .topology import Channel, BipartiteGraph
from .resources import ResourceSlot

__all__ = [
    "Fingerprint",
    "InvalidFingerprintKeyError",
~~~~~
~~~~~python.new
from .triad import BleachNode, WorkerNode, StainNode, ObservabilityNode
from .topology import Channel, BipartiteGraph
from .resources import ResourceSlot
from .environment import EnvironmentDef, ResourceDef

__all__ = [
    "Fingerprint",
    "InvalidFingerprintKeyError",
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~
~~~~~python.old
    "Channel",
    "BipartiteGraph",
    "ResourceSlot",
]
~~~~~
~~~~~python.new
    "Channel",
    "BipartiteGraph",
    "ResourceSlot",
    "EnvironmentDef",
    "ResourceDef",
]
~~~~~

#### Acts 3: 创建 Builder 环境测试 (RED)
编写测试用例，预期 `Builder.build` 将接受 `environment` 参数，并据此创建资源。

~~~~~act
write_file
packages/cascade-compiler/tests/unit/backend/test_builder_environment.py
~~~~~
~~~~~python
import pytest
from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef, ArgumentDef
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.environment import EnvironmentDef, ResourceDef
from cascade.compiler.backend.builder import Builder


@pytest.fixture
def simple_graph_ir():
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(name="task_a", args=[], fingerprint=fp)
    
    # Node requesting a 'gpu' resource
    node = NodeIR(
        id="node_a", 
        name="NodeA", 
        task=task_def,
        constraints={"gpu": 1}
    )
    return GraphIR(nodes=[node])


def test_builder_creates_resources_from_env(simple_graph_ir):
    # 1. Define Environment with 'gpu'
    env = EnvironmentDef(resources=[
        ResourceDef(name="gpu", capacity=4),
        ResourceDef(name="cpu", capacity=8) # Unused resource
    ])

    # 2. Build (Expect this to fail currently due to signature mismatch)
    builder = Builder()
    graph = builder.build(simple_graph_ir, environment=env)

    # 3. Assert D_res creation
    # Used resource should exist
    assert "global_res_gpu" in graph.nodes
    gpu_node = graph.nodes["global_res_gpu"]
    assert gpu_node.capacity == 4
    # Initial tokens should match capacity (potential energy)
    assert gpu_node.initial_tokens == 4

    # Unused resource should ALSO exist (Physics is objective)
    assert "global_res_cpu" in graph.nodes
    cpu_node = graph.nodes["global_res_cpu"]
    assert cpu_node.capacity == 8


def test_builder_raises_on_missing_resource(simple_graph_ir):
    # 1. Empty Environment (No GPU)
    env = EnvironmentDef(resources=[])

    builder = Builder()
    
    # 2. Build should fail because Graph requests 'gpu' but Env has none
    with pytest.raises(ValueError, match="Resource 'gpu' required by node 'node_a' is not defined"):
        builder.build(simple_graph_ir, environment=env)
~~~~~

### 下一步建议
当前状态为 **RED**。
`test_builder_environment.py` 将会失败，因为 `Builder.build` 还不接受 `environment` 参数，也不会进行资源校验。

下一步，我们将修改 `Builder` 的实现（**Phase 4.5 Step 2**），使其通过这些测试，并修复因 API 变更而破坏的旧测试。
