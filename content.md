完美，所有的测试都已通过，证明了新的语义消息架构是健壮的，并且测试用例现在正确地遵循了新的解耦模式。

现在我将生成一个 `[COMMIT]` 计划来封装这次架构升级和测试修复。

## [COMMIT] feat(runtime): Implement semantic messaging bus for robust testing

### 用户需求
将 Cascade 的日志和事件报告系统从耦合的 `Subscriber` 模式升级为基于语义 ID 的消息总线架构。目标是彻底解耦核心逻辑与 UI 表现层，并使测试能够通过断言消息 ID 来验证意图。

### 评论
这次重构是一次关键的架构投资，它遵循了“验证意图而非实现”的最高测试原则。通过引入 `MessageStore`、`MessageBus` 和 `CliRenderer`，我们为 Cascade 提供了国际化（i18n）、结构化日志输出（如 JSON）的能力，并极大地增强了测试套件的健壮性。现在，对日志文案、颜色或格式的任何更改都不会导致集成测试失败。

### 目标
1.  **架构升级**: 引入 `cascade.messaging` 模块，实现语义消息总线。
2.  **职责分离**: 将 `HumanReadableLogSubscriber` 转换为一个纯粹的“翻译层”，它将运行时 `Event` 映射到 `MessageBus` 的语义 ID 调用。
3.  **测试健壮性**: 重构了所有依赖日志输出的集成测试（包括 `tests/runtime/test_bus.py` 和 `tests/integration/test_end_to_end.py`），使其现在 Mock `MessageBus` 并断言语义 ID，或使用新的 `CliRenderer` 进行健壮的 UI 验证。

### 基本原理
旧的日志系统将 UI 文本硬编码在 `Subscriber` 中，导致测试用例必须依赖硬编码的字符串进行断言，这极易导致测试脆弱。新的架构通过引入一个抽象的语义层（例如 `"run.started"`），使得核心运行时、事件翻译层、消息模板和渲染层各自独立。这不仅解决了测试中的脆弱性问题，也为 Cascade 的可观测性和可扩展性奠定了高级基础。

### 标签
#intent/architect #intent/refine #flow/ready #priority/high #comp/runtime #comp/tests #concept/messaging #scope/dx #task/domain/core #task/object/messaging-system #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 暂存所有变更的文件

我们将暂存所有新增和修改的文件，为提交做准备。

~~~~~act
git_add
src/cascade/locales/en/events.json
src/cascade/messaging/bus.py
src/cascade/messaging/renderer.py
src/cascade/messaging/__init__.py
src/cascade/__init__.py
src/cascade/runtime/subscribers.py
tests/conftest.py
tests/integration/test_end_to_end.py
tests/runtime/test_bus.py
~~~~~

#### Acts 2: 执行提交

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime): Implement semantic messaging bus for robust testing

This commit introduces a new semantic messaging architecture to decouple core runtime logic from console output and logging formats.

Key changes:
1. **New `cascade.messaging` module**: Implements `MessageStore`, `MessageBus`, and `CliRenderer`. The `MessageBus` now acts as the centralized authority for all user-facing output via stable semantic IDs (e.g., `run.started`).
2. **Refactored `HumanReadableLogSubscriber`**: This component is now a pure "translator" that listens to runtime events (like `RunStarted`) and translates them into semantic ID calls on the new messaging bus. It no longer contains hardcoded strings.
3. **Test Robustness**:
    - Removed fragile hardcoded string assertions in `tests/runtime/test_bus.py`.
    - Refactored `tests/integration/test_end_to_end.py` to utilize `unittest.mock` to assert that the correct semantic message IDs and data payloads were sent to the messaging bus, making these critical tests completely UI-agnostic.
    - Added `tests/conftest.py` with a centralized `SpySubscriber` and fixtures to standardize event-driven testing across the project.

This upgrade significantly improves the maintainability and testability of the entire project, laying the groundwork for i18n and structured logging.
~~~~~

### 下一步建议
核心架构工作已经完成，测试债务也已偿还。下一步应该回到性能和开发者体验的优化上：

1.  **优化 Fixture 作用域**: 审查测试套件中创建成本较高的 fixture（例如，可能涉及 I/O 或昂贵设置的资源 fixture），并根据 `d3-principle-pytest-fixture-scoping` 原则提升其作用域（如从 `function` 到 `class` 或 `module`），以减少重复设置开销，提高测试执行速度。
2.  **JSON Log Renderer**: 利用新实现的语义消息总线，实现一个 `JsonRenderer`，将所有输出结构化为 JSON 格式，便于机器解析和日志聚合。
