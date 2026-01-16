好的，我们已经成功完成了对 `Engine` 的深度架构重构。这次改动不仅彻底消除了 `cascade-runtime` 与 `cascade-execution-graph` 之间的循环依赖，还通过引入中央工厂和统一测试 Fixture，解决了核心服务状态分裂的问题，并大幅提升了系统的可维护性。

我将生成一个 `[COMMIT]` 计划，将这些变更作为一个逻辑单元进行提交。

## [COMMIT] refactor(runtime): Decouple Engine via strict DI and central factory

### 用户需求
将之前的重构变更提交到 Git 仓库。

### 评论
这次重构是 Cascade 架构演进中的一个里程碑。我们不仅修复了一个隐蔽的循环依赖 Bug，还通过强制实施依赖注入（DI），将 `Engine` 从一个复杂的“自组装容器”转变为一个纯粹的“服务集成器”。通过中央工厂 `create_engine` 和全局 Pytest Fixture 的引入，我们确保了在生产和测试环境下整个运行时堆栈的一致性和可观测性。

### 目标
1.  将所有受影响的文件添加到 Git 暂存区。
2.  创建一个内容详尽的提交记录，说明重构的原因、方法和收益。

### 基本原理
按照 Quipu 协议的要求，我们在确认所有测试通过并稳定后，通过一个独立的 `[COMMIT]` 计划执行 Git 操作。这确保了文件系统的变更与版本控制操作物理隔离，保证了开发历史的清晰。

### 标签
#intent/refine #flow/done #priority/high #comp/runtime #comp/application #comp/library #comp/tests #scope/core #ai/instruct #task/domain/architecture #task/object/dependency-injection #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交重构变更

我将添加所有修改过的核心文件和测试套件，并提交。

~~~~~act
git_add
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(runtime): Decouple Engine from strategies via strict DI

Implemented a major architectural refactoring of the 'Engine' class to
resolve circular dependencies and improve service modularity.

Core Changes:
- Engine: Removed self-assembly logic for execution strategies and core
  services (ConstraintManager, ResourceContainer). The constructor now
  strictly requires these as dependencies.
- Central Factory: Introduced 'create_engine' in cascade-runtime/host/factory.py
  as the Single Source of Truth for assembling the runtime stack.
- State Unification: Ensured that Engine and its ExecutionStrategy share
  identical service instances, fixing a critical bug where constraints
  received via connectors were ignored by the execution logic.
- Application Integration: Updated CascadeApp to use the central factory
  and introduced a 'use_vm' flag for easy switching to the experimental VM.
- Test Infrastructure: Unified all tests (unit, integration, E2E) to use
  global 'engine' and 'engine_factory' fixtures, removing manual assembly
  overhead and ensuring architectural correctness in tests.

This change restores the correct dependency flow (Strategy -> Runtime)
and establishes a robust foundation for future execution backend
experiments.
~~~~~

### 下一步建议
重构工作现已圆满完成。建议在接下来的开发中：
- **监控 CI**: 观察 CI 环境下的执行稳定性，确保没有因环境差异导致的竞态条件。
- **扩展 VM 能力**: 既然后端切换已经变得非常简单，可以考虑逐步在更多测试场景中启用 `use_vm=True` 来验证新引擎的兼容性。
- **文档更新**: 如果有开发者文档，应更新有关 `Engine` 实例化和自定义 `ExecutionStrategy` 的说明。
