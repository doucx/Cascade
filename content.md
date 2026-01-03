## [WIP] tool: 优化基准测试以原生执行异步任务

### 用户需求

修改 `scripts/benchmark_loop_performance.py` 脚本，使其在运行 Cascade VM 基准测试时，对 `async def` 函数直接进行 `await` 调用，而不是通过 `ThreadPoolExecutor`，以验证原生异步执行的性能。

### 评论

这是一个关键的实验，它将用数据证明引入“智能分发”执行器架构的必要性和巨大潜力。通过这次修改，我们将能看到 Cascade VM 在理想情况下的性能上限。

### 目标

1.  将脚本中的 `loop_logic` 函数修改为 `async def`。
2.  修改 `run_cascade_benchmark` 中的 `Reactor._fire` 方法的实现，使其能够检测到协程函数并直接 `await` 它。
3.  保持对普通函数的 `executor.submit` 调用作为后备。

### 基本原理

我们将利用 `inspect.iscoroutinefunction` 来动态判断一个函数是否是异步的。在 `Reactor._fire` 方法中，我们加入一个 `if` 判断：如果是异步函数，就走新的、高性能的路径；如果不是，就走旧的、安全的线程池路径。

### 标签

#intent/refine #flow/ready #priority/high #comp/vm #concept/performance #scope/dx #ai/brainstorm #task/domain/performance #task/object/reactor-loop #task/action/optimization

---

### Script

#### Acts 1: 修改基准测试脚本以支持原生异步

~~~~~act
patch_file
scripts/benchmark_loop_performance.py
~~~~~
~~~~~python.old
import asyncio
import time
from typing import Dict

# --- Cascade VM Imports ---
from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.ports import PortDef, PortRole
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor

ITERATIONS = 10000

# --- Cascade Benchmark Components ---

def loop_logic(inputs: Dict[str, Token], node: PhysicsFuncNode) -> Dict[str, Token]:
    """
    The "business logic" for our self-looping node.
    It increments the counter in the token payload.
    """
    in_token = inputs["loop_in"]
    count = in_token.payload

    if count < ITERATIONS:
        # Continue the loop by emitting a new token
        return {"loop_out": Token(payload=count + 1)}
    else:
        # Terminate the loop by producing no output, starving the graph
        return {}

async def run_cascade_benchmark() -> float:
    """Sets up and runs the self-loop benchmark using the Cascade VM."""
    # 1. Build the physical graph: D_loop -> F_loop -> D_loop
    d_loop = PhysicsDataNode(id="D_loop", name="LoopCounter")
    f_loop = PhysicsFuncNode(
        id="F_loop",
        name="Incrementer",
        input_ports={"loop_in": PortDef("loop_in", PortRole.DATA)},
        output_ports={"loop_out": PortDef("loop_out", PortRole.DATA)},
    )
    graph = BipartiteGraph()
    graph.nodes = {d_loop.id: d_loop, f_loop.id: f_loop}
    graph.channels.append(Channel(d_loop.id, "out", f_loop.id, "loop_in"))
    graph.channels.append(Channel(f_loop.id, "loop_out", d_loop.id, "in"))

    # 2. Setup the VM
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f_loop.id: loop_logic}
    reactor = Reactor(graph, memory, executor, function_map)

    # 3. Prime the system with the initial state
    reactor.prime()
    memory.put(d_loop, Token(payload=0))

    # 4. Run the benchmark
    print("Starting Cascade VM benchmark...")
    start_time = time.monotonic()

    # The reactor loop continues as long as there are state changes
    while (await reactor.step()) > 0:
        pass

    end_time = time.monotonic()
    print("Cascade VM benchmark finished.")
    return end_time - start_time
~~~~~
~~~~~python.new
import asyncio
import time
import inspect
from typing import Dict

# --- Cascade VM Imports ---
from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.ports import PortDef, PortRole
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor

ITERATIONS = 10000

# --- Cascade Benchmark Components ---

async def loop_logic(inputs: Dict[str, Token], node: PhysicsFuncNode) -> Dict[str, Token]:
    """
    The "business logic" for our self-looping node.
    It increments the counter in the token payload.
    NOW AN ASYNC FUNCTION.
    """
    # In a real async function, we might do `await asyncio.sleep(0)`
    # to yield control, but for a pure computation benchmark, this is fine.
    in_token = inputs["loop_in"]
    count = in_token.payload

    if count < ITERATIONS:
        # Continue the loop by emitting a new token
        return {"loop_out": Token(payload=count + 1)}
    else:
        # Terminate the loop by producing no output, starving the graph
        return {}

async def run_cascade_benchmark() -> float:
    """Sets up and runs the self-loop benchmark using the Cascade VM."""
    # 1. Build the physical graph: D_loop -> F_loop -> D_loop
    d_loop = PhysicsDataNode(id="D_loop", name="LoopCounter")
    f_loop = PhysicsFuncNode(
        id="F_loop",
        name="Incrementer",
        input_ports={"loop_in": PortDef("loop_in", PortRole.DATA)},
        output_ports={"loop_out": PortDef("loop_out", PortRole.DATA)},
    )
    graph = BipartiteGraph()
    graph.nodes = {d_loop.id: d_loop, f_loop.id: f_loop}
    graph.channels.append(Channel(d_loop.id, "out", f_loop.id, "loop_in"))
    graph.channels.append(Channel(f_loop.id, "loop_out", d_loop.id, "in"))

    # 2. Setup the VM
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f_loop.id: loop_logic}
    reactor = Reactor(graph, memory, executor, function_map)

    # MONKEY-PATCH the _fire method to be "smart"
    original_fire = reactor._fire
    async def smart_fire(node: PhysicsFuncNode, input_data: Dict[str, Token]) -> None:
        func = reactor.function_map.get(node.id)
        if not func:
            return
        
        # THE CORE OF THE OPTIMIZATION
        if inspect.iscoroutinefunction(func):
            # If it's async, await it directly on the event loop
            result_tokens = await func(input_data, node)
            # This part is duplicated from Reactor but necessary for the patch
            outbound = reactor._outbound_channels.get(node.id, [])
            for channel in outbound:
                token = result_tokens.get(channel.source_port)
                if token is not None:
                    target_node = reactor.graph.nodes[channel.target_node_id]
                    reactor.memory.put(target_node, token)
        else:
            # Otherwise, use the original, safe method
            await original_fire(node, input_data)

    reactor._fire = smart_fire


    # 3. Prime the system with the initial state
    reactor.prime()
    memory.put(d_loop, Token(payload=0))

    # 4. Run the benchmark
    print("Starting Cascade VM benchmark (with native async optimization)...")
    start_time = time.monotonic()

    # The reactor loop continues as long as there are state changes
    while (await reactor.step()) > 0:
        pass

    end_time = time.monotonic()
    print("Cascade VM benchmark finished.")
    return end_time - start_time
~~~~~

---

在你运行这个修改后的脚本后，我预计你会看到 Cascade VM 的开销从 `~1600x` 大幅下降到 `~50x` 甚至更低。这依然比原生循环慢，因为我们还有状态检查和函数分发的开销，但它会清晰地展示出**绕过线程池所带来的巨大性能收益**。

这为我们下一步的架构决策提供了强有力的数据支持。
