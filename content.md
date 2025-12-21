简要回答：
你的直觉非常敏锐。问题确实出在 `worker_main` 中对 `local_limit` 的计算逻辑上。由于一个数学错误，原本设定的限制被错误地缩小了 N 倍（N 为 Agent 数量），导致 `--limit 100` 实际上变成了 `--limit 1`。

## [WIP] fix(exp): 修正并行模式下的并发限制分配逻辑

### 错误分析

在 `worker_main` 函数中，目前的逻辑是：
```python
local_limit = concurrency_limit // len(agent_indices)
```
这里的意图是“分配给这个进程的配额”，但逻辑完全错了：
1.  **分母错误**：`len(agent_indices)` 是该进程管理的 Agent 数量。如果全局限制是 100，进程管理 100 个 Agent，那么 `local_limit` 变成了 `100 // 100 = 1`。
2.  **后果**：由于 `firefly_agent` 任务内部包含 `await asyncio.sleep` 和 `await asyncio.wait_for`，在执行这些异步等待时，它**仍然占据着资源槽位**。如果 `local_limit` 为 1，意味着整个进程中**同一时刻只能有一个 Agent 在运行**（包括在它的 refractory 或 sensitive 阶段等待）。其他 99 个 Agent 都在 `resource_manager.acquire` 处排队。这就是为什么屏幕上只有零星闪烁的原因。

### 用户需求
修复并发限制的分配算法，使得 `--limit` 选项能按照预期（全局配额的比例分配）工作。

### 评论
这是一个典型的“比例缩放”错误。在分布式或多进程系统中，全局资源的本地化（Localization）必须基于“进程贡献度”而非“个体数量”。修正后，即使开启了限制，只要 Agent 总数未超过限制，它们就应该能全部正常运行。

### 目标
1.  在 `run_orchestrator` 中向 `worker_main` 传递 Agent 总数。
2.  在 `worker_main` 中使用比例公式重新计算 `local_limit`：`local_limit = ceil(global_limit * (进程内 Agent 数 / 总 Agent 数))`。

### 基本原理
为了在不使用中心化资源服务器（如 Redis）的情况下模拟全局限制，我们将全局容量按比例切割给每个工作进程。公式：$LocalCapacity = GlobalLimit \times \frac{LocalAgents}{TotalAgents}$。这确保了所有进程的本地容量之和近似等于全局限制。

### 标签
#intent/fix #flow/ready #priority/high #comp/experiments #scope/perf #ai/instruct #task/domain/experiments #task/object/resource-allocation #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正分配逻辑

我们需要更新 `run_orchestrator` 传递参数的方式，并重写 `worker_main` 中的计算公式。

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
~~~~~
~~~~~python
def worker_main(
    worker_id: int,
    agent_indices: List[int],
    total_agents: int,
    uplink_queue: mp.Queue,
    concurrency_limit: Optional[int],
    grid_width: int,
    grid_height: int,
    period: float,
    nudge: float,
):
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
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
        # 2. Setup Resources
        # We partition the global limit proportionally among workers.
        local_limit = None
        if concurrency_limit:
            # Formula: (Global Limit * Agents in this Worker) / Total Agents
            # Using math.ceil to ensure we don't end up with 0 due to rounding
            local_limit = math.ceil(concurrency_limit * (len(agent_indices) / total_agents))
        
        resource_manager = None
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
        p = mp.Process(
            target=worker_main,
            args=(
                w_id, indices, uplink_queue, concurrency_limit,
                grid_width, grid_width, period, nudge
            )
        )
~~~~~
~~~~~python
        p = mp.Process(
            target=worker_main,
            args=(
                w_id, indices, num_agents, uplink_queue, concurrency_limit,
                grid_width, grid_width, period, nudge
            )
        )
~~~~~

### 下一步建议
现在你可以再次尝试运行：
`python -m observatory.experiments.run_fireflies --grid-side 10 --limit 100`
预期结果是：所有 100 个 Agent 都能流畅闪烁，因为此时 `local_limit` 应该被正确计算为 `100`。

随后你可以尝试：
`python -m observatory.experiments.run_fireflies --grid-side 20 --limit 100`
此时你会看到 400 个 Agent 中只有约 1/4 在同时活跃，这验证了限制确实生效了。
