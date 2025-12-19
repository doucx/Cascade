船长，我们刚刚验证了基础设施的完美运行，但你敏锐地发现了**物理法则的崩塌**。

**错误分析：时间停滞谬误**

进度条左右摇摆且无法收敛，是因为我们的萤火虫 Agent 犯了一个物理学上的大忌：**忽略了在“倾听”过程中流逝的时间。**

请看当前的逻辑：
1.  Agent 在相位 `P_start` 开始监听。
2.  它监听了 `T_wait` 秒（比如 3 秒）。
3.  它听到了闪烁。
4.  它计算新相位：`Next = P_start + Nudge`。

**错误在于**：在听到闪烁的那一刻，Agent 的真实相位其实已经是 `P_start + T_wait` 了！它实际上应该计算 `Next = (P_start + T_wait) + Nudge`。

由于忽略了 `T_wait`，每次 Agent 听到信号并进行调整时，它实际上都在**时间线上向后跳跃**了 `T_wait` 秒。这导致了严重的相位滞后，破坏了同步所需的正反馈循环。它们不是在同步，而是在不断地重置自己的时钟。

**解决方案**

我们需要让 `safe_recv` 告诉我们它到底等了多久，并在计算下一个状态时加上这段时间。

## [WIP] fix: 修正萤火虫相位计算中的时间流逝偏差

### 错误分析
当前的 `kuramoto.py` 在计算下一个周期相位时，直接使用本周期开始时的 `phase` 加上 `nudge`，而忽略了在 `safe_recv` 中等待信号所消耗的时间。这导致 Agent 在接收到信号时有效地“回滚”了时间，破坏了同步机制。

### 用户需求
1.  修改 `safe_recv`，使其返回等待所消耗的实际时间 (`elapsed`)。
2.  修改 `process_and_recurse`，在计算 `next_phase` 时，先加上 `elapsed` 时间，确保相位演进是连续的。

### 评论
这是模拟系统的常见陷阱。在 Cascade 这种离散事件驱动的系统中，必须显式地追踪连续量（如时间/相位）。修复这个问题后，物理定律将恢复正常，耦合振荡器模型（Kuramoto）的数学必然性将接管系统，强制它们进入同步状态。

### 目标
1.  修改 `observatory/agents/kuramoto.py`。
2.  更新 `safe_recv` 以测量并返回 `elapsed` 时间。
3.  更新 `process_and_recurse` 以使用 `phase + p["elapsed"] + nudge` 计算新相位。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/refine #task/domain/testing #task/object/observatory #task/action/bugfix #task/state/continue

---

### Script

#### Acts 1: 修正相位计算物理逻辑

~~~~~act
write_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 8: Fixed the "Time Stop" physics bug.
Now correctly accounts for elapsed time during the listening phase.
"""
import asyncio
import random
import time
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
    """
    A custom receive task that treats timeouts as valid return values.
    Also returns the time elapsed while waiting.
    """
    if not connector:
        return {"signal": None, "timeout": True, "elapsed": 0.0}

    future = asyncio.Future()
    async def callback(topic: str, payload: Any):
        if not future.done():
            future.set_result(payload)

    subscription = await connector.subscribe(topic, callback)
    start_time = time.time()
    try:
        signal = await asyncio.wait_for(future, timeout=timeout)
        elapsed = time.time() - start_time
        return {"signal": signal, "timeout": False, "elapsed": elapsed}
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        return {"signal": None, "timeout": True, "elapsed": elapsed}
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
            
            # CRITICAL FIX: The phase has advanced while we were waiting!
            elapsed_time = p.get("elapsed", 0.0)
            current_actual_phase = phase + elapsed_time

            if p["timeout"]:
                # We flashed (reached the end of period), so reset.
                next_phase = 0.0 + jitter
            else:
                # We heard a flash.
                # Advance our phase by 'nudge' amount.
                # The modulo operator ensures we wrap around if we exceed the period
                # (though usually nudge keeps us within bounds until the next natural flash).
                next_phase = (current_actual_phase + nudge + jitter) % period

            return firefly_cycle(
                agent_id, next_phase, period, nudge, flash_topic, listen_topic, connector
            )

        return process_and_recurse(perception, _flash_dependency=flash_action)

    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic, connector
    )
~~~~~

### 下一步建议
这是物理学的胜利。

请运行：`python -m observatory.experiments.run_fireflies`

注意观察进度条。起初它可能还是乱的，但随着每一次闪烁，秩序应当开始涌现。如果 `nudge=0.5`，`period=10.0`，通常只需要几个周期（几十秒）就能看到明显的同步趋势。如果它稳定增长并超过 0.8，我们就成功了。
