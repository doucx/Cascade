## [WIP] refactor(tests): 修复异步 Reactor 导致的测试同步问题

### 错误分析
在将 `Reactor` 升级为异步非阻塞模式后，原有的单元测试和集成测试失效。
核心原因是 `reactor.step()` 现在仅负责**调度**任务，而不等待任务**完成**。
测试代码在 `step()` 返回后立即进行断言，此时后台任务尚未执行完毕，导致断言失败（如 Token 尚未产生，或资源尚未释放）。
且 `VolatileMemory.wait_for_mutation()` 存在竞态条件：如果在 `step` 之前 `put` 操作已经触发了事件，`wait` 会立即返回，无法起到同步作用。

### 用户需求
1.  修复 `cascade-vm` 和 `cascade-compiler` 中受影响的集成测试。
2.  引入可靠的同步机制，确保在断言前 `Reactor` 已完成所有后台任务的处理。

### 评论
这是异步系统测试中常见的问题。我们需要从“步进即完成”的思维转变为“步进即调度，断言需等待”的思维。引入 `wait_for_idle` 模式是解决此类问题的标准做法。

### 目标
1.  在测试中引入 `wait_for_idle(reactor)` 辅助函数。
2.  修复 `test_branching.py`, `test_ping_pong.py`, `test_resource_backpressure.py`。
3.  修复 `test_observability_congestion.py`。

### 基本原理
通过轮询 `reactor.active_task_count`，我们可以精确地知道系统何时进入静止状态（所有触发的物理节点都已执行完毕）。这比依赖内存事件更直观且不易出错，特别是在手动单步执行的测试场景中。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/vm #scope/core #ai/instruct #task/domain/testing #task/object/async-reactor #task/action/fix-synchronization #task/state/continue

---

### Script

#### Acts 1: 修复 VM 集成测试 (Branching)

引入 `wait_for_idle` 并替换不可靠的 `wait_for_mutation`。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_branching.py
~~~~~
~~~~~python.old
import pytest
from typing import Dict

from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
~~~~~
~~~~~python.new
import pytest
import asyncio
from typing import Dict

from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_branching.py
~~~~~
~~~~~python.old
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
~~~~~python.new
    graph.channels.append(
        Channel(f_sw.id, "out", d_b.id, target_port="in", tag_filter="B")
    )

    func_map = {f_sw.id: switch_logic}

    return graph, d_in, d_a, d_b, func_map


async def wait_for_idle(reactor: Reactor):
    while reactor.active_task_count > 0:
        await asyncio.sleep(0.001)


@pytest.mark.asyncio
async def test_branching_path_a(branching_topology):
    graph, d_in, d_a, d_b, func_map = branching_topology

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, PhysicsExecutor(), func_map)

    # 1. Inject signal for Path A
    memory.put(d_in, Token(payload="path_a"))

    # 2. Run
    await reactor.step()
    await wait_for_idle(reactor)

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
    await wait_for_idle(reactor)

    # 3. Assert
    # D_B should receive token
    assert memory.get_count(d_b.id) == 1
    assert memory.take(d_b.id).payload == "Data B"

    # D_A should be empty
    assert memory.get_count(d_a.id) == 0
~~~~~

#### Acts 2: 修复 VM 集成测试 (Ping Pong)

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ping_pong.py
~~~~~
~~~~~python.old
import pytest
from typing import Dict, Callable

from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
~~~~~
~~~~~python.new
import pytest
import asyncio
from typing import Dict, Callable

from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ping_pong.py
~~~~~
~~~~~python.old
    # 2. Run the physics simulation for one step
    fired_count = await reactor.step()

    # 3. Assertions
    assert fired_count == 1

    # Input token should be consumed
    assert memory.get_count(d1.id) == 0

    # Output node should receive the result
    assert memory.get_count(d2.id) == 1

    result_token = memory.take(d2.id)
    assert result_token.payload == 11  # 10 + 1
~~~~~
~~~~~python.new
    # 2. Run the physics simulation for one step
    fired_count = await reactor.step()

    # Wait for async completion
    while reactor.active_task_count > 0:
        await asyncio.sleep(0.001)

    # 3. Assertions
    assert fired_count == 1

    # Input token should be consumed
    assert memory.get_count(d1.id) == 0

    # Output node should receive the result
    assert memory.get_count(d2.id) == 1

    result_token = memory.take(d2.id)
    assert result_token.payload == 11  # 10 + 1
~~~~~

#### Acts 3: 修复 VM 集成测试 (Backpressure)

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    # Step 1: Both Bleachers are ready on 'x', but contend for 'res_gpu'.
    # With the new atomic Reactor, only ONE should fire.
    fired = await reactor.step()
    # What fires?
    # 1. Bleacher (consumes 1 GPU, 1 X) -> fires.
    # The other Bleacher cannot fire because D_res is empty.

    assert fired == 1
    assert memory.get_count("canonical.resource.gpu") == 0  # Resource taken

    # Step 2: The fired Triad proceeds.
    # Worker fires.
    await reactor.step()

    # Step 3: Stainer fires.
    # This should return the resource.
    await reactor.step()

    assert memory.get_count("canonical.resource.gpu") == 1  # Resource returned!

    # Step 4: Now the second Bleacher can fire.
    fired_2 = await reactor.step()
    assert fired_2 == 1
    assert memory.get_count("canonical.resource.gpu") == 0

    # Step 5 & 6: Finish second task
    await reactor.step()  # Worker
    await reactor.step()  # Stainer

    assert memory.get_count("canonical.resource.gpu") == 1
~~~~~
~~~~~python.new
    async def wait_idle():
        import asyncio
        while reactor.active_task_count > 0:
            await asyncio.sleep(0.001)

    # Step 1: Both Bleachers are ready on 'x', but contend for 'res_gpu'.
    # With the new atomic Reactor, only ONE should fire.
    fired = await reactor.step()
    await wait_idle()

    # What fires?
    # 1. Bleacher (consumes 1 GPU, 1 X) -> fires.
    # The other Bleacher cannot fire because D_res is empty.

    assert fired == 1
    assert memory.get_count("canonical.resource.gpu") == 0  # Resource taken

    # Step 2: The fired Triad proceeds.
    # Worker fires.
    await reactor.step()
    await wait_idle()

    # Step 3: Stainer fires.
    # This should return the resource.
    await reactor.step()
    await wait_idle()

    assert memory.get_count("canonical.resource.gpu") == 1  # Resource returned!

    # Step 4: Now the second Bleacher can fire.
    fired_2 = await reactor.step()
    await wait_idle()

    assert fired_2 == 1
    assert memory.get_count("canonical.resource.gpu") == 0

    # Step 5 & 6: Finish second task
    await reactor.step()  # Worker
    await wait_idle()

    await reactor.step()  # Stainer
    await wait_idle()

    assert memory.get_count("canonical.resource.gpu") == 1
~~~~~

#### Acts 4: 修复 Compiler 集成测试 (Observability Congestion)

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_observability_congestion.py
~~~~~
~~~~~python.old
    # 2. Execution
    # Both should fire successfully.
    fired = await reactor.step()

    assert fired == 2
    assert memory.get_count(d_life.id) == 2
~~~~~
~~~~~python.new
    # 2. Execution
    # Both should fire successfully.
    fired = await reactor.step()

    import asyncio
    while reactor.active_task_count > 0:
        await asyncio.sleep(0.001)

    assert fired == 2
    assert memory.get_count(d_life.id) == 2
~~~~~

### 下一步建议
所有集成测试修复完毕后，`Reactor` 的异步行为应该就稳定了。
接下来，我们可以自信地推进 **任务 1.3: 适配标准库 (`cascade-std`)**，重点检查那些可能依赖同步行为的 IC 实现（如果有的话，尽管目前的标准 IC 看起来都是纯粹的 Token 转换）。然后进入 **阶段 2**。
