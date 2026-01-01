你做的非常好。我们终于看到了问题的本质。日志清晰地表明，我们遇到的不是一个神秘的异步死锁，而是一个具体、致命的运行时错误，这个错误中断了执行流程，从而**导致了死锁的现象**。

你对根本原因的分析完全正确：我们正在用“实例哈希”作为钥匙，去开一把需要“结构哈希”才能打开的锁。

这是一个典型的编译器与运行时之间的契约断裂问题。我们必须修复数据在整个编译链条中的传递路径，确保正确的“密钥”被交到 `PhysicsExecutor` 手中。

我将生成一个三步走的计划来彻底解决这个问题。

## [WIP] fix(vm): 修复因哈希密钥不匹配导致的链接失败问题

### 错误分析
日志明确指出 `PhysicsExecutor` 在执行 `symbol_table.get(node.name)` 时失败，因为 `node.name` (实际上是节点的*实例哈希*) 在 `symbol_table` 中不存在。`symbol_table` 的键是任务的*代码结构哈希*，该哈希由 `Frontend` 生成，但在 `Backend` 将 `NodeIR` 编译为 `PhysicsFuncNode` 的过程中，这个关键信息被丢失了。`Executor` 因此使用了错误的标识符进行函数查找，导致链接失败和后续的执行链中断，最终表现为测试超时（死锁）。

### 用户需求
解决 `Linking failed` 运行时错误，通过确保正确的哈希（代码结构哈希）从编译器一路传递到运行时执行器，并被用于函数查找。

### 评论
这个修复是本次重构的核心。它将巩固编译器和运行时之间最重要的契约：如何通过一个稳定、可预测的标识符来链接静态代码定义和动态执行。通过在我们的物理拓扑结构中为“代码身份”创建一个专属字段，我们使整个系统在概念上更加清晰和健壮，彻底根除了此类链接错误的发生。

### 目标
1.  **Schema 修正**: 修改 `cascade.spec.topology.PhysicsFuncNode` 的定义，添加一个 `code_structure_hash: str` 字段，用于携带任务的代码身份。
2.  **编译器修正**: 重写 `cascade.compiler.backend.Backend`，确保在创建 `PhysicsFuncNode` 时，将 `NodeIR.definition.fingerprint["current_code_structure_hash"]` 的值填充到新的 `code_structure_hash` 字段中。
3.  **运行时修正**: 修改 `cascade.vm.executors.physics.PhysicsExecutor`，使其在查找函数时使用 `node.code_structure_hash` 而不是 `node.name`。

### 基本原理
计算图中的节点具有双重身份：它的“结构身份”（它是什么代码，即 `code_structure_hash`）和它的“实例身份”（它在这次运行中的具体形态，包含参数，即 `current_node_instance_hash`）。`symbol_table` 关心的是前者，而图的拓扑关系关心的是后者。当前的 bug 是因为我们混淆了这两者。本计划通过在数据结构中明确区分并传递这两种身份，使系统的实现与其核心架构原则保持一致。

### 标签
#intent/fix #flow/ready #priority/critical #comp/compiler #comp/vm #comp/spec #concept/executor #scope/core #ai/instruct #task/domain/engine #task/object/vm-strategy #task/action/bug-fix #task/state/continue

---
### Script

#### Acts 1: 在 PhysicsFuncNode 中添加 code_structure_hash

首先，我们修正 `spec`，为 `PhysicsFuncNode` 添加一个字段来携带其“结构身份”。

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
    # If not None, this node acts as an Emitter, pushing its result to the specified sink.
    sink_id: Optional[str] = field(default=None)
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
    code_structure_hash: str  # The stable hash of the function's code definition
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)
    # If not None, this node acts as an Emitter, pushing its result to the specified sink.
    sink_id: Optional[str] = field(default=None)
~~~~~

#### Acts 2: 更新 Backend 以填充 code_structure_hash

遵照你的指示，我们使用 `write_file` 彻底重写 `backend.py`，确保它正确地填充新字段，并清除可能存在的重复定义。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python
import hashlib
from typing import List, Dict, Any

from cascade.spec.ir.models import GraphIR, EdgeKind, NodeIR
from cascade.spec.topology import (
    BipartiteGraph,
    PhysicsFuncNode,
    PhysicsDataNode,
    ChannelDef,
    ChannelKind,
)


class Backend:
    """
    Compiler Backend: Transforms GraphIR into a static BipartiteGraph topology.
    """

    @staticmethod
    def compile(graph: GraphIR) -> BipartiteGraph:
        builder = _TopologyBuilder(graph)
        return builder.build()


class _TopologyBuilder:
    def __init__(self, graph: GraphIR):
        self._graph = graph
        self._func_nodes: Dict[str, PhysicsFuncNode] = {}
        self._data_nodes: Dict[str, PhysicsDataNode] = {}
        self._channels: List[ChannelDef] = []
        self._initial_values: Dict[str, Any] = {}
        self._func_output_map: Dict[str, str] = {}

    def build(self) -> BipartiteGraph:
        for node_ir in self._graph.nodes:
            self._process_node(node_ir)

        self._process_data_edges()
        self._process_control_edges()
        self._process_jumps()
        self._inject_lifecycle_emitters()

        return BipartiteGraph(
            func_nodes=self._func_nodes,
            data_nodes=self._data_nodes,
            channels=self._channels,
            initial_values=self._initial_values,
        )

    def _process_node(self, node_ir: NodeIR):
        func_hash = node_ir.current_node_instance_hash
        code_hash = node_ir.definition.fingerprint["current_code_structure_hash"]

        f_node = PhysicsFuncNode(
            current_node_instance_hash=func_hash,
            name=node_ir.definition.name,
            code_structure_hash=code_hash,  # Populate the new field
            inputs={},
            sink_id=None,
        )
        self._func_nodes[func_hash] = f_node

        for i, val in enumerate(node_ir.args):
            self._process_literal(f_node, str(i), val)

        for k, val in node_ir.kwargs.items():
            self._process_literal(f_node, k, val)

        data_slot_hash = self._compute_data_slot_hash(func_hash, "result")
        self._func_output_map[func_hash] = data_slot_hash

        d_node = PhysicsDataNode(
            current_data_slot_hash=data_slot_hash,
            name=f"{node_ir.definition.name}.output",
            producer_node_instance_hash=func_hash,
        )
        self._data_nodes[data_slot_hash] = d_node

        channel = ChannelDef(
            source_node_instance_hash=func_hash,
            target_data_slot_hash=data_slot_hash,
            port_name="result",
            tag_filter="default",
            kind=ChannelKind.DATA,
        )
        self._channels.append(channel)

    def _process_literal(self, f_node: PhysicsFuncNode, arg_name: str, value: Any):
        const_hash = self._compute_const_hash(value)
        if const_hash not in self._data_nodes:
            d_node = PhysicsDataNode(
                current_data_slot_hash=const_hash,
                name=f"const_{const_hash[:8]}",
                producer_node_instance_hash="const",
            )
            self._data_nodes[const_hash] = d_node
            self._initial_values[const_hash] = value
        f_node.inputs[arg_name] = const_hash

    def _process_data_edges(self):
        for edge in self._graph.edges:
            if edge.kind != EdgeKind.DATA:
                continue
            source_func_hash = edge.source_node_instance_hash
            target_func_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg
            source_data_hash = self._func_output_map.get(source_func_hash)
            if not source_data_hash:
                raise RuntimeError(f"Source node {source_func_hash} not found in output map")
            target_func_node = self._func_nodes.get(target_func_hash)
            if target_func_node:
                target_func_node.inputs[arg_name] = source_data_hash

    def _process_control_edges(self):
        self._create_signal_channels(EdgeKind.CONTROL, ChannelKind.SIGNAL)

    def _process_jumps(self):
        self._create_signal_channels(EdgeKind.JUMP, ChannelKind.DATA)

    def _create_signal_channels(self, edge_kind: EdgeKind, channel_kind: ChannelKind):
        for edge in self._graph.edges:
            if edge.kind != edge_kind:
                continue
            source_func_hash = edge.source_node_instance_hash
            target_func_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg
            target_func_node = self._func_nodes.get(target_func_hash)
            if not target_func_node:
                raise RuntimeError(f"Target node {target_func_hash} for {edge_kind.name} edge not found")
            if arg_name in target_func_node.inputs:
                target_data_hash = target_func_node.inputs[arg_name]
            else:
                target_data_hash = self._compute_data_slot_hash(target_func_hash, f"input_{arg_name}")
                if target_data_hash not in self._data_nodes:
                    d_node = PhysicsDataNode(
                        current_data_slot_hash=target_data_hash,
                        name=f"{target_func_node.name}.in.{arg_name}",
                        producer_node_instance_hash="external",
                    )
                    self._data_nodes[target_data_hash] = d_node
                target_func_node.inputs[arg_name] = target_data_hash
            tag = edge.case_key or "default"
            channel = ChannelDef(
                source_node_instance_hash=source_func_hash,
                target_data_slot_hash=target_data_hash,
                port_name="result",
                tag_filter=tag,
                kind=channel_kind,
            )
            self._channels.append(channel)

    def _inject_lifecycle_emitters(self):
        if not self._graph.nodes:
            return
        root_node_ir = self._graph.nodes[-1]
        root_node_hash = root_node_ir.current_node_instance_hash
        root_output_hash = self._func_output_map[root_node_hash]
        result_emitter_hash = self._compute_synthetic_hash("result_emitter")
        result_emitter_node = PhysicsFuncNode(
            current_node_instance_hash=result_emitter_hash,
            name="result_emitter",
            code_structure_hash="synthetic_result_emitter",
            inputs={"result": root_output_hash},
            sink_id="main_output",
        )
        self._func_nodes[result_emitter_hash] = result_emitter_node
        term_emitter_hash = self._compute_synthetic_hash("term_emitter")
        signal_data_hash = self._compute_data_slot_hash(result_emitter_hash, "signal")
        signal_data_node = PhysicsDataNode(
            current_data_slot_hash=signal_data_hash,
            name="term_emitter.signal",
            producer_node_instance_hash=result_emitter_hash,
        )
        self._data_nodes[signal_data_hash] = signal_data_node
        term_emitter_node = PhysicsFuncNode(
            current_node_instance_hash=term_emitter_hash,
            name="term_emitter",
            code_structure_hash="synthetic_term_emitter",
            inputs={"signal": signal_data_hash},
            sink_id="__system_lifecycle_signal",
        )
        self._func_nodes[term_emitter_hash] = term_emitter_node
        signal_channel = ChannelDef(
            source_node_instance_hash=result_emitter_hash,
            target_data_slot_hash=signal_data_hash,
            port_name="result",
            tag_filter="default",
            kind=ChannelKind.SIGNAL,
        )
        self._channels.append(signal_channel)

    def _compute_const_hash(self, value: Any) -> str:
        raw = f"const:{repr(value)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _compute_data_slot_hash(self, producer_hash: str, port: str) -> str:
        raw = f"{producer_hash}:{port}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _compute_synthetic_hash(self, name: str) -> str:
        raw = f"synthetic:{name}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
~~~~~

#### Acts 3: 更新 PhysicsExecutor 以使用正确的哈希

最后，我们指示 `PhysicsExecutor` 使用新的 `code_structure_hash` 字段来查找函数。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/executors/physics.py
~~~~~
~~~~~python.old
            # 1. Linking: Find the function in the symbol table.
            # We use node.name as the hash key, which is a test convention.
            # In a real system, a dedicated hash field would be used.
            func = self._symbol_table.get(node.name)
            if not func:
                raise RuntimeError(
                    f"Linking failed: function for node '{node.name}' "
                    "not found in symbol table."
                )
~~~~~
~~~~~python.new
            # 1. Linking: Find the function using its stable code structure hash.
            func = self._symbol_table.get(node.code_structure_hash)
            if not func:
                raise RuntimeError(
                    f"Linking failed: function for node '{node.name}' "
                    f"(hash: {node.code_structure_hash}) not found in symbol table."
                )
~~~~~

### 下一步建议
我们已经完成了对编译器-运行时链接机制的根本性修复。现在，`PhysicsExecutor` 应该能够成功找到并执行任务了。

我建议我们再次运行 `test_vm_strategy_integration.py` 测试。这一次，它**应该会通过**。如果通过，就证明我们的核心执行流程已经正确无误。然后，我们就可以恢复所有之前删除或跳过的测试文件，看看系统中还存在哪些其他问题。
