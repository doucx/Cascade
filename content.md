这是一个非常精彩的调试过程。实验的快速失败（0.23s）揭示了一个关于 Cascade 异常传播机制的关键误解。

**错误根源深度剖析**

你目前的 `kuramoto.py` 是这样设计的：
```python
recv_task = cs.recv(...)  # 任务 A
handled_recv = recv_with_timeout_handler(recv_task)  # 任务 B
```

在 Cascade 的执行模型中：
1.  引擎首先调度 **任务 A (`cs.recv`)**。
2.  当超时发生时，`cs.recv` 的实现（在核心库中）会**抛出 `asyncio.TimeoutError`**。
3.  引擎捕获到这个异常，将其标记为 **任务 A 失败**。
4.  因为任务 A 失败，依赖它的 **任务 B (`recv_with_timeout_handler`) 永远不会被执行**。
5.  引擎判定当前工作流执行失败，抛出异常，进而导致外部的 `run_experiment` 中的 `asyncio.gather` 崩溃。

**结论**：试图在下游任务（任务 B）中捕获上游任务（任务 A）的异常是行不通的，因为上游失败会直接阻断执行流。

**解决方案**

我们需要将“超时”这一行为，从“异常（Exception）”降级为“数据（Data）”。

我们需要在 `kuramoto.py` 中实现一个自定义的 `safe_recv` 任务，它在内部捕获 `TimeoutError`，并返回一个表示超时的字典（例如 `{"timeout": True}`），而不是抛出异常。这完全符合 Cascade 的哲学：**让数据流驱动控制流**。

我将生成一个计划来实施这个修复。

## [WIP] fix: 将 cs.recv 替换为 safe_recv 以处理超时

### 错误分析
当前的萤火虫 Agent 依赖于 `cs.recv` 抛出 `TimeoutError` 来触发闪烁行为。然而，在 Cascade 引擎中，任务抛出异常会导致工作流直接失败，而不是将异常传递给下游任务处理。这导致只要有任何一只萤火虫超时（准备闪烁），整个实验就会崩溃。

### 用户需求
修改 `kuramoto.py`，实现一个不抛出异常的信号接收机制，使萤火虫能够在超时后继续执行“闪烁”逻辑，而不是导致程序崩溃。

### 评论
这又是一次观念的纠正。在分布式系统中，超时不是“错误”，而是一种“状态”。我们需要将这种状态内化到原子任务中，而不是依赖异常处理机制。通过实现 `safe_recv`，我们将不可控的异常流转变为可控的数据流，这是构建健壮 Agent 的关键一步。

### 目标
1.  在 `kuramoto.py` 中实现一个新的 `@cs.task`：`safe_recv`。
2.  `safe_recv` 应直接使用 `connector` 订阅主题，并在 `asyncio.wait_for` 超时时捕获异常，返回 `{"timeout": True}`。
3.  移除旧的 `recv_with_timeout_handler` 任务。
4.  更新 `firefly_cycle` 逻辑以使用 `safe_recv`。

### 基本原理
我们利用 Cascade 的 `cs.inject("_internal_connector")` 机制，在用户定义的任务中直接访问底层的连接器。这赋予了我们极大的灵活性，允许我们在不修改核心库的情况下，定制特定于实验的 I/O 行为。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/refine #task/domain/testing #task/object/observatory #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 用 safe_recv 重构萤火虫 Agent

我们将重写 `kuramoto.py`，用内置了错误处理的 `safe_recv` 替换掉原生的 `cs.recv` + `handler` 组合。

~~~~~act
write_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 3: Replaced cs.recv with a custom safe_recv task.
This ensures timeouts are treated as data, not exceptions, preventing
the engine from aborting the workflow when a firefly needs to flash.
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
    connector: Connector = cs.inject("_internal_connector"),
) -> None:
    """A task to publish a message to the shared bus."""
    if connector:
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
         # Should not happen in a properly configured engine
        return {"signal": None, "timeout": True}

    future = asyncio.Future()

    async def callback(topic: str, payload: Any):
        if not future.done():
            future.set_result(payload)

    subscription = await connector.subscribe(topic, callback)
    try:
        # Wait for the signal
        signal = await asyncio.wait_for(future, timeout=timeout)
        return {"signal": signal, "timeout": False}
    except asyncio.TimeoutError:
        # Crucial: Return data, don't raise exception
        return {"signal": None, "timeout": True}
    finally:
        # Always clean up the subscription to prevent memory leaks
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
        # Ensure timeout is positive and reasonable
        wait_timeout = max(0.01, time_to_flash)

        # 1. PERCEIVE: Use our custom safe_recv
        perception = safe_recv(listen_topic, timeout=wait_timeout)

        # 2. DECIDE: Was the perception a timeout?
        @cs.task
        def was_timeout(p: Dict[str, Any]) -> bool:
            return p.get("timeout", False)

        is_timeout = was_timeout(perception)

        # 3. ACT: Flash *only if* it was a timeout.
        flash_action = send_signal(
            topic=flash_topic, payload={"agent_id": agent_id, "phase": phase}
        ).run_if(is_timeout)

        # 4. EVOLVE & RECURSE: Calculate the next state and loop.
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

            # The recursive call that powers the agent's lifecycle
            return firefly_cycle(
                agent_id, next_phase, period, nudge, flash_topic, listen_topic
            )

        return process_and_recurse(perception)

    # Start the first cycle
    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic
    )
~~~~~

### 下一步建议
这是最后一块拼图。我们修复了引擎的调度模型（让出控制权），并修复了 Agent 的异常处理模型（将超时视为数据）。

现在，系统应当是健壮的。请再次运行实验。

执行命令：
`python -m observatory.experiments.run_fireflies`

期待看到：
1.  完整的 60 秒运行。
2.  日志中持续的 Flash 记录。
3.  最重要的是：同步进度条的稳步增长。
