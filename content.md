我们将创建一个 `[COMMIT]` 计划，用于提交日志等级功能的完整实现。

## [COMMIT] feat(runtime): Add configurable log levels for human-readable output

### 用户需求
引入日志等级控制 (`log_level` 参数) 来过滤运行时日志。这将允许用户在 `cs.run` 时抑制不必要的 `INFO` 级别输出（如任务启动/完成、跳过信息），只关注 `WARNING` 或 `ERROR` 级别的事件。

### 评论
这个功能极大地提高了 `Cascade` 在自动化和 CI/CD 环境中的可观测性和可用性。通过将事件（如任务重试、失败）映射到预定义的日志等级，用户可以精确控制输出的详细程度，从而降低日志噪音。

### 目标
创建一个 Git 提交，包含 `HumanReadableLogSubscriber` 中的日志等级映射和过滤逻辑，以及 `cascade.run` 入口函数的签名更新。

### 基本原理
我们定义了标准的 `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` 等级，并将事件（如 `TaskRetrying` 映射到 `WARNING`，`TaskExecutionFinished(Failed)` 映射到 `ERROR`）映射到这些等级上。`HumanReadableLogSubscriber` 现在根据用户提供的 `min_level` 决定是否将事件打印到 `stderr`。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #comp/tests #concept/ui #scope/dx
#ai/instruct
#task/domain/logging #task/object/log-level #task/action/implementation
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交日志等级功能及其测试

将所有修改文件添加到 Git 暂存区，并执行提交。

~~~~~act
git_add
src/cascade/runtime/subscribers.py
src/cascade/__init__.py
tests/runtime/test_bus.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime): Add configurable log levels for human-readable output

Introduces configurable logging levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) to the `HumanReadableLogSubscriber`.

Key changes:
1.  **`subscribers.py`**: Implements `LOG_LEVELS` mapping and updates the subscriber to dynamically assign a level to each event (e.g., RunStarted=INFO, TaskRetrying=WARNING, TaskFailed=ERROR).
2.  **`cascade.run`**: Exposes the `log_level` parameter, allowing users to set the minimum level required for an event to be printed.

This enhancement significantly improves the clarity of the runtime output, especially in automated environments where only high-severity events are required.
~~~~~

### 下一步建议
虽然核心功能已完成，但用户通过 `cs.run()` 命令行运行工作流时，目前还不能直接通过命令行参数控制 `log_level`。

我建议下一步：
**更新 `cs.cli` 工具**: 修改 `src/cascade/tools/cli.py`，使它自动识别 `log_level` 参数并将其作为标准选项暴露给最终用户。这需要修改 `cli` 工具的生成逻辑。
