好的，第一阶段“建立资源物理学基础”已经圆满完成。我们通过引入 `ResourceRegistry` 并统一物理函数签名，成功地将计算图与具体的运行时环境在物理契约层面进行了隔离。

现在，我将生成 `[COMMIT]` 计划，将这些核心架构变更提交到代码库。

## [COMMIT] refactor(vm): implement ResourceRegistry and unify physical function signatures

### 用户需求
执行“统一上下文与资源管理”路线图的阶段 1：
1. 实现 `ResourceRegistry`。
2. 改造 `Reactor` 以支持资源注入。
3. 统一 `cascade-std` 所有物理原语的函数签名。
4. 修复并重构测试套件。

### 评论
这是一个里程碑式的提交。它标志着 Cascade 物理层正式从“隐式依赖（通过 partial/闭包）”转向“显式注入（通过 Registry）”。这为实现图的完全序列化和分布式执行铺平了道路，同时通过重构测试套件，显著提升了代码的 DX（开发者体验）。

### 目标
创建一个完整的 Git 提交，包含 `ResourceRegistry` 的实现、`Reactor` 的改造、`cascade-std` 签名的统一以及所有测试的修复。

### 基本原理
通过强制所有物理函数接受 `resources: Any` 参数，我们在底层建立了一个通用的物理契约。这种统一性允许 `Reactor` 在不了解函数具体需求的情况下，安全地注入环境资源。同时，通过 `pytest` fixture 的重构，我们确保了测试代码在面对架构变更时依然保持简洁和健壮。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/std #concept/resource #scope/core #ai/instruct #task/domain/core #task/object/resource-registry #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交阶段 1 的所有变更

我们将所有涉及到的源文件和测试文件添加到暂存区。

~~~~~act
git_add
packages/cascade-vm/src/cascade/vm/resource_registry.py
packages/cascade-vm/src/cascade/vm/__init__.py
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-std/src/cascade/std/probe/const.py
packages/cascade-std/src/cascade/std/probe/context.py
packages/cascade-std/src/cascade/std/probe/env.py
packages/cascade-std/src/cascade/std/probe/pulse.py
packages/cascade-std/src/cascade/std/resource/continuous.py
packages/cascade-std/src/cascade/std/resource/discrete.py
packages/cascade-std/src/cascade/std/resource/requestor.py
packages/cascade-std/src/cascade/std/system/drainer.py
packages/cascade-std/src/cascade/std/system/terminator.py
packages/cascade-std/src/cascade/std/triad/bleacher.py
packages/cascade-std/src/cascade/std/triad/observer.py
packages/cascade-std/src/cascade/std/triad/stainer.py
packages/cascade-vm/tests/unit/test_reactor.py
packages/cascade-vm/tests/integration/test_observability_congestion.py
packages/cascade-vm/tests/integration/test_branching.py
packages/cascade-vm/tests/integration/test_ping_pong.py
packages/cascade-vm/tests/integration/test_resource_backpressure.py
packages/cascade-std/tests/unit/resource/test_discrete.py
packages/cascade-std/tests/unit/resource/test_continuous.py
packages/cascade-std/tests/unit/triad/test_observer.py
packages/cascade-std/tests/unit/probe/test_context.py
packages/cascade-std/tests/unit/probe/test_env.py
packages/cascade-std/tests/unit/probe/test_pulse.py
packages/cascade-std/tests/unit/system/test_drainer.py
packages/cascade-std/tests/unit/system/test_terminator.py
packages/cascade-std/tests/unit/triad/test_bleacher.py
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(vm): implement ResourceRegistry and unify physical function signatures

This commit implements Phase 1 of the "Unified Context & Resource Management" roadmap, establishing a clean separation between the computational graph and the runtime environment.

Key Changes:
1. **ResourceRegistry**: Introduced a new central registry in `cascade-vm` to manage runtime resources (queues, sockets, etc.) by unique IDs.
2. **Reactor Refactor**: Updated `Reactor` to hold a `ResourceRegistry` instance and inject it as a mandatory third argument `(inputs, node, resources)` into all physical functions during execution.
3. **Signature Standardization**: Updated all physical primitives in `cascade-std` (Probes, Brokers, Triad ICs, System ICs) to adhere to the new 3-parameter signature.
4. **Test Suite Modernization**: Fixed all failing tests by injecting Mock registries. Refactored major test modules in `cascade-std` to use pytest fixtures, significantly reducing boilerplate and improving maintainability.

This architectural shift eliminates the need for 'functools.partial' when binding dependencies to nodes, making the physical graph truly serializable and environment-agnostic.
~~~~~

### 下一步建议
阶段 1 已顺利闭环。接下来我们将进入 **阶段 2：应用新模型并重构测试工具 (Application & Tooling Refactor)**。

我们的首要任务是重构 `EventDrivenRunner`。目前它还在内部使用 `partial` 来强行注入 `queue` 给 `standard_observer`。我们将改为：
1. 让 `EventDrivenRunner` 将 `event_queue` 注册到其内部的 `ResourceRegistry` 中（ID 为 `"system.observer.queue"`）。
2. 让 `standard_observer` 内部通过 `resources.get("system.observer.queue")` 获取队列。

完成后，我们将彻底终结物理层中的所有“魔法”绑定。如果你准备好了，请告知。
