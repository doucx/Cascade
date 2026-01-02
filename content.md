好的，技术债务清理工作已圆满完成。我们不仅解决了物理层面的潜在死锁，还通过引入字面量支持和规范化命名，极大地增强了系统的确定性和可观测性。

我将生成一个 `[COMMIT]` 计划，将这些重构成果沉淀到版本库中。

## [COMMIT] refactor(compiler): resolve technical debt in observability, literals, and naming

### 用户需求
提交累计的重构和修复工作。

### 评论
这次重构是阶段四的重要收尾，它将实现层面的零散修复提升到了架构规范的高度。通过消除魔法字符串和提升观测系统的物理鲁棒性，Cascade 的物理场实现现在更加符合其“全对称”的哲学设计。

### 目标
1.  将所有修改过的文件（涉及编译器后端、VM 运行时和 Spec 定义）添加到 Git 暂存区。
2.  创建一个结构化的提交信息，详细记录此次重构的五个核心要点。

### 基本原理
由于这次重构涉及多个组件的协同变更（例如 Spec 中的 `initial_payload` 需要 Reactor 的配合，而 Builder 的 ID 命名变更影响了多个测试文件），将它们作为一个原子提交是最合理的方案，这保证了版本历史的逻辑完整性。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/compiler #comp/vm #comp/spec #concept/observability #concept/identity #scope/core 
#ai/instruct 
#task/domain/compiler #task/object/compiler-backend #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交重构成果

我们将这些相关的变更作为一个完整的逻辑单元提交。

~~~~~act
git_add
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-compiler/src/cascade/compiler/utils/naming.py
packages/cascade-compiler/tests/integration/test_observability_congestion.py
packages/cascade-compiler/tests/unit/backend/test_builder.py
packages/cascade-compiler/tests/unit/backend/test_builder_environment.py
packages/cascade-compiler/tests/unit/backend/test_builder_observability.py
packages/cascade-compiler/tests/unit/backend/test_expander.py
packages/cascade-spec/src/cascade/spec/physics.py
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(compiler): resolve technical debt in observability, literals, and naming

This commit addresses several architectural gaps identified during the stage 4 review:

1. Observability Deadlock Prevention: Increased the capacity of the global observability bus (D_life) to `sys.maxsize`. This ensures that telemetry events never cause backpressure on task execution nodes, adhering to the "Zero-Interference" principle.
2. Literal Support in Builder: The compiler backend now correctly handles literal inputs in NodeIR by automatically instantiating pre-filled constant DataNodes and wiring them to the appropriate ports.
3. Reactor Payload Priming: Upgraded `Reactor.prime()` to inject specific payloads into initial tokens, enabling the physical embodiment of constants and configuration.
4. Canonical Naming: Introduced `PhysicalIdGenerator` to eliminate magic strings in physical node IDs. All nodes now follow a structured naming scheme:
   - Tasks: `<id>.bleach`, `<id>.worker`, `<id>.stain`
   - Data: `<id>.data.in`, `<id>.data.out`, `<id>.data.trace`
   - Resources: `canonical.resource.<name>`
   - Observability: `global.observability.<entity>`
5. Static Analysis & Safety: Fixed Pyright optional member access errors in `builder.py` using explicit type assertions and added a safety check in `standard_bleacher` for port identification.

These changes significantly improve the robustness and self-documentation of the physical graph construction.
~~~~~

### 下一步建议
- **开始阶段五**: 我们现在拥有了一个稳定且规范的物理后端。下一步可以开始集成 `Reactor` 的监控接口，或者开始设计 TUI 调试器，直观地观察这些物理令牌的流动。
- **文档同步**: 建议更新架构白皮书的实现细节部分，将 `PhysicalIdGenerator` 的命名规范正式作为文档的一部分。
