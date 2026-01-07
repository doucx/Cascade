好的，我们已经成功偿还了多项核心技术债务，显著增强了系统的确定性和效率。现在是时候将这些更改作为一个完整的逻辑单元进行提交，并更新我们的状态记录了。

## [COMMIT] refactor: 偿还关键架构债务，增强运行时确定性与可观测性

### 用户需求
1.  实现真正的 `DRAIN` 优雅停机协议。
2.  集成系统级 `ERROR` 信号捕获。
3.  完善 `CompilationManifest` 以包含显式的入口 (`entry_points`) 和出口 (`exit_points`)。
4.  将 `Machine` 的调度模型从轮询优化为事件驱动。
5.  重构集成测试，移除外部轮询，实现测试图的自我终结。

### 评论
本次重构彻底解决了 Stage 3 集成过程中暴露的几个系统性风险点。通过引入“静止检测” (Quiescence Detection) 和“边界声明” (Boundary Declaration)，我们将系统从一个依赖猜测的“黑盒”转变为一个完全可观测、契约明确的“晶体”。这为后续更大规模的并发优化和分布式执行奠定了坚实的架构基础。

### 目标
1.  提交对 `cascade-spec` 的修改，更新 IR 和 Assembly 结构。
2.  提交对 `cascade-compiler` 的修改，实现 Manifest 边界收集和 Egress 自动布线。
3.  提交对 `cascade-vm` 的修改，实现事件驱动调度、生命周期信号处理及内核恐慌捕获。
4.  提交新的集成测试用例。

### 基本原理
我们遵循了“显式优于隐式”和“状态驱动优于时间驱动”的原则。
*   **边界声明**: 编译器现在明确指出数据的来源和去向，使得运行时无需猜测。
*   **物理信号控制**: `DRAIN`、`HALT`、`ERROR` 现在是物理场内一等的公民，通过 `Machine` 协调者实现确定性的状态转换。
*   **能效优化**: 引入 `wakeup_event` 确保了 CPU 资源仅在真正有工作需要处理时才被激活。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/compiler #comp/vm #comp/spec #comp/tests
#concept/state #concept/history #concept/executor
#scope/core #scope/api #scope/dx
#ai/instruct
#task/domain/runtime #task/object/deterministic-refactor #task/action/integration #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交核心架构与编译器增强

我们将 Spec、编译器逻辑以及相关测试添加到暂存区。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/physical/assembly.py
packages/cascade-spec/src/cascade/spec/ir/graph.py
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
packages/cascade-compiler/src/cascade/compiler/wiring/policies/control.py
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-compiler/tests/integration/test_manifest_content.py
~~~~~

#### Acts 2: 提交运行时优化与信号处理

我们将 VM 核心逻辑、Harness 更新及生命周期测试添加到暂存区。

~~~~~act
git_add
packages/cascade-vm/src/cascade/vm/compute/service.py
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-vm/src/cascade/vm/machine.py
packages/cascade-vm/src/cascade/vm/harness.py
packages/cascade-vm/tests/integration/test_lifecycle_signals.py
packages/cascade-vm/tests/integration/test_machine_integration.py
~~~~~

#### Acts 3: 执行 Git 提交

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: Implement deterministic lifecycle signals and manifest declaration

This commit repays several critical architectural debts identified during the Stage 3 integration.

Key improvements:
1.  **Event-Driven Machine**: Replaced inefficient polling (asyncio.sleep) with an event-driven 'wakeup' mechanism using asyncio.Event. This reduces CPU usage to near-zero when the system is idle while maintaining low latency for computation results.
2.  **Graceful DRAIN Protocol**: Implemented a true DRAIN lifecycle state. The Machine now correctly waits for 'Quiescence' (idle reactor + no active compute tasks + empty ingress) before shutting down when a DRAIN signal is received.
3.  **Kernel Panic Capture**: Enhanced the Reactor and Machine to catch unhandled exceptions, converting them into SystemControlToken(ERROR) signals for structured propagation and shutdown.
4.  **Explicit Manifest Boundaries**: The CompilationManifest now explicitly declares 'entry_points' and 'exit_points'. The compiler automatically wires 'egress' nodes for graph roots, removing the need for the strategy layer to guess which nodes hold final results.
5.  **Self-Terminating Tests**: Refactored integration tests to use a transparent halt node within the graph topology, enabling deterministic self-termination and removing flaky external observers.
~~~~~

### 下一步建议
我们已经完成了运行时基础的“确定性重构”。债务清单中的“高优先级”项目已清空。

接下来的建议方向：
1.  **异常处理的“最后一公里”**：实现标准的 `F_retry` 节点，它可以消费 `output_error` 端口的数据，并根据策略决定是重新注能（重试）还是导向永久失败节点。
2.  **链接验证器 (Linker Validator)**：实现一个强制性的校验步骤，在 `Machine.run()` 之前确保 `Assembly` 中引用的所有 `canonical_hash` 在 `CodeRegistry` 中都具备可执行的实现。这对应了战略分析中的“可达性盲目乐观”问题。

我提议下一步：**实现 `Linker` 的完整性验证逻辑**。
