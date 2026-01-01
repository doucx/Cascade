好的，我来分析这个问题。

这是一个典型的**接口不匹配 (Interface Mismatch)** 错误，但其根源在于我们新旧架构之间的数据流失，是一个战略层面的问题。

**错误分析**:
1.  **直接原因**: `Reactor` (来自 `cascade-vm`) 期望它的 `executor` 有一个 `async def submit(self, node, inputs)` 方法。然而，我们传递给它的是 `LocalExecutor` (来自 `cascade-engine`)，它的方法签名是 `async def execute(self, node, args, kwargs)`。方法名不同，导致 `AttributeError`。
2.  **深层原因**: 这种不匹配暴露了一个更深层次的问题：**信息在编译链中丢失了**。
    *   `Reactor` 工作在**物理层**，它处理的是 `FuncNode` 和 `Token`。它不知道 Python 函数是什么，只知道要激发一个节点。
    *   `LocalExecutor` 工作在**逻辑层**，它需要知道具体的 Python `callable`（函数对象）才能执行。
    *   在我们的新 `VMExecutionStrategy` 中，`Frontend` 正确地将 Python 函数和其结构哈希存入了 `symbol_table`。但这个 `symbol_table` 只存在于 `VMExecutionStrategy` 层面，并没有传递给 `Reactor` 或其 `executor`。`Reactor` 内部的 `FuncNode` 只是一个数据结构，它丢失了与其对应的 Python 函数的链接。

**解决方案**:
我们需要创建一个**适配器 (Adapter)**。这个适配器将作为 `Reactor` 和 `LocalExecutor` 之间的桥梁。它的职责是：
1.  向 `Reactor` 暴露其期望的 `submit` 接口。
2.  在内部，接收 `Reactor` 传递的物理对象 (`FuncNode`, `Token`)。
3.  使用 `symbol_table` 查找 `FuncNode` 对应的 Python 函数。
4.  将 `Token` 解包成 `LocalExecutor` 期望的 `args`/`kwargs`。
5.  创建一个临时的、`LocalExecutor` 能理解的 `Node` 对象（Shim）。
6.  调用 `LocalExecutor.execute`。
7.  将执行结果包装成 `ExecutionFinished` 事件，并推回给 `Reactor`，以驱动图的继续演化。

为了让适配器能工作，我们还必须确保 `FuncNode` 携带了足以在 `symbol_table` 中查找所需信息的标识符（即 `code_structure_hash`）。这意味着我们需要将这个哈希值从 `NodeIR` 一路传递到 `PhysicsFuncNode`，再到运行时的 `FuncNode`。

现在，让我们生成一个计划来实施这个适配器和必要的数据流修复。

## [WIP] fix(vm): Create ReactorExecutor adapter to bridge Reactor and LocalExecutor

### 用户需求
修复 `Reactor` 调用 `LocalExecutor` 时因接口不匹配导致的 `AttributeError`。

### 评论
这个修复不仅仅是重命名一个方法调用，它通过创建一个适配器，正式地解决了新物理引擎 (`Reactor`) 与旧执行器 (`LocalExecutor`) 之间的鸿沟。此适配器现在是连接调度层和执行层的关键组件，负责在运行时动态链接代码（通过 `symbol_table`）并转换数据格式，确保了两个世界的正确通信。

### 目标
1.  **增强信息传递**: 修改 `PhysicsFuncNode` (静态) 和 `FuncNode` (动态) 以携带 `code_structure_hash`，确保从编译到运行的信息完整性。
2.  **创建适配器**: 在 `VMExecutionStrategy` 内部实现一个 `_ReactorExecutorAdapter`，它暴露 `submit` 接口并包装 `LocalExecutor`。
3.  **集成适配器**: 修改 `VMExecutionStrategy`，将此适配器实例传递给 `Reactor`。

### 基本原理
我们将修复编译后端，确保 `code_structure_hash` 被保存在 `BipartiteGraph` 的 `PhysicsFuncNode` 中。然后，在 `VMExecutionStrategy._load_topology` 中，这个哈希将被传递给动态的 `FuncNode`。
`_ReactorExecutorAdapter` 将利用这个哈希在 `symbol_table` 中找到真正的 Python 函数，构造一个 `LocalExecutor` 能理解的调用请求，执行它，然后将结果通过 `ExecutionFinished` 事件报告回 `Reactor`，从而闭合了整个执行-反馈循环。

### 标签
#intent/fix #flow/ready #priority/critical #comp/vm #comp/engine #concept/executor #task/domain/runtime #task/object/reactor #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 在拓扑和物理层中添加 code_structure_hash

首先，我们修复信息丢失问题，确保 `code_structure_hash` 能一路传递到运行时。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """
    current_node_instance_hash: str
    name: str
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """
    current_node_instance_hash: str
    name: str
    code_structure_hash: str # Added for linking
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
class FuncNode:
    """
    Stateless transformer. Represents the 'Verb' in the physics model.
    """
    def __init__(
        self, 
        name: str, 
        code_structure_hash: str, # Added for linking
        resource_requirements: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.code_structure_hash = code_structure_hash
        self.resource_requirements = resource_requirements or {}
        self.inputs: Dict[str, Port] = {}
        self.outputs: Dict[str, Port] = {}
~~~~~

#### Acts 2: 更新编译器后端以传递哈希

修改 `backend.py`，将 `code_structure_hash` 从 `NodeIR` 写入 `PhysicsFuncNode`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
        # 1. Create PhysicsFuncNode
        f_node = PhysicsFuncNode(
            current_node_instance_hash=func_hash,
            name=node_ir.definition.name,
            inputs={} 
        )
        self._func_nodes[func_hash] = f_node
~~~~~
~~~~~python.new
        # 1. Create PhysicsFuncNode
        f_node = PhysicsFuncNode(
            current_node_instance_hash=func_hash,
            name=node_ir.definition.name,
            code_structure_hash=node_ir.definition.fingerprint["current_code_structure_hash"],
            inputs={} 
        )
        self._func_nodes[func_hash] = f_node
~~~~~

#### Acts 3: 实现适配器并重构 VMExecutionStrategy

这是核心修改。我们在 `vm.py` 中创建适配器，并在 `_load_topology` 中传递哈希，最后在 `execute` 中使用适配器。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
import asyncio
from contextlib import ExitStack
from typing import Any, Dict

from cascade.spec.protocols import StateBackend, Executor
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints.manager import ConstraintManager
from cascade.runtime.bus import MessageBus

# New Compiler Stack & Physics
from cascade.compiler import Frontend, Backend
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import DataNode, FuncNode, TerminatorNode, EmitterNode, Port, Token
from cascade.vm.reactor import Reactor, Channel, TokenGenerated
~~~~~
~~~~~python.new
import asyncio
from contextlib import ExitStack
from typing import Any, Dict, Callable

from cascade.spec.protocols import StateBackend, Executor
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints.manager import ConstraintManager
from cascade.runtime.bus import MessageBus

# New Compiler Stack & Physics
from cascade.compiler import Frontend, Backend
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import DataNode, FuncNode, TerminatorNode, EmitterNode, Port, Token
from cascade.vm.reactor import Reactor, Channel, TokenGenerated, ExecutionFinished

# Shim for LocalExecutor
from cascade.graph.model import Node as OldNode
from cascade.spec.ir.models import TaskDef
from cascade.spec.fingerprint import Fingerprint
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
class VMExecutionStrategy:
    def __init__(
        self,
~~~~~
~~~~~python.new
class _ReactorExecutorAdapter:
    """Bridges the Reactor's simple executor protocol with the legacy LocalExecutor."""
    def __init__(self, local_executor: Executor, reactor: Reactor, symbol_table: Dict[str, Callable]):
        self.local_executor = local_executor
        self.reactor = reactor
        self.symbol_table = symbol_table

    async def submit(self, node: FuncNode, inputs: Dict[str, Token]):
        """The interface expected by the Reactor."""
        # This runs in a background task so it doesn't block the reactor loop.
        asyncio.create_task(self._execute_and_report(node, inputs))

    async def _execute_and_report(self, node: FuncNode, inputs: Dict[str, Token]):
        try:
            # 1. Link to find the callable
            func = self.symbol_table[node.code_structure_hash]

            # 2. Unpack payloads
            # Emitter/Terminator don't have inputs in this path
            kwargs = {name: token.payload for name, token in inputs.items()}
            
            # 3. Create a shim Node for LocalExecutor
            # TODO: Propagate is_async and mode properly
            is_async = asyncio.iscoroutinefunction(func)
            shim_def = TaskDef(name=node.name, args=[], fingerprint=Fingerprint(), is_async=is_async)
            shim_node = OldNode(
                current_node_instance_hash=node.name, # Approximation
                definition=shim_def,
                _callable=func
            )
            
            # 4. Execute
            result = await self.local_executor.execute(shim_node, [], kwargs)
            
            # 5. Report back with ExecutionFinished event
            # For now, assume single 'result' output
            output_token = Token(payload=result)
            event = ExecutionFinished(node=node, outputs={"result": output_token})

        except Exception as e:
            event = ExecutionFinished(node=node, error=e)
            
        self.reactor.push_event(event)


class VMExecutionStrategy:
    def __init__(
        self,
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        # 3. Setup Reactor
        reactor = Reactor(executor=self.executor, resource_manager=self.resource_manager)
        
        # 4. Load Topology into Reactor
        self._load_topology(reactor, topology)
        
        # 5. Setup Sink
~~~~~
~~~~~python.new
        # 3. Setup Reactor and its Executor Adapter
        reactor = Reactor(executor=None, resource_manager=self.resource_manager)
        adapter = _ReactorExecutorAdapter(
            local_executor=self.executor,
            reactor=reactor,
            symbol_table=compilation_result.symbol_table
        )
        reactor.executor = adapter # Set the adapter as the executor
        
        # 4. Load Topology into Reactor
        self._load_topology(reactor, topology)
        
        # 5. Setup Sink
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        f_nodes: Dict[str, FuncNode] = {}
        for fn_hash, fn_spec in topology.func_nodes.items():
            f_nodes[fn_hash] = FuncNode(name=fn_spec.name) # TODO: resource reqs
        for en_hash, en_spec in topology.emitter_nodes.items():
            f_nodes[en_hash] = EmitterNode(name=en_spec.name, sink_id=en_spec.sink_id)
        for tn_hash, tn_spec in topology.terminator_nodes.items():
            f_nodes[tn_hash] = TerminatorNode(name=tn_spec.name)
~~~~~
~~~~~python.new
        f_nodes: Dict[str, FuncNode] = {}
        for fn_hash, fn_spec in topology.func_nodes.items():
            f_nodes[fn_hash] = FuncNode(
                name=fn_spec.name,
                code_structure_hash=fn_spec.code_structure_hash
            ) # TODO: resource reqs
        for en_hash, en_spec in topology.emitter_nodes.items():
            f_nodes[en_hash] = EmitterNode(
                name=en_spec.name,
                sink_id=en_spec.sink_id,
                code_structure_hash="" # Emitters don't have user code
            )
        for tn_hash, tn_spec in topology.terminator_nodes.items():
            f_nodes[tn_hash] = TerminatorNode(
                name=tn_spec.name,
                code_structure_hash="" # Terminators don't have user code
            )
~~~~~

### 下一步建议
我们已经通过适配器模式解决了 `Reactor` 和 `LocalExecutor` 之间的核心接口冲突，并修复了编译链中的信息丢失问题。现在的架构在概念上更加完整和健壮。

下一步是重新运行所有 `cascade-engine` 的测试套件，特别是与 `VMExecutionStrategy` 相关的测试。这个大规模的重构很可能会暴露出一些新的、更细微的集成问题，我们需要逐一解决它们，以确保新架构的行为与旧架构完全兼容。
