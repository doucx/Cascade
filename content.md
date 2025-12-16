执行成功，现在所有测试应该已通过。我们将此完整的逻辑单元（JSON Renderer实现、API暴露以及所有相关的架构修正和测试修复）作为一个原子提交进行版本控制。

## [COMMIT] feat(observability): Implement JSON logging and structured data contract

### 用户需求
实现 `JsonRenderer`，将运行时事件输出为结构化 JSON 格式，并通过 `cs.run` 和生成的 CLI (`--log-format`) 对外暴露此功能。同时，修复了由架构重构引起的所有日志不一致性、模板契约冲突以及测试捕获问题。

### 评论
这是一个对生产级可观测性具有决定性意义的提交。它将 Cascade 的日志系统从单纯的人类报告升级为机器可读的结构化数据流，极大地增强了其在 CI/CD 和大规模部署环境中的可操作性。

本次提交的关键成就包括：
1.  **实现 `JsonRenderer`**：提供了 JSON 格式的结构化日志输出。
2.  **API 暴露**：在 `cs.run` 和 `cs.cli` 中引入 `--log-format` 选项。
3.  **架构净化**：通过将表现逻辑（如列表连接）移入 `CliRenderer` 或通过 `MessageStore` 智能处理，确保了事件总线和订阅者只传递原始、结构化的数据，从而稳定了整个日志架构。
4.  **解决测试陷阱**：修复了因 Python 默认参数绑定机制导致的 `CliRunner` 无法捕获日志的运行时错误。

### 目标
将实现结构化日志所需的所有文件变更打包，并进行一次干净的提交。

### 基本原理
为了支持“预编排”和“嵌入式引擎”的战略定位，`Cascade` 必须在可观测性方面达到工业标准。结构化日志是实现与现代日志聚合系统（Loki, ELK）无缝集成的先决条件。所有关联的架构修正都是为了确保这一新功能可以在不破坏现有功能和测试稳定性的前提下，保持高可维护性。

### 标签
#intent/build #intent/refine #flow/ready #priority/high #comp/core #comp/cli #comp/tests #concept/ui #scope/api #scope/dx #ai/delegate #task/domain/observability #task/object/json-logging #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交所有与结构化日志和渲染器重构相关的变更

~~~~~act
git_add
src/cascade/__init__.py
src/cascade/messaging/bus.py
src/cascade/messaging/renderer.py
src/cascade/runtime/subscribers.py
src/cascade/tools/cli.py
tests/messaging/test_renderer.py
tests/integration/test_end_to_end.py
tests/tools/test_cli.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(observability): Implement JSON logging and expose log_format option

This commit introduces comprehensive structured logging capabilities to Cascade, ensuring it meets production standards for observability.

Key changes:
1. **Renderer Protocol Refactor**: The core `Renderer` protocol is changed to accept structured data (`msg_id`, `level`, `**kwargs`) instead of a pre-formatted string. This cleanly separates the semantic message from its presentation format.
2. **`JsonRenderer` Implementation**: A new renderer is added to output structured JSON logs, critical for machine parsing by tools like Loki or Elasticsearch.
3. **API Exposure**: Added `log_format` parameter to `cs.run` and exposed `--log-format` option via `cs.cli`, allowing users to choose between "human" (default) and "json" output.
4. **Architectural Fixes**:
    - Stabilized the data contract by moving list-to-string formatting logic from the event subscriber into the `CliRenderer` and simulating a template fix in `MessageStore`.
    - Fixed a critical bug where `CliRunner` could not capture output due to late binding of `sys.stderr` in `Renderer` default arguments, making the test suite robust against I/O redirection.
5. **New Test Suite**: Added `tests/messaging/test_renderer.py` for dedicated testing of all renderer formats.
~~~~~

### 下一步建议
我们已经完成了两个重要的开发者体验改进：结构化日志和 Renderer 架构稳定。

根据 `当前.md` 中未完成的任务，下一步应该回到性能优化，**优化 Fixture 作用域**，以提高测试套件的执行速度。

1.  **优化 Fixture 作用域**: 审查测试套件中创建成本较高的 fixture（例如，`sqlite_db` 资源 fixture 或 Mock 依赖项），并根据 `d3-principle-pytest-fixture-scoping` 原则提升其作用域（如从 `function` 到 `class` 或 `module`），以减少重复设置开销，提高测试执行速度。

我建议我们首先分析 `tests/integration/test_sql.py` 中的 `sqlite_db` fixture，因为它涉及 I/O 和数据库连接创建，是一个耗时操作，非常适合作用域优化。
