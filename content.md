## [WIP] feat: 实现 TCO 编译逻辑

### 用户需求
使 `cascade-compiler` 能够通过测试 `test_backend_tco.py`，即正确地将 `JUMP` 类型的边编译为物理图中的反馈通道。

### 评论
这是实现静态循环的关键逻辑。我们需要在 IR 模型中引入表达“跳转”和“分支”的词汇，并在后端将其翻译为“路由通道”。

### 目标
1.  修改 `cascade.spec.ir.models`，添加 `EdgeKind.JUMP` 和 `EdgeIR.case_key`。
2.  修改 `cascade.compiler.backend`，在构建过程中识别 JUMP 边，并生成对应的、带有 `tag_filter` 的 `ChannelDef`。

### 基本原理
为了支持数据流网络中的循环，我们不能仅依赖简单的 `Consumer <- Producer` 依赖关系。我们需要显式建模 `Producer -> Consumer` 的反馈路径。在 IR 层，这通过 `JUMP` 边表示。在物理层，这通过一个从 Producer 输出指向 Consumer **输入槽位** 的 Channel 表示，且该 Channel 通常带有非默认的 Tag 过滤器。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #comp/spec #scope/core #ai/instruct
#task/domain/compiler #task/object/tco-backend #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新 IR 模型 (Spec)

首先，我们扩展 IR 模型以支持 TCO 所需的元数据。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
class EdgeKind(str, Enum):
    DATA = "DATA"  # Standard data dependency
    CONTROL = "CONTROL"  # Conditional execution (run_if)


class ArgumentKind(str, Enum):
~~~~~
~~~~~python.new
class EdgeKind(str, Enum):
    DATA = "DATA"  # Standard data dependency
    CONTROL = "CONTROL"  # Conditional execution (run_if)
    JUMP = "JUMP"  # Control flow jump (recursion/loop)


class ArgumentKind(str, Enum):
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
@dataclass
class EdgeIR:
    source_node_instance_hash: str
    target_node_instance_hash: str
    target_arg: str
    kind: EdgeKind = EdgeKind.DATA


@dataclass
~~~~~
~~~~~python.new
@dataclass
class EdgeIR:
    source_node_instance_hash: str
    target_node_instance_hash: str
    target_arg: str
    kind: EdgeKind = EdgeKind.DATA
    case_key: Optional[str] = None


@dataclass
~~~~~

#### Acts 2: 更新编译器后端 (Backend)

现在我们修改 `_TopologyBuilder`。我们需要增加一个处理 JUMP 边的过程。对于每一个 JUMP 边，我们需要确保目标参数有一个对应的 DataNode（如果没有则创建），然后建立一个从源到该 DataNode 的 Channel。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import (
    BipartiteGraph,
    PhysicsFuncNode,
    PhysicsDataNode,
    ChannelDef,
)
~~~~~
~~~~~python.new
from cascade.spec.ir.models import GraphIR, EdgeKind
from cascade.spec.topology import (
    BipartiteGraph,
    PhysicsFuncNode,
    PhysicsDataNode,
    ChannelDef,
)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
        # Pass 2: Wire Inputs based on Edges (Dependencies)
        # This will OVERWRITE any literal inputs if an edge exists for the same arg
        # (Though IR shouldn't have both literal and edge for same arg)
        self._process_edges()

        return BipartiteGraph(
            func_nodes=self._func_nodes,
~~~~~
~~~~~python.new
        # Pass 2: Wire Inputs based on Edges (Dependencies)
        # This will OVERWRITE any literal inputs if an edge exists for the same arg
        # (Though IR shouldn't have both literal and edge for same arg)
        self._process_edges()

        # Pass 3: Wire Jumps (Feedback Loops)
        self._process_jumps()

        return BipartiteGraph(
            func_nodes=self._func_nodes,
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
    def _process_edges(self):
        for edge in self._graph.edges:
            # Source of the edge is a FuncNode (in IR)
            source_func_hash = edge.source_node_instance_hash
            target_func_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg

            # Find the DataNode produced by the source FuncNode
            source_data_hash = self._func_output_map.get(source_func_hash)
            
            if not source_data_hash:
                raise RuntimeError(f"Source node {source_func_hash} not found in output map")

            # Link: Target FuncNode input 'arg_name' <- Source DataNode
            target_func_node = self._func_nodes.get(target_func_hash)
            if target_func_node:
                target_func_node.inputs[arg_name] = source_data_hash

    def _compute_const_hash(self, value: Any) -> str:
~~~~~
~~~~~python.new
    def _process_edges(self):
        for edge in self._graph.edges:
            if edge.kind != EdgeKind.DATA:
                continue

            # Source of the edge is a FuncNode (in IR)
            source_func_hash = edge.source_node_instance_hash
            target_func_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg

            # Find the DataNode produced by the source FuncNode
            source_data_hash = self._func_output_map.get(source_func_hash)
            
            if not source_data_hash:
                raise RuntimeError(f"Source node {source_func_hash} not found in output map")

            # Link: Target FuncNode input 'arg_name' <- Source DataNode
            target_func_node = self._func_nodes.get(target_func_hash)
            if target_func_node:
                target_func_node.inputs[arg_name] = source_data_hash

    def _process_jumps(self):
        for edge in self._graph.edges:
            if edge.kind != EdgeKind.JUMP:
                continue

            # 1. Identify Source and Target
            source_func_hash = edge.source_node_instance_hash
            target_func_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg
            
            target_func_node = self._func_nodes.get(target_func_hash)
            if not target_func_node:
                raise RuntimeError(f"Target node {target_func_hash} for jump not found")

            # 2. Identify or Create the Target DataNode (Input Slot)
            # The target function needs a place to receive the jump data.
            # If it already has an input DataNode for this arg (from literals or data edges), we use it.
            # If not, we must create a new, dedicated input slot.
            
            if arg_name in target_func_node.inputs:
                target_data_hash = target_func_node.inputs[arg_name]
            else:
                # Create a new Input Slot DataNode
                # Naming convention: target_node_hash:input:arg_name
                target_data_hash = self._compute_data_slot_hash(target_func_hash, f"input_{arg_name}")
                
                # Check if it already exists (e.g. created by another Jump to same arg)
                if target_data_hash not in self._data_nodes:
                    d_node = PhysicsDataNode(
                        current_data_slot_hash=target_data_hash,
                        name=f"{target_func_node.name}.in.{arg_name}",
                        producer_node_instance_hash="external" # Marked as external/input
                    )
                    self._data_nodes[target_data_hash] = d_node
                
                # Wire it to the function input
                target_func_node.inputs[arg_name] = target_data_hash

            # 3. Create the Jump Channel
            # Source (Func Output) -> Channel (Filter) -> Target (Data Input)
            
            # Use the default "result" output of the source function
            # Future: IR might specify which output port to use
            
            tag = edge.case_key or "default"
            
            channel = ChannelDef(
                source_node_instance_hash=source_func_hash,
                target_data_slot_hash=target_data_hash,
                port_name="result",
                tag_filter=tag
            )
            self._channels.append(channel)

    def _compute_const_hash(self, value: Any) -> str:
~~~~~

### 下一步建议
我们已经完成了 Spec 和 Backend 的修改。现在 `test_backend_tco.py` 应该可以通过了。
建议运行测试以验证实现。如果通过，我们将完成阶段 3.4，并可以进入 **第四阶段 (Phase 4: Strategy Alignment)**，开始改造 `Engine` 和 `VMExecutionStrategy` 以驱动这个新的物理网络。
