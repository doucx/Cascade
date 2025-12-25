我理解，在测试通过后，应该立即固化这些变更。我们已经完成了 Application 层重构、API 统一、并修复了所有测试中暴露的副作用，现在是时候提交了。

## [COMMIT] feat(arch): 引入 Application 层并统一 API 入口点

### 用户需求
将 Cascade 架构重构为包含独立的 `cascade-application` 层，并使用面向对象的 `CascadeApp` 统一 `cs.run`, `cs.visualize`, `cs.dry_run` 等全局 API 的底层实现，同时确保向后兼容性。

### 评论
这是一项战略性重构，旨在解决核心 API 设计中的 DRY 原则违反和职责模糊问题（如 CP-005 和 CP-012 所述）。

**核心变更**:
1.  **引入 `cascade-application` 包**: 封装所有基础设施初始化、配置和生命周期管理（Engine, MessageBus, Renderer, State Backend）。
2.  **统一 API**: `CascadeApp` 成为所有工作流操作的中心枢纽，确保 `run/visualize/dry_run` 共享一套预处理逻辑（如自动汇合）。
3.  **向后兼容**: 原有的 `cascade.run`, `cascade.visualize`, `cascade.dry_run` 全局函数现在作为 `CascadeApp` 的轻量级包装器存在，对用户代码无侵入。

此变更极大地提升了系统的模块化程度、可维护性和未来的扩展性（例如，支持 Web UI）。

### 目标
将所有阶段性的重构（阶段一到阶段四，以及测试修复）合并为一个逻辑上完整的原子提交。

### 基本原理
新的 `Application` 层明确地将“运行环境和配置”的职责从“调度和执行”的职责中分离出来。这遵循了单一职责原则，并为未来的高级功能（如项目管理、多租户隔离）奠定了坚实的基础。

### 标签
#intent/refine #flow/ready #priority/high #comp/sdk #comp/application #comp/tests #scope/api #scope/dx #ai/instruct #task/domain/architecture #task/object/application-layer #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 添加所有新建和修改的文件

我们将添加在重构过程中新建和修改的所有文件，包括新的 `cascade-application` 包、重构后的 `cascade-sdk` 文件、以及新的测试文件。

~~~~~act
git_add .
~~~~~

#### Acts 2: 删除已过时的文件

删除在 `cascade-sdk` 中重复的功能实现，以及过时的测试文件。

~~~~~act
delete_file
packages/cascade-sdk/src/cascade/tools/preview.py
packages/cascade-sdk/src/cascade/tools/visualize.py
tests/sdk/tools/test_preview.py
~~~~~

#### Acts 3: 提交变更

~~~~~act
git_commit
~~~~~
~~~~~text
feat(arch): Introduce Application Layer and unify API entrypoints

This strategic refactoring introduces the dedicated `cascade-application` package and the `CascadeApp` class, resolving architectural contradictions related to API entrypoints and infrastructure management (per CP-005 and CP-012).

Key Changes:

1.  **New Application Layer (`cascade-application`)**: Created to encapsulate all configuration, `Engine` setup, messaging, and state backend factory logic. This separates "Configuration" from "Execution."
2.  **Unified API**: `CascadeApp` implements a clean, stable API for top-level operations: `.run()`, `.visualize()`, and `.dry_run()`. It centralizes input processing (like auto-gathering) in its constructor.
3.  **SDK Refactor (Facade Pattern)**: The global functions in `cascade-sdk` (`cs.run`, `cs.visualize`, `cs.dry_run`) are now thin, backward-compatible wrappers that instantiate and call the `CascadeApp`.
4.  **Cleanup**: Removed redundant core logic and events from `cascade-sdk.tools`, migrating all core utility functionality to `cascade-application`.
5.  **Test Stability**: Fixed issues related to global messaging bus state pollution in CLI E2E tests and restored coverage for `dry_run` against the new `CascadeApp` interface.

This change ensures a higher level of architectural purity, decoupling the SDK API from the Engine's implementation details.
~~~~~
