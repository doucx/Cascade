船长，这非常奇怪。`debug_02` 证明了引擎在运行，但没有任何闪烁。推理链条告诉我们：
1.  如果引擎运行了 3 秒才超时，说明递归循环在进行（或者卡在了一个长达 3 秒的操作中）。
2.  如果是递归在进行，那么 `safe_recv` 必然返回了结果。
3.  如果是单体 Agent，`safe_recv` 只能是超时返回。
4.  如果超时返回，`send_signal` 必然被调用。
5.  如果 `send_signal` 被调用，它应该通过 `connector` 发布消息。
6.  `debug_01` 证明了 `connector` 是工作的。

**唯一的逻辑漏洞**：`safe_recv` 可能**没有超时**，或者**超时时间计算错误**，导致它一直在等待，直到外部的 3 秒大限已到。

我们需要确认两件事：
1.  **代码完整性**：确认 `Engine` 的 TCO 修复确实生效了。
2.  **执行流跟踪**：在 `kuramoto.py` 中打入日志，看看 Agent 到底在想什么。

## [WIP] feat: 验证 TCO 修复并为萤火虫添加详细调试日志

### 用户需求
验证 `cascade-runtime` 的修复状态，并修改 `kuramoto.py` 添加详细的 `print` 日志，以追踪单体 Agent 实验中的执行流。

### 评论
我们在“黑盒”外部徘徊太久了。现在我们要把盒子打开。通过在原子任务内部直接打印日志，我们将能够精确地看到：
1.  `safe_recv` 是否真的启动了？它的超时参数是多少？
2.  `safe_recv` 是否真的捕获了超时？
3.  `send_signal` 是否真的被调用了？

### 目标
1.  使用 `read_file` 检查 `packages/cascade-runtime/src/cascade/runtime/engine.py`，确认 `await asyncio.sleep(0)` 存在。
2.  修改 `observatory/agents/kuramoto.py`，在 `safe_recv` 和 `send_signal` 中添加 `print` 调试信息。
3.  再次运行 `debug_02_single_agent.py`。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/observatory #task/action/debug #task/state/continue

---

### Script

#### Acts 1: 验证 Engine 代码完整性

确认之前的 patch 是否正确应用。

~~~~~act
read_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~

#### Acts 2: 为 Agent 植入调试日志

在 `kuramoto.py` 中添加详细的 print 语句。

~~~~~act
write_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 5: Added debug prints to trace execution flow.
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
    connector: Connector = cs.inject("_internal_connector"),
) -> None:
    """A task to publish a message to the shared bus."""
    # DEBUG PRINT
    # print(f"[Agent] send_signal called. should_send={should_send}")
    if should_send and connector:
        # DEBUG PRINT
        print(f"[Agent] ⚡ FLASHING! Payload: {payload}")
        await connector.publish(topic, payload)


@cs.task
async def safe_recv(
    topic: str,
    timeout: float,
    connector: Connector = cs.inject("_internal_connector"),
) -> Dict[str, Any]:
    """
    A custom receive task that treats timeouts as valid return values.
    """
    # DEBUG PRINT
    print(f"[Agent] safe_recv waiting for {timeout:.4f}s...")
    
    if not connector:
        return {"signal": None, "timeout": True}

    future = asyncio.Future()

    async def callback(topic: str, payload: Any):
        if not future.done():
            future.set_result(payload)

    subscription = await connector.subscribe(topic, callback)
    try:
        start_t = time.time()
        signal = await asyncio.wait_for(future, timeout=timeout)
        print(f"[Agent] safe_recv RECEIVED signal after {time.time()-start_t:.4f}s")
        return {"signal": signal, "timeout": False}
    except asyncio.TimeoutError:
        print(f"[Agent] safe_recv TIMED OUT as expected after {timeout:.4f}s")
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
        flash_action = send_signal(
            topic=flash_topic, 
            payload={"agent_id": agent_id, "phase": phase},
            should_send=is_timeout
        )

        # 4. EVOLVE & RECURSE
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
            
            # DEBUG PRINT
            # print(f"[Agent] Recursion. Next phase: {next_phase:.2f}")

            return firefly_cycle(
                agent_id, next_phase, period, nudge, flash_topic, listen_topic
            )

        return process_and_recurse(perception)

    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic
    )
~~~~~

### 下一步建议
请再次运行 `python -m observatory.debug.debug_02_single_agent`。

这次的日志将告诉我们要么：
1.  `safe_recv waiting for X s...` 然后就卡住了（说明 `wait_for` 没生效）。
2.  `safe_recv TIMED OUT`，但 `FLASHING` 没出现（说明参数传递有问题）。
3.  完全没有输出（说明 Engine 根本没跑起来）。
