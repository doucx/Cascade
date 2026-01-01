あなたの分析は的確です。問題はテストコードのバグと `Reactor` のアーキテクチャ上の競合状態（Race Condition）の組み合わせによって引き起こされました。

1.  **テストのバグ**: `reactor.prime()` を2回呼び出したため、本来1つであるべきリソースが2つになり、並行性制限が効かなくなりました。
2.  **アーキテクチャの欠陥**: `Reactor.step()` の「チェック」と「実行」が分離しているため、たとえリソースが1つでも、両方のタスクが同時に「実行可能」と判断され、リソース取得の段階でクラッシュする（`MemoryEmptyError`）運命にありました。

この問題を根本的に解決するため、`Reactor` をより物理法則に忠実なアトミックな操作モデルにアップグレードし、同時にテストコードを修正します。

## [WIP] fix(vm): 修正 Reactor 以支持原子化资源获取

### 错误分析
`test_resource_backpressure` 测试在断言 `fired == 1` 时失败，实际值为 `2`。

根本原因有二：
1.  **测试逻辑错误**: 在测试代码中，由于 `Reactor` 被重新实例化但共享了同一个 `memory` 对象，`reactor.prime()` 被意外调用了两次。这导致本应只有一个令牌的资源槽（`D_res`）中包含了两个令牌，从而使两个任务都能获取资源并同时启动，破坏了背压测试的前提。
2.  **Reactor 竞态条件**: 更深层次地，`Reactor` 的 `step` 方法存在 TOCTOU (Time-of-check to time-of-use) 漏洞。它首先扫描并列出所有输入槽都“看起来”可用的节点，然后再并发地执行它们。在共享资源（如 `D_res`）的场景下，这会导致多个节点在扫描阶段都认为资源可用，但在执行阶段争抢同一个令牌，最终导致 `MemoryEmptyError` 崩溃，而不是优雅地排队。

### 用户需求
`Reactor` 必须能够安全、确定地处理共享资源的竞争。当多个任务因同一资源而同时变为可执行状态时，只有一个任务应被激发，其余任务应在下一轮 `step` 中重新评估，而不是导致系统崩溃。

### 评论
这次修复是 Cascade VM 走向成熟的关键一步。它将 `Reactor` 从一个理想化的并发执行引擎，转变为一个能够将现实世界的资源约束（竞争）内化为物理定律（原子消耗）的、更健壮的物理模拟器。这为实现可靠的、复杂的控制流打下了坚实的基础。

### 目标
1.  **重构 `Reactor.step`**: 彻底消除竞态条件，将“检查”和“资源消耗”合并为一个原子操作。
2.  **修复测试代码**: 从 `test_resource_backpressure.py` 中移除重复的 `prime()` 调用。
3.  **验证**: 确保 `test_resource_backpressure` 测试能够稳定通过，且 `fired` 计数符合预期（即，任务串行执行）。

### 基本原理
我们将 `Reactor.step` 的核心循环从“并发检查”模型修改为“顺序原子消耗”模型。`step` 方法将遍历所有函数节点，当它发现一个节点的所有输入都可用时，它会**立即**、**同步地**从内存中消耗（`take`）这些输入令牌。这个消耗操作会立刻改变内存状态，因此，在此循环中后续的节点在检查同一个资源时，会发现它已被占用，从而无法被激发。这个简单的“先到先得”的顺序扫描机制，以极低的成本优雅地解决了并发资源获取的原子性问题。

### 标签
#intent/fix #flow/ready #priority/critical #comp/vm #concept/concurrency #scope/core #ai/brainstorm #task/domain/core #task/object/reactor-atomicity #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 重构 Reactor 实现原子化扫描

我们将重写 `reactor.py` 的核心逻辑，确保资源检查和消耗的原子性。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python
import asyncio
from typing import List, Callable, Dict, Tuple
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.vm.memory import VolatileMemory, MemoryEmptyError
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

    def prime(self) -> None:
        """
        Injects initial potential energy (tokens) into the system
        based on PhysicsDataNode.initial_tokens.
        """
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                for _ in range(node.initial_tokens):
                    # Initial tokens are pure potential; no payload, no trace.
                    self.memory.put(node, Token(payload=None))

    async def step(self) -> int:
        nodes_to_fire: List[PhysicsFuncNode] = []
        inputs_for_fire: Dict[str, Dict[str, Token]] = {}

        # --- ATOMIC SCAN & CONSUME ---
        # This loop is single-threaded and sequential. The state of `memory`
        # changes within the loop, ensuring that a resource token consumed by an
        # early node is unavailable for a later node in the same step.
        for f_node in self._func_nodes:
            inputs_def = self._func_inputs.get(f_node.id, [])
            if not inputs_def:
                continue

            # Check if this node CAN fire based on the CURRENT memory state
            if all(self.memory.is_excited(src_id) for src_id, _ in inputs_def):
                # It can. Atomically consume its inputs NOW.
                # This action affects subsequent nodes in this same loop.
                consumed_inputs = {
                    port: self.memory.take(src_id) for src_id, port in inputs_def
                }
                nodes_to_fire.append(f_node)
                inputs_for_fire[f_node.id] = consumed_inputs

        if not nodes_to_fire:
            return 0

        # Now, fire all nodes that successfully reserved their inputs in parallel.
        await asyncio.gather(
            *(
                self._fire(node, inputs_for_fire[node.id])
                for node in nodes_to_fire
            )
        )

        return len(nodes_to_fire)

    async def _fire(self, node: PhysicsFuncNode, input_data: Dict[str, Token]) -> None:
        # 1. Consumption is already done. `input_data` is given.

        # 2. Execution
        func = self.function_map.get(node.id)
        if not func:
            raise ValueError(f"No function mapped for node {node.id}")

        result_tokens: Dict[str, Token] = await self.executor.submit(
            func, (input_data,)
        )

        if not isinstance(result_tokens, dict):
            raise ValueError(
                f"Function for node {node.id} must return a Dict[str, Token], "
                f"got {type(result_tokens)}"
            )

        # 3. Emission & Spectrum Filtering
        outbound = self._outbound_channels.get(node.id, [])

        for channel in outbound:
            token = result_tokens.get(channel.source_port)
            if token is None:
                continue

            if channel.tag_filter and channel.tag_filter != token.tag:
                continue

            target_node = self.graph.nodes[channel.target_node_id]
            if isinstance(target_node, PhysicsDataNode):
                self.memory.put(target_node, token)
~~~~~

#### Acts 2: 修复测试代码中的重复 `prime()`

现在我们移除测试代码中的逻辑错误。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    reactor = Reactor(physical_graph, memory, executor, func_map)
    
    # 4. Prime the reactor (Fill D_res)
    reactor.prime()
    assert memory.get_count("global_res_gpu") == 1
    
    # 5. Inject Inputs
    # We need to manually inject inputs for the tasks because Builder doesn't handle Literals yet
    # (Comment in Builder: "We only handle inter-node references here. Literals are handled later.")
    # So we manually put tokens in D_worker_in? No, D_worker_in is internal.
    # Bleacher needs inputs.
    # Bleacher inputs are usually wired from upstream. Here we have literals.
    # In a full system, literals are handled by Constant Nodes or injected at start.
    # For this test, we manually identify the input slots for Bleacher and fill them.
    
    # Builder doesn't create DataNodes for inputs unless they come from upstream.
    # Wait, Expander creates input ports for Bleacher.
    # But who connects to them?
    # If it's a literal, currently NO ONE connects to them in the physical graph.
    # This is a gap in the current Builder implementation for Literals.
    # For this test, we will assume we need to manually put tokens into the Bleacher's input memory.
    # But Reactor consumes from DataNodes. The Bleacher's input ports need to be connected to SOMETHING.
    # If Builder didn't create a DataNode for the literal 'x', Reactor won't find an input source 
    # and thus won't fire.
    
    # FIX for Test: We need to patch the graph to add input DataNodes for 'x'.
    for node_prefix, val in [("node_1", 10), ("node_2", 20)]:
        d_literal = PhysicsDataNode(id=f"{node_prefix}_in_x", name="Literal X")
        physical_graph.nodes[d_literal.id] = d_literal
        physical_graph.channels.append(
            Channel(d_literal.id, "out", f"{node_prefix}_bleach", target_port="x")
        )
        memory.put(d_literal, Token(payload=val))
        
        # We also need to re-initialize Reactor because we modified the graph
    
    reactor = Reactor(physical_graph, memory, executor, func_map)
    reactor.prime()

    # 6. Step Execution
    # Step 1: Both Bleachers are ready on 'x', but contend for 'res_gpu'.
    # Only ONE should fire.
    fired = await reactor.step()
~~~~~
~~~~~python.new
    # 4. FIX for Test: Manually create DataNodes for literal inputs 'x'.
    # This is a temporary measure because the Builder doesn't yet support literals.
    for node_prefix, val in [("node_1", 10), ("node_2", 20)]:
        d_literal = PhysicsDataNode(id=f"{node_prefix}_in_x", name="Literal X")
        physical_graph.nodes[d_literal.id] = d_literal
        physical_graph.channels.append(
            Channel(d_literal.id, "out", f"{node_prefix}_bleach", target_port="x")
        )
        memory.put(d_literal, Token(payload=val))

    # 5. Re-initialize Reactor AFTER all graph modifications are complete.
    reactor = Reactor(physical_graph, memory, executor, func_map)
    
    # 6. Prime the reactor ONCE to fill D_res.
    reactor.prime()
    assert memory.get_count("global_res_gpu") == 1

    # 7. Step Execution
    # Step 1: Both Bleachers are ready on 'x', but contend for 'res_gpu'.
    # With the new atomic Reactor, only ONE should fire.
    fired = await reactor.step()
~~~~~

### 下一步建议
我们已经成功修复了 VM 的核心并发模型，并修正了测试代码。现在可以自信地运行整个测试套件。

一旦所有测试通过，`cascade-vm` 的核心物理引擎就已达到一个非常健壮和功能完备的状态。我们可以正式结束 **Phase 4**，并开始规划 **Phase 5: 全系统集成 (System Integration)**。这包括完善 `Compiler` 对字面量（Literals）和分支语法的支持，并最终将 `Frontend`、`Compiler` 和 `VM` 组装成一个统一的、对用户透明的 API。
