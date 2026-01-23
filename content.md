好的，我们已经完成了针对物理布线策略缺陷以及 VM 运行时依赖注入问题的完整修复。测试结果显示，原本失败的 4 个 `test_resource.py` 集成测试现在已经全部通过（失败总数从 35 降至 31）。

我将生成一个 `[COMMIT]` 计划来记录这些变更。

## [COMMIT] fix(compiler,vm): resolve wiring deadlocks and recursive DI issues

### 用户需求
修复编译器在处理带有静态输入或资源注入的源节点时的布线缺陷，并增强 VM 运行时的依赖注入能力以支持嵌套资源和生命周期事件。

### 评论
这是一次关键的底层架构加固。通过标准化物理端口并精细化触发逻辑，我们消除了编译器中的“死锁”风险。同时，VM 运行时的改进使其在功能特性上与原生的 Graph 引擎达到了对等，为后续完全迁移到物理拓扑执行奠定了坚实基础。

### 目标
1.  **编译器修复**: 
    *   确保所有 `Launcher` 节点始终具有物理 `__pulse__` 端口。
    *   改进脉冲生成策略，使其能正确识别无上游依赖（仅有静态或注入参数）的“孤立”源节点。
2.  **VM 运行时修复**:
    *   实现资源的递归解析，允许资源提供者依赖于其他资源。
    *   在 `ResourceContainer` 中统一异常类型为 `NameError`。
    *   在 VM 适配层发布资源获取和释放事件，满足可观测性要求。

### 标签
#intent/fix #flow/ready #priority/high 
#comp/compiler #comp/runtime #comp/vm #concept/wiring #concept/dependency-injection 
#ai/instruct 
#task/domain/compiler #task/object/wiring-policy #task/action/fix #task/state/end

---

### Script

#### Acts 1: 提交代码变更

我们将所有涉及编译器和运行时的修复提交到 Git。

~~~~~act
git_add
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/pulse.py
packages/cascade-runtime/src/cascade/runtime/services/resources/container.py
packages/cascade-vm/src/cascade/vm/compute/adapters.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(compiler,vm): resolve wiring deadlocks and implement recursive DI

This commit fixes a critical defect in the compiler where source nodes with
static inputs or resource injections (via cs.inject) failed to be triggered
properly. 

Key changes:
- Compiler: Standardized LauncherNode to always expose a '__pulse__' port,
  decoupling physical capability from logical wiring policies.
- Compiler: Updated PulseExpansionPolicy to correctly identify nodes needing
  self-bootstrapping pulses by checking for upstream execution dependencies
  rather than simply the presence of any input.
- VM Runtime: Implemented recursive resource dependency resolution in
  BridgedComputeService, allowing resources to depend on other resources.
- VM Runtime: Standardized ResourceContainer to throw NameError on missing
  resources and added publication of ResourceAcquired/Released events.

These fixes resolve several integration test failures in test_resource.py.
~~~~~

### 下一步建议
- **回归测试**: 建议在更复杂的现实工作流中测试这些改动，特别是那些深度嵌套的资源依赖。
- **文档更新**: 更新架构文档中关于“物理布线”的部分，明确 Pulse 端口作为所有 Launcher 通用接口的地位。
- **处理其他失败**: 现在 DI 和基础布线已稳定，可以开始着手解决剩下的 31 个测试失败，其中大部分看起来与 Map 算子的具体实现和 Router 剪枝逻辑有关。
