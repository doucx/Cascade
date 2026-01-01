好的，进入阶段 5.2.2。我们将为 Reactor 添加 Sink 注册 API 和 EmitterNode 处理逻辑。

## [WIP] feat(vm): Implement EmitterNode logic

### 用户需求
1.  在 `Reactor` 中实现 `register_sink` 方法。
2.  在 `Reactor._fire` 中添加对 `EmitterNode` 的处理逻辑。
3.  确保 `test_result_emission.py` 测试通过。

### 评论
我们将在 `Reactor` 中添加一个 Sink 注册表，并通过修改 `_fire` 方法，将 `EmitterNode` 的激发从“提交给 Executor”转变为“调用 Sink 回调”。这完成了数据从图内部到外部的单向投影。

### 目标
1.  修改 `packages/cascade-vm/src/cascade/vm/reactor/core.py`。
2.  确保所有测试通过。

### 基本原理
-   `Reactor.__init__` 将初始化一个 `_sinks` 字典。
-   `register_sink` 方法将填充这个字典。
-   `_fire` 方法将增加一个 `isinstance(node, EmitterNode)` 的分支。在此分支中，它会查找对应的 Sink 并调用它，然后立即返回，绕过 Executor。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/io #task/domain/runtime #task/object/emitter #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 在 Reactor 中添加 Sink 注册 API

首先，为 `Reactor` 添加 `_sinks` 属性和 `register_sink` 方法。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
from typing import Deque, Set, List, Dict, Any, Optional
from cascade.spec.physics import DataNode, FuncNode, TerminatorNode
from .events import ReactorEvent, TokenGenerated, ExecutionFinished
from .model import Channel
from cascade.vm.protocols import ResourceManager
~~~~~
~~~~~python.new
from typing import Deque, Set, List, Dict, Any, Optional, Callable
from cascade.spec.physics import DataNode, FuncNode, TerminatorNode, EmitterNode
from .events import ReactorEvent, TokenGenerated, ExecutionFinished
from .model import Channel
from cascade.vm.protocols import ResourceManager
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
class Reactor:
    def __init__(self, executor: Any, resource_manager: Optional[ResourceManager] = None):
        self.executor = executor
        self.resource_manager = resource_manager
        self._event_queue: Deque[ReactorEvent] = deque()
        
        # Topology Indexes
        self._nodes: Set[Any] = set()
~~~~~
~~~~~python.new
class Reactor:
    def __init__(self, executor: Any, resource_manager: Optional[ResourceManager] = None):
        self.executor = executor
        self.resource_manager = resource_manager
        self._event_queue: Deque[ReactorEvent] = deque()
        
        # External world interfaces
        self._sinks: Dict[str, Callable] = {}

        # Topology Indexes
        self._nodes: Set[Any] = set()
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
        self._is_running = False
        self._activity_signal = asyncio.Event()

    def register_node(self, node: Any):
        if node in self._nodes:
            return
        self._nodes.add(node)
~~~~~
~~~~~python.new
        self._is_running = False
        self._activity_signal = asyncio.Event()

    def register_sink(self, sink_id: str, callback: Callable):
        """Registers an external sink (callback) for EmitterNodes."""
        self._sinks[sink_id] = callback

    def register_node(self, node: Any):
        if node in self._nodes:
            return
        self._nodes.add(node)
~~~~~

#### Acts 2: 在 Reactor 中实现 Emitter 逻辑

现在，修改 `_fire` 方法以处理 `EmitterNode`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
    async def _fire(self, node: FuncNode):
        # 1. Atomically consume inputs (Physics: Consume Energy)
        inputs = node.consume_inputs()
        
        # 2. Special Case: Terminator
        if isinstance(node, TerminatorNode):
            self.stop()
            return

        # 3. Submit to Executor
        await self.executor.submit(node, inputs)
~~~~~
~~~~~python.new
    async def _fire(self, node: FuncNode):
        # 1. Atomically consume inputs (Physics: Consume Energy)
        inputs = node.consume_inputs()
        
        # 2. Handle Intrinsic Nodes (not submitted to executor)
        if isinstance(node, TerminatorNode):
            self.stop()
            return
        
        if isinstance(node, EmitterNode):
            sink = self._sinks.get(node.sink_id)
            if sink:
                # Emitter assumes a single input token for simplicity
                # We find the first token from the consumed inputs
                input_token = next(iter(inputs.values()), None)
                if input_token:
                    sink(input_token.payload)
            return

        # 3. Submit to Executor
        await self.executor.submit(node, inputs)
~~~~~

### 下一步建议
我们已经实现了 Reactor 的自我终止和结果发射机制。这是构建一个自治计算图的两个核心原语。

下一步（阶段 5.3），我们将把这些新能力集成到 `VMExecutionStrategy` 中，彻底重构其工作方式，使其从一个“微观管理者”转变为一个“点火器”。
