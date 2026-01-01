好的，我们正式进入 **阶段 5.A.2**。

此阶段的核心任务是让我们的 `Reactor` 物理引擎“学会”新的物理定律。我们将对其进行升级，使其能够理解和执行基于“通道极化”的“双势垒”激活模型。这意味着，一个函数节点必须同时满足其所有的数据依赖和信号依赖，才能被激发。

我将生成一个计划来实现这一目标。

## [WIP] feat(vm): 在 Reactor 中实现双势垒激活逻辑

### 用户需求
执行“路线图：全对称物理引擎与编译器重构”中修正后的阶段 5.A.2。我们需要修改 `cascade-vm`，使 `Reactor` 能够处理极化通道，并根据数据和信号的双重依赖关系来调度任务。

### 评论
这是将我们上一阶段定义的静态规范（`ChannelKind`）转化为动态运行时行为的关键一步。通过实现双势垒逻辑，我们正在将 `Reactor` 从一个简单的调度器，转变为一个真正的、能够模拟不同“物理力”（数据流与控制信号）的物理引擎。这个修改将极大地增强我们计算模型的表达能力和健壮性，是实现全对称架构的核心所在。

### 目标
1.  **增强物理模型 (`cascade-spec`)**: 更新 `Port` 定义，使其包含 `kind` 属性，从而让 `FuncNode` 能够区分其输入是来自数据通道还是信号通道。
2.  **更新 `FuncNode` 激活逻辑**: 重写 `FuncNode.is_ready()` 方法，实现双势垒检查：必须所有 `DATA` 端口和所有 `SIGNAL` 端口的输入源 `DataNode` 都处于“激发态”，该节点才算就绪。
3.  **更新 `Reactor` 内部模型**: 使 `Reactor` 内部的 `Channel` 表现形式与 `spec` 中的 `ChannelDef` 保持一致，也包含 `kind` 属性。
4.  **实现信号感知路由**: 修改 `Reactor` 的路由逻辑，当一个 `Token` 通过 `SIGNAL` 类型的通道进行路由时，其 `payload` 必须被丢弃，只传递一个纯粹的“激活信号”。

### 基本原理
我们将遵循“契约优先”的原则，首先修改 `cascade-spec` 中的 `physics.py`。通过将 `kind` 属性添加到 `Port`，我们为 `FuncNode` 提供了执行双势垒检查所需的所有本地信息，这是一种清晰且解耦的设计。

随后，我们同步更新 `cascade-vm` 中的 `reactor/model.py`，确保其内部数据结构的一致性。

最后，我们修改 `Reactor` 的核心逻辑 (`reactor/core.py`)。在这里，我们将实现信号感知的路由，确保 `SIGNAL` 通道只传递激活，不传递数据。这些修改将共同完成 `Reactor` 的物理模型升级。所有操作都使用 `patch_file`，因为它们都是对现有文件的精确、集中的增强。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #concept/state #scope/core #ai/instruct #task/domain/vm #task/object/reactor-physics #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: [Spec] 增强物理模型以支持极化端口

我们首先修改 `spec`，将通道的 `kind` 属性内化到 `FuncNode` 的 `Port` 中，并重写 `is_ready()` 以实现双势垒检查。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
@dataclass
class Port:
    """
    Connection point on a FuncNode.
    """
    name: str
    source: Optional[DataNode] = None
    target: Optional[DataNode] = None


class FuncNode:
    """
    Stateless transformer. Represents the 'Verb' in the physics model.
    """
    def __init__(
        self, 
        name: str, 
        resource_requirements: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.resource_requirements = resource_requirements or {}
        self.inputs: Dict[str, Port] = {}
        self.outputs: Dict[str, Port] = {}

    def add_input(self, port: Port):
        self.inputs[port.name] = port

    def add_output(self, port: Port):
        self.outputs[port.name] = port

    def is_ready(self) -> bool:
        """
        Potential Barrier Check: Are all connected inputs excited?
        """
        for port in self.inputs.values():
            if port.source and not port.source.is_excited():
                return False
        return True

    def consume_inputs(self) -> Dict[str, Token]:
        """
        Atomically consume tokens from all input sources.
~~~~~
~~~~~python.new
from cascade.spec.topology import ChannelKind


@dataclass
class Port:
    """
    Connection point on a FuncNode, representing a dependency.
    """
    name: str
    kind: ChannelKind = ChannelKind.DATA
    source: Optional[DataNode] = None
    target: Optional[DataNode] = None


class FuncNode:
    """
    Stateless transformer. Represents the 'Verb' in the physics model.
    """
    def __init__(
        self, 
        name: str, 
        resource_requirements: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.resource_requirements = resource_requirements or {}
        self.inputs: Dict[str, Port] = {}
        self.outputs: Dict[str, Port] = {}

    def add_input(self, port: Port):
        self.inputs[port.name] = port

    def add_output(self, port: Port):
        self.outputs[port.name] = port

    def is_ready(self) -> bool:
        """
        Dual-Barrier Potential Check: 
        Are all DATA inputs AND all SIGNAL inputs excited?
        """
        for port in self.inputs.values():
            if port.source and not port.source.is_excited():
                # If any input is not ready, the node is not ready.
                return False
        return True

    def consume_inputs(self) -> Dict[str, Token]:
        """
        Atomically consume tokens from all input sources.
~~~~~

#### Acts 2: [VM] 更新 Reactor 的内部通道模型

接下来，我们让 `Reactor` 内部使用的 `Channel` 对象也拥有 `kind` 属性，与 `spec` 保持一致。

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
    Includes routing logic (tag filtering) and physical kind.
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

#### Acts 3: [VM] 在 Reactor 中实现信号感知路由

最后，我们修改 `Reactor` 的核心路由逻辑，使其在处理 `SIGNAL` 通道时，生成一个不含业务数据的纯激活令牌。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
    async def _handle_execution_finished(self, event: ExecutionFinished):
        # 1. Release Resources
        if self.resource_manager and event.node.resource_requirements:
            await self.resource_manager.release(event.node.resource_requirements)
            # Optimization hint: Releasing resources might wake up pending nodes.
            # In Phase 4.2, we might explicitly trigger a wake-up here.
            # For now, the next step() call will re-evaluate _pending_on_resource.

        # 2. Routing Logic
        channels = self._channels_by_source.get(event.node.name, [])
        
        for output_name, token in event.outputs.items():
            # Find matching channels for this output port
            for channel in channels:
                if channel.output_name == output_name and channel.match(token.tag):
                    # Route: Generate a TokenGenerated event for the target DataNode
                    self.push_event(TokenGenerated(node=channel.target, token=token))
~~~~~
~~~~~python.new
from cascade.spec.physics import Token
from cascade.spec.topology import ChannelKind

    async def _handle_execution_finished(self, event: ExecutionFinished):
        # 1. Release Resources
        if self.resource_manager and event.node.resource_requirements:
            await self.resource_manager.release(event.node.resource_requirements)
            # Optimization hint: Releasing resources might wake up pending nodes.
            # In Phase 4.2, we might explicitly trigger a wake-up here.
            # For now, the next step() call will re-evaluate _pending_on_resource.

        # 2. Routing Logic
        channels = self._channels_by_source.get(event.node.name, [])
        
        for output_name, token in event.outputs.items():
            # Find matching channels for this output port
            for channel in channels:
                if channel.output_name == output_name and channel.match(token.tag):
                    # Route: Generate a TokenGenerated event for the target DataNode
                    if channel.kind == ChannelKind.SIGNAL:
                        # For signal channels, create a new, payload-less token
                        signal_token = Token(payload=None, tag=token.tag, metadata=token.metadata)
                        self.push_event(TokenGenerated(node=channel.target, token=signal_token))
                    else:
                        # For data channels, pass the original token
                        self.push_event(TokenGenerated(node=channel.target, token=token))
~~~~~

### 下一步建议
我们已经成功地将双势垒物理模型和信号感知路由的逻辑实现到了 `Reactor` 中。理论上，我们的物理引擎现在已经具备了处理复杂依赖的能力。

然而，代码的正确性需要通过测试来验证。我建议下一步是创建一个新的测试文件 `tests/vm/reactor/test_polarized_channels.py`，专门用于验证以下场景：
1.  一个 `FuncNode` 只有在它的 `DATA` 输入和 `SIGNAL` 输入都到达后，才会被激发。
2.  通过 `SIGNAL` 通道路由的 `Token`，其 `payload` 会被正确地剥离。
