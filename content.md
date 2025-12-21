我们需要修复 `process_perception_and_recurse` 的逻辑，使其能够正确处理来自 `cs.wait` 的 `None` 值。在“不应期”之后，逻辑总是继续下一个常规循环，这在语义上等同于“没有收到信号”或“不是超时”，而是简单地时间流逝。我们可以通过检查 `perception_result` 是否为 `None` 来识别这种情况。

## [WIP] fix(agent): 修正 Agent 在不应期后的状态处理逻辑

### 用户需求
修复在 TCO 优化重构中引入的 `AttributeError`，使得 Agent 在不应期结束后能够正确地进入下一个计算循环。

### 评论
这是一个典型的重构引入的逻辑错误。通过显式处理 `cs.wait` 返回的 `None` 值，我们可以修复这条执行路径，同时保持代码结构的扁平化，以继续受益于 TCO 优化。

### 目标
1.  修改 `process_perception_and_recurse` 函数，增加对 `perception_result` 为 `None` 的检查。
2.  当 `perception_result` 为 `None` 时（表明它来自 `cs.wait`），将其视作一次成功的、非超时的等待，直接进入下一个周期的递归调用。

### 基本原理
不应期结束后的状态转换是确定性的：Agent 的相位推进到了 `refractory_period`，并且它没有接收到任何信号。我们的代码需要显式地模拟这个确定性状态转换，而不是错误地假设 `perception_result` 总是一个字典。

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #scope/core #ai/instruct
#task/domain/infra
#task/object/agent-logic
#task/action/bug-fix
#task/state/continue

---

### Script

#### Acts 1: 修复 Kuramoto Agent 的逻辑

我们将直接修改 `process_perception_and_recurse` 函数。

~~~~~act
patch_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
@cs.task
def process_perception_and_recurse(
    agent_id: int,
    phase: float,
    period: float,
    nudge: float,
    neighbors: List[DirectChannel],
    my_channel: DirectChannel,
    connector: Connector,
    refractory_period: float,
    perception_result: Dict[str, Any],
    flash_dependency: Any = None, # Used to chain flash action
) -> cs.LazyResult:
    """
    This task now contains the logic that was previously in the inner function.
    It returns the *next* LazyResult in the recursive chain.
    """
    is_timeout = perception_result.get("timeout", False)
    elapsed_time = perception_result.get("elapsed", 0.0)
    current_actual_phase = phase + elapsed_time

    if is_timeout:
        # We flashed. Reset phase and recurse.
        jitter = random.uniform(0.0, 0.1)
        return firefly_cycle(
            agent_id, 0.0 + jitter, period, nudge, neighbors,
            my_channel, connector, refractory_period
        )
    else:
        # We were nudged. Update phase and recurse.
        next_phase = current_actual_phase + nudge
        return firefly_cycle(
            agent_id, next_phase, period, nudge, neighbors,
            my_channel, connector, refractory_period
        )
~~~~~
~~~~~python
@cs.task
def process_perception_and_recurse(
    agent_id: int,
    phase: float,
    period: float,
    nudge: float,
    neighbors: List[DirectChannel],
    my_channel: DirectChannel,
    connector: Connector,
    refractory_period: float,
    perception_result: Dict[str, Any],
    flash_dependency: Any = None, # Used to chain flash action
) -> cs.LazyResult:
    """
    This task now contains the logic that was previously in the inner function.
    It returns the *next* LazyResult in the recursive chain.
    """
    # Handle the case where the input comes from cs.wait() which returns None
    if perception_result is None:
        # This occurs after the refractory period wait. The phase is already advanced.
        # We simply continue to the next cycle from the new phase.
        return firefly_cycle(
            agent_id, phase, period, nudge, neighbors,
            my_channel, connector, refractory_period
        )
        
    is_timeout = perception_result.get("timeout", False)
    elapsed_time = perception_result.get("elapsed", 0.0)
    current_actual_phase = phase + elapsed_time

    if is_timeout:
        # We flashed. Reset phase and recurse.
        jitter = random.uniform(0.0, 0.1)
        return firefly_cycle(
            agent_id, 0.0 + jitter, period, nudge, neighbors,
            my_channel, connector, refractory_period
        )
    else:
        # We were nudged or the refractory wait finished. Update phase and recurse.
        next_phase = current_actual_phase + nudge
        return firefly_cycle(
            agent_id, next_phase, period, nudge, neighbors,
            my_channel, connector, refractory_period
        )
~~~~~

### 下一步建议
我们已经修复了这个 `NoneType` 错误。请再次运行实验。这次我们预期它能够完整地运行下去，并且保持高性能和流畅的UI。

```bash
python -m observatory.experiments.run_fireflies
```
