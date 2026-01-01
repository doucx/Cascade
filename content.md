好的，我们来让它变绿。

## [WIP] feat(vm): Implement EmitterNode logic in Reactor

### 用户需求
1.  在 `Reactor` 中实现 `register_sink` API。
2.  实现 `EmitterNode` 的激发逻辑，使其能将数据推送到已注册的 Sink。
3.  确保 `test_result_emission.py` 测试通过。

### 评论
我们正在为 Reactor 添加“输出端口”。通过 `register_sink` API 和 `EmitterNode`，Reactor 现在可以将内部计算结果安全地、异步地传递给外部世界，完成了数据流的闭环。

### 目标
1.  修改 `packages/cascade-vm/src/cascade/vm/reactor/core.py` 以添加 Sink 注册和 Emitter 处理逻辑。
2.  确保 `test_result_emission.py` 通过，验证发射机制。

### 基本原理
1.  `Reactor.__init__` 将初始化一个 `_sinks` 字典来存储外部回调。
2.  `register_sink` 方法将填充此字典。
3.  `_fire` 方法将增加一个 `isinstance(node, EmitterNode)` 的分支。当匹配时，它会查找对应的 Sink，并使用从输入端口消耗的令牌的载荷（payload）来调用它。与 `TerminatorNode` 一样，`EmitterNode` 是一个“虚节点”，其逻辑在 Reactor 内部处理，不会被提交给 Executor。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/io #task/domain/runtime #task/object/emitter #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 实现 Reactor 的发射机制

我们将修改 `Reactor` 类，添加 Sink 注册表和处理 `EmitterNode` 的逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
import asyncio
from collections import deque, defaultdict
from typing import Deque, Set, List, Dict, Any, Optional
from cascade.spec.physics import DataNode, FuncNode, TerminatorNode
from .events import ReactorEvent, TokenGenerated, ExecutionFinished
from .model import Channel
from cascade.vm.protocols import ResourceManager
~~~~~
~~~~~python.new
import asyncio
from collections import deque, defaultdict
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
~~~~~
~~~~~python.new
class Reactor:
    def __init__(self, executor: Any, resource_manager: Optional[ResourceManager] = None):
        self.executor = executor
        self.resource_manager = resource_manager
        self._event_queue: Deque[ReactorEvent] = deque()
        self._sinks: Dict[str, Callable] = {}
        
        # Topology Indexes
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
        self._sinks[sink_id] = callback

    def register_node(self, node: Any):
        if node in self._nodes:
            return
        self._nodes.add(node)
~~~~~

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
        
        # 2. Handle special intrinsic nodes
        if isinstance(node, TerminatorNode):
            self.stop()
            return

        if isinstance(node, EmitterNode):
            sink = self._sinks.get(node.sink_id)
            if sink and inputs:
                # Assume the first input token's payload is the data to emit.
                # A more complex Emitter could have routing logic based on port names.
                token_to_emit = next(iter(inputs.values()), None)
                if token_to_emit:
                    sink(token_to_emit.payload)
            return

        # 3. Submit to Executor
        await self.executor.submit(node, inputs)
~~~~~

#### Acts 2: 修复测试文件

测试文件 `test_result_emission.py` 的 API 调用部分是正确的，但 `register_sink` 失败时会 `pytest.fail`，这在 TDD 流程中可能掩盖了真正的运行时行为。我们将其移除，让测试自然地因为 `AttributeError` 或 `InvalidStateError` 而失败。但鉴于我们已经修复了 API，并且上一步的失败信息是 `Reactor.register_sink API is missing`，现在的修复将直接让测试通过。因此，不需要修改测试文件。

我将生成一个 `echo` 操作来确认这一点。

~~~~~act
echo
~~~~~
~~~~~text
No changes are needed for the test file. The previous run failed due to the missing `register_sink` API. My changes in `core.py` directly address this by adding the method and the corresponding logic in `_fire`. The existing test is now expected to pass.
~~~~~

### 下一步建议
测试现在应该通过了。我们已经成功地将 Reactor 的生命周期控制和结果输出都内化到了图的物理模型中。

下一步是**阶段 5.3: 全对称集成**。我们将重写 `VMExecutionStrategy`，使其不再扮演“超级监工”的角色，而是退化为一个简单的“点火器”：它负责编译图（自动注入 `Emitter` 和 `Terminator`），绑定 Sink，然后启动 Reactor 并等待其自行结束。
