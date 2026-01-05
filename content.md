太棒了。既然所有的单元测试、集成测试以及 E2E 测试都已经顺利通过，并且 `pyright` 的静态分析也恢复了清爽，这标志着我们的架构重构已经达到了一个稳定且一致的状态。

我将生成一个提交计划，将这些修复作为一个完整的工作单元固化到 Git 历史中。

## [COMMIT] fix(runtime/sdk): 修复重构后的导入、类型提示及测试路径

### 用户需求
完成所有修复工作并提交代码。

### 评论
这是一组关键的“粘合逻辑”修复。在架构大规模重构后，确保公共接口（SDK）、内部依赖（__init__ 导出）、协议契约（Protocols）以及测试套件（Tests）同步更新是维持项目生命力的必要步骤。目前的修复已经消除了所有的导入错误和主要的类型争议。

### 目标
1.  提交对 `cascade-runtime`、`cascade-spec` 和 `cascade-sdk` 的修改。
2.  提交对单元测试和 E2E 测试路径的修复。

### 基本原理
根据架构原则，我们通过显式导出、协议对齐和路径同步，恢复了系统的“逻辑闭环”。这不仅让当前代码能够运行，也为后续基于新架构的开发奠定了坚实的基础。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #comp/sdk #comp/spec #scope/core #ai/instruct #task/domain/testing #task/object/refactoring-fix #task/action/commit #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交所有变更

我们将把涉及重构修复的所有文件添加到 Git 暂存区并提交。

~~~~~act
git_add
packages/cascade-runtime/src/cascade/runtime/services/constraints/__init__.py
packages/cascade-runtime/src/cascade/runtime/io/state/__init__.py
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/__init__.py
packages/cascade-runtime/src/cascade/runtime/io/caching/__init__.py
packages/cascade-spec/src/cascade/spec/protocols.py
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/vm.py
packages/cascade-runtime/src/cascade/runtime/services/observability/events.py
packages/cascade-sdk/src/cascade/sdk.py
packages/cascade-runtime/tests/unit/test_solver_csp.py
tests/e2e/integration/test_end_to_end.py
tests/e2e/runtime/test_e2e_robustness.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(runtime/sdk): fix broken imports and type hints after refactoring

Consolidated and resolved multiple regression issues introduced during the AXA v1.0 refactoring:

1.  Public API (SDK): Updated 'cascade.sdk' _IMPORT_MAP and TYPE_CHECKING blocks with correct module paths for Engine, EventBus, solvers, and executors.
2.  Module Exports: Added missing class exports to __init__.py files across cascade-runtime (constraints, state, strategies, caching).
3.  Protocols: Updated 'Executor' protocol signature to match its 4-argument implementation and usage.
4.  Type Safety: Fixed pyright errors in Event (static from_ir stub) and VMExecutionStrategy (async callback type and MappedLazyResult attribute access).
5.  Tests: Corrected internal module import paths and monkeypatch targets in both unit tests (CSP Solver) and E2E tests.

These changes restore system-wide integrity, passing all static analysis and runtime test suites.
~~~~~

### 下一步建议
- **监控持续集成**: 建议在 CI 环境中运行全量测试，确保不同环境下的兼容性。
- **文档同步**: 检查 SDK 变更是否需要更新外部用户手册或示例代码。

