简要回答：
好的，我将实现 `Reactor` 及其核心组件。这将包括事件定义、通道模型以及反应堆的主循环逻辑，使其能够通过之前定义的测试用例。

## [WIP] feat: Implement Reactor Core

### 用户需求
实现 `cascade-vm` 包中的动力层核心，以支持基于势能和事件驱动的执行模型。

### 评论
这是新架构的心脏。
1.  `events.py`: 定义系统内的物理事件 (`TokenGenerated`, `ExecutionFinished`)。
2.  `model.py`: 定义 `Channel`，它是连接 `FuncNode` 和 `DataNode` 的桥梁，承载路由逻辑。
3.  `core.py`: 实现 `Reactor` 类。它维护事件队列，处理事件以更新节点势能，管理“脏节点”集合，并驱动 `Executor` 执行满足激发条件的节点。

### 目标
1.  创建 `packages/cascade-vm/src/cascade/vm/reactor` 目录。
2.  实现 `events.py`, `model.py`, `core.py`。
3.  导出模块接口。

### 基本原理
`Reactor.step()` 将采用“处理所有积压事件 -> 激发就绪节点”的循环模式。
- **事件处理**: `TokenGenerated` 会更新 DataNode 并标记下游 FuncNode 为“脏”；`ExecutionFinished` 会通过 `Channel` 路由产生新的 `TokenGenerated` 事件（或直接更新状态）。为了满足测试中单次 `step()` 完成传播的要求，事件队列将在 step 内被排空（或处理多轮）。
- **路由**: `Channel` 实现简单的 Tag 匹配过滤。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/reactor #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 Reactor 包目录

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-vm/src/cascade/vm/reactor
~~~~~

#### Acts 2: 实现事件定义 (`events.py`)

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/reactor/events.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Dict, Any
from cascade.spec.physics import DataNode, FuncNode, Token


@dataclass
class ReactorEvent:
    """Base class for all reactor events."""
    pass


@dataclass
class TokenGenerated(ReactorEvent):
    """
    Event emitted when a Token is destined for a DataNode.
    Handler should put the token into the node.
    """
    node: DataNode
    token: Token


@dataclass
class ExecutionFinished(ReactorEvent):
    """
    Event emitted when an Executor finishes a job.
    Handler should route outputs to downstream DataNodes.
    """
    node: FuncNode
    outputs: Dict[str, Token] = field(default_factory=dict)
    error: Any = None
~~~~~

#### Acts 3: 实现模型定义 (`model.py`)

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/reactor/model.py
~~~~~
~~~~~python
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

#### Acts 4: 实现核心反应堆 (`core.py`)

这里实现了物理引擎的主循环。注意 `step()` 方法的设计，它会循环处理事件直到队列为空，从而确保事件传播（ExecutionFinished -> TokenGenerated -> DataNode Update）在一个 step 内完成，满足测试预期。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python
import asyncio
from collections import deque, defaultdict
from typing import Deque, Set, List, Dict, Any

from cascade.spec.physics import DataNode, FuncNode
from .events import ReactorEvent, TokenGenerated, ExecutionFinished
from .model import Channel


class Reactor:
    def __init__(self, executor: Any):
        self.executor = executor
        self._event_queue: Deque[ReactorEvent] = deque()
        
        # Topology Indexes
        self._nodes: Set[Any] = set() # Track all known nodes
        self._channels_by_source: Dict[str, List[Channel]] = defaultdict(list)
        
        # Optimization: Map DataNode -> List[FuncNode] (Reverse dependency)
        # Used to quickly find which FuncNodes to check when a DataNode updates.
        self._downstream_map: Dict[str, List[FuncNode]] = defaultdict(list)
        
        # Dirty set for potential evaluation
        self._dirty_func_nodes: Set[FuncNode] = set()

    def register_node(self, node: Any):
        if node in self._nodes:
            return
        self._nodes.add(node)
        
        # Build reverse index for FuncNodes
        if isinstance(node, FuncNode):
            for port in node.inputs.values():
                if port.source:
                    self._downstream_map[port.source.name].append(node)

    def register_channel(self, channel: Channel):
        self._channels_by_source[channel.source.name].append(channel)
        # Ensure nodes are registered
        self.register_node(channel.source)
        self.register_node(channel.target)

    def push_event(self, event: ReactorEvent):
        self._event_queue.append(event)

    async def step(self):
        """
        Advance the reactor by one "tick".
        A tick consists of:
        1. Processing all pending events (State Updates & Routing).
           - This includes cascading events generated during processing.
        2. Evaluating potentials of affected (dirty) nodes.
        3. Firing ready nodes.
        """
        # 1. Process Event Loop
        # We drain the queue completely to handle propagation chains within one step.
        while self._event_queue:
            event = self._event_queue.popleft()
            self._handle_event(event)

        # 2. Fire Ready Nodes
        # Iterate over a snapshot of dirty nodes
        ready_nodes = []
        for node in list(self._dirty_func_nodes):
            if node.is_ready():
                ready_nodes.append(node)
        
        self._dirty_func_nodes.clear()

        for node in ready_nodes:
            self._fire(node)

    def _handle_event(self, event: ReactorEvent):
        if isinstance(event, TokenGenerated):
            self._handle_token_generated(event)
        elif isinstance(event, ExecutionFinished):
            self._handle_execution_finished(event)

    def _handle_token_generated(self, event: TokenGenerated):
        # 1. Update State (Physics: Inject Energy)
        event.node.put(event.token)
        
        # 2. Mark downstream FuncNodes as dirty (Potential might have increased)
        downstream = self._downstream_map.get(event.node.name, [])
        for f_node in downstream:
            self._dirty_func_nodes.add(f_node)

    def _handle_execution_finished(self, event: ExecutionFinished):
        # Routing Logic
        channels = self._channels_by_source.get(event.node.name, [])
        
        for output_name, token in event.outputs.items():
            # Find matching channels for this output port
            for channel in channels:
                if channel.output_name == output_name and channel.match(token.tag):
                    # Route: Generate a TokenGenerated event for the target DataNode
                    # This queues the event for processing in the same step loop
                    self.push_event(TokenGenerated(node=channel.target, token=token))

    def _fire(self, node: FuncNode):
        # 1. Atomically consume inputs (Physics: Consume Energy)
        inputs = node.consume_inputs()
        
        # 2. Submit to Executor
        # Note: Executor is responsible for running the code and eventually
        # pushing an ExecutionFinished event back to the reactor.
        # For AsyncMock in tests, this call is synchronous.
        self.executor.submit(node, inputs)
~~~~~

#### Acts 5: 导出模块 (`__init__.py`)

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/reactor/__init__.py
~~~~~
~~~~~python
from .core import Reactor
from .events import ReactorEvent, TokenGenerated, ExecutionFinished
from .model import Channel

__all__ = ["Reactor", "ReactorEvent", "TokenGenerated", "ExecutionFinished", "Channel"]
~~~~~

### 下一步建议
我们已经实现了 Reactor 及其配套组件。
下一步应该是：
1.  运行刚才创建的测试 `packages/cascade-vm/tests/reactor/`，确保它们从 RED 变为 GREEN。
2.  如果不通过，根据错误信息进行微调。
3.  一旦通过，我们就可以进入 **第三阶段：拓扑层构建 (Phase 3: The Compiler Refactor)**，开始重写编译器后端以生成二分图。
