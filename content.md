> FAILED packages/cascade-engine/tests/integration/test_vm_strategy_integration.py::test_vm_strategy_executes_simplest_workflow - TypeError: PhysicsFuncNode.__init__() missing 1 required positional argument: 'code_structure_hash'

Excellent. This is progress. We have moved from a mysterious deadlock to a clear, specific `TypeError`. This error tells us exactly what is wrong.

The error `TypeError: PhysicsFuncNode.__init__() missing 1 required positional argument: 'code_structure_hash'` is the smoking gun. It means that somewhere in the code, `PhysicsFuncNode` is being instantiated without the `code_structure_hash` that we just added to its definition.

Your previous intuition was also correct: `packages/cascade-compiler/src/cascade/compiler/backend.py` had internal inconsistencies.

Let's trace the failure:

1.  **Schema Change**: In the last step, I correctly identified that we needed to add `code_structure_hash` to the `PhysicsFuncNode` dataclass in `topology.py`.
2.  **Implementation Mismatch**: However, it seems my previous plan to patch `topology.py` was insufficient or didn't get applied correctly, while the changes to `backend.py` which *use* that new field were. The `backend.py` file is now trying to call a constructor (`PhysicsFuncNode(...)`) with a `code_structure_hash` argument, but the actual class definition in `topology.py` doesn't have that field yet. This creates the `TypeError`.
3.  **File Integrity**: Additionally, you were right to suggest using `write_file` for `backend.py`. My analysis of the context files shows it currently has duplicated method definitions, which is a sign of a previous partial patch. We need to clean that up.

The root cause is a desynchronization between the `spec` (the definition) and the `compiler` (the implementation). We need to fix the spec file (`topology.py`) definitively, and ensure the compiler (`backend.py`) is clean and correct.

I will generate a plan that uses the more robust `write_file` command to fix both `topology.py` and `backend.py`, ensuring they are perfectly synchronized and internally consistent.

## [WIP] fix(spec,compiler): 同步 PhysicsFuncNode 定义与实现

### 错误分析
`TypeError: PhysicsFuncNode.__init__() missing ... 'code_structure_hash'` 表明，尽管编译器 (`backend.py`) 已被更新以传递 `code_structure_hash` 参数，但 `PhysicsFuncNode` 的实际类定义 (`topology.py`) 并未成功更新以接收此参数。这是一个典型的、由于接口（spec）与其实现（compiler）之间不同步而导致的错误。此外，`backend.py` 文件本身也存在重复定义，需要清理。

### 用户需求
修复因 `PhysicsFuncNode` 定义与其实例化代码不匹配而导致的 `TypeError`，并清理 `backend.py` 文件。

### 评论
这次修复将通过强制性的 `write_file` 操作来确保 `spec` 和 `compiler` 之间契约的一致性。这是解决 `TypeError` 的根本方法。通过修正 `PhysicsFuncNode` 的 schema 并清理其实现，我们确保了数据在编译链中能够被正确地传递和使用，为打通端到端测试铺平了道路。

### 目标
1.  **Schema 修复**: 使用 `write_file` 彻底重写 `packages/cascade-spec/src/cascade/spec/topology.py`，确保 `PhysicsFuncNode` 包含 `code_structure_hash` 字段且没有重复字段。
2.  **编译器清理**: 再次使用 `write_file` 重写 `packages/cascade-compiler/src/cascade/compiler/backend.py`，确保其代码干净、无重复，并正确地为 `PhysicsFuncNode` 填充 `code_structure_hash`。

### 基本原理
`TypeError` 是一个清晰的信号，表明函数调用的签名不匹配。问题的根源在于 `PhysicsFuncNode` 的定义文件 (`topology.py`) 状态不正确。通过 `write_file` 覆盖该文件，我们可以保证其定义与我们的预期完全一致。同时，再次覆盖 `backend.py` 可以确保它不仅使用了正确的实例化调用，而且其自身的文件结构也是健康的。

### 标签
#intent/fix #flow/ready #priority/critical #comp/spec #comp/compiler #scope/core #ai/instruct #task/domain/engine #task/object/vm-strategy #task/action/refactor #task/state/continue

---
### Script

#### Acts 1: 强制修正 `topology.py` 的 Schema

我们将使用 `write_file` 来确保 `PhysicsFuncNode` 的定义是正确且唯一的。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


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


@dataclass(frozen=True)
class PhysicsDataNode:
    """
    Represents a data storage slot in the physical bipartite graph.
    This is the "Noun" or the container. It tracks its origin.
    """

    current_data_slot_hash: str
    name: str
    producer_node_instance_hash: str


class ChannelKind(str, Enum):
    """
    Defines the physical nature of a channel, separating data flow from control flow.
    """

    DATA = "DATA"  # Transports a payload. Contributes to 'data potential'.
    SIGNAL = "SIGNAL"  # Transports only an activation signal. Contributes to 'control potential'.


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


@dataclass(frozen=True)
class BipartiteGraph:
    """
    The static, physical blueprint of the computation network, output by the compiler.
    """

    func_nodes: Dict[str, PhysicsFuncNode]
    data_nodes: Dict[str, PhysicsDataNode]
    channels: List[ChannelDef]
    # Map data_slot_hash -> literal value for constant inputs
    initial_values: Dict[str, Any] = field(default_factory=dict)
~~~~~

#### Acts 2: 清理并同步 `backend.py`

我们再次使用 `write_file` 来确保 `backend.py` 的内容是干净的，并且与新的 `PhysicsFuncNode` 定义同步。

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
            code_structure_hash=code_hash,
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
        self._channels.append(channel)

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

### 下一步建议
我们已经完成了对 `spec` 和 `compiler` 的同步修复，从根本上解决了 `TypeError`。现在，`Backend` 在创建 `PhysicsFuncNode` 时，应该不会再遇到构造函数不匹配的问题了。

我强烈建议再次运行我们的诊断测试：
`pytest -s packages/cascade-engine/tests/integration/test_vm_strategy_integration.py`

这一次，我们期望 `TypeError` 会消失。测试可能会通过，或者暴露出下一个层级的逻辑问题。无论结果如何，我们都离最终的成功更近了一步。
