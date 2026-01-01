**Task Breakdown**:
  1.  **Spec Upgrade**: Update `Channel` in `topology.py` to include `target_port`.
  2.  **Expander Upgrade**: Update `expander.py` to populate `target_port`.
  3.  **Reactor Refactor**: Rewrite `_fire` to handle Dict IO and Tag Filtering.
  4.  **Test Update**: Fix `test_ping_pong.py` and `test_reactor.py`.
  5.  **New Feature Verification**: Create `test_branching.py`.

  考虑到 `PingPong` 是基线，必须保证它绿。
  
  我们先创建 `test_branching.py`。

  **关于 `Worker` 的物理化**:
  为了让 `PingPong` 继续工作且符合新物理定律，我们需要一个 `adapt_worker` 装饰器或 wrapper，把 `(a, b) -> c` 转换成 `{'in': Token(a), 'in2': Token(b)} -> {'out': Token(c)}`。
  
  这可以放在 `cascade/vm/instructions/worker_adapter.py` 里？
  不，我们可以直接在 Reactor 里做一个简单的判断：如果函数返回的不是 Dict，假设它是 Single Output Payload，封装成 Default Token？
  **不，这样 Reactor 又有“魔法”了**。全对称物理场要求 Reactor 只有定律。
  所有的“魔法”应该在 `Compiler/Expander` 阶段处理（比如自动给 Worker 包一层 Adapter），或者在 `Instruction` 定义里处理。
  对于 `PingPong` 测试，我们手动包一下就好。

  Let's go.

好的，这是 **Phase 4.1: The Prism (棱镜)** 的实施计划。

本计划将通过核心重构，使 Cascade 的运行时引擎具备“光谱识别能力”，从而支持基于 Tag 的控制流分支。这将涉及 Spec、Compiler 和 VM 三个层面的协同升级。

## [WIP] feat(core): 实现物理通道的光谱过滤 (Channel Tag Filtering)

### 用户需求
实现白皮书中定义的“光谱过滤通道”。`Reactor` 在将令牌从上游节点传递到下游时，必须检查通道的 `tag_filter`。只有当令牌的 `tag` 与过滤条件匹配时，才允许通过，否则物理阻断。

### 评论
这是实现 `run_if`、`switch` 和 `retry` 逻辑的物理基础。目前的 `Reactor` 盲目转发所有令牌，无法支持条件执行。此次重构还将规范化物理节点的 I/O 协议，强制所有物理交互都通过具名端口 (`port`) 和 `Token` 字典进行。

### 目标
1.  **Spec 升级**: 为 `Channel` 增加 `target_port` 字段，以支持多输入端口的精确连接。
2.  **VM 重构**: 改造 `Reactor` 以支持基于端口的 I/O 映射和 Tag 过滤。
3.  **Compiler 适配**: 更新 `Expander` 以填充新的 `Channel` 字段。
4.  **验证**: 通过 `test_branching.py` 验证分支逻辑，并修复受影响的 `PingPong` 测试。

### 基本原理
全对称物理场要求 `Reactor` 是无业务逻辑的。所有的控制流（如“如果是 error 则重试”）都必须物化为拓扑结构（“只有 tag=error 才能通过这条回环通道”）。因此，`Channel` 必须携带过滤逻辑，且 `Reactor` 必须严格执行它。此外，为了让 `Reactor` 正确组装 `inputs` 字典，`Channel` 必须明确指出它连接到了目标节点的哪个端口。

### 标签
#intent/build #flow/ready #priority/high #comp/vm #comp/spec #concept/control-flow #scope/core #ai/instruct #task/domain/core #task/object/channel-filter #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: Spec 升级 - 增加目标端口定义

我们需要在拓扑层明确连接的终点端口，这是 Reactor 正确组装输入参数的前提。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
    target_node_id: str
    """
    The ID of the downstream node.
    Note: In a bipartite graph, if Source is Func, Target MUST be Data.
    """

    tag_filter: Optional[str] = None
~~~~~
~~~~~python.new
    target_node_id: str
    """
    The ID of the downstream node.
    Note: In a bipartite graph, if Source is Func, Target MUST be Data.
    """

    target_port: str = "in"
    """
    The name of the input port on the target node.
    For DataNodes, this is typically 'in'. For FuncNodes, it matches the argument name.
    """

    tag_filter: Optional[str] = None
~~~~~

#### Acts 2: Compiler 适配 - 填充目标端口

更新 `Expander`，在生成物理图时显式指定连接的端口。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # Path 1: Execution Flow
        # F_pre -> D_worker_in
        channels.append(Channel(f_pre_id, "worker_input", d_worker_in_id))
        # D_worker_in -> F_worker
        channels.append(
            Channel(d_worker_in_id, "out", f_worker_id)
        )  # Implicit 'out' for DataNode source
        # F_worker -> D_worker_out
        channels.append(Channel(f_worker_id, "worker_result", d_worker_out_id))
        # D_worker_out -> F_post
        channels.append(Channel(d_worker_out_id, "out", f_post_id))

        # Path 2: Trace Bypass
        # F_pre -> D_trace
        channels.append(Channel(f_pre_id, "trace_output", d_trace_id))
        # D_trace -> F_post
        channels.append(Channel(d_trace_id, "out", f_post_id))
~~~~~
~~~~~python.new
        # Path 1: Execution Flow
        # F_pre -> D_worker_in
        channels.append(
            Channel(
                source_node_id=f_pre_id,
                source_port="worker_input",
                target_node_id=d_worker_in_id,
                target_port="in",
            )
        )
        # D_worker_in -> F_worker
        channels.append(
            Channel(
                source_node_id=d_worker_in_id,
                source_port="out",
                target_node_id=f_worker_id,
                target_port="worker_input",
            )
        )
        # F_worker -> D_worker_out
        channels.append(
            Channel(
                source_node_id=f_worker_id,
                source_port="worker_result",
                target_node_id=d_worker_out_id,
                target_port="in",
            )
        )
        # D_worker_out -> F_post
        channels.append(
            Channel(
                source_node_id=d_worker_out_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port="worker_result",
            )
        )

        # Path 2: Trace Bypass
        # F_pre -> D_trace
        channels.append(
            Channel(
                source_node_id=f_pre_id,
                source_port="trace_output",
                target_node_id=d_trace_id,
                target_port="in",
            )
        )
        # D_trace -> F_post
        channels.append(
            Channel(
                source_node_id=d_trace_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port="trace_input",
            )
        )
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
            # F_pre (start) -> D_life
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.bleacher.id,
                    source_port="obs_output",
                    target_node_id=d_life.id,
                )
            )
            # F_post (end) -> D_life
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.stainer.id,
                    source_port="obs_output",
                    target_node_id=d_life.id,
                )
            )
~~~~~
~~~~~python.new
            # F_pre (start) -> D_life
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.bleacher.id,
                    source_port="obs_output",
                    target_node_id=d_life.id,
                    target_port="event_token",
                )
            )
            # F_post (end) -> D_life
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.stainer.id,
                    source_port="obs_output",
                    target_node_id=d_life.id,
                    target_port="event_token",
                )
            )
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
                    # Connect: Source.Stainer -> Target.Bleacher
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=target_subgraph.bleacher.id,
                            # Note: The target port is implicitly the 'arg_name',
                            # which the Bleacher is designed to handle.
                        )
                    )
~~~~~
~~~~~python.new
                    # Connect: Source.Stainer -> Target.Bleacher
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )
~~~~~

#### Acts 3: VM 重构 - 核心光谱过滤逻辑

这是最关键的改动。我们将重写 `Reactor` 的 `__init__` 和 `_fire`，使其支持多端口 IO 和 Tag 过滤。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python
import asyncio
from typing import List, Callable, Dict, Tuple
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor


class Reactor:
    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        executor: PhysicsExecutor,
        function_map: Dict[str, Callable],
    ):
        self.graph = graph
        self.memory = memory
        self.executor = executor
        self.function_map = function_map

        # Indexing for O(1) lookups during step/fire
        self._func_nodes: List[PhysicsFuncNode] = []
        # node_id -> List[(source_data_node_id, target_port_name)]
        self._func_inputs: Dict[str, List[Tuple[str, str]]] = {}
        # node_id -> List[Channel]
        self._outbound_channels: Dict[str, List[Channel]] = {}

        # 1. Identify Function Nodes
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsFuncNode):
                self._func_nodes.append(node)
                self._func_inputs[node.id] = []
                self._outbound_channels[node.id] = []

        # 2. Build Connectivity Index
        for channel in self.graph.channels:
            source = self.graph.nodes.get(channel.source_node_id)
            target = self.graph.nodes.get(channel.target_node_id)

            if not source or not target:
                continue

            # Case A: Data -> Func (Input wiring)
            if isinstance(source, PhysicsDataNode) and isinstance(
                target, PhysicsFuncNode
            ):
                # Record that Target(F) needs input from Source(D) on specific Port
                self._func_inputs[target.id].append((source.id, channel.target_port))

            # Case B: Func -> Data (Output wiring)
            elif isinstance(source, PhysicsFuncNode) and isinstance(
                target, PhysicsDataNode
            ):
                # Record the full channel to support filtering logic later
                self._outbound_channels[source.id].append(channel)

    async def step(self) -> int:
        ready_nodes: List[PhysicsFuncNode] = []

        for f_node in self._func_nodes:
            inputs = self._func_inputs.get(f_node.id, [])

            # Full-Input Firing Rule: All connected input slots must be excited.
            if not inputs:
                continue

            # Check if all source DataNodes have tokens
            is_ready = all(
                self.memory.is_excited(src_id) for src_id, _ in inputs
            )

            if is_ready:
                ready_nodes.append(f_node)

        if not ready_nodes:
            return 0

        # Fire all ready nodes in parallel
        await asyncio.gather(*(self._fire(node) for node in ready_nodes))

        return len(ready_nodes)

    async def _fire(self, node: PhysicsFuncNode) -> None:
        # 1. Atomic Consumption (Hydration)
        # We must pull tokens from memory and map them to the function's expected argument names (ports).
        input_data: Dict[str, Token] = {}
        inputs = self._func_inputs.get(node.id, [])
        
        for src_id, target_port in inputs:
            token = self.memory.take(src_id)
            input_data[target_port] = token

        # 2. Execution
        func = self.function_map.get(node.id)
        if not func:
            raise ValueError(f"No function mapped for node {node.id}")

        # The contract is now strict: FuncNodes must accept Dict[str, Token] and return Dict[str, Token]
        result_tokens: Dict[str, Token] = await self.executor.submit(func, (input_data,))

        if not isinstance(result_tokens, dict):
             raise ValueError(f"Function for node {node.id} must return a Dict[str, Token], got {type(result_tokens)}")

        # 3. Emission & Spectrum Filtering
        outbound = self._outbound_channels.get(node.id, [])
        
        for channel in outbound:
            # Locate the token produced for this specific source port
            token = result_tokens.get(channel.source_port)
            
            if token is None:
                # It is legal for a node NOT to emit on a declared port (e.g. conditional output)
                continue

            # --- THE PRISM: Spectrum Filtering ---
            if channel.tag_filter and channel.tag_filter != token.tag:
                # Physics Block: The token's color (tag) does not match the channel's filter.
                continue
            # -------------------------------------

            # Transport to target DataNode
            target_node = self.graph.nodes[channel.target_node_id]
            if isinstance(target_node, PhysicsDataNode):
                self.memory.put(target_node, token)
~~~~~

#### Acts 4: 测试更新 - 适配新协议

`test_ping_pong.py` 和 `test_reactor.py` 必须升级，因为现在 `Reactor` 强制要求输入/输出都是字典。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ping_pong.py
~~~~~
~~~~~python.old
def simple_increment(val: int) -> int:
    return val + 1
~~~~~
~~~~~python.new
def simple_increment(inputs: Dict[str, Token]) -> Dict[str, Token]:
    # Extract
    in_token = inputs["value"]
    val = in_token.payload
    
    # Process
    res = val + 1
    
    # Wrap
    return {"result": Token(payload=res)}
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ping_pong.py
~~~~~
~~~~~python.old
    # D1 -> F1
    graph.channels.append(
        Channel(source_node_id=d1.id, source_port="value", target_node_id=f1.id)
    )
    # F1 -> D2
    graph.channels.append(
        Channel(source_node_id=f1.id, source_port="result", target_node_id=d2.id)
    )
~~~~~
~~~~~python.new
    # D1 -> F1 (Explicit target port 'value')
    graph.channels.append(
        Channel(
            source_node_id=d1.id, 
            source_port="out", 
            target_node_id=f1.id, 
            target_port="value"
        )
    )
    # F1 -> D2
    graph.channels.append(
        Channel(
            source_node_id=f1.id, 
            source_port="result", 
            target_node_id=d2.id,
            target_port="in"
        )
    )
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
# Dummy function for testing
def noop(*args):
    return "result"
~~~~~
~~~~~python.new
# Dummy function for testing
def noop(inputs):
    # Echos back a generic result token on 'out' port
    return {"out": Token(payload="result")}
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
    # Connect D1 -> F1
    channel = Channel(source_node_id=d1.id, source_port="out", target_node_id=f1.id)
    graph.channels.append(channel)
~~~~~
~~~~~python.new
    # Connect D1 -> F1
    channel = Channel(source_node_id=d1.id, source_port="out", target_node_id=f1.id, target_port="in")
    graph.channels.append(channel)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
    # D1 -> F1
    graph.channels.append(Channel(d1.id, "out", f1.id))
    # D2 -> F1
    graph.channels.append(Channel(d2.id, "out", f1.id))
~~~~~
~~~~~python.new
    # D1 -> F1
    graph.channels.append(Channel(d1.id, "out", f1.id, target_port="in1"))
    # D2 -> F1
    graph.channels.append(Channel(d2.id, "out", f1.id, target_port="in2"))
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
    graph.channels.append(Channel(d1.id, "out", f1.id))
    graph.channels.append(Channel(d2.id, "out", f2.id))
~~~~~
~~~~~python.new
    graph.channels.append(Channel(d1.id, "out", f1.id, target_port="in"))
    graph.channels.append(Channel(d2.id, "out", f2.id, target_port="in"))
~~~~~

#### Acts 5: 功能验证 - 分支测试

最后，我们创建一个专门的测试用例来验证光谱过滤（Tag Filtering）是否生效。

~~~~~act
write_file
packages/cascade-vm/tests/integration/test_branching.py
~~~~~
~~~~~python
import pytest
from typing import Dict, Any

from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor


def switch_logic(inputs: Dict[str, Token]) -> Dict[str, Token]:
    """
    A logical switch.
    Input payload 'path_a' -> Tag 'A'
    Input payload 'path_b' -> Tag 'B'
    """
    in_token = inputs["in"]
    direction = in_token.payload
    
    if direction == "path_a":
        return {"out": Token(payload="Data A", tag="A")}
    else:
        return {"out": Token(payload="Data B", tag="B")}


@pytest.fixture
def branching_topology():
    # D_in -> Switch -> (D_A, D_B)
    d_in = PhysicsDataNode(id="D_in", name="Input")
    f_sw = PhysicsFuncNode(id="Switch", name="SwitchNode")
    d_a = PhysicsDataNode(id="D_A", name="Branch A")
    d_b = PhysicsDataNode(id="D_B", name="Branch B")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_in, f_sw, d_a, d_b]}

    # Wiring
    # D_in -> Switch
    graph.channels.append(
        Channel(d_in.id, "out", f_sw.id, target_port="in")
    )
    
    # Switch -> D_A (Only allows Tag 'A')
    graph.channels.append(
        Channel(f_sw.id, "out", d_a.id, target_port="in", tag_filter="A")
    )
    
    # Switch -> D_B (Only allows Tag 'B')
    graph.channels.append(
        Channel(f_sw.id, "out", d_b.id, target_port="in", tag_filter="B")
    )

    func_map = {f_sw.id: switch_logic}
    
    return graph, d_in, d_a, d_b, func_map


@pytest.mark.asyncio
async def test_branching_path_a(branching_topology):
    graph, d_in, d_a, d_b, func_map = branching_topology
    
    memory = VolatileMemory()
    reactor = Reactor(graph, memory, PhysicsExecutor(), func_map)

    # 1. Inject signal for Path A
    memory.put(d_in, Token(payload="path_a"))

    # 2. Run
    await reactor.step()

    # 3. Assert
    # D_A should receive token
    assert memory.get_count(d_a.id) == 1
    assert memory.take(d_a.id).payload == "Data A"
    
    # D_B should be empty (physically blocked)
    assert memory.get_count(d_b.id) == 0


@pytest.mark.asyncio
async def test_branching_path_b(branching_topology):
    graph, d_in, d_a, d_b, func_map = branching_topology
    
    memory = VolatileMemory()
    reactor = Reactor(graph, memory, PhysicsExecutor(), func_map)

    # 1. Inject signal for Path B
    memory.put(d_in, Token(payload="path_b"))

    # 2. Run
    await reactor.step()

    # 3. Assert
    # D_B should receive token
    assert memory.get_count(d_b.id) == 1
    assert memory.take(d_b.id).payload == "Data B"
    
    # D_A should be empty
    assert memory.get_count(d_a.id) == 0
~~~~~

### 下一步建议
我们已经赋予了物理场“辨色能力”。下一步，我们将进入 **Phase 4.2: The Loop (环路)**，利用这一能力来实现资源管理和重试逻辑。这涉及到引入全局资源槽 ($D_{res}$) 并通过 Reactor 的初始化逻辑进行预填充。

此外，当前的 `WorkerWrapper` 是手动模拟的。未来应当在 `cascade-compiler` 中实现一个自动装配机制，将用户的纯函数自动包装成符合物理协议的 `Dict[str, Token]` 接口。
