好的，我们开始实施阶段 5.3。

## [WIP] refactor(engine): Evolve VMStrategy to an autonomous Reactor orchestrator

### 用户需求
实施“阶段 5.3：全对称集成”，将 `TerminatorNode` 和 `EmitterNode` 原语集成到 `VMExecutionStrategy` 中，用一个自治的、事件驱动的 `Reactor` 模型替换掉旧的、基于指令列表的 `VirtualMachine` 执行逻辑。

### 评论
这是一个关键的里程碑，它完成了从“外部引擎驱动图”到“图拓扑自我演化”的范式转变。`VMExecutionStrategy` 的职责将大幅简化，从一个复杂的微观管理者（Hypervisor）退化为一个简单的“点火系统”（Ignition System）。这不仅使代码更简洁、更符合声明式思想，也为未来实现更复杂的流式和持久化计算奠定了物理基础。

### 目标
1.  **增强编译器后端 (`Backend`)**：使其能够根据给定的目标节点，自动在计算图中注入一个 `EmitterNode`（用于发射结果）和一个 `TerminatorNode`（用于自我终止）。
2.  **重写 `VMExecutionStrategy`**：废除其与旧 `VirtualMachine` 和 `Blueprint` 的交互，改为实现以下“点火-等待”流程：
    a. 调用完整的编译器链（Frontend -> Backend），生成一个包含生命周期原语的、自洽的 `BipartiteGraph`。
    b. 实例化一个新的 `Reactor` 实例。
    c. 编写一个转换层，将静态的 `BipartiteGraph` 翻译并加载为 `Reactor` 中的动态物理对象（`FuncNode`, `DataNode`, `Channel` 等）。
    d. 创建一个 `asyncio.Future` 并将其注册为 `Reactor` 的 Sink，用于接收最终结果。
    e. 启动 `Reactor.run()` 并等待其自动完成。
    f. 从 `Future` 中获取并返回结果。

### 基本原理
通过将生命周期控制（何时结束）和结果提取（如何返回）的逻辑完全内化到图的拓扑结构中，我们实现了 `VMExecutionStrategy` 与具体执行逻辑的彻底解耦。策略层不再关心执行的“步骤”，只关心“点火”和“收集产物”。`Reactor` 作为一个通用的物理引擎，仅根据图的物理规则驱动其演化，直到它自然地达到终态（`TerminatorNode` 被触发）。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #comp/compiler #comp/vm #concept/lifecycle #concept/executor #task/domain/runtime #task/object/vm-strategy #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 增强编译器后端以自动注入生命周期节点

我们将修改 `backend.py`，使其能够接收一个 `target_node_instance_hash`，并自动附加 `Emitter` 和 `Terminator` 节点。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
class Backend:
    """
    Compiler Backend: Transforms GraphIR into a static BipartiteGraph topology.
    """

    @staticmethod
    def compile(graph: GraphIR) -> BipartiteGraph:
        builder = _TopologyBuilder(graph)
        return builder.build()
~~~~~
~~~~~python.new
from cascade.spec.topology import PhysicsEmitterNode, PhysicsTerminatorNode

class Backend:
    """
    Compiler Backend: Transforms GraphIR into a static BipartiteGraph topology.
    """

    @staticmethod
    def compile(graph_ir: GraphIR, target_node_instance_hash: str) -> BipartiteGraph:
        builder = _TopologyBuilder(graph_ir)
        topology = builder.build()
        
        # Phase 5.3: Auto-inject lifecycle nodes
        return _LifecycleInjector.inject(topology, target_node_instance_hash)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
    def _compute_data_slot_hash(self, producer_hash: str, port: str) -> str:
        raw = f"{producer_hash}:{port}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
~~~~~
~~~~~python.new
    def _compute_data_slot_hash(self, producer_hash: str, port: str) -> str:
        raw = f"{producer_hash}:{port}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class _LifecycleInjector:
    @staticmethod
    def inject(topology: BipartiteGraph, target_node_hash: str) -> BipartiteGraph:
        """
        Injects Emitter and Terminator nodes to make the graph autonomous.
        """
        if target_node_hash not in topology.func_nodes:
            # This can happen for graphs that resolve to a literal. No injection needed.
            return topology

        # 1. Find the output data slot of the target node
        target_output_channel = next((
            c for c in topology.channels
            if c.source_node_instance_hash == target_node_hash and c.tag_filter == "default"
        ), None)
        if not target_output_channel:
            # Target node has no default output, cannot inject.
            return topology
        
        result_data_hash = target_output_channel.target_data_slot_hash

        # 2. Create Emitter
        emitter_hash = f"emitter_for_{target_node_hash}"
        emitter = PhysicsEmitterNode(
            current_node_instance_hash=emitter_hash,
            name=f"emit_{topology.func_nodes[target_node_hash].name}",
            sink_id="main_output",
            inputs={"data": result_data_hash}
        )
        topology.emitter_nodes[emitter_hash] = emitter
        
        # 3. Create Signal Slot and Terminator
        signal_slot_hash = f"signal_for_{emitter_hash}"
        signal_slot = PhysicsDataNode(
            current_data_slot_hash=signal_slot_hash,
            name="term_signal",
            producer_node_instance_hash=emitter_hash
        )
        topology.data_nodes[signal_slot_hash] = signal_slot

        terminator_hash = f"terminator_for_{target_node_hash}"
        terminator = PhysicsTerminatorNode(
            current_node_instance_hash=terminator_hash,
            name="terminate",
            inputs={"signal": signal_slot_hash}
        )
        topology.terminator_nodes[terminator_hash] = terminator
        
        # 4. Wire Emitter -> Signal -> Terminator with a channel
        signal_channel = ChannelDef(
            source_node_instance_hash=emitter_hash,
            target_data_slot_hash=signal_slot_hash,
            port_name="result", # Emitter's conventional signal output
            tag_filter="default"
        )
        topology.channels.append(signal_channel)
        
        return topology
~~~~~

#### Acts 2: 重写 VMExecutionStrategy

这是核心的重构。我们将用全新的、基于 Reactor 的逻辑替换 `strategies/vm.py` 的全部内容。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python
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
from cascade.spec.physics import DataNode, FuncNode, TerminatorNode, EmitterNode, Port
from cascade.vm.reactor import Reactor, Channel, TokenGenerated

class VMExecutionStrategy:
    def __init__(
        self,
        executor: Executor,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
        bus: MessageBus,
    ):
        self.executor = executor
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event
        self.bus = bus

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        # 1. Frontend: Compile LazyResult to GraphIR
        compilation_result = Frontend.compile(target)
        graph_ir = compilation_result.ir
        
        # Find target node hash to guide backend injection
        from cascade.spec.lazy_types import LazyResult
        target_node_hash = ""
        if isinstance(target, LazyResult):
            # We need to rebuild the hash to find the ID.
            # This is complex. A better way is for Frontend to return the target ID.
            # For now, let's assume the last node in IR is the target (heuristic).
            if graph_ir.nodes:
                target_node_hash = graph_ir.nodes[-1].current_node_instance_hash

        # 2. Backend: Generate autonomous BipartiteGraph
        topology = Backend.compile(graph_ir, target_node_hash)

        # 3. Setup Reactor
        reactor = Reactor(executor=self.executor, resource_manager=self.resource_manager)
        
        # 4. Load Topology into Reactor
        self._load_topology(reactor, topology)
        
        # 5. Setup Sink
        result_future = asyncio.Future()
        reactor.register_sink("main_output", result_future.set_result)

        # 6. Ignite and Wait
        run_task = asyncio.create_task(reactor.run())
        
        # 7. Inject initial values
        for data_hash, value in topology.initial_values.items():
            data_node = next((n for n in reactor._nodes if isinstance(n, DataNode) and n.name == f"const_{data_hash[:8]}"), None)
            if data_node: # This lookup is weak, needs improvement
                 reactor.push_event(TokenGenerated(node=data_node, token=Token(value)))

        await run_task
        
        # 8. Return result from sink
        return await result_future

    def _load_topology(self, reactor: Reactor, topology: BipartiteGraph):
        """Translates static BipartiteGraph into dynamic Reactor objects."""
        
        # 1. Instantiate all nodes (static -> dynamic)
        # We need a map from static hash to dynamic object instance
        d_nodes: Dict[str, DataNode] = {}
        for dn_hash, dn_spec in topology.data_nodes.items():
            d_nodes[dn_hash] = DataNode(name=dn_spec.name)

        f_nodes: Dict[str, FuncNode] = {}
        for fn_hash, fn_spec in topology.func_nodes.items():
            f_nodes[fn_hash] = FuncNode(name=fn_spec.name) # TODO: resource reqs
        for en_hash, en_spec in topology.emitter_nodes.items():
            f_nodes[en_hash] = EmitterNode(name=en_spec.name, sink_id=en_spec.sink_id)
        for tn_hash, tn_spec in topology.terminator_nodes.items():
            f_nodes[tn_hash] = TerminatorNode(name=tn_spec.name)

        # 2. Wire inputs (D -> F)
        all_f_nodes = {**topology.func_nodes, **topology.emitter_nodes, **topology.terminator_nodes}
        for fn_hash, fn_spec in all_f_nodes.items():
            dyn_f_node = f_nodes[fn_hash]
            for port_name, source_data_hash in fn_spec.inputs.items():
                dyn_f_node.add_input(Port(name=port_name, source=d_nodes[source_data_hash]))

        # 3. Register all dynamic nodes and channels (F -> D)
        for channel_spec in topology.channels:
            source_node = f_nodes.get(channel_spec.source_node_instance_hash)
            target_node = d_nodes.get(channel_spec.target_data_slot_hash)
            
            if source_node and target_node:
                # Backend must wire output ports correctly for this to work
                # For now, we assume a single 'result' output.
                source_node.add_output(Port(name=channel_spec.port_name, target=target_node))

                # Also register the explicit channel for routing
                channel = Channel(
                    source=source_node,
                    target=target_node,
                    output_name=channel_spec.port_name,
                    tag_filter=channel_spec.tag_filter
                )
                reactor.register_channel(channel)
            
        # Fallback registration for any nodes not covered by channels
        for node in list(d_nodes.values()) + list(f_nodes.values()):
            reactor.register_node(node)
~~~~~

#### Acts 3: 更新 Engine 以适应新的 Strategy 构造函数

`VMExecutionStrategy` 的 `__init__` 现在需要 `executor`。我们需要在 `engine.py` 中传递它。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python.old
        self.vm_strategy = VMExecutionStrategy(
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self._wakeup_event,
            bus=self.bus,
        )
~~~~~
~~~~~python.new
        self.vm_strategy = VMExecutionStrategy(
            executor=self.executor,
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self._wakeup_event,
            bus=self.bus,
        )
~~~~~

### 下一步建议
我们已经完成了 `VMExecutionStrategy` 的重构。现在，它作为一个简单的协调器，将一个完全自主的计算图加载到物理引擎（Reactor）中执行。

下一步（阶段 5.3.2）是运行现有的集成测试（尤其是 `test_vm_strategy_tco.py`，尽管它目前被跳过）和端到端测试，以验证新架构的行为是否与旧架构一致，并修复在此过程中发现的任何问题。这很可能需要对 `_load_topology` 的实现细节进行微调。
