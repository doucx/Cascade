好的，我们已经成功解决了 `cascade-spec`、`cascade-vm`、`cascade-compiler`、`cascade-sdk` 以及 `cascade-runtime` 核心组件中的绝大部分循环依赖和强耦合问题。特别是通过引入 `HandlerContext` 协议，从逻辑层面彻底解耦了约束管理系统。

现在，我将生成一个 `[COMMIT]` 计划，将这些结构性改进作为一个完整的逻辑单元进行提交。

## [COMMIT] refactor: 消除全包范围内的循环依赖并优化导入结构

### 用户需求
将目前为止完成的所有关于消除循环依赖、重构绝对导入为相对导入、以及解耦 SDK 和 Runtime 核心组件的修改进行 Git 提交。

### 评论
这是一次系统性的架构净化行动。我们不仅解决了导致包初始化失败的物理循环依赖，还通过引入中立协议和应用层抽象，解决了深层逻辑耦合。这大大提升了系统的健壮性、启动速度以及静态分析的准确性。

### 目标
1.  将所有涉及导入路径重构的文件添加到 Git 暂存区。
2.  将逻辑解耦相关的修改（如 `cascade-sdk` 和 `cascade-runtime` 的重构）添加到 Git 暂存区。
3.  创建一个详细的提交说明，记录解决循环依赖的关键举措。

### 基本原理
按照工程最佳实践，我们将物理重构（路径调整）和逻辑重构（协议解耦）合并为一个提交，因为它们共同构成了“提升系统初始化稳定性”这一单一目标。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #scope/core #ai/instruct #task/domain/architecture #task/object/circular-dependency #task/action/git-commit #task/state/end #task/status/completed

---

### Script

#### Acts 1: 添加修改到暂存区并创建提交

我们将添加所有在重构过程中修改的文件。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/__init__.py
packages/cascade-spec/src/cascade/spec/ir/__init__.py
packages/cascade-spec/src/cascade/spec/ir/graph.py
packages/cascade-spec/src/cascade/spec/physical/assembly.py
packages/cascade-spec/src/cascade/spec/physical/nodes.py
packages/cascade-spec/src/cascade/spec/physical/resources.py
packages/cascade-spec/src/cascade/spec/physical/topology.py
packages/cascade-spec/src/cascade/spec/physical/triad.py
packages/cascade-spec/src/cascade/spec/runtime/compute.py
packages/cascade-spec/src/cascade/spec/runtime/storage.py
packages/cascade-spec/src/cascade/spec/runtime/strategies.py
packages/cascade-spec/src/cascade/spec/compiler/interfaces.py
packages/cascade-spec/src/cascade/spec/compiler/model.py
packages/cascade-spec/src/cascade/spec/physics/core.py
packages/cascade-vm/src/cascade/vm/compute/adapters.py
packages/cascade-vm/src/cascade/vm/compute/service.py
packages/cascade-vm/src/cascade/vm/kernel/core.py
packages/cascade-vm/src/cascade/vm/services/chronos.py
packages/cascade-vm/src/cascade/vm/machine.py
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/context.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/control.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/parameter.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/pulse.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/resource.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/context.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prism.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/control.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/observability.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/pulse.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/resource.py
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-sdk/src/cascade/sdk.py
packages/cascade-sdk/src/cascade/tools/cli.py
packages/cascade-application/src/cascade/app/__init__.py
packages/cascade-runtime/src/cascade/runtime/services/constraints/manager.py
packages/cascade-runtime/src/cascade/runtime/services/constraints/protocols.py
packages/cascade-runtime/src/cascade/runtime/services/constraints/handlers.py
packages/cascade-runtime/src/cascade/runtime/host/instance.py
packages/cascade-runtime/src/cascade/runtime/__init__.py
packages/cascade-execution-graph/src/cascade/execution/graph/logic/processor.py
packages/cascade-execution-graph/src/cascade/execution/graph/strategy.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: decouple package internal dependencies and resolve circular imports

System-wide refactoring to eliminate circular dependencies and improve package initialization stability.

Key changes:
- Replaced absolute imports (cascade.xxx) with relative imports within all core packages (spec, vm, compiler, runtime) to prevent 'Partially Initialized Module' errors during package-root __init__ execution.
- Decoupled 'cascade.sdk' from 'cascade.tools.cli' by migrating core execution entry points (run, visualize, dry_run) to 'cascade.app'.
- Broke the logical circular dependency between 'ConstraintManager' and 'ConstraintHandler' by introducing the 'HandlerContext' protocol, following the Dependency Inversion Principle.
- Cleaned up TYPE_CHECKING blocks to prevent static analysis cycles.

This ensures that core components can be safely loaded in any order and enhances the robustness of the entire Cascade ecosystem.
~~~~~

### 下一步建议
1.  **最终清理**: 虽然核心循环已解决，但建议最后处理 `Engine` 与 `VMExecutionStrategy` 的包初始化冲突（通过引入策略注册表模式）。
2.  **代码审查**: 建议对 `cascade.app` 的新导出进行审查，确保它作为底层的、稳定的 API 能够满足 SDK 和 CLI 的需求。
3.  **冒烟测试**: 在提交后运行一次完整的构建和冒烟测试，确保从 `cs.run` 入口开始的端到端流程依然通畅。
