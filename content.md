我们已经详细分析了日志等级的设计，现在是时候将这些构想转化为具体的代码实现了。

这个计划将分三步走：首先在订阅者中实现核心过滤逻辑，然后在入口函数中暴露配置参数，最后通过测试验证功能。

## [WIP] feat(runtime): Implement log levels for HumanReadableLogSubscriber

### 用户需求
在 `Cascade` 运行时引入日志等级控制。用户应该能够指定日志等级（如 `INFO`, `WARNING`, `ERROR`），以过滤掉不关注的运行时信息。默认等级应为 `INFO`。

### 评论
这是一个标准且必要的运维特性。随着工作流复杂度的增加，能够抑制噪音（例如在 CI 环境中只关注错误）对于保持输出清晰至关重要。

### 目标
1.  修改 `src/cascade/runtime/subscribers.py`，实现日志等级定义 (`LOG_LEVELS`) 和过滤逻辑。
2.  更新 `HumanReadableLogSubscriber` 以根据事件类型和状态动态确定日志等级，并与用户配置的 `min_level` 进行比较。
3.  修改 `src/cascade/__init__.py` 中的 `run` 函数，暴露 `log_level` 参数。
4.  添加测试用例以验证过滤逻辑的正确性。

### 基本原理
我们将采用“适配器负责过滤”的策略。`MessageBus` 继续派发所有事件，而 `HumanReadableLogSubscriber` 根据配置决定是否将这些事件渲染到流中。我们将定义以下映射规则：
*   **INFO**: 正常的启动、完成、跳过事件。
*   **WARNING**: 任务重试事件。
*   **ERROR**: 任务失败、运行失败事件。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #concept/ui #scope/dx
#ai/instruct
#task/domain/logging #task/object/log-level #task/action/implementation
#task/state/begin

---

### Script

#### Acts 1: 在订阅者中实现日志等级过滤

我们将修改 `subscribers.py`，引入等级常量，并在每个事件处理方法中添加过滤检查。

~~~~~act
patch_file
src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
class HumanReadableLogSubscriber:
    """
    Listens to events and prints user-friendly logs to a stream (default: stderr).
    """

    def __init__(self, bus: MessageBus, stream: TextIO = sys.stderr):
        self._stream = stream

        # Subscribe to relevant events
        bus.subscribe(RunStarted, self.on_run_started)
        bus.subscribe(RunFinished, self.on_run_finished)
        bus.subscribe(TaskExecutionStarted, self.on_task_started)
        bus.subscribe(TaskExecutionFinished, self.on_task_finished)
        bus.subscribe(TaskSkipped, self.on_task_skipped)
        bus.subscribe(TaskRetrying, self.on_task_retrying)

    def _print(self, msg: str):
        print(msg, file=self._stream)

    def on_run_started(self, event: RunStarted):
        targets = ", ".join(event.target_tasks)
        self._print(f"▶️  Starting Run for targets: [{targets}]")
        if event.params:
            self._print(f"   With params: {event.params}")

    def on_run_finished(self, event: RunFinished):
        if event.status == "Succeeded":
            self._print(f"🏁 Run finished successfully in {event.duration:.2f}s.")
        else:
            self._print(f"💥 Run failed after {event.duration:.2f}s: {event.error}")

    def on_task_started(self, event: TaskExecutionStarted):
        self._print(f"  ⏳ Running task `{event.task_name}`...")

    def on_task_finished(self, event: TaskExecutionFinished):
        if event.status == "Succeeded":
            self._print(
                f"  ✅ Finished task `{event.task_name}` in {event.duration:.2f}s"
            )
        else:
            self._print(
                f"  ❌ Failed task `{event.task_name}` after {event.duration:.2f}s: {event.error}"
            )

    def on_task_skipped(self, event: TaskSkipped):
        self._print(f"  ⏩ Skipped task `{event.task_name}` (Reason: {event.reason})")

    def on_task_retrying(self, event: TaskRetrying):
        self._print(
            f"  ⚠️  Retrying task `{event.task_name}` "
            f"(Attempt {event.attempt}/{event.max_attempts}) "
            f"in {event.delay:.2f}s... Error: {event.error}"
        )
~~~~~
~~~~~python
LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


class HumanReadableLogSubscriber:
    """
    Listens to events and prints user-friendly logs to a stream (default: stderr).
    """

    def __init__(
        self, bus: MessageBus, stream: TextIO = sys.stderr, min_level: str = "INFO"
    ):
        self._stream = stream
        self._min_level_val = LOG_LEVELS.get(min_level.upper(), 20)

        # Subscribe to relevant events
        bus.subscribe(RunStarted, self.on_run_started)
        bus.subscribe(RunFinished, self.on_run_finished)
        bus.subscribe(TaskExecutionStarted, self.on_task_started)
        bus.subscribe(TaskExecutionFinished, self.on_task_finished)
        bus.subscribe(TaskSkipped, self.on_task_skipped)
        bus.subscribe(TaskRetrying, self.on_task_retrying)

    def _should_log(self, level: str) -> bool:
        return LOG_LEVELS.get(level, 20) >= self._min_level_val

    def _print(self, msg: str):
        print(msg, file=self._stream)

    def on_run_started(self, event: RunStarted):
        if self._should_log("INFO"):
            targets = ", ".join(event.target_tasks)
            self._print(f"▶️  Starting Run for targets: [{targets}]")
            if event.params:
                self._print(f"   With params: {event.params}")

    def on_run_finished(self, event: RunFinished):
        level = "INFO" if event.status == "Succeeded" else "ERROR"
        if self._should_log(level):
            if event.status == "Succeeded":
                self._print(f"🏁 Run finished successfully in {event.duration:.2f}s.")
            else:
                self._print(f"💥 Run failed after {event.duration:.2f}s: {event.error}")

    def on_task_started(self, event: TaskExecutionStarted):
        if self._should_log("INFO"):
            self._print(f"  ⏳ Running task `{event.task_name}`...")

    def on_task_finished(self, event: TaskExecutionFinished):
        level = "INFO" if event.status == "Succeeded" else "ERROR"
        if self._should_log(level):
            if event.status == "Succeeded":
                self._print(
                    f"  ✅ Finished task `{event.task_name}` in {event.duration:.2f}s"
                )
            else:
                self._print(
                    f"  ❌ Failed task `{event.task_name}` after {event.duration:.2f}s: {event.error}"
                )

    def on_task_skipped(self, event: TaskSkipped):
        if self._should_log("INFO"):
            self._print(
                f"  ⏩ Skipped task `{event.task_name}` (Reason: {event.reason})"
            )

    def on_task_retrying(self, event: TaskRetrying):
        if self._should_log("WARNING"):
            self._print(
                f"  ⚠️  Retrying task `{event.task_name}` "
                f"(Attempt {event.attempt}/{event.max_attempts}) "
                f"in {event.delay:.2f}s... Error: {event.error}"
            )
~~~~~

#### Acts 2: 更新 run 函数入口

修改 `__init__.py`，使 `cs.run` 接受 `log_level` 参数并传递给订阅者。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    Args:
        target: The workflow target.
        params: Runtime parameters.
        system_resources: A dictionary defining total system capacity
                          (e.g. {"gpu": 1, "threads": 4}).
    """
    bus = MessageBus()
    # Attach the default logger
    HumanReadableLogSubscriber(bus)

    engine = Engine(bus=bus, system_resources=system_resources)

    return asyncio.run(engine.run(target, params=params))
~~~~~
~~~~~python
def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    Args:
        target: The workflow target.
        params: Runtime parameters.
        system_resources: A dictionary defining total system capacity
                          (e.g. {"gpu": 1, "threads": 4}).
        log_level: Minimum logging level ("DEBUG", "INFO", "WARNING", "ERROR").
                   Defaults to "INFO".
    """
    bus = MessageBus()
    # Attach the default logger
    HumanReadableLogSubscriber(bus, min_level=log_level)

    engine = Engine(bus=bus, system_resources=system_resources)

    return asyncio.run(engine.run(target, params=params))
~~~~~

#### Acts 3: 验证日志等级过滤

在 `tests/runtime/test_bus.py` 中添加一个新的测试用例，验证 `min_level` 参数确实能过滤掉低优先级的日志。

~~~~~act
patch_file
tests/runtime/test_bus.py
~~~~~
~~~~~python
    logs = output.getvalue()

    assert "▶️  Starting Run" in logs
    assert "env': 'prod'" in logs
    assert "✅ Finished task `build_image` in 1.23s" in logs
    assert "❌ Failed task `deploy_k8s`" in logs
    assert "AuthError" in logs
~~~~~
~~~~~python
    logs = output.getvalue()

    assert "▶️  Starting Run" in logs
    assert "env': 'prod'" in logs
    assert "✅ Finished task `build_image` in 1.23s" in logs
    assert "❌ Failed task `deploy_k8s`" in logs
    assert "AuthError" in logs


def test_subscriber_log_level_filtering():
    """Test that setting min_level suppresses lower priority logs."""
    bus = MessageBus()
    output = io.StringIO()
    # Set level to ERROR, so INFO logs should be skipped
    HumanReadableLogSubscriber(bus, stream=output, min_level="ERROR")

    # INFO event
    bus.publish(RunStarted(target_tasks=["t1"]))
    # INFO event
    bus.publish(
        TaskExecutionFinished(
            task_id="1", task_name="t1", status="Succeeded", duration=0.1
        )
    )
    # ERROR event
    bus.publish(
        TaskExecutionFinished(
            task_id="2", task_name="t2", status="Failed", error="Boom", duration=0.1
        )
    )

    logs = output.getvalue()

    # Should NOT contain INFO logs
    assert "Starting Run" not in logs
    assert "Finished task `t1`" not in logs
    # Should contain ERROR logs
    assert "Failed task `t2`" in logs
    assert "Boom" in logs
~~~~~

### 下一步建议
我们已经实现了日志等级过滤。接下来应该提交这个变更，并在 `cs.cli` (命令行工具) 中暴露这个 `log_level` 选项，让用户在通过 CLI 运行工作流时也能控制日志等级。
