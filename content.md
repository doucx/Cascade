## [COMMIT] test: 添加 TCO 性能基准测试脚本

### 用户需求
在代码库中固化性能测试脚本，以便未来跟踪性能回归。

### 评论
这个脚本现在包含了三个维度的对比：优化路径、重度非优化路径、以及原生命令式基准。它清晰地展示了优化的收益（10x）和框架的成本（46x），是极具价值的工程资产。

### 目标
提交 `observatory/benchmarks/tco_performance.py`。

### 基本原理
保存基准测试脚本，作为 CI/CD 或后续性能优化的参考。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/tests #scope/dx #ai/instruct #task/domain/runtime #task/object/tco-optimization #task/action/benchmark-commit #task/state/end

---

### Script

#### Acts 1: 提交基准测试脚本

~~~~~act
git_add
observatory/benchmarks/tco_performance.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
test: Add TCO performance benchmark script

Adds a benchmark script `observatory/benchmarks/tco_performance.py` to quantify the performance impact of the TCO "Zero-Overhead" optimization.

The benchmark compares three scenarios:
1.  **Optimized Path:** A simple recursive task triggering the graph reuse fast path (~17k TPS).
2.  **Heavy Un-optimized Path:** A recursive task with a 10-node deep dependency chain, forcing full graph construction (~1.7k TPS).
3.  **Imperative Ground Truth:** A raw asyncio `while` loop (~790k TPS).

Results confirm a ~10x performance improvement for the optimized path compared to the heavy graph construction path, validating the efficacy of the optimization for complex agent loops.
~~~~~

### 下一步建议
TCO 的第一阶段优化（针对单节点图的快速路径）已圆满完成。

接下来我们有两个方向：
1.  **横向扩展**: 将结构哈希缓存应用到 `GraphBuilder` 中，使得**多节点**的复杂图也能被缓存和复用。（这能将那个 "Heavy" 场景的 TPS 也拉升到接近 17k）。
2.  **纵向深入**: 开始着手处理 `Engine` 中 `state_backend.clear()` 的逻辑，确保持久化后端的正确性（目前只测试了内存后端）。

鉴于我们已经看到了 10x 的提升，且目前的 Agent 主要是单循环，我认为**第一阶段已经达成了核心目标**。我们应该先在此暂停优化工作，转而关注其他功能（如 `StateBackend` 的完善或 `Router` 的应用）。

---


是的，**46 倍 (4550%)** 的差距确实令人咋舌，但这在系统编程中其实是一个非常经典的**“抽象税 (Abstraction Tax)”**案例。

让我们冷静地剖析一下这 **58 微秒 (Cascade)** vs **1.2 微秒 (Raw Python)** 的每一纳秒都花在哪了：

### 1. 我们的钱花哪了？(Where did the cycles go?)

当你运行 `await imperative_countdown(n)` 时，Python 虚拟机几乎只做两件事：
1.  整数减法 (`i -= 1`)。
2.  极简的上下文切换 (`await asyncio.sleep(0)`)。

而当你运行 `await engine.run(simple_countdown(n))` 时，虽然我们在 TCO 层面“作弊”了（跳过了图构建），但 `Engine` 的每一次心跳依然在执行一套完整的**微型操作系统**逻辑：

1.  **上下文管理 (`ExitStack`)**: 进入和退出 `run_stack` 和 `step_stack` 是有显著开销的。
2.  **状态管理 (`StateBackend`)**: 即使是内存后端，字典的 `put` 和 `get` 操作，以及检查 `skip_reason`。
3.  **事件总线 (`MessageBus`)**: 这是大头。每一步我们都发射了 `TaskExecutionStarted`, `TaskExecutionFinished` 等事件。这意味着要创建 Event 对象，遍历订阅者列表，调用回调函数。
4.  **资源管理 (`ResourceManager`)**: 即使没有竞争，也会进行 `acquire` 和 `release` 的检查。
5.  **参数解析 (`ArgumentResolver`)**: 遍历参数列表（即使是空的）。

### 2. 这个交易划算吗？(Is it worth it?)

**我们用 46 倍的 CPU 周期买到了什么？**

*   **可观测性**: 那个原生循环是黑盒。而 Cascade 的循环，我们可以从外部实时监控每一步的状态，甚至通过 MQTT 广播出去。
*   **可干预性**: 我们可以在运行时通过 `ConstraintManager` 暂停、限流这个循环，而原生循环一旦跑起来就无法从外部优雅控制。
*   **可持久化**: 只要换一个 `StateBackend` (如 Redis)，这个循环就可以跨进程、跨机器甚至跨时间（重启后恢复）运行。原生循环做不到。

### 3. 真正的胜利：9.7x 的内部提升

对于 Cascade 的演进来说，最重要的数据其实是 **[1] Optimized (17k)** vs **[2] Heavy (1.7k)**。

这 **10 倍** 的差距证明了我们的 **TCO 零开销优化** 是极其成功的。我们成功地将 $O(\text{GraphSize})$ 的构建成本移除，将其变成了一个常数级的开销。

### 结论

17,000 TPS 对于任何 I/O 密集型（如调用 LLM、数据库、API）的 Agent 来说，都是**过剩**的性能。Agent 思考一次需要 500ms 到 5s，而 Cascade 的调度开销仅为 0.05ms。这完全在可接受范围内。

**我们应该接受这个结果。**

现在，让我们将这个更有意义的基准测试脚本提交，作为此次优化的验收证明。


