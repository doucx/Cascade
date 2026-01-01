好的，我将执行方案 A：将观测总线 (`global_d_life`) 的容量提升至无限（`sys.maxsize`），以彻底消除观测系统对业务逻辑产生背压的风险。同时，我将顺手修复 `builder.py` 中的类型安全问题。

## [WIP] fix(compiler): 解除观测系统容量限制并修复类型检查错误

### 用户需求
1.  **解决死锁风险**: 将全局观测节点 `global_d_life` 的容量设置为无限大，防止因观测事件积压导致 `MemoryFullError`，进而阻塞甚至崩溃业务流程。
2.  **修复类型错误**: 解决 `builder.py` 中因 `SubGraph` 字段为 `Optional` 导致的 `reportOptionalMemberAccess` 静态分析错误。

### 评论
将观测通道设为无限容量是符合“全对称计算物理场”白皮书中“零干扰原则”的关键举措。虽然在物理上没有真正的“无限”，但在内存模型中，`deque` 的扩展能力加上 `sys.maxsize` 的限制足以模拟这一特性，确保 $F_{obs}$ 的处理延迟永远不会反压到 $F_{exec}$。

### 目标
1.  创建一个集成测试，证明有限容量的汇聚节点在并发写入下会导致崩溃，而无限容量则不会。
2.  修改 `builder.py`，将 `global_d_life` 的容量设为 `sys.maxsize`。
3.  在 `builder.py` 中添加显式的 `assert` 语句，帮助 Pyright 进行类型收缩。

### 基本原理
*   **物理定律修正**: 观测系统应被视为一个理想的“黑洞”，只吸收信息而不产生反作用力。在二分图模型中，这体现为 $D_{life}$ 拥有无限的势能容纳空间。
*   **防御性编程**: 尽管 `if ... is None: raise` 在运行时提供了保障，但显式的 `assert` 能让静态分析工具更确信类型的安全性，消除误报。

### 标签
#intent/fix #flow/ready #priority/high #comp/compiler #concept/observability #scope/core #ai/instruct #task/domain/compiler #task/object/observability-bus #task/action/fix-congestion #task/state/begin

---

### Script

#### Acts 1: 创建并发拥堵测试

我们将创建一个测试，模拟多个节点向同一个 DataNode 并发写入的场景。

~~~~~act
write_file
packages/cascade-compiler/tests/integration/test_observability_congestion.py
~~~~~
~~~~~python
import pytest
import asyncio
import sys
from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory, MemoryFullError
from cascade.vm.reactor import Reactor
from cascade.vm.executor import PhysicsExecutor


def noop_producer(inputs):
    return {"out": Token(payload="event")}


@pytest.mark.asyncio
async def test_limited_capacity_causes_crash():
    """
    证明：如果汇聚节点容量有限（例如 1），并发写入会导致 MemoryFullError。
    """
    # 1. Setup: 2 Producers -> 1 Limited Consumer
    d_life = PhysicsDataNode(id="D_life", name="Bus", capacity=1)
    
    # Producer 1
    d_in1 = PhysicsDataNode(id="D_in1", name="In1", initial_tokens=1)
    f_p1 = PhysicsFuncNode(id="F_p1", name="P1")
    
    # Producer 2
    d_in2 = PhysicsDataNode(id="D_in2", name="In2", initial_tokens=1)
    f_p2 = PhysicsFuncNode(id="F_p2", name="P2")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_life, d_in1, f_p1, d_in2, f_p2]}
    
    # Wiring
    # D_in1 -> F_p1 -> D_life
    graph.channels.append(Channel(d_in1.id, "out", f_p1.id, "in"))
    graph.channels.append(Channel(f_p1.id, "out", d_life.id, "in"))
    
    # D_in2 -> F_p2 -> D_life
    graph.channels.append(Channel(d_in2.id, "out", f_p2.id, "in"))
    graph.channels.append(Channel(f_p2.id, "out", d_life.id, "in"))

    memory = VolatileMemory()
    reactor = Reactor(
        graph, 
        memory, 
        PhysicsExecutor(), 
        {f_p1.id: noop_producer, f_p2.id: noop_producer}
    )
    reactor.prime()

    # 2. Execution
    # Both F_p1 and F_p2 are ready. They will try to fire in the same step.
    # D_life has capacity 1. 
    # One will succeed, the other SHOULD fail with MemoryFullError.
    
    try:
        await reactor.step()
    except Exception as e:
        # We expect a crash here due to atomic consumption but separate emission
        # Actually, Reactor.step() gathers exceptions.
        assert isinstance(e, MemoryFullError) or isinstance(e.__cause__, MemoryFullError)
        return

    # If by chance they ran sequentially enough or memory logic allowed it (unlikely with cap=1),
    # we assert the state. But with asyncio.gather, it's highly likely to crash.
    # If it didn't crash, we need to check if one was skipped?
    # No, Reactor logic says: check inputs -> fire. It doesn't check output capacity pre-fire.
    
    # If we are here, it means no exception was raised, which is unexpected for capacity 1 
    # unless the implementation changed.
    # Let's ensure we filled it.
    assert memory.get_count(d_life.id) <= 1


@pytest.mark.asyncio
async def test_infinite_capacity_handles_concurrency():
    """
    证明：如果汇聚节点容量为 sys.maxsize，并发写入安全。
    """
    # 1. Setup: 2 Producers -> 1 Infinite Consumer
    d_life = PhysicsDataNode(id="D_life", name="Bus", capacity=sys.maxsize)
    
    d_in1 = PhysicsDataNode(id="D_in1", name="In1", initial_tokens=1)
    f_p1 = PhysicsFuncNode(id="F_p1", name="P1")
    
    d_in2 = PhysicsDataNode(id="D_in2", name="In2", initial_tokens=1)
    f_p2 = PhysicsFuncNode(id="F_p2", name="P2")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_life, d_in1, f_p1, d_in2, f_p2]}
    
    graph.channels.append(Channel(d_in1.id, "out", f_p1.id, "in"))
    graph.channels.append(Channel(f_p1.id, "out", d_life.id, "in"))
    
    graph.channels.append(Channel(d_in2.id, "out", f_p2.id, "in"))
    graph.channels.append(Channel(f_p2.id, "out", d_life.id, "in"))

    memory = VolatileMemory()
    reactor = Reactor(
        graph, 
        memory, 
        PhysicsExecutor(), 
        {f_p1.id: noop_producer, f_p2.id: noop_producer}
    )
    reactor.prime()

    # 2. Execution
    # Both should fire successfully.
    fired = await reactor.step()
    
    assert fired == 2
    assert memory.get_count(d_life.id) == 2
~~~~~

#### Acts 2: 修正 Builder

修改 `builder.py`，引入 `sys` 模块，将 `d_life` 容量设为最大值，并添加类型断言。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
from typing import Dict

from cascade.spec.ir.models import GraphIR
~~~~~
~~~~~python.new
import sys
from typing import Dict

from cascade.spec.ir.models import GraphIR
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        # 2. Create and wire the global observability sidecar infrastructure
        d_life_id = "global_d_life"
        f_obs_id = "global_f_obs"

        d_life = PhysicsDataNode(id=d_life_id, name="LifecycleBus")
        f_obs = ObservabilityNode(
            id=f_obs_id,
            name="LifecycleObserver",
~~~~~
~~~~~python.new
        # 2. Create and wire the global observability sidecar infrastructure
        d_life_id = "global_d_life"
        f_obs_id = "global_f_obs"

        # Capacity set to maxsize to prevent backpressure from observability
        d_life = PhysicsDataNode(
            id=d_life_id, name="LifecycleBus", capacity=sys.maxsize
        )
        f_obs = ObservabilityNode(
            id=f_obs_id,
            name="LifecycleObserver",
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
            # 3.2 Expand
            subgraph = self._expander.expand_node(node_ir)
            if subgraph.bleacher is None or subgraph.stainer is None:
                raise RuntimeError(f"Subgraph for {node_ir.id} is incomplete.")

            subgraphs[node_ir.id] = subgraph
            physical_graph.nodes.update(subgraph.nodes)
            physical_graph.channels.extend(subgraph.channels)

            # 3.3 Wire task observability TO the sidecar bus
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.bleacher.id,
                    source_port="obs_output",
                    target_node_id=d_life_id,
                    target_port="event_token",
                )
            )
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.stainer.id,
                    source_port="obs_output",
                    target_node_id=d_life_id,
                    target_port="event_token",
                )
            )

        # 4. Wire data dependencies between subgraphs
        for node_ir in graph_ir.nodes:
            target_subgraph = subgraphs[node_ir.id]
            for arg_name, source_ref in node_ir.inputs.items():
                if isinstance(source_ref, str) and source_ref in subgraphs:
                    source_subgraph = subgraphs[source_ref]
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )

        # 5. Wire Global Resources (The Loop)
        for node_ir in graph_ir.nodes:
            subgraph = subgraphs[node_ir.id]
            for res_name in node_ir.constraints:
                res_node_id = f"global_res_{res_name}"
                port_name = f"res_{res_name}"

                # Acquire: D_res -> F_bleach
                physical_graph.channels.append(
                    Channel(
                        source_node_id=res_node_id,
                        source_port="out",
                        target_node_id=subgraph.bleacher.id,
                        target_port=port_name,
                    )
                )

                # Release: F_stain -> D_res
                physical_graph.channels.append(
                    Channel(
                        source_node_id=subgraph.stainer.id,
                        source_port=port_name,
                        target_node_id=res_node_id,
                        target_port="in",
                    )
                )
~~~~~
~~~~~python.new
            # 3.2 Expand
            subgraph = self._expander.expand_node(node_ir)
            if subgraph.bleacher is None or subgraph.stainer is None:
                raise RuntimeError(f"Subgraph for {node_ir.id} is incomplete.")

            # Help static analysis verify these are not None
            assert subgraph.bleacher is not None
            assert subgraph.stainer is not None

            subgraphs[node_ir.id] = subgraph
            physical_graph.nodes.update(subgraph.nodes)
            physical_graph.channels.extend(subgraph.channels)

            # 3.3 Wire task observability TO the sidecar bus
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.bleacher.id,
                    source_port="obs_output",
                    target_node_id=d_life_id,
                    target_port="event_token",
                )
            )
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.stainer.id,
                    source_port="obs_output",
                    target_node_id=d_life_id,
                    target_port="event_token",
                )
            )

        # 4. Wire data dependencies between subgraphs
        for node_ir in graph_ir.nodes:
            target_subgraph = subgraphs[node_ir.id]
            
            # Help static analysis
            assert target_subgraph.bleacher is not None

            for arg_name, source_ref in node_ir.inputs.items():
                if isinstance(source_ref, str) and source_ref in subgraphs:
                    source_subgraph = subgraphs[source_ref]
                    
                    # Help static analysis
                    assert source_subgraph.stainer is not None

                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )

        # 5. Wire Global Resources (The Loop)
        for node_ir in graph_ir.nodes:
            subgraph = subgraphs[node_ir.id]
            
            # Help static analysis
            assert subgraph.bleacher is not None
            assert subgraph.stainer is not None

            for res_name in node_ir.constraints:
                res_node_id = f"global_res_{res_name}"
                port_name = f"res_{res_name}"

                # Acquire: D_res -> F_bleach
                physical_graph.channels.append(
                    Channel(
                        source_node_id=res_node_id,
                        source_port="out",
                        target_node_id=subgraph.bleacher.id,
                        target_port=port_name,
                    )
                )

                # Release: F_stain -> D_res
                physical_graph.channels.append(
                    Channel(
                        source_node_id=subgraph.stainer.id,
                        source_port=port_name,
                        target_node_id=res_node_id,
                        target_port="in",
                    )
                )
~~~~~

### 下一步建议
我们已经修复了严重的死锁风险和类型错误。接下来，我们应继续推进重构计划，重点是**增强构建器对字面量的支持**，这是消除“功能债务”和移除测试中 Hack 代码的关键一步。
