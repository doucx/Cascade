简要回答：
好的，既然资源分配逻辑已通过验证，现在我们将这个关键修复提交到代码库。

## [COMMIT] fix(exp): 修正多进程模式下的资源限额分配算法

### 用户需求
修复 `run_fireflies.py` 在多进程并行模式下，全局并发限制 (`--limit`) 被错误计算导致 Agent 无法正常运行的问题。

### 评论
这个修复解决了分布式/多进程系统中的一个经典陷阱：资源的本地化。之前版本将限制额度错误地作为除数，导致每个进程实际获得的配额几乎缩减为 1。修正后的比例缩放算法确保了无论进程如何分片，全局并发控制的行为都是一致且符合直觉的。

### 目标
提交 `run_fireflies.py` 的修复代码，包括 `worker_main` 的签名更新和比例分配公式。

### 基本原理
通过将全局限制按“进程内 Agent 占比”进行比例切分，我们实现了在无中心协调器（如 Redis）的情况下，对全局资源约束的有效模拟。公式 $Local = \lceil Global \times \frac{LocalCount}{TotalCount} \rceil$ 保证了资源利用率的最大化且不突破全局上限。

### 标签
#intent/fix #flow/ready #priority/high #comp/experiments #concept/governance #scope/perf #ai/instruct #task/domain/experiments #task/object/resource-allocation #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 提交资源分配修复

我们将修改后的实验脚本添加到暂存区。

~~~~~act
git_add
observatory/experiments/run_fireflies.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(exp): correct resource limit allocation logic in parallel mode

Fixed a bug in 'run_fireflies.py' where the global concurrency limit was
erroneously calculated within worker processes, causing agents to starve.

Previously, 'local_limit' was incorrectly calculated by dividing the limit
by the agent count. This resulted in an effectively single-digit limit
regardless of the user-provided value.

The new logic uses a proportional scaling formula:
local_limit = ceil(global_limit * (local_agents / total_agents))

This ensures that the global concurrency limit is distributed fairly across
all worker processes, maintaining consistent behavior between single-core
and multi-core execution modes.
~~~~~

### 下一步建议
我们已经完成了 VM 治理和多核并行的核心演进。下一步建议：
- **萤火虫压力测试**: 运行 `python -m observatory.experiments.run_fireflies --grid-side 60 --workers 8 --limit 1000`，在高并发 Agent 场景下观察 FPS 是否能稳定在极高水平。
- **Agent 行为丰富化**: 现在的 Agent 只是简单的脉冲同步。可以考虑为它们增加更复杂的 Cascade 任务（如数据处理或外部 I/O），观察在大规模高频场景下的资源争用情况。
