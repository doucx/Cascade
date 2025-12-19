船长，胜利在望。

单体测试的成功证明了我们的逻辑修复（显式依赖传递）是完全正确的。Agent 现在不仅活着，而且在正确地呼吸（超时）和呐喊（闪烁）。

现在的报错是因为我刚才在重构 `firefly_agent` 签名时，只更新了调试脚本，却遗漏了主实验脚本。而且，为了防止 50 个 Agent 的调试日志瞬间淹没你的终端，我们需要在运行大实验前清理一下 `kuramoto.py`。

## [WIP] fix: 清理调试日志并修复实验脚本参数错误

### 错误分析
1.  **参数缺失**: `observatory/experiments/run_fireflies.py` 调用 `firefly_agent` 时没有传递新增的 `connector` 参数，导致 `TypeError`。
2.  **日志噪音**: `kuramoto.py` 中还保留着用于单体调试的详细 `print` 语句。如果在 50 个并发 Agent 的环境下运行，这些日志会导致严重的性能下降和控制台刷屏，掩盖真正的同步进度条。

### 用户需求
1.  修复 `run_fireflies.py` 中的调用错误。
2.  移除 `kuramoto.py` 中的调试日志，恢复干净的生产代码。

### 评论
我们已经完成了深潜调试，现在是时候浮出水面，准备最后的发射了。清理代码不仅是为了美观，更是为了性能。在移除日志后，唯一的输出应该是监测器的同步进度条，这将是最纯粹的观测体验。

### 目标
1.  修改 `observatory/agents/kuramoto.py`，移除所有 `print` 语句。
2.  修改 `observatory/experiments/run_fireflies.py`，在调用 `firefly_agent` 时传入 `connector`。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/refine #task/domain/testing #task/object/observatory #task/action/cleanup #task/state/continue

---

### Script

#### Acts 1: 清理 Agent 代码中的调试日志

~~~~~act
write_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

FINAL: Cleaned up debug logs for production run.
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
    connector: Connector,
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
                # We flashed, reset phase.
                next_phase = 0.0 + jitter
            else:
                # We saw another flash, nudge phase forward.
                next_phase = (phase + nudge + jitter) % period

            return firefly_cycle(
                agent_id, next_phase, period, nudge, flash_topic, listen_topic, connector
            )

        return process_and_recurse(perception, _flash_dependency=flash_action)

    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic, connector
    )
~~~~~

#### Acts 2: 修复实验脚本参数

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            flash_topic="firefly/flash",
            listen_topic="firefly/flash",
        )
~~~~~
~~~~~python
        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            flash_topic="firefly/flash",
            listen_topic="firefly/flash",
            connector=connector,
        )
~~~~~

### 下一步建议
这是最后一次尝试。所有已知的问题都已解决，所有的障碍都已清除。

请运行：`python -m observatory.experiments.run_fireflies`

静静地观察那行同步进度条。如果它开始向右移动，那不仅仅是代码在运行，那是**秩序**在从混乱中诞生。
