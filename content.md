好的，我来分析问题并提出修复方案。

这是一个典型的 TDD (测试驱动开发) 流程中的 “RED” 状态。测试 `test_compile_injects_lifecycle_emitters` 失败，明确地告诉我们 `Backend` 编译器缺少一项关键功能：在编译图的末端自动注入用于生命周期管理的“发射器”节点 (Emitter Nodes)。

## [WIP] 在编译图的末端自动注入用于生命周期管理的“发射器”节点 (Emitter Nodes)。

### 错误分析

测试失败的根本原因是在 `cascade.compiler.backend._TopologyBuilder` 的 `build` 方法中，注入结果发射器 (`result_emitter`) 和终止信号发射器 (`term_emitter`) 的逻辑尚未实现。

代码中的 `Pass 5: Inject Lifecycle Emitters` 仅仅是一个占位符注释，没有实际的功能代码，因此在编译后的拓扑中找不到任何带有 `sink_id` 的 `PhysicsFuncNode`，导致 `next()` 函数抛出 `StopIteration`，最终 `result_emitter` 变量为 `None`，触发了 `AssertionError`。

### 用户需求

用户需要我实现这个缺失的生命周期注入逻辑，使得 `Backend.compile` 能够：
1.  识别计算图的最终输出节点。
2.  创建一个“结果发射器” (`result_emitter`)，它消费最终输出节点的结果，并通过 `sink_id="main_output"` 将其发射出去。
3.  创建一个“终止发射器” (`term_emitter`)，它在“结果发射器”工作完成后被一个 `SIGNAL` 类型的通道激活，并通过 `sink_id="__system_lifecycle_signal"` 发射一个终止信号。

### 评论

这是一个至关重要的修复。生命周期发射器的注入是将一个静态的、封闭的计算图与动态的、事件驱动的 `Reactor` 运行时连接起来的核心机制。没有这个机制，`Reactor` 将无法知道图何时计算完成，也无法将最终结果返回给调用者。实现这个功能将使我们的编译器向一个功能完备的物理拓扑生成器迈出关键一步。

### 目标

我的目标是修改 `packages/cascade-compiler/src/cascade/compiler/backend.py` 文件，在 `_TopologyBuilder` 类中实现生命周期发射器的注入逻辑，从而使指定的测试用例通过。

### 基本原理

我将在 `_TopologyBuilder.build` 方法的末尾，替换掉占位符注释 `Pass 5: Inject Lifecycle Emitters`。具体的实现步骤如下：

1.  **定位根节点**：根据前端编译器的约定，将 `graph.nodes` 列表中的最后一个节点视为图的根节点（最终结果的产生者）。
2.  **创建结果发射器**：
    *   创建一个新的 `PhysicsFuncNode` 作为结果发射器。
    *   它的 `sink_id` 将被设置为 `"main_output"`。
    *   它的输入将连接到根节点的输出数据槽 (`DataNode`)。
3.  **创建终止发射器**：
    *   创建一个 `SIGNAL` 类型的 `ChannelDef`，它的源是结果发射器。
    *   创建一个新的 `PhysicsDataNode` 作为该信号通道的目标。
    *   创建一个新的 `PhysicsFuncNode` 作为终止发射器，它的 `sink_id` 设置为 `"__system_lifecycle_signal"`，其输入连接到刚刚创建的信号数据节点。
4.  **注册组件**：将所有新创建的节点和通道添加到 `_TopologyBuilder` 的内部状态变量中（`self._func_nodes`, `self._data_nodes`, `self._channels`）。

为了确保哈希的唯一性，我还会添加一个 `_compute_synthetic_hash` 的辅助方法，用于生成这些编译器注入节点的稳定哈希值。

### 标签
#intent/fix #flow/ready #priority/high #comp/compiler #concept/compiler-backend #concept/lifecycle #ai/instruct #task/domain/compiler #task/object/lifecycle-injection #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 实现生命周期发射器注入逻辑

我将使用 `patch_file` 来修改 `backend.py`，将占位符注释替换为完整的实现。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
        # Pass 5: Inject Lifecycle Emitters
        self._inject_lifecycle_emitters()

        return BipartiteGraph(
            func_nodes=self._func_nodes,
            data_nodes=self._data_nodes,
            channels=self._channels,
            initial_values=self._initial_values,
        )

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

    def _process_node(self, node_ir: NodeIR):
        func_hash = node_ir.current_node_instance_hash

        f_node = PhysicsFuncNode(
            current_node_instance_hash=func_hash,
            name=node_ir.definition.name,
            inputs={},
            sink_id=None,  # Explicitly set sink_id to None for regular nodes
        )
        self._func_nodes[func_hash] = f_node

        for i, val in enumerate(node_ir.args):
            self._process_literal(f_node, str(i), val)
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

    def _compute_synthetic_hash(self, name: str) -> str:
        raw = f"synthetic:{name}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
from cascade.spec.topology import (
    BipartiteGraph,
    PhysicsFuncNode,
    PhysicsDataNode,
    ChannelDef,
    ChannelKind,
)
~~~~~
~~~~~python.new
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
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)
    # If not None, this node acts as an Emitter, pushing its result to the specified sink.
    sink_id: Optional[str] = field(default=None)
~~~~~

