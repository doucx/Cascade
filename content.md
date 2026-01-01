好的，我们已经圆满完成了 Phase 4.5 的所有重构与对齐任务。现在的代码库不仅解决了所有已知的静态分析错误，而且在架构上更加符合《全对称计算物理场》白皮书的定义。

这是一个逻辑上完整的里程碑，我将生成一个 `[COMMIT]` 计划来记录这些变更。

## [COMMIT] refactor(physics): align with whitepaper and fix static analysis

### 用户需求
1.  **修复技术债务**: 解决 `pyright` 发现的类型错误，并将中文注释统一为英文。
2.  **形式化环境资源**: 引入 `EnvironmentDef`，将资源定义从编译器逻辑中剥离，建立客观的资源边界条件。
3.  **闭合观测环路**: 在物理图中实例化全局 `F_obs` 节点并连接 `D_life`，确保遥测数据的流出。

### 评论
这次提交是 Cascade 3.0 重构过程中的一个重要“存盘点”。通过将资源管理从“按需生成”转向“基于环境供给”，我们确立了物理场中因果关系的正确性。同时，观测环路的闭合为后续全系统集成时的调试和监控提供了架构层面的保证。

### 目标
创建一个包含以下变更的 Git 提交：
1.  **Spec 层**: 新增 `environment.py`，更新 `__init__.py`。
2.  **Compiler 层**: 重构 `Builder` 和 `Expander`，实现环境验证和观测节点实例化。
3.  **VM 层**: 修复指令集中的类型提示。
4.  **测试套件**: 增加环境验证和观测拓扑的单元测试，修复集成测试中的接口变更。

### 基本原理
按照单路提交原则，我们将所有相关的、已验证的代码修改添加并提交。由于这是一次跨多个包的关联修改（Spec 的变更影响了 Compiler 和 VM 及其测试），作为一个单一的逻辑单元提交是最合适的。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/spec #comp/compiler #comp/vm 
#concept/resources #concept/observability #scope/core 
#ai/delegate
#task/domain/refactoring #task/object/physics-field-alignment #task/action/integration #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交物理场对齐与清理变更

我们将涉及的所有修改文件添加到 Git 暂存区，并创建一个内容详尽的提交说明。

~~~~~act
git_add
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-compiler/tests/unit/backend/test_builder.py
packages/cascade-compiler/tests/unit/backend/test_builder_environment.py
packages/cascade-compiler/tests/unit/backend/test_builder_observability.py
packages/cascade-spec/src/cascade/spec/__init__.py
packages/cascade-spec/src/cascade/spec/environment.py
packages/cascade-spec/src/cascade/spec/environment.stitcher.yaml
packages/cascade-spec/src/cascade/spec/input.py
packages/cascade-vm/src/cascade/vm/instructions/bleacher.py
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(physics): align with whitepaper and fix static analysis

This commit completes Phase 4.5 by formalizing the physical field's boundary
conditions and ensuring holographic observability.

Key Architectural Changes:
1.  **Objective Environment**: Introduced `EnvironmentDef` and `ResourceDef` in Spec.
    `Builder` now requires an environment to build the graph, enforcing that
    all requested task constraints must exist in the objective environment.
    This fixes the "demand creates supply" fallacy.
2.  **Closed Observability Loop**: The physical graph now includes a global
    `F_obs` (ObservabilityNode) connected to the `D_life` bus. This ensures
    that telemetry events are processed and not lost in a data sink.
3.  **Typed Triads**: Updated `SubGraph` and `standard_bleacher` with proper
    Optional and Any typing to satisfy pyright and improve DX.

Maintenance:
- Translated all internal comments in `cascade.spec.input` to English.
- Updated all integration and unit tests to align with the new Builder(ir, env) signature.
- Added deterministic tests for environment resource validation and observability topology.
~~~~~

### 下一步建议

我们已经建立了稳固且符合物理学原理的底层。根据路线图，下一步我们将进入 **Phase 5: 全系统集成 (System Integration)**。

由于底层 `Builder` 现在要求 `EnvironmentDef`，我们需要在更高层级（如 `Engine` 或 `VMExecutionStrategy`）建立一种机制，来管理默认环境或允许用户自定义环境。

我建议我们开始实施 **Phase 5.1: 重建 `VMExecutionStrategy`**，它将负责连接 `Frontend` (IR), `Backend` (Builder), 和 `Reactor`。
