好的，Phase 1 和 Phase 2 的实施与验证已经圆满完成。我们成功清理了标准库，优化了编译器后端，并建立了一套高保真的测试基础设施。

现在，我将为这些变更创建一个正式的 Git 提交。

## [COMMIT] refactor(vm): implement Phase 1 & 2 of Physical Kernel Integration

### 用户需求
完成 **Project Singularity** 集成路线图的前两个阶段：
1.  **Phase 1**: 净化标准库，移除所有 `probe` 组件，并引入 `standard_egress` 作为唯一的物理出口。
2.  **Phase 2**: 优化编译器后端，移除对 `F_probe` 节点的依赖，建立直接的 `D_const` 连线模型。
3.  **Harness Update**: 升级测试工具链，支持常量物质化 (Materialization) 和标量提升 (Scalar Hoisting) 机制。

### 评论
这是 Cascade VM 迈向生产级的里程碑。通过将“数据采样”逻辑从物理层彻底剥离到策略层/计算层，我们实现了物理内核的纯粹性。特别是“标量提升”机制的引入，完美解决了物理内核无 I/O 执行与读取资源约束值之间的矛盾，为后续的 TCO 优化打下了坚实基础。

### 目标
创建一个包含标准库净化、编译器瘦身及测试工具链升级的完整提交。

### 基本原理
遵循“计算同质性”和“边界显式化”公理。通过在编译时简化结构、在加载时预处理数据，我们实现了一个更紧凑、更鲁棒的物理执行模型。

### 标签
#intent/refine #flow/ready #priority/high #comp/vm #comp/compiler #comp/std #concept/physics #concept/materialization #scope/core #ai/instruct #task/domain/vm #task/object/physical-kernel-integration #task/action/standardization-optimization #task/state/continue

---

### Script

#### Acts 1: 提交 Phase 1 & 2 的所有变更

我们将所有新增、修改以及由于目录删除导致的变更添加到暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/cascade-std/src/cascade/std/system/egress.py
packages/cascade-vm/src/cascade/vm/linker.py
packages/cascade-compiler/src/cascade/compiler/wiring/policies/parameter.py
packages/cascade-compiler/src/cascade/compiler/wiring/prisms/discrete.py
packages/cascade-spec/src/cascade/spec/runtime/storage.py
packages/cascade-vm/src/cascade/vm/harness.py
packages/cascade-compiler/tests/integration/test_resource_contention.py
packages/cascade-vm/tests/integration/test_ref_architecture.py
packages/cascade-vm/tests/integration/test_resource_backpressure.py
packages/cascade-std/src/cascade/std/probe
packages/cascade-std/tests/unit/probe
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(vm): implement Phase 1 & 2 of Physical Kernel Integration

This commit marks the completion of the first two phases of the Project Singularity roadmap, focusing on physical layer purification and compiler optimization.

Key Changes:
1.  **Standard Library Purification (Phase 1)**:
    -   Completely removed the legacy `cascade.std.probe` package. All environment/parameter sampling is now treated as a compute task or handled via pre-materialization.
    -   Introduced `cascade.std.system.egress.standard_egress`, the new physical exit node that teleports tokens to the strategy-managed egress queue.
    -   Updated `Linker` to map `egress.*` nodes and removed all probe-related mappings.

2.  **Compiler Backend Thinning (Phase 2)**:
    -   Refactored `ParameterWiringPolicy` and `DiscreteResourcePrism` to eliminate the generation of `F_probe` and `D_probed` nodes.
    -   Implemented a direct `D_const -> TargetFunc` wiring model, reducing graph complexity and node count per constant.

3.  **Test Harness Alignment**:
    -   Updated `EventDrivenRunner` to implement 'Constant Materialization' and 'Scalar Hoisting'.
    -   User constants are now automatically materialized into `Ref` objects before reactor priming.
    -   Critical kernel-readable values (like resource amounts) are hoisted into Ref metadata, satisfying the Data-Free Physics Axiom while maintaining synchronous kernel execution.

These changes establish a robust, high-fidelity physical field model ready for integration into the runtime engine.
~~~~~

### 下一步建议
我们已经稳固了底层的物理模型。下一步是 **Phase 3: 策略层重构**。

我们需要开始编写 `packages/cascade-runtime/src/cascade/runtime/strategies/vm.py`，实现 `CascadeVMStrategy`。我建议首要任务是实现其 **子阶段 3.2: 编译与物质化** 逻辑，将我们在测试工具中验证过的物质化算法正式引入生产级策略中。
