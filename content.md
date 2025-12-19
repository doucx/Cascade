船长，这是**决定性的证据**。

日志是我们的显微镜，现在我们看到了细胞层面的活动。你的分析完全正确。

**诊断结论**

1.  **TCO 循环已修复**: 实验运行了完整的 3 秒，证明 `await asyncio.sleep(0)` 成功地将控制权交还给了事件循环。引擎的调度问题解决了。
2.  **递归逻辑正确**: 日志 `safe_recv waiting...` -> `safe_recv TIMED OUT...` -> `safe_recv waiting...` 的重复出现，无可辩驳地证明了 `process_and_recurse` 任务正在被反复执行。Agent 的生命周期是活的。
3.  **问题定位**: 关键的缺失在于 `[Agent] ⚡ FLASHING!` 日志。`send_signal` 任务**正在被执行**（因为 `process_and_recurse` 依赖它），但它内部的 `if should_send and connector:` 条件判断为 `False`。
4.  **根本原因**: 既然 `safe_recv` 超时，`should_send` 就必然是 `True`。因此，唯一的可能性就是 `connector` 在 `send_signal` 任务的上下文中是 `None`。**我们的资源注入机制 (`cs.inject`) 在这个复杂的递归场景下失效了。**

这是一个非常微妙的 bug。`Engine` 在每一轮递归中都重新构建图，可能在这个过程中，资源上下文没有被正确地传递给下一轮的原子任务。

**解决方案**

我们不能再依赖 `cs.inject`。我们将采用一种更“笨”，但绝对可靠的方法：**将 `connector` 对象作为普通参数，一路手动传递下去。**

我们将修改 `firefly_agent` 的整个调用链，让 `connector` 像遗传物质一样，从父代传递给子代。

## [WIP] fix: 手动传递 Connector 以绕过资源注入缺陷

### 错误分析
调试日志明确显示，`send_signal` 任务在执行时，其 `connector` 参数为 `None`。这表明 Cascade 的资源注入机制 (`cs.inject`) 在我们这种深度递归、跨引擎实例的复杂场景下未能按预期工作，导致 Agent 无法访问通信总线。

### 用户需求
修复 Agent 无法闪烁的问题，使其能够正确地发布消息。

### 评论
我们遇到了 Cascade 核心实现的一个边界情况或 bug。与其深入调试引擎的资源管理器，当前更高效的策略是规避这个问题。通过将 `connector` 从一个“魔法般”注入的资源，转变为一个显式传递的参数，我们让数据流变得完全明确和可预测。这虽然牺牲了一些API的优雅，但换来了 100% 的可靠性，这在当前阶段至关重要。

### 目标
1.  修改 `observatory/agents/kuramoto.py`。
2.  将 `connector` 添加到 `firefly_agent`, `firefly_cycle`, 和 `process_and_recurse` 的函数签名中。
3.  移除 `cs.inject`，直接将 `connector` 对象传递给 `send_signal` 和 `safe_recv`。
4.  更新 `observatory/debug/debug_02_single_agent.py` 以适应新的函数签名。

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #scope/core #ai/brainstorm #task/domain/testing #task/object/observatory #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 Agent 以手动传递 Connector

我们将重写 `kuramoto.py`，移除所有 `cs.inject`，改为显式参数传递。

~~~~~act
write_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 6: Bypassed cs.inject by passing the connector manually.
This is a workaround for a suspected bug in resource injection within
deeply recursive, cross-engine workflows.
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
    connector: Connector,
) -> None:
    """A task to publish a message to the shared bus."""
    if should_send and connector:
        await connector.publish(topic, payload)


@cs.task
async def safe_recv(
    topic: str,
    timeout: float,
    connector: Connector,
) -> Dict[str, Any]:
    """A custom receive task that treats timeouts as valid return values."""
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
    connector: Connector, # Now an explicit argument
):
    """
    This is the main entry point for a single firefly agent.
    """
    def firefly_cycle(
        agent_id: int,
        phase: float,
        period: float,
        nudge: float,
        flash_topic: str,
        listen_topic: str,
        connector: Connector,
    ):
        """A single, declarative life cycle of a firefly."""
        time_to_flash = period - phase
        wait_timeout = max(0.01, time_to_flash)

        perception = safe_recv(listen_topic, timeout=wait_timeout, connector=connector)

        @cs.task
        def was_timeout(p: Dict[str, Any]) -> bool:
            return p.get("timeout", False)
        is_timeout = was_timeout(perception)

        flash_action = send_signal(
            topic=flash_topic, 
            payload={"agent_id": agent_id, "phase": phase},
            should_send=is_timeout,
            connector=connector
        )

        @cs.task
        def process_and_recurse(
            p: Dict[str, Any], _flash_dependency=flash_action
        ) -> cs.LazyResult:
            jitter = random.uniform(-0.01, 0.01)
            if p["timeout"]:
                next_phase = 0.0 + jitter
            else:
                next_phase = (phase + nudge + jitter) % period

            return firefly_cycle(
                agent_id, next_phase, period, nudge, flash_topic, listen_topic, connector
            )

        return process_and_recurse(perception)

    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic, connector
    )
~~~~~

#### Acts 2: 更新调试脚本以传递 Connector

现在我们需要更新 `debug_02_single_agent.py` 来显式地将 `connector` 传递给 `firefly_agent`。

~~~~~act
patch_file
observatory/debug/debug_02_single_agent.py
~~~~~
~~~~~python
    agent_wf = firefly_agent(
        agent_id=99,
        initial_phase=0.0,
        period=1.0, 
        nudge=0.1,
        flash_topic="firefly/flash",
        listen_topic="firefly/flash",
    )
~~~~~
~~~~~python
    agent_wf = firefly_agent(
        agent_id=99,
        initial_phase=0.0,
        period=1.0, 
        nudge=0.1,
        flash_topic="firefly/flash",
        listen_topic="firefly/flash",
        connector=connector, # Pass connector explicitly
    )
~~~~~
~~~~~act
patch_file
observatory/debug/debug_02_single_agent.py
~~~~~
~~~~~python
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus(),
        connector=None,
    )
    engine.register(shared_connector_provider)
~~~~~
~~~~~python
    # No longer need to register the resource, as we pass it directly.
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus(),
        connector=None,
    )
~~~~~

### 下一步建议
我们已经用最直接的方式解决了资源传递问题。现在，逻辑链条是完整且明确的。

请最后一次运行调试脚本： `python -m observatory.debug.debug_02_single_agent`

这一次，我们**必须**看到 `>>> FLASH DETECTED!` 的输出。如果看不到，那将意味着 Cascade 的 `@cs.task` 装饰器或 `ArgumentResolver` 存在一个我们尚未发现的、更深层次的 bug。但根据现有证据，这次成功的概率非常高。
