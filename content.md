好的，我们开始实施 "Cascade 3.0 Assembly 与 链接系统" 路线图。

第一阶段是协议层，目标是在 `cascade-spec` 包中定义核心数据结构。这是一个关键的基础步骤，它将确立编译器和运行时之间的核心契约。

我将生成一个计划来创建 `Assembly` 模型并将其导出。

## [WIP] feat: 在 cascade-spec 中定义 Assembly 和 SymbolTable

### 用户需求

根据 "The Linker Protocol" 路线图，实施第一阶段：在 `cascade-spec` 包中定义 `Assembly` 数据类及其相关的 `SymbolTable` 类型。

### 评论

这是路线图中至关重要的一步。通过在 `cascade-spec` 中明确定义 `Assembly` 作为一个纯粹、可序列化的数据结构，我们为编译器（生产者）和运行时（消费者）之间建立了一个清晰、稳定的契约。这彻底解决了当前架构中“身份丢失”和“运行时污染编译产物”的核心问题，是实现分布式执行和持久化调度的基石。

### 目标

1.  创建新文件 `packages/cascade-spec/src/cascade/spec/assembly.py`。
2.  在该文件中定义 `SymbolTable` 类型别名和 `Assembly` 数据类。
3.  更新 `packages/cascade-spec/src/cascade/spec/__init__.py`，导出新定义的 `Assembly` 和 `SymbolTable`，使其成为包的公共 API 的一部分。

### 基本原理

我们遵循“协议先行”的原则。首先在系统的核心规范包 (`cascade-spec`) 中定义数据结构，确保所有后续的实现（编译器、链接器、虚拟机）都有一个共同的、稳定的目标可以遵循。这避免了因实现细节泄漏而导致的耦合，并保证了新架构的概念完整性。

### 标签

#intent/architect #flow/ready #priority/high #comp/interfaces #scope/api #ai/instruct #task/domain/compiler #task/object/linker-protocol #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 定义 Assembly 数据模型

我们首先创建 `assembly.py` 文件，并定义 `SymbolTable` 和 `Assembly`。`Assembly` 将被定义为一个“冷”数据结构，只包含可序列化的数据，为后续的链接和分布式执行奠定基础。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/assembly.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Dict, Any

from .topology import BipartiteGraph

# The SymbolTable defines the mapping between a physical node's ID
# in the graph and the canonical hash of its executable code structure.
SymbolTable = Dict[str, str]


@dataclass(frozen=True)
class Assembly:
    """
    The final, serializable output of the compilation process.
    It contains the full physical topology of the graph and the symbol table
    needed to link it to executable code at runtime.
    """

    # The physical topology, defining nodes (What) and channels (How).
    graph: BipartiteGraph

    # The symbol table, mapping physical node IDs to canonical code structure hashes.
    # Key: Physical Node ID (e.g., "hash123.worker")
    # Value: Canonical Code Structure Hash (e.g., "sha256:abc...")
    symbol_table: SymbolTable = field(default_factory=dict)

    # Metadata about the assembly, such as compiler version, build time, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
~~~~~

#### Acts 2: 导出新的协议定义

现在，我们将新创建的 `Assembly` 和 `SymbolTable` 从 `cascade.spec` 包中导出，使它们可供其他包（如 `cascade-compiler` 和 `cascade-vm`）使用。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~
~~~~~python.old
from .fingerprint import Fingerprint, InvalidFingerprintKeyError
from .physics import Token, PhysicsNode, PhysicsDataNode, PhysicsFuncNode
from .triad import BleachNode, WorkerNode, StainNode, ObservabilityNode
from .topology import Channel, BipartiteGraph
from .resources import ResourceSlot
from .environment import EnvironmentDef, ResourceDef
from .ports import PortRole, PortDef

__all__ = [
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Token",
    "PhysicsNode",
    "PhysicsDataNode",
    "PhysicsFuncNode",
    "BleachNode",
    "WorkerNode",
    "StainNode",
    "ObservabilityNode",
    "Channel",
    "BipartiteGraph",
    "ResourceSlot",
    "EnvironmentDef",
    "ResourceDef",
    "PortRole",
    "PortDef",
]
~~~~~
~~~~~python.new
from .fingerprint import Fingerprint, InvalidFingerprintKeyError
from .physics import Token, PhysicsNode, PhysicsDataNode, PhysicsFuncNode
from .triad import BleachNode, WorkerNode, StainNode, ObservabilityNode
from .topology import Channel, BipartiteGraph
from .resources import ResourceSlot
from .environment import EnvironmentDef, ResourceDef
from .ports import PortRole, PortDef
from .assembly import Assembly, SymbolTable

__all__ = [
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Token",
    "PhysicsNode",
    "PhysicsDataNode",
    "PhysicsFuncNode",
    "BleachNode",
    "WorkerNode",
    "StainNode",
    "ObservabilityNode",
    "Channel",
    "BipartiteGraph",
    "ResourceSlot",
    "EnvironmentDef",
    "ResourceDef",
    "PortRole",
    "PortDef",
    "Assembly",
    "SymbolTable",
]
~~~~~

### 下一步建议

我们已经成功定义了 `Assembly` 协议。根据路线图，下一步是 **Phase 2: 编译器层**。我们将改造 `Builder`，使其不再直接返回 `BipartiteGraph`，而是产出符合新协议的 `Assembly` 对象，并正确填充其中的 `symbol_table`。

准备好后，我们就可以开始实施第二阶段了。
