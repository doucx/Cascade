好的，既然测试已经全面通过，我们已经成功地将 Cascade 3.0 的核心逻辑——从标准元器件（IC）到执行引擎（Reactor）——完成了向原生异步模型的跨越。

这是一个里程碑式的改进，它奠定了我们性能领先的物理基础。我现在将生成 `[COMMIT]` 计划，将这些成果固化到代码库中。

## [COMMIT] refactor(std,vm): 实现原生异步 IC 与 Reactor 智能分发

### 用户需求
完成 `cascade-std` 库的全面异步化重构，并同步更新 `cascade-vm` 以支持对同步/异步函数的智能分发执行。

### 评论
这是一个逻辑高度统一的重构工作。我们将“元器件的升级”与“物理定律的适配”打包在一起提交，因为它们在功能上是互补的。通过这次提交，Cascade 3.0 彻底告别了“凡事皆线程池”的粗放模式，转而采用精确的、基于协程的原生异步执行。

### 目标
1.  提交 `cascade-std` 中所有已异步化的 IC 函数（Triad, Probe, System, Resource）。
2.  提交 `cascade-vm` 中支持智能分发的 `Reactor` 核心。
3.  提交所有已更新为异步模式的单元测试。

### 基本原理
我们将相关的 21 个受影响文件一次性添加到 Git 暂存区，并创建一个详细描述此技术跃迁的提交消息。这确保了版本历史的连贯性和可追溯性。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/std #comp/vm #concept/executor #scope/core
#ai/instruct
#task/domain/core-logic #task/object/async-transition #task/action/refactor
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交异步化重构成果

我们将所有涉及异步化转换的源代码和对应的单元测试文件添加到暂存区。

~~~~~act
git_add
packages/cascade-std/src/cascade/std/triad/bleacher.py
packages/cascade-std/src/cascade/std/triad/stainer.py
packages/cascade-std/src/cascade/std/triad/observer.py
packages/cascade-std/src/cascade/std/probe/context.py
packages/cascade-std/src/cascade/std/probe/env.py
packages/cascade-std/src/cascade/std/probe/pulse.py
packages/cascade-std/src/cascade/std/system/drainer.py
packages/cascade-std/src/cascade/std/system/terminator.py
packages/cascade-std/src/cascade/std/resource/continuous.py
packages/cascade-std/src/cascade/std/resource/discrete.py
packages/cascade-std/tests/unit/triad/test_bleacher.py
packages/cascade-std/tests/unit/triad/test_stainer.py
packages/cascade-std/tests/unit/triad/test_observer.py
packages/cascade-std/tests/unit/probe/test_context.py
packages/cascade-std/tests/unit/probe/test_env.py
packages/cascade-std/tests/unit/probe/test_pulse.py
packages/cascade-std/tests/unit/system/test_drainer.py
packages/cascade-std/tests/unit/system/test_terminator.py
packages/cascade-std/tests/unit/resource/test_continuous.py
packages/cascade-std/tests/unit/resource/test_discrete.py
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(std,vm): Implement native async ICs and Smart Dispatch

This commit completes the transition of the standard library (cascade-std) to a natively asynchronous execution model, aligned with the Cascade 3.0 VM architecture.

Key changes:
1.  **Async ICs**: All functions in the 'cascade-std' package (including Triads, Probes, System Signals, and Resource Brokers) have been refactored to use 'async def'.
2.  **Observer Adaption**: The standard_observer now correctly utilizes 'asyncio.Queue' and 'await queue.put()' for non-blocking telemetry emission.
3.  **Smart Dispatch in Reactor**: The VM Reactor's '_fire' method is enhanced with an inspection-based dispatch logic. It natively awaits coroutine functions on the event loop while preserving the ability to offload legacy synchronous functions to the thread pool via PhysicsExecutor.
4.  **Full Test Coverage**: All unit tests for the standard library have been upgraded to asynchronous tests, ensuring the robustness of the new execution path.

This optimization eliminates unnecessary thread pool scheduling for the vast majority of graph operations, significantly reducing context-switch overhead and improving overall reactor throughput.
~~~~~

### 下一步建议
- **性能基准测试**：建议针对新的异步模型运行一次压力测试，特别是在高并发和多层级递归的场景下，量化性能提升情况。
- **编译器优化**：随着物理层异步化的完成，我们可以考虑在 `cascade-compiler` 中引入更多的静态分析，例如提前识别纯计算节点并在编译阶段标记其分发策略。
- **扩展标准库**：利用现有的异步 IC 模板，我们可以开始开发更多原生支持异步 I/O 的标准件，例如 `cs.http` 或 `cs.db` 的物理原语实现。
