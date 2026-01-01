Okay, let's begin **Phase 5.C.1: [Compiler] Compiler Backend support for signaling and lifecycle injection**.

This is a critical step in aligning our compiler's output with the new, purer physics model. I will modify the `Backend` to correctly handle polarized channels (`DATA` vs. `SIGNAL`) and to inject the new emitter-based lifecycle management nodes into the compiled graph.

The changes involve:
1.  **Channel Polarization**: Ensuring `DATA`, `CONTROL`, and `JUMP` edges from the `GraphIR` are compiled into `ChannelDef` objects with the correct `ChannelKind`.
2.  **Lifecycle Injection**: Replacing the old `TerminatorNode` concept with a new pattern:
    *   Injecting a `result_emitter` `FuncNode` that consumes the graph's final output and sends it to the `main_output` sink.
    *   Injecting a `term_emitter` `FuncNode` downstream of the result emitter, connected by a `SIGNAL` channel, which sends a termination signal to the `__system_lifecycle_signal` sink.

Based on the scope and distribution of these changes within `packages/cascade-compiler/src/cascade/compiler/backend.py`, I will use `write_file` to provide the complete, updated content of the file.

## [WIP] feat(compiler): Implement signal channels and lifecycle injection in Backend

### 用户需求
Implement **Phase 5.C.1** of the refactoring roadmap. The compiler `Backend` needs to be updated to support channel polarization (DATA vs. SIGNAL) and to inject the new emitter-based lifecycle nodes, replacing the old `TerminatorNode` logic.

### 评论
This is a foundational step in realizing the "full-symmetry" architecture. By making the `Backend` aware of signal channels, we create a physically accurate representation of control flow. By replacing the special-cased `TerminatorNode` with generic, sink-based emitters, we make the compiled topology more uniform and decouple the physics engine (`Reactor`) from lifecycle management.

### 目标
1.  Update `cascade.compiler.backend.Backend` to differentiate between `DATA` and `SIGNAL` channels during compilation.
2.  Modify the `Backend` to inject two chained `FuncNode` emitters at the end of the graph for result reporting and system termination.
3.  Ensure the new `BipartiteGraph` structure is fully compliant with the expectations of the `Reactor` and `VMExecutionStrategy`.

### 基本原理
I will perform a significant refactoring of the `_TopologyBuilder` within `backend.py`.
- The `_create_signal_channels` method will be parameterized to accept a `ChannelKind`, allowing it to create both `DATA` channels (for jumps) and `SIGNAL` channels (for control edges).
- A new private method, `_inject_lifecycle_emitters`, will be added. This method will be called at the end of the `build` process. It will identify the graph's root output node and attach the result and termination emitter `FuncNode`s, connecting them with a `SIGNAL` channel.
- All existing channel creation points will be updated to explicitly set `kind=ChannelKind.DATA` by default, ensuring correctness.

This approach centralizes the new logic and cleanly integrates it into the existing build process.

### 标签
#intent/build #flow/ready #priority/high
#comp/compiler #concept/executor #concept/state
#scope/core #scope/api
#ai/instruct
#task/domain/compiler #task/object/backend #task/action/refactor
#task/state/continue

---

### Script

#### Acts 1: Refactor `backend.py` for Channel Polarization and Lifecycle Injection

I will now overwrite `packages/cascade-compiler/src/cascade/compiler/backend.py` with the updated implementation.

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

        # Helper map: FuncNode Hash -> Default Output DataNode Hash
        self._func_output_map: Dict[str, str] = {}

    def build(self) -> BipartiteGraph:
        # Pass 1: Instantiate Nodes (Func & Data) and Output Channels
        for node_ir in self._graph.nodes:
            self._process_node(node_ir)

        # Pass 2: Wire Inputs based on standard data Edges
        self._process_data_edges()

        # Pass 3: Wire Control Edges (e.g., from .run_if) as SIGNAL channels
        self._process_control_edges()

        # Pass 4: Wire Jumps (Feedback Loops) as DATA channels
        self._process_jumps()

        # Pass 5: Inject Lifecycle Emitters
        self._inject_lifecycle_emitters()

        return BipartiteGraph(
            func_nodes=self._func_nodes,
            data_nodes=self._data_nodes,
            channels=self._channels,
            initial_values=self._initial_values,
        )

    def _process_node(self, node_ir: NodeIR):
        func_hash = node_ir.current_node_instance_hash

        f_node = PhysicsFuncNode(
            current_node_instance_hash=func_hash,
            name=node_ir.definition.name,
            inputs={},
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
            kind=ChannelKind.DATA,  # Explicitly a DATA channel
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
                raise RuntimeError(
                    f"Source node {source_func_hash} not found in output map"
                )

            target_func_node = self._func_nodes.get(target_func_hash)
            if target_func_node:
                target_func_node.inputs[arg_name] = source_data_hash

    def _process_control_edges(self):
        self._create_signal_channels(EdgeKind.CONTROL, ChannelKind.SIGNAL)

    def _process_jumps(self):
        # Jumps are data-carrying control flow, so they use DATA channels.
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
                raise RuntimeError(
                    f"Target node {target_func_hash} for {edge_kind.name} edge not found"
                )

            # A control/jump edge needs a dedicated input slot on the target.
            # If one already exists (from a literal or other edge), we reuse it.
            # Otherwise, we create one.
            if arg_name in target_func_node.inputs:
                target_data_hash = target_func_node.inputs[arg_name]
            else:
                target_data_hash = self._compute_data_slot_hash(
                    target_func_hash, f"input_{arg_name}"
                )
                if target_data_hash not in self._data_nodes:
                    d_node = PhysicsDataNode(
                        current_data_slot_hash=target_data_hash,
                        name=f"{target_func_node.name}.in.{arg_name}",
                        producer_node_instance_hash="external",
                    )
                    self._data_nodes[target_data_hash] = d_node
                target_func_node.inputs[arg_name] = target_data_hash

            # Create the Channel
            tag = edge.case_key or "default"
            channel = ChannelDef(
                source_node_instance_hash=source_func_hash,
                target_data_slot_hash=target_data_hash,
                port_name="result",  # Signals/Jumps use the default output port
                tag_filter=tag,
                kind=channel_kind,
            )
            self._channels.append(channel)

    def _inject_lifecycle_emitters(self):
        if not self._graph.nodes:
            return  # Empty graph, nothing to do

        # Assumption: The last node processed by the Frontend is the target.
        root_node_ir = self._graph.nodes[-1]
        root_node_hash = root_node_ir.current_node_instance_hash
        root_output_hash = self._func_output_map[root_node_hash]

        # 1. Create Result Emitter Node
        result_emitter_hash = self._compute_synthetic_hash("result_emitter")
        result_emitter_node = PhysicsFuncNode(
            current_node_instance_hash=result_emitter_hash,
            name="result_emitter",
            inputs={"result": root_output_hash},
            sink_id="main_output",
        )
        self._func_nodes[result_emitter_hash] = result_emitter_node

        # 2. Create Termination Emitter Node and its input DataNode
        term_emitter_hash = self._compute_synthetic_hash("term_emitter")
        # The signal comes FROM the result emitter
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
            inputs={"signal": signal_data_hash},
            sink_id="__system_lifecycle_signal",
        )
        self._func_nodes[term_emitter_hash] = term_emitter_node

        # 3. Create SIGNAL Channel connecting the two emitters
        signal_channel = ChannelDef(
            source_node_instance_hash=result_emitter_hash,
            target_data_slot_hash=signal_data_hash,
            port_name="result",  # Emitters also have a default output for signaling
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

### 下一步建议
The `Backend` is now aligned with our new physics model. The next logical step is to implement **Phase 5.C.2**, which involves rewriting the `VMExecutionStrategy` to consume this new `BipartiteGraph`, set up the `Reactor` and `PhysicsExecutor`, register the sinks for `main_output` and `__system_lifecycle_signal`, and orchestrate the entire end-to-end execution.

If you agree, I will proceed to generate the plan for that phase.

