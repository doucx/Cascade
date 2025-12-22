好的，我来检查一下这个工作流卡死 Bug 的原因。

这是一个非常严重的问题。控制平面的指令不应该导致工作流引擎死锁。根据你的描述，问题出在 `set-limit` 命令上，并且你怀疑是“解析问题”。这个线索非常关键。

我将生成一个分析和修复计划。

## [WIP] fix(engine): 使速率限制约束解析器健壮以防止死锁

### 错误分析

你的判断是正确的，这确实是一个解析问题，但其后果比预想的更严重，并直接导致了死锁。根本原因在于 `RateLimitConstraintHandler` 中的 `_parse_rate_string` 函数不够健壮，一个未处理的异常会使引擎的控制消息处理任务崩溃，从而导致死锁。

详细的异常传递路径如下：

1.  **入口点**: `Engine` 的 `_on_constraint_update` 方法异步地接收来自 `Connector` 的消息（例如 MQTT 消息）。这个方法是引擎与控制平面通信的“耳朵”。
2.  **分发**: `_on_constraint_update` 将消息解析为 `GlobalConstraint` 对象，并调用 `constraint_manager.update_constraint()`。
3.  **处理**: `ConstraintManager` 找到对应的 `RateLimitConstraintHandler` 并调用其 `on_constraint_add` 方法。
4.  **解析**: `on_constraint_add` 内部调用了 `_parse_rate_string` 来转换 `rate` 参数（例如 `"0.5/s"`）。
5.  **崩溃点**: `_parse_rate_string` 函数在设计上存在缺陷。如果 `rate` 字符串格式不正确（例如 `"foo/s"`），`float(parts[0])` 会抛出一个未被捕获的 `ValueError`。
6.  **任务死亡**: 这个 `ValueError` 会沿着调用栈向上传播，最终导致运行 `_on_constraint_update` 的 `asyncio.Task` 崩溃。
7.  **死锁**: `_on_constraint_update` 方法的 `finally` 块中，有一行至关重要的代码：`self._wakeup_event.set()`。如果引擎当前因为没有可执行任务而处于等待状态（`await self.wakeup_event.wait()`），这个事件就是唤醒它的唯一方式。由于处理消息的任务因异常而提前终止，`set()` 从未被调用。
8.  **结果**: 引擎将永远等待一个永远不会被设置的事件，从而导致整个工作流卡死。

因此，用户通过 `cs-controller` 发送一个格式错误的 `rate` 值，就能导致整个 `Engine` 实例永久挂起。这是一个严重的高可用性风险。

### 用户需求
当 `Engine` 收到一个格式错误的 `rate_limit` 约束时，它应该能够优雅地处理这个错误（例如，打印一条错误日志），而不是整个系统卡死。

### 评论
这是一个关键的可靠性修复。控制平面绝不能成为一个攻击向量，让一个无效的输入就能导致服务中断。修复这个问题将显著提升 Cascade 引擎在生产环境中的健壮性。

### 目标
1.  修改 `_parse_rate_string` 函数，使其能够捕获因格式错误导致的 `ValueError`。
2.  在捕获异常时，通过 `bus` 记录一条明确的错误日志，并返回一个安全地默认值。
3.  确保即使在处理无效约束时，`Engine` 的消息处理循环也能正常完成，并最终唤醒主循环。

### 基本原理
我们将通过在 `_parse_rate_string` 函数内部添加一个 `try...except ValueError` 块来解决这个问题。这种方法将错误隔离在最小的范围内，阻止了异常的破坏性传播。通过记录错误而不是让程序崩溃，我们遵循了健壮的服务器设计原则：即单个无效请求不应影响整个服务的可用性。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/brainstorm #task/domain/runtime #task/object/constraint-manager #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 增强 `_parse_rate_string` 的健壮性

我们将修改位于 `packages/cascade-engine/src/cascade/runtime/constraints/handlers.py` 的 `_parse_rate_string` 函数，为其增加异常处理逻辑。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/constraints/handlers.py
~~~~~
~~~~~python
def _parse_rate_string(rate_str: str) -> float:
    """Parses '10/m', '5/s', '300/h' into tokens per second."""
    if not isinstance(rate_str, str):
        return float(rate_str)

    parts = rate_str.split("/")
    if len(parts) != 2:
        try:
            return float(rate_str)
        except ValueError:
            # Default fallback or error
            return 1.0

    count = float(parts[0])
    unit = parts[1].lower()

    divisor = 1.0
    if unit in ("s", "sec", "second"):
        divisor = 1.0
    elif unit in ("m", "min", "minute"):
        divisor = 60.0
    elif unit in ("h", "hr", "hour"):
        divisor = 3600.0

    return count / divisor
~~~~~
~~~~~python
from cascade.common.messaging import bus


def _parse_rate_string(rate_str: str) -> float:
    """Parses '10/m', '5/s', '300/h' into tokens per second."""
    try:
        if not isinstance(rate_str, str):
            return float(rate_str)

        parts = rate_str.split("/")
        if len(parts) != 2:
            return float(rate_str)

        count = float(parts[0])
        unit = parts[1].lower()

        divisor = 1.0
        if unit in ("s", "sec", "second"):
            divisor = 1.0
        elif unit in ("m", "min", "minute"):
            divisor = 60.0
        elif unit in ("h", "hr", "hour"):
            divisor = 3600.0
        else:
            # Invalid unit, treat as malformed
            raise ValueError(f"Unknown rate limit unit: '{unit}'")

        return count / divisor
    except (ValueError, TypeError) as e:
        bus.error(
            "constraint.parse.error",
            constraint_type="rate_limit",
            raw_value=rate_str,
            error=str(e),
        )
        # Return a safe default (e.g., 1 token per second) to prevent crashes
        return 1.0
~~~~~

### 下一步建议

代码修复后，我们必须添加一个专门的集成测试来防止此类问题再次发生。这个测试应该：

1.  启动一个 `Engine` 实例。
2.  通过 `Connector` 发送一个**格式错误**的 `rate_limit` 约束（例如，`{"rate": "foo/bar"}`）。
3.  **Mock 消息总线 (`bus`)**，并断言 `bus.error("constraint.parse.error", ...)` 被调用。
4.  发送一个**格式正确**的 `pause` 约束。
5.  验证工作流确实被暂停了，以此证明 `Engine` 在处理完第一个无效消息后没有死锁，并能继续正常处理后续消息。

这将确保我们的控制平面在未来能抵御无效输入的干扰。如果你同意，我将为你生成实现这个测试的计划。
