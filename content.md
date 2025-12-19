好的，船长。我们已经搭建好了实验室，现在是时候注入生命了。

我们将为萤火虫 Agent 编写核心的“神经代码”。这不仅是对“涌现”理论的一次实践，更是对 Cascade 声明式原语 (`cs.wait`, `cs.recv`) 和递归工作流能力的一次深度检验。

这个实现将遵循一个优雅的模式：**将 `asyncio.TimeoutError` 从一个“错误”转变为一个“信号”**。当 `cs.recv` 等待超时，这并非失败，而是萤火虫自己的“生物钟”到点，是它闪烁的时刻。

我将生成一个计划来实现这个逻辑。

## [WIP] feat: 实现基于 Kuramoto 模型的萤火虫 Agent 工作流

### 用户需求
在 `observatory/agents/kuramoto.py` 文件中，使用 `cs.wait`, `cs.recv` 和递归工作流，实现萤火虫 Agent 的核心闪烁与同步逻辑。

### 评论
这是“萤火计划”的核心实现。它将一个经典的科学模型（脉冲耦合振荡器）完全用 Cascade 的声明式原语来表达。这个过程不仅能验证我们新增的 `cs.wait` 和 `cs.recv` 是否足够强大，更重要的是，它将成为一个范例，展示如何用 Cascade 构建能够感知并响应环境、且能长期运行的自主代理 (Agent)，而无需引入任何新的 `Agent` 类。

### 目标
1.  在 `kuramoto.py` 中创建一个本地的、原子的 `send_signal` 任务，用于向消息总线广播“闪烁”事件。
2.  创建一个 `recv_with_timeout_handler` 任务，它能将 `cs.recv` 的 `TimeoutError` 异常转化为一个正常的、可处理的数据输出。
3.  实现一个核心的 `firefly_cycle` 递归子流程，该流程封装了萤火虫的“等待-感知-调整-行动”循环。
4.  将上述组件组合成一个完整的、可由外部实验脚本调用的 `firefly_agent` 工作流。

### 基本原理
萤火虫的行为被建模为一个递归的状态机，其核心状态是内部的“相位时钟”（phase）。
1.  **等待与感知**: `cs.recv` 会在 `time_to_flash` 的时间内等待其他萤火虫的信号。
2.  **事件驱动决策**:
    *   如果 `cs.recv` **超时**，意味着是时候自己闪烁了。Agent 会广播一个信号，并将自己的相位重置为 0。
    *   如果 `cs.recv` **接收到信号**，意味着看到了邻居的闪烁。Agent 会根据接收到的信号，将自己的相位向前“推动”一小步。
3.  **递归循环**: 决策完成后，工作流会使用更新后的相位值，再次调用自身，从而实现永不停止的生命周期。

### 标签
#intent/build #flow/ready #priority/high #comp/tests #scope/dx #ai/delegate #task/domain/testing #task/object/observatory #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 实现萤火虫 Agent 的完整逻辑

我们将使用 `write_file` 覆盖占位符文件，并填入完整的 Agent 实现。这包括了所有辅助任务和核心的递归工作流。

~~~~~act
write_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.
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
async def recv_with_timeout_handler(recv_lazy_result: cs.LazyResult) -> Dict[str, Any]:
    """
    Wraps a cs.recv call to transform asyncio.TimeoutError into a structured output,
    making it a predictable control flow mechanism instead of an exception.
    """
    try:
        signal = await recv_lazy_result
        return {"signal": signal, "timeout": False}
    except asyncio.TimeoutError:
        return {"signal": None, "timeout": True}


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

    @cs.task
    def process_cycle_result(
        agent_id: int,
        cycle_result: Dict[str, Any],
        period: float,
        nudge: float,
        flash_topic: str,
        listen_topic: str,
    ):
        """
        Takes the result of one cycle, calculates the new state,
        and recursively calls the next cycle.
        """
        current_phase = cycle_result["phase"]
        # Add a small random jitter to avoid perfect, static synchronization
        jitter = random.uniform(-0.01, 0.01)

        # Main logic:
        # If the cycle timed out, it means we flashed. Reset phase.
        if cycle_result["timeout"]:
            next_phase = 0.0 + jitter
        else:
            # We received a signal. Nudge the phase forward.
            # We also account for the time we spent waiting.
            time_waited = cycle_result["time_waited"]
            next_phase = (current_phase + time_waited + nudge + jitter) % period
        
        # This is the recursive call
        return firefly_cycle(
            agent_id, next_phase, period, nudge, flash_topic, listen_topic
        )

    def firefly_cycle(
        agent_id: int,
        phase: float,
        period: float,
        nudge: float,
        flash_topic: str,
        listen_topic: str,
    ):
        """A single life cycle of a firefly."""
        time_to_flash = period - phase
        
        # We must ensure timeout is positive
        wait_timeout = max(0.01, time_to_flash)

        # Wait for a signal OR until it's time to flash
        recv_task = cs.recv(listen_topic, timeout=wait_timeout)
        handled_recv = recv_with_timeout_handler(recv_task)
        
        # Decide what to do based on whether we timed out or received a signal
        @cs.task
        def decide_and_act(handled_recv_result: Dict[str, Any]) -> Dict[str, Any]:
            if handled_recv_result["timeout"]:
                # Our turn to flash!
                send_signal(
                    topic=flash_topic,
                    payload={"agent_id": agent_id, "phase": phase},
                )
                return {"phase": phase, "timeout": True, "time_waited": wait_timeout}
            else:
                # We saw another flash
                return {"phase": phase, "timeout": False, "time_waited": wait_timeout}

        decision = decide_and_act(handled_recv)
        
        # This is TCO: the result of this subflow is another subflow
        return process_cycle_result(
            agent_id, decision, period, nudge, flash_topic, listen_topic
        )

    # Start the first cycle
    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic
    )
~~~~~

### 下一步建议
我们已经成功定义了单个萤火虫的“心智模型”。现在，我们需要一个“环境”来孕育它们，并启动一个萤火虫“种群”。

我建议下一步是创建实验脚本 `observatory/experiments/run_fireflies.py`。这个脚本将负责：
1.  **初始化环境**：配置并启动一个 `LocalBusConnector`。
2.  **批量生成 Agent**：循环创建多个 `firefly_agent` 工作流实例，每个都有随机的初始相位。
3.  **并发执行**：使用 `asyncio.gather` 同时运行所有的萤火虫 Agent。

这将是我们第一次真正“点亮”这个系统，并为后续的观测和分析做好准备。
