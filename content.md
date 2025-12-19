这是一个极其隐蔽但致命的逻辑陷阱，你的观察非常敏锐。

**错误分析**

当前 `kuramoto.py` 的设计导致了**“听到即死”**的现象：

1.  代码逻辑：
    ```python
    flash_action = send_signal(...).run_if(is_timeout)

    @cs.task
    def process_and_recurse(..., _flash_dependency=flash_action):
        ...
    ```
2.  **Cascade 的依赖传播规则**: 如果任务 A 依赖任务 B，而任务 B 被跳过（Skipped），那么任务 A 也会自动被跳过。
3.  **致命后果**:
    *   当萤火虫**超时**时：`is_timeout=True` -> `flash_action` 执行 -> `process_and_recurse` 执行 -> **存活**。
    *   当萤火虫**听到信号**时：`is_timeout=False` -> `flash_action` **被跳过** -> `process_and_recurse` **被连锁跳过** -> **递归终止，Agent 死亡**。
4.  **现象解释**:
    *   实验开始，大家都在等。
    *   第一只萤火虫（相位最快的）超时，闪烁，存活。
    *   其他 49 只萤火虫收到信号，`safe_recv` 返回，`is_timeout=False`。
    *   这 49 只萤火虫试图跳过闪烁，结果导致递归步骤也被跳过，全部死亡。
    *   剩下的那只萤火虫继续闪烁，但已经没有听众了。
    *   而且，由于我们没有看到日志，可能是因为第一只闪烁的时候，监测器可能还没来得及打印（或者被死锁的 Agent 干扰了）。或者更有可能的是，那 49 只死亡的 Agent 抛出的 `TaskSkipped` 事件淹没了系统，或者导致 `gather` 认为任务已完成（如果 `process_and_recurse` 被跳过，整个工作流就结束了）。

**解决方案**

我们必须打破这种“强依赖链”。最简单、最稳健的方法是**将条件逻辑内化到 `send_signal` 任务中**。

我们将修改 `send_signal`，使其接受一个 `should_send` 布尔参数。这样，`send_signal` 任务本身**总是会执行**（不会被跳过），从而保证后续的递归任务 `process_and_recurse` 也能总是执行。

我将为你生成修复计划。

## [WIP] fix: 修复 Agent 在接收信号后意外终止的逻辑缺陷

### 错误分析
当前的声明式依赖链导致了非预期的副作用：当 `send_signal` 因条件不满足被跳过时，依赖它的递归任务 `process_and_recurse` 也会被自动跳过，导致 Agent 在接收到邻居信号后意外终止运行。这解释了为什么实验中没有观察到持续的活动。

### 用户需求
修改 `kuramoto.py`，确保无论是否需要闪烁，Agent 的生命周期循环都能继续进行。

### 评论
这是声明式编程中常见的一个陷阱：控制流与数据流的耦合。为了解耦，我们需要将“是否执行副作用”的逻辑放入任务内部，保证任务本身在图层面是“总是成功”的。这虽然牺牲了一点点声明式的纯粹性（`.run_if` 很漂亮），但换来了绝对的运行时稳定性。

### 目标
1.  修改 `send_signal` 任务签名，增加 `should_send: bool` 参数。
2.  在 `send_signal` 内部检查 `should_send`，仅在为 True 时执行 `publish`。
3.  移除 `firefly_cycle` 中的 `.run_if(is_timeout)` 调用。
4.  将 `is_timeout` 结果作为参数直接传递给 `send_signal`。

### 基本原理
通过让 `send_signal` 总是执行（Always Run），我们保证了它总是产生一个结果（哪怕是 None）。这样，依赖它的 `process_and_recurse` 就永远不会因为上游缺失而触发 `DependencyMissingError` 或被跳过，从而确保了递归循环的连续性。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/refine #task/domain/testing #task/object/observatory #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 将条件逻辑内化到 send_signal 任务中

我们将修改 `kuramoto.py`，移除导致断链的 `.run_if`，改用参数控制副作用。

~~~~~act
write_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 4: Internalized the conditional logic into send_signal.
This prevents the 'skip propagation' issue where skipping the flash action
caused the recursive step to be skipped as well, killing the agent.
"""
import asyncio
import random
from typing import Any, Dict

import cascade as cs
from cascade.interfaces.protocols import Connector


# --- Atomic Primitives for Agent Behavior ---

@cs.task
async def send_signal(
    topic: str,
    payload: Dict[str, Any],
    should_send: bool,
    connector: Connector = cs.inject("_internal_connector"),
) -> None:
    """
    A task to publish a message to the shared bus.
    Now accepts 'should_send' to handle conditional logic internally,
    ensuring the task always executes and doesn't break downstream dependencies.
    """
    if should_send and connector:
        await connector.publish(topic, payload)


@cs.task
async def safe_recv(
    topic: str,
    timeout: float,
    connector: Connector = cs.inject("_internal_connector"),
) -> Dict[str, Any]:
    """
    A custom receive task that treats timeouts as valid return values.
    Returns: {"signal": payload, "timeout": False} OR {"signal": None, "timeout": True}
    """
    if not connector:
        return {"signal": None, "timeout": True}

    future = asyncio.Future()

    async def callback(topic: str, payload: Any):
        if not future.done():
            future.set_result(payload)

    subscription = await connector.subscribe(topic, callback)
    try:
        signal = await asyncio.wait_for(future, timeout=timeout)
        return {"signal": signal, "timeout": False}
    except asyncio.TimeoutError:
        return {"signal": None, "timeout": True}
    finally:
        if subscription:
            await subscription.unsubscribe()


# --- Core Agent Logic ---

def firefly_agent(
    agent_id: int,
    initial_phase: float,
    period: float,
    nudge: float,
    flash_topic: str,
    listen_topic: str,
):
    """
    This is the main entry point for a single firefly agent.
    It kicks off the recursive cycle.
    """

    def firefly_cycle(
        agent_id: int,
        phase: float,
        period: float,
        nudge: float,
        flash_topic: str,
        listen_topic: str,
    ):
        """A single, declarative life cycle of a firefly."""
        time_to_flash = period - phase
        wait_timeout = max(0.01, time_to_flash)

        # 1. PERCEIVE
        perception = safe_recv(listen_topic, timeout=wait_timeout)

        # 2. DECIDE
        @cs.task
        def was_timeout(p: Dict[str, Any]) -> bool:
            return p.get("timeout", False)

        is_timeout = was_timeout(perception)

        # 3. ACT
        # We pass 'is_timeout' as a data dependency. 
        # The task will always run, but only emit side effects if True.
        flash_action = send_signal(
            topic=flash_topic, 
            payload={"agent_id": agent_id, "phase": phase},
            should_send=is_timeout
        )

        # 4. EVOLVE & RECURSE
        # We explicitly depend on flash_action to ensure ordering (Act before Recurse)
        @cs.task
        def process_and_recurse(
            p: Dict[str, Any], _flash_dependency=flash_action
        ) -> cs.LazyResult:
            jitter = random.uniform(-0.01, 0.01)

            if p["timeout"]:
                # We flashed, reset phase.
                next_phase = 0.0 + jitter
            else:
                # We saw another flash, nudge phase forward.
                next_phase = (phase + nudge + jitter) % period

            return firefly_cycle(
                agent_id, next_phase, period, nudge, flash_topic, listen_topic
            )

        return process_and_recurse(perception)

    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic
    )
~~~~~

### 下一步建议
这次修复应该是决定性的。我们解决了 Agent 意外死亡的问题，也解决了 Engine 资源竞争的问题。

请再次运行实验。

执行命令：
`python -m observatory.experiments.run_fireflies`

期待：
1.  **Monitor Logs**: 看到大量的 `[Monitor] Received flash...`。
2.  **Sync Bar**: 进度条出现，并开始波动或增长。

如果成功，这将是我们构建“合成智能”原语的一个重要里程碑。
