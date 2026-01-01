好的，我们开始这项重要的架构重构。`Reactor` 作为纯粹物理引擎的理念非常清晰，第一步就是强化底层的物理模型规范。

我将生成一个计划，执行 **阶段 5.A.1：[Spec] 端口化节点与通道极化**。

## [WIP] feat(spec): 实现通道极化以区分数据与信号

### 用户需求
执行“路线图：全对称物理引擎与编译器重构”中的第一步（5.A.1），为物理拓扑模型引入“通道极化”的概念，即在静态定义中区分数据通道（`DATA`）和信号通道（`SIGNAL`）。

### 评论
这是迈向“全对称架构”的奠基性一步。通过在最底层的规范（Spec）中区分数据流和控制流（信号），我们为 `Reactor` 能够以统一的物理规则处理复杂的执行时序（如纯粹的触发而不传递数据）铺平了道路。这极大地增强了拓扑语言的表达能力。

### 目标
1.  在 `cascade.spec.topology` 中定义 `ChannelKind` 枚举（`DATA`, `SIGNAL`）。
2.  更新 `cascade.spec.topology.ChannelDef`（静态定义）以包含 `kind` 字段。
3.  更新 `cascade.vm.reactor.model.Channel`（运行时模型）以包含 `kind` 字段。
4.  更新编译器后端（`cascade.compiler.backend`），使其在生成 `ChannelDef` 时明确指定 `kind`（当前阶段默认为 `DATA`）。

### 基本原理
我们将 `ChannelKind` 的定义放在核心的 `cascade-spec` 包中，因为它是一个基础的拓扑概念。随后，运行时的 `Channel` 对象和编译器的 `ChannelDef` 构造过程都将引用此定义。

路线图（5.A.1）中提到的对 `cascade.spec.physics` 的修改似乎与当前代码库的状况不符，现有 `FuncNode` 已采用基于 `Port` 的连接模型。因此，本次计划将专注于实现“通道极化”这一核心目标，这是推进后续工作的关键。

### 标签
#intent/architect #intent/build #flow/ready #priority/high
#comp/spec #comp/compiler #comp/vm #concept/state
#task/domain/refactor #task/object/physics-model #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 在 `cascade-spec` 中定义通道类型

我们首先在 `topology.py` 中定义 `ChannelKind` 枚举，并将其添加到静态的 `ChannelDef` 数据类中。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class PhysicsFuncNode:
~~~~~
~~~~~python.new
from dataclasses import dataclass, field
from typing import Dict, List
from enum import Enum, auto


class ChannelKind(Enum):
    """
    Defines the physical nature of a channel, distinguishing data transfer from pure signaling.
    """
    DATA = auto()    # The channel carries a payload from the source.
    SIGNAL = auto()  # The channel carries only an activation signal, payload is ignored.


@dataclass(frozen=True)
class PhysicsFuncNode:
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class ChannelDef:
    """
    Defines a static, directed connection from a FuncNode's output port
    to a DataNode's input slot, with routing logic.
    """
    source_node_instance_hash: str
    target_data_slot_hash: str
    port_name: str
    tag_filter: str = "default"
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class ChannelDef:
    """
    Defines a static, directed connection from a FuncNode's output port
    to a DataNode's input slot, with routing logic.
    """
    source_node_instance_hash: str
    target_data_slot_hash: str
    port_name: str
    tag_filter: str = "default"
    kind: ChannelKind = ChannelKind.DATA
~~~~~

#### Acts 2: 更新运行时的 `Channel` 模型

接下来，我们更新 `cascade-vm` 中 `Reactor` 使用的 `Channel` 模型，使其也包含 `kind` 字段。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/model.py
~~~~~
~~~~~python.old
from dataclasses import dataclass
from cascade.spec.physics import FuncNode, DataNode


@dataclass
class Channel:
    """
    Represents a directed connection from a FuncNode output port to a DataNode.
    Includes routing logic (tag filtering).
    """
    source: FuncNode
    target: DataNode
    output_name: str
    tag_filter: str = "default"

    def match(self, tag: str) -> bool:
        """
        Check if the token tag matches this channel's filter.
        """
        return self.tag_filter == tag
~~~~~
~~~~~python.new
from dataclasses import dataclass
from cascade.spec.physics import FuncNode, DataNode
from cascade.spec.topology import ChannelKind


@dataclass
class Channel:
    """
    Represents a directed connection from a FuncNode output port to a DataNode.
    Includes routing logic (tag filtering).
    """
    source: FuncNode
    target: DataNode
    output_name: str
    tag_filter: str = "default"
    kind: ChannelKind = ChannelKind.DATA

    def match(self, tag: str) -> bool:
        """
        Check if the token tag matches this channel's filter.
        """
        return self.tag_filter == tag
~~~~~

#### Acts 3: 更新编译器后端

最后，我们更新编译器后端，使其在构建 `ChannelDef` 时明确指定通道类型。当前阶段，所有通道都默认为 `DATA`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
from cascade.spec.ir.models import GraphIR, EdgeKind
from cascade.spec.topology import (
    BipartiteGraph,
    PhysicsFuncNode,
    PhysicsDataNode,
    ChannelDef,
)
~~~~~
~~~~~python.new
from cascade.spec.ir.models import GraphIR, EdgeKind
from cascade.spec.topology import (
    BipartiteGraph,
    PhysicsFuncNode,
    PhysicsDataNode,
    ChannelDef,
    ChannelKind,
)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
        # 3. Create Output Channel (Func -> Data)
        channel = ChannelDef(
            source_node_instance_hash=func_hash,
            target_data_slot_hash=data_slot_hash,
            port_name="result",
            tag_filter="default" 
        )
        self._channels.append(channel)
~~~~~
~~~~~python.new
        # 3. Create Output Channel (Func -> Data)
        channel = ChannelDef(
            source_node_instance_hash=func_hash,
            target_data_slot_hash=data_slot_hash,
            port_name="result",
            tag_filter="default",
            kind=ChannelKind.DATA
        )
        self._channels.append(channel)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
            channel = ChannelDef(
                source_node_instance_hash=source_func_hash,
                target_data_slot_hash=target_data_hash,
                port_name="result",
                tag_filter=tag
            )
            self._channels.append(channel)
~~~~~
~~~~~python.new
            channel = ChannelDef(
                source_node_instance_hash=source_func_hash,
                target_data_slot_hash=target_data_hash,
                port_name="result",
                tag_filter=tag,
                kind=ChannelKind.DATA # TCO Jumps carry data; pure signals are a future feature
            )
            self._channels.append(channel)
~~~~~

### 下一步建议
我们已经成功地在静态规范中引入了通道极化。下一步是让 `Reactor` 能够理解并利用这个新信息。

我建议我们继续执行路线图的 **阶段 5.A.2：[VM] Reactor 适配通道极化**。这将涉及修改 `Reactor` 的路由逻辑，使其在遇到 `SIGNAL` 类型的通道时，只传递激活信号而不传递数据载荷。
