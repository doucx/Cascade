好的，重构阶段的所有测试均已通过。现在我们将创建一个包含所有变更的提交，标志着 Cascade 核心确定性基础建设的圆满完成。

[简要回答]
我将生成一个 `[COMMIT]` 计划，将涉及编译器契约增强、链接器校验、VM 信号驱动生命周期以及错误路由的所有修改正式提交到版本库。

## [COMMIT] refactor(core): 建立确定性执行基础 (Manifest, Linker Validation & Signal Lifecycle)

### 用户需求
结束“Stage 3 - Reset”重构阶段，将编译器增强、启动前校验、信号驱动退出和错误路由功能合并入主分支，确保系统地基稳固。

### 评论
这次重构彻底解决了此前“假死”和“隐式命名依赖”的根本问题。通过显式的 `CompilationManifest`，我们将 Strategy 与 Compiler 的耦合从代码层面提升到了数据结构层面；通过信号驱动机制，我们让 VM 的行为变得完全可预测。

### 目标
1.  提交 `CompilationManifest` 及其相关的编译器（Frontend/Backend）变更。
2.  提交 `Linker` 的完整性校验逻辑及其单元测试。
3.  提交 `Machine` 的信号驱动循环和 `Reactor` 的控制信号拦截机制。
4.  提交 `Stainer` 的错误流路由逻辑。
5.  提交全新的微观物理验证测试套件。

### 基本原理
按照 HFEA 协议，我们拒绝了对“假死”问题的战术修补，而是选择了回归架构基石进行重演。这些改动虽然涉及面广，但统一了物理层的行为准则，即“一切皆显式，万物皆有迹”。

### 标签
#intent/refine #flow/ready #priority/critical
#comp/compiler #comp/engine #comp/runtime #comp/std
#task/domain/core #task/object/execution-engine #task/action/refactor
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交确定性重构的所有变更

我们将所有修改的文件添加到暂存区。由于涉及包较多，我们将分包执行 `git_add`，最后统一执行一个内容详尽的 `git_commit`。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/ir/graph.py
packages/cascade-spec/src/cascade/spec/physical/assembly.py
packages/cascade-spec/src/cascade/spec/runtime/system.py
~~~~~

~~~~~act
git_add
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-compiler/tests/unit/backend/test_builder.py
packages/cascade-compiler/tests/unit/backend/test_builder_environment.py
packages/cascade-compiler/tests/unit/backend/test_builder_observability.py
packages/cascade-compiler/tests/integration/test_assembly_purity.py
packages/cascade-compiler/tests/integration/test_graph_purity.py
packages/cascade-compiler/tests/integration/test_resource_contention.py
packages/cascade-compiler/tests/integration/test_sovereign_wiring.py
packages/cascade-compiler/tests/integration/test_source_node_execution.py
packages/cascade-compiler/tests/integration/test_ref_architecture.py
packages/cascade-compiler/tests/integration/test_resource_backpressure.py
~~~~~

~~~~~act
git_add
packages/cascade-vm/src/cascade/vm/linker.py
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-vm/src/cascade/vm/machine.py
packages/cascade-vm/tests/unit/test_linker.py
packages/cascade-vm/tests/integration/test_machine_integration.py
packages/cascade-vm/tests/unit/physics/test_micro_physics.py
~~~~~

~~~~~act
git_add
packages/cascade-std/src/cascade/std/triad/stainer.py
packages/cascade-std/src/cascade/std/system/terminator.py
packages/cascade-std/src/cascade/std/system/drainer.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): Establish deterministic foundation for VM execution

This commit completes the "Phase 3-Reset" architectural reconstruction,
replacing implicit assumptions and heuristic-based logic with explicit
contracts and signal-driven lifecycles.

Key components:

1.  **Compilation Manifest**: 'Builder.build' now returns a 'CompilationArtifact'
    containing a 'CompilationManifest'. This manifest explicitly maps logical
    UUIDs (from LazyResult) to physical Node IDs, eliminating the need for
    the Strategy layer to guess physical IDs.

2.  **Linker Integrity Check**: The Linker now performs a mandatory pre-run
    validation, ensuring all code hashes referenced in the physical Assembly
    exist in the CodeRegistry. Failure to link now results in a descriptive
    'LinkerError' before the VM starts.

3.  **Signal-Driven Lifecycle**: Introduced 'SystemControlToken' and 'ControlCommand'.
    The 'Machine' run loop has been refactored to stop only upon receiving an
    explicit HALT/DRAIN signal or a critical error, replacing the fragile
    'idle-exit' mechanism that caused premature shutdowns.

4.  **Error-as-Data Routing**: The 'standard_stainer' now implements sovereign
    routing for exceptions. If a worker fails, the exception is encapsulated
    as a Token and routed to the 'output_error' port (if defined), preserving
    energy conservation laws in the physical field.

5.  **Micro-Physics Verification**: Added a specialized test suite to verify
    fundamental physics laws (The Spark, The Crash, The Halt) without
    business logic overhead.

This refactoring provides the rock-solid ground required for implementing
complex dynamic features like cs.Router and cs.Map.
~~~~~

### 下一步建议
我们已经完成了地基重写。接下来的路线将非常顺畅。
按照原始的阶段规划，我们应该重新回到 **Stage 3: 高级 DSL 能力**。
由于现在的物理层已经支持了主权路由（Sovereign Routing）和信号机制，实现 **`cs.Router`** 将变得非常直观。

我建议下一步开始实现 `cs.Router` 的编译器前端生成逻辑。
