这是一个激动人心的新篇章。为了实现“真理之镜”，我们需要从基础做起：实现一个绝对正确的“黄金参考”模型，以及一个能在 Cascade 分布式运行时中复现该逻辑的 Agent 实现。

由于目前的 `Kuramoto` (萤火虫) 模型是基于连续时间的，不适合进行逐代的精确快照对比，我们将引入**康威生命游戏 (Game of Life)** 作为新的实验载体。这是一个经典的离散时间、离散状态的元胞自动机，非常适合用于一致性验证。

我将生成一个计划，包含以下步骤：
1.  **黄金参考**: 实现 `GoldenLife` 类，使用 NumPy 进行极速的矩阵运算，作为我们的“真理”。
2.  **Cascade Agent**: 实现 `ConwayAgent`。与萤火虫不同，它必须实现**严格的屏障同步 (Barrier Synchronization)**——即只有收到所有邻居 $G$ 代的状态后，才计算 $G+1$ 代。这将测试 Cascade 处理复杂因果依赖的能力。
3.  **验证器**: 实现 `Validator`，用于收集快照并进行对比。

## [WIP] feat(proto): 实现真理之镜基础设施 (Golden CA & Conway Agent)

### 错误分析
无（新功能开发）。

### 用户需求
1.  **黄金参考**: 一个基于 NumPy 的、性能极高的康威生命游戏实现，用于产生“标准答案”。
2.  **分布式 Agent**: 一个基于 Cascade 的康威生命游戏 Agent 实现，能够通过消息传递与其他 Agent 协作计算下一代状态，并向验证器报告自身状态。
3.  **验证逻辑**: 能够对比“分布式计算结果”与“黄金参考结果”的差异。

### 评论
这个计划将 Cascade 从“物理模拟”（萤火虫）推向了“逻辑计算”（元胞自动机）。这要求更高的通信可靠性和因果一致性。任何一个消息的丢失或乱序都将导致验证失败。这是对 Cascade 协议健壮性的终极压力测试。

### 目标
1.  创建 `observatory/protoplasm/truth/golden_ca.py`: 实现 `GoldenLife` 类。
2.  创建 `observatory/protoplasm/agents/conway.py`: 实现 `conway_agent` 工作流。
3.  创建 `observatory/protoplasm/truth/validator.py`: 实现 `StateValidator` 类。

### 基本原理
-   **黄金参考**: 使用 NumPy 的卷积 (`scipy.signal.convolve2d` 或简单的切片操作) 来计算邻居数量，实现向量化的状态更新，确保微秒级的计算速度。
-   **Conway Agent**: 每个 Agent 代表一个细胞。它必须知道自己的邻居 ID。在每一代，它广播自己的状态，收集邻居状态，计算下一代，并向验证器发送报告。
-   **验证器**: 维护一个“滑动窗口”来处理异步到达的报告。当某一代的所有报告齐备时，触发比对。

### 标签
#intent/architect #flow/ready #priority/high #comp/observatory #concept/consistency #scope/core #ai/instruct #task/domain/simulation #task/object/golden-reference #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 实现黄金参考 (Golden Reference)

我们将使用 NumPy 实现一个高性能的生命游戏引擎。

~~~~~act
write_file
observatory/protoplasm/truth/golden_ca.py
~~~~~
~~~~~python
import numpy as np
from typing import Tuple

class GoldenLife:
    """
    A high-performance, synchronous implementation of Conway's Game of Life
    using NumPy. Serves as the 'Source of Truth' for validation.
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.grid = np.zeros((height, width), dtype=np.int8)

    def seed(self, initial_state: np.ndarray):
        """Sets the initial state of the grid."""
        if initial_state.shape != (self.height, self.width):
            raise ValueError(f"Shape mismatch: expected {(self.height, self.width)}, got {initial_state.shape}")
        self.grid = initial_state.astype(np.int8)

    def step(self) -> np.ndarray:
        """
        Advances the simulation by one generation.
        Returns the new state.
        """
        # Count neighbors using simple array slicing (toroidal/wrap-around boundary)
        # N, S, E, W, NE, NW, SE, SW
        N  = np.roll(self.grid, -1, axis=0)
        S  = np.roll(self.grid,  1, axis=0)
        E  = np.roll(self.grid, -1, axis=1)
        W  = np.roll(self.grid,  1, axis=1)
        NE = np.roll(N, -1, axis=1)
        NW = np.roll(N,  1, axis=1)
        SE = np.roll(S, -1, axis=1)
        SW = np.roll(S,  1, axis=1)

        neighbors = N + S + E + W + NE + NW + SE + SW

        # Apply rules:
        # 1. Any live cell with 2 or 3 live neighbours survives.
        # 2. Any dead cell with 3 live neighbours becomes a live cell.
        # 3. All other live cells die in the next generation.
        
        # Use boolean masks for speed
        alive = self.grid == 1
        keep_alive = (neighbors == 2) | (neighbors == 3)
        resurrect = (neighbors == 3)
        
        next_grid = np.zeros_like(self.grid)
        next_grid[alive & keep_alive] = 1
        next_grid[~alive & resurrect] = 1
        
        self.grid = next_grid
        return self.grid.copy()

    def get_state(self) -> np.ndarray:
        return self.grid.copy()
~~~~~

#### Acts 2: 实现分布式 Conway Agent

这个 Agent 需要比 Firefly 更复杂的逻辑。它不仅要收消息，还要**匹配代数**。即：我在计算第 G 代时，收到的必须是邻居第 G-1 代的状态。如果收到 G 代的（邻居跑得快），需要缓存起来给下一轮用。这太复杂了。

**简化策略**：我们使用**推模式 (Push Model)**。
1.  Agent 处于 Gen 0。
2.  广播 Gen 0 状态给邻居。
3.  等待收集所有 8 个邻居的 Gen 0 状态。
4.  计算 Gen 1 状态。
5.  报告 Gen 1 给 Validator。
6.  重复。

这需要一个可靠的 `recv`，能过滤特定代数的消息。但 Cascade 目前没有带过滤器的 `recv`。
**解决方案**：Agent 内部维护一个 `Mailbox`。`recv` 收到所有消息，放入 Mailbox。计算逻辑从 Mailbox 取出符合当前代数的消息。

~~~~~act
write_file
observatory/protoplasm/agents/conway.py
~~~~~
~~~~~python
import asyncio
from typing import List, Dict, Tuple, Any, Set
import cascade as cs
from cascade.interfaces.protocols import Connector

# --- Atomic Tasks ---

@cs.task
async def broadcast_state(
    topic_base: str,
    agent_id: int,
    generation: int,
    state: int,
    connector: Connector,
) -> None:
    """Publishes current state to a topic sharded by agent ID."""
    payload = {
        "agent_id": agent_id,
        "gen": generation,
        "state": state
    }
    # Topic structure: cell/{agent_id}/state
    await connector.publish(f"{topic_base}/{agent_id}/state", payload)

@cs.task
async def report_to_validator(
    topic: str,
    agent_id: int,
    x: int, y: int,
    generation: int,
    state: int,
    connector: Connector
) -> None:
    """Sends a report to the central validator."""
    payload = {
        "id": agent_id,
        "coords": [x, y],
        "gen": generation,
        "state": state
    }
    await connector.publish(topic, payload)

# --- Agent Logic ---

def conway_agent(
    agent_id: int,
    x: int, 
    y: int,
    initial_state: int,
    neighbor_ids: List[int],
    topic_base: str,
    validator_topic: str,
    connector: Connector,
    max_generations: int = 100
):
    """
    A distributed Game of Life cell.
    It synchronizes with neighbors barrier-style.
    """
    
    # We need a stateful mailbox to handle out-of-order messages from neighbors.
    # Since Cascade tasks are stateless, we pass this mailbox state through the recursion.
    # Mailbox structure: { generation: { neighbor_id: state } }
    initial_mailbox = {}

    def lifecycle(
        gen: int,
        current_state: int,
        mailbox: Dict[int, Dict[int, int]]
    ):
        if gen >= max_generations:
            return current_state

        # 1. Broadcast current state to neighbors (and validator)
        # Note: We broadcast state for 'gen'. Neighbors need this to calculate 'gen+1'.
        broadcast = broadcast_state(topic_base, agent_id, gen, current_state, connector)
        report = report_to_validator(validator_topic, agent_id, x, y, gen, current_state, connector)

        # 2. Wait for all neighbors' state for *this* generation 'gen'
        @cs.task
        async def collect_neighbors(
            _b, _r, # Depend on broadcast/report to ensure they happened
            current_gen: int,
            current_mb: Dict[int, Dict[int, int]],
            my_neighbor_ids: List[int],
            conn: Connector
        ) -> Tuple[Dict[int, int], Dict[int, Dict[int, int]]]:
            
            # Helper to check if we have everything for current_gen
            def is_ready(mb):
                if current_gen not in mb: return False
                return len(mb[current_gen]) >= len(my_neighbor_ids)

            # Fast path: maybe we already have everything in the mailbox?
            if is_ready(current_mb):
                return current_mb[current_gen], current_mb

            # Slow path: Listen for messages until ready
            # We subscribe to a wildcard that covers all neighbors? 
            # Or subscribe to specific topics? 
            # Optimization: Subscribe to "cell/+/state" is easiest but noisy.
            # Ideally: "cell/+/state" but filtered by neighbor list logic?
            # For simplicity in prototype: Subscribe wildcard.
            
            future = asyncio.Future()
            
            async def callback(topic: str, payload: Any):
                # payload: {agent_id, gen, state}
                sender = payload['agent_id']
                p_gen = payload['gen']
                p_state = payload['state']
                
                if sender in my_neighbor_ids:
                    if p_gen not in current_mb:
                        current_mb[p_gen] = {}
                    
                    current_mb[p_gen][sender] = p_state
                    
                    if is_ready(current_mb) and not future.done():
                        future.set_result(None)

            sub = await conn.subscribe(f"{topic_base}/+/state", callback)
            
            try:
                # Wait with a timeout to prevent deadlocks
                await asyncio.wait_for(future, timeout=5.0)
            except asyncio.TimeoutError:
                # In simulation, this is fatal. In prod, maybe fallback?
                # For validation, we crash.
                raise RuntimeError(f"Agent {agent_id} timed out waiting for gen {current_gen} from neighbors {my_neighbor_ids}. Mailbox: {current_mb.get(current_gen)}")
            finally:
                await sub.unsubscribe()
                
            # Cleanup: We can remove old generations from mailbox to save memory
            # Keep current_gen + 1 (for future)
            # Remove current_gen (we are about to consume it) and older
            consumed_data = current_mb[current_gen]
            new_mb = {g: m for g, m in current_mb.items() if g > current_gen}
            
            return consumed_data, new_mb

        neighbors_data, next_mailbox = collect_neighbors(
            broadcast, report, gen, mailbox, neighbor_ids, connector
        )

        # 3. Compute next state based on neighbors
        @cs.task
        def compute_next(neighbor_states: Dict[int, int], my_state: int) -> int:
            alive_neighbors = sum(neighbor_states.values())
            
            if my_state == 1:
                if alive_neighbors in (2, 3):
                    return 1
                else:
                    return 0
            else:
                if alive_neighbors == 3:
                    return 1
                else:
                    return 0
        
        next_state = compute_next(neighbors_data[0], current_state)
        
        # 4. Recurse
        @cs.task
        def step_recursion(ns, nmb):
            return lifecycle(gen + 1, ns, nmb)
            
        return step_recursion(next_state, neighbors_data[1])

    return lifecycle(0, initial_state, initial_mailbox)
~~~~~

#### Acts 3: 实现验证器 (Validator)

验证器将作为一个独立的组件，可以在实验脚本中运行，也可以单独运行。它需要能够订阅 MQTT/LocalBus，并使用 `GoldenLife` 进行校验。

~~~~~act
write_file
observatory/protoplasm/truth/validator.py
~~~~~
~~~~~python
import asyncio
import time
import numpy as np
from typing import Dict, Any, List
from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife

class StateValidator:
    def __init__(self, width: int, height: int, connector: Connector):
        self.width = width
        self.height = height
        self.connector = connector
        self.golden = GoldenLife(width, height)
        
        # buffer[gen][agent_id] = state
        self.buffer: Dict[int, Dict[int, int]] = {}
        # Stores the validated/truth state for each generation
        self.truth_history: Dict[int, np.ndarray] = {}
        
        self.total_agents = width * height
        self._running = False
        
        # Stats
        self.errors_found = 0
        self.max_gen_verified = -1

    async def run(self):
        self._running = True
        print(f"⚖️  Validator active. Grid: {self.width}x{self.height}")
        
        sub = await self.connector.subscribe("validator/report", self.on_report)
        
        try:
            while self._running:
                self._process_buffers()
                await asyncio.sleep(0.01)
        finally:
            await sub.unsubscribe()

    async def on_report(self, topic: str, payload: Any):
        """
        Payload: {id, coords: [x, y], gen, state}
        """
        gen = payload['gen']
        agent_id = payload['id']
        state = payload['state']
        
        if gen not in self.buffer:
            self.buffer[gen] = {}
            
        # Optimization: We could store (x,y) mapping once, but payload carries it.
        # For validation we need to map id -> (x,y) to construct the matrix.
        # Let's trust the coords in payload for now.
        if 'coords' in payload:
             # We store full metadata in buffer to reconstruct grid later
             self.buffer[gen][agent_id] = payload

    def _process_buffers(self):
        # Check if any generation is complete
        # We process generations in order.
        next_gen = self.max_gen_verified + 1
        
        if next_gen not in self.buffer:
            return

        current_buffer = self.buffer[next_gen]
        if len(current_buffer) < self.total_agents:
            # Waiting for more reports...
            return
            
        # Complete! Let's validate.
        print(f"[Validator] Verifying Generation {next_gen}...")
        self._verify_generation(next_gen, current_buffer)
        
        # Cleanup
        del self.buffer[next_gen]
        self.max_gen_verified = next_gen

    def _verify_generation(self, gen: int, reports: Dict[int, Any]):
        # 1. Construct Actual Grid
        actual_grid = np.zeros((self.height, self.width), dtype=np.int8)
        for r in reports.values():
            x, y = r['coords']
            actual_grid[y, x] = r['state']
            
        # 2. Get Expected Grid
        if gen == 0:
            # Gen 0 is the axiom. We set the golden reference to match it.
            self.golden.seed(actual_grid)
            self.truth_history[0] = actual_grid
            print("✅ Gen 0 accepted as Axiom.")
            return
        
        # For Gen > 0, we must calculate expectation from Gen-1 Truth
        prev_truth = self.truth_history.get(gen - 1)
        if prev_truth is None:
            print(f"❌ Missing truth for Gen {gen-1}, cannot verify Gen {gen}")
            return
            
        # Reset golden to prev state and step
        self.golden.seed(prev_truth)
        expected_grid = self.golden.step()
        self.truth_history[gen] = expected_grid
        
        # 3. Compare
        diff = actual_grid != expected_grid
        errors = np.sum(diff)
        
        if errors == 0:
            print(f"✅ Gen {gen} Verified. Perfect Match.")
        else:
            self.errors_found += errors
            print(f"🚨 Gen {gen} MISMATCH! {errors} errors found.")
            # Optional: Print diff locations
            rows, cols = np.where(diff)
            for r, c in zip(rows[:5], cols[:5]):
                print(f"   - Mismatch at ({c}, {r}): Expected {expected_grid[r,c]}, Got {actual_grid[r,c]}")
            if errors > 5: print("   ... and more.")

    def stop(self):
        self._running = False
~~~~~

### 下一步建议
我们已经建立了“真理之镜”的三大支柱。现在我们需要一个实验脚本将它们整合起来。

1.  创建一个实验脚本 `observatory/protoplasm/truth/run_conway_experiment.py`。
2.  该脚本需要：
    *   初始化一个 $N \times N$ 的网格。
    *   计算每个 Agent 的邻居列表（处理环形边界）。
    *   启动 $N^2$ 个 `conway_agent` 任务（使用单 Engine 多任务模式）。
    *   同时启动 `StateValidator`。
    *   观察控制台输出，确认是否看到连续的 "✅ Gen X Verified"。

如果这个实验成功，我们将证明 Cascade 不仅能做物理模拟，还能进行精确的、强一致性的分布式计算。这将是架构的一个巨大胜利。
