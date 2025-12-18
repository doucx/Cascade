好的，所有测试都已通过。我们成功完成了一次关键的架构重构，为未来的工具链开发奠定了坚实的基础。

现在，我将为你创建一个 Git 提交，清晰地记录下这次重构的所有工作。

## [WIP] feat(arch): Introduce decoupled message bus and cascade-common package

### 用户需求
创建一个 Git 提交，全面、清晰地总结从引入 `cascade-common` 包到完成所有相关测试修复的整个重构过程。

### 评论
这个提交标志着 Cascade 项目架构的一次重要升级。它不仅解决了眼前为 CLI 工具解耦的问题，更重要的是，它为整个生态系统的长期健康和可扩展性建立了正确的基础。提交信息将详细阐述这次重构的动机、新架构的设计以及为使其正常工作而进行的一系列修复，为未来的开发者提供了宝贵的上下文。

### 目标
1.  使用 `git add .` 将所有更改添加到暂存区。
2.  使用 `git commit` 创建一个符合规范的、信息丰富的提交。提交信息将包括：
    *   **类型**: `refactor`
    *   **范围**: `(core, arch)` 来表示这是一次核心架构级别的重构。
    *   **主题**: 清晰总结本次变更的核心内容。
    *   **正文**: 详细说明重构的动机（支持 CLI 工具、解耦）、新架构的设计（`cascade-common`, Renderer 协议）、具体实施步骤以及在此过程中解决的构建和测试问题。

### 基本原理
我们将创建一个单一、完整的提交来封装这次原子性的重构操作。这使得代码历史清晰，便于未来进行代码考古、审查或是在必要时进行回滚。

### 标签
#intent/build #flow/ready #priority/high #comp/vcs #scope/dx #ai/instruct #task/domain/version-control #task/object/commit #task/action/create #task/state/begin

---

### Script

#### Acts 1: 暂存所有更改

~~~~~act
run_command
~~~~~
~~~~~bash
git add .
~~~~~

#### Acts 2: 创建提交

~~~~~act
git_commit
~~~~~
~~~~~
refactor(core, arch): Introduce decoupled message bus and cascade-common

This major refactoring introduces a decoupled messaging architecture to the entire Cascade ecosystem, laying a robust foundation for building independent tools like CLI observers and controllers. The design is heavily inspired by the proven patterns in the `quipu` project.

The primary motivation was to break the tight coupling between the core workflow logic (which generates events) and the user-facing presentation layer (which displays information). Previously, this coupling would have made it difficult to build and test CLI tools without them depending directly on internal `cascade-py` components.

Key architectural changes:

1.  **New `cascade-common` Package**:
    *   A new foundational package, `cascade-common`, has been created.
    *   It houses ecosystem-wide utilities that are independent of the core runtime logic, starting with the new messaging system.

2.  **Decoupled MessageBus and Renderer Protocol**:
    *   The message bus in `cascade-common` is now solely responsible for dispatching semantic message "intents" (e.g., `bus.info("run.started", ...)`).
    *   The actual presentation logic (e.g., printing to the console with colors) is delegated to a `Renderer` object, which is injected at application startup.
    *   This separates the "what" (the intent) from the "how" (the presentation).

3.  **Centralized Locales**:
    *   All user-facing message strings have been moved out of Python code and into JSON files within `cascade-common/src/cascade/common/locales`.

Implementation details and fixes:

*   **Code Migration**: The old messaging system was removed from `cascade-py`. `HumanReadableLogSubscriber` in `cascade-runtime` was updated to use the new `cascade.common.messaging.bus`.
*   **Build System Fixes**:
    *   Configured `[tool.uv.sources]` in all relevant `pyproject.toml` files to enable correct local workspace package resolution.
    *   Added missing `__init__.py` files to make the new packages properly importable.
*   **Test Suite Refactoring**:
    *   Restructured the `tests/` directory to mirror the new multi-package layout (`tests/common`, `tests/runtime`).
    *   Updated all test import paths to reflect the new module locations.
    *   Corrected `monkeypatch` targets in integration tests to patch the message bus where it is *used* (`cascade.runtime.subscribers.bus`), ensuring tests remain robust after the refactor.

This change unblocks the development of `cs-observer` and other ecosystem tools on a clean, testable, and maintainable architecture.
~~~~~

### 下一步建议
我们已经成功地完成了这次重构并提交了代码。基础架构已经准备就绪。

现在，我们可以满怀信心地回到我们最初的目标：**实现 `cs-observer watch` 命令的核心功能**。我将为你生成一个计划，该计划将利用我们刚刚建立的新架构，连接到 MQTT 并实时显示遥测事件。
