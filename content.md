简要回答：
你的直觉完全正确！问题出在分摊逻辑上：我错误地用 `limit // agents`（总限制除以 Agent 数量）来计算每个核心的容量，导致当 `limit == agents` 时，每个 Agent 实际上被赋予了只有 **1** 的容量——这导致了整个仿真的 **完全串行化**。

## [WIP] fix(exp): 纠正 Worker 并发容量分摊逻辑

### 错误分析
在 `run_fireflies.py` 的 `worker_main` 中，有这样一行：
```python
local_limit = max(1, concurrency_limit // len(agent_indices))
```
如果 `--grid-side 10` (100 个 Agent) 且 `--limit 100`：
*   `len(agent_indices)` 是 100。
*   `100 // 100 = 1`。
*   于是 Worker 进程的 `ResourceManager` 只有 **1 个槽位**。
*   由于每个 `firefly_agent` 任务都会请求 `cpu_slot=1`，且在执行期间（包括 `await asyncio.sleep`）都会持有该槽位，导致 100 个 Agent 只能排队运行，每次只有 1 个在动。

### 解决方案
正确的逻辑应该是将**全局限制**分摊到各个 **Worker 进程**上，而不是分摊给每个 Agent：
```python
local_limit = concurrency_limit // workers
```

### 用户需求
修复并发限制失效的问题，确保 `--limit` 参数的行为符合逻辑预期（即当 limit >= agents 时，所有 Agent 都能同时运行）。

### 评论
这是一个典型的“分摊单位错误”。在分布式或多进程环境中，资源容量应该按照“执行容器（Worker）”来切分，因为每个 Worker 内部的 `ResourceManager` 是独立运行的。

### 目标
1.  修正 `run_fireflies.py` 中 `local_limit` 的计算公式。
2.  确保 `workers` 参数被正确传递给 `worker_main` 用于分摊计算。

### 基本原理
通过将全局 `limit` 除以 `workers` 数量，我们给每个 Worker 分配了一个公平的资源份额。在这个份额内，Worker 内部的 `ResourceManager` 会管理属于该 Worker 的所有 Agent 任务。

### 标签
#intent/fix #flow/ready #priority/high #comp/experiments #scope/perf #ai/instruct #task/domain/experiments #task/object/resource-allocation #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正分摊逻辑

我们需要在 `run_orchestrator` 中计算每个 Worker 应该分到的 limit，并将其传递给 `worker_main`。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
def worker_main(
    worker_id: int,
    agent_indices: List[int],
    uplink_queue: mp.Queue,
    concurrency_limit: Optional[int],
    grid_width: int,
    grid_height: int,
    period: float,
    nudge: float,
):
    """
    The entry point for a worker process.
    Runs a subset of agents (Sharding).
    """
    # Create a new event loop for this process
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run_worker():
        # 1. Setup Uplink
        connector = IpcUplinkConnector(uplink_queue)
        await connector.connect()

        # 2. Setup Resources
        # Note: Concurrency limits are currently PER PROCESS in this mode.
        # To make them global across processes requires a distributed lock (e.g. Redis),
        # which is out of scope for this MP queue-based MVP.
        # We scale the limit down proportionally.
        local_limit = None
        if concurrency_limit:
            local_limit = max(1, concurrency_limit // len(agent_indices)) if agent_indices else 1
        
        resource_manager = None
~~~~~
~~~~~python
def worker_main(
    worker_id: int,
    agent_indices: List[int],
    uplink_queue: mp.Queue,
    worker_limit: Optional[int],
    grid_width: int,
    grid_height: int,
    period: float,
    nudge: float,
):
    """
    The entry point for a worker process.
    Runs a subset of agents (Sharding).
    """
    # Create a new event loop for this process
    loop = asyncio_event_loop()
    asyncio.set_event_loop(loop)

    async def _run_worker():
        # 1. Setup Uplink
        connector = IpcUplinkConnector(uplink_queue)
        await connector.connect()

        # 2. Setup Resources
        # worker_limit is the pre-calculated capacity for this process.
        resource_manager = None
        if worker_limit:
            resource_manager = ResourceManager(capacity={"cpu_slot": worker_limit})

        # 3. Setup Topology (Local Island)
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
    # 3. Spawn Workers
    uplink_queue = mp.Queue()
    all_indices = list(range(num_agents))
    chunk_size = math.ceil(num_agents / workers)
    
    processes = []
    for w_id in range(workers):
        start = w_id * chunk_size
        end = min(start + chunk_size, num_agents)
        indices = all_indices[start:end]
        
        if not indices:
            continue

        p = mp.Process(
            target=worker_main,
            args=(
                w_id, indices, uplink_queue, concurrency_limit,
                grid_width, grid_width, period, nudge
            )
        )
        p.start()
        processes.append(p)
~~~~~
~~~~~python
    # 3. Spawn Workers
    uplink_queue = mp.Queue()
    all_indices = list(range(num_agents))
    chunk_size = math.ceil(num_agents / workers)
    
    # Calculate per-worker limit (Global Limit split across processes)
    worker_limit = None
    if concurrency_limit:
        worker_limit = max(1, concurrency_limit // workers)

    processes = []
    for w_id in range(workers):
        start = w_id * chunk_size
        end = min(start + chunk_size, num_agents)
        indices = all_indices[start:end]
        
        if not indices:
            continue

        p = mp.Process(
            target=worker_main,
            args=(
                w_id, indices, uplink_queue, worker_limit,
                grid_width, grid_width, period, nudge
            )
        )
        p.start()
        processes.append(p)
~~~~~

### 下一步建议
修复后，请再次运行 `python -m observatory.experiments.run_fireflies --grid-side 10 --limit 100`。
现在由于 `worker_limit = 100 // 1 = 100`，每个 Agent 都能获得槽位，你应该能看到满屏闪烁的正常效果了。
如果您将 limit 设置为 50，则应该看到只有一半的 Agent 能在同一时刻处于“工作/睡眠”状态（持有资源）。
