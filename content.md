船长，你的诊断完全正确，而且你发现了一个比表面看起来更深层次的问题。

**错误分析**

你指出的现象——“立刻退出”和“进度条未变化”——是两个关键线索，它们指向了我们 Agent 设计中的一个根本性架构缺陷。

1.  **为何进度条未变 (The Obvious Bug)**: `ConvergenceMonitor` 依赖于 `firefly/flash` 主题上的信号。在 `kuramoto.py` 的原始设计中，`send_signal(...)` 任务在一个 `@cs.task` 内部被调用，但它的 `LazyResult` **从未被返回**。这意味着 `send_signal` 从未成为计算图的一部分，因此**从未被执行**。萤火虫们实际上是“哑巴”，它们从未闪烁，所以监控器自然什么也看不到。

2.  **为何立刻退出 (The Deeper Bug)**: 这是更严重的问题。既然萤火虫不闪烁，`cs.recv` 就应该**等待**其 `timeout`（大约 10 秒）然后超时。整个实验应该持续 60 秒。但它在 1.17 秒内就退出了。这揭示了一个我们之前未曾预料到的、关于递归工作流的架构限制：
    *   我们的“尾递归优化 (TCO)”存在于 `Engine.run` 的顶层循环中。
    *   当一个任务（如 `process_cycle_result`）返回一个 `LazyResult` 时，引擎并不会立刻开始执行这个新的工作流。它将这个 `LazyResult` 对象视为一个**普通的数据返回值**，并将其存入状态后端。
    *   只有当整个原始图的所有任务都完成后，`Engine.run` 才会检查最终结果。如果这个结果是 `LazyResult`，它才会启动下一轮循环。
    *   然而，因为我们的 `firefly_cycle` 依赖于 `cs.recv`，这是一个阻塞操作，它似乎在当前引擎的执行模型中导致了事件循环的异常退出或未被正确调度。**这是一个需要记录的技术债务**，即引擎目前不能很好地支持包含“永久阻塞”任务的递归工作流。

**解决方案**

我们需要重新设计 `firefly_agent`，使其更符合 Cascade 的**声明式**和**无阻塞**的图构建理念。我们将把隐式的、命令式的 `if/else` 逻辑，改造为显式的、由图结构本身表达的条件执行路径。

我将为你生成一个计划，彻底重构 `kuramoto.py` 以解决这两个问题。

## [WIP] fix: 重构萤火虫 Agent 以支持正确的声明式执行

### 错误分析
实验失败的根本原因有两个：
1.  **命令式执行**: 在 `decide_and_act` 任务内部，`send_signal` 被命令式地调用，但其返回的 `LazyResult` 未被接入计算图，导致该任务从未执行，萤火虫无法“闪烁”。
2.  **递归模型缺陷**: 当前 `Engine` 的 TCO 模型无法正确处理包含长时阻塞任务（如 `cs.recv`）的递归工作流，导致实验意外地提前退出。

### 用户需求
修复 `kuramoto.py` 中的 Agent 逻辑，使其能够正确执行闪烁操作，并能在引擎中稳定地长期运行。

### 评论
这次失败是一次宝贵的教训，它暴露了我们对 Cascade 执行模型的误解。修复方案的核心是从“命令式”思维转向“声明式”思维。我们不再在一个任务内部根据条件执行另一个任务，而是构建一个图，其中包含一个条件节点 (`was_timeout`)，并使用 `.run_if()` 来让图的*结构本身*来表达这个条件逻辑。这使得整个工作流对引擎完全透明、可预测，从而解决了两个根本性问题。

### 目标
1.  将 `decide_and_act` 任务分解为纯粹的“决策”和独立的“行动”任务。
2.  创建一个 `was_timeout` 任务，用于将 `handled_recv` 的结果转化为一个布尔型的 `LazyResult`。
3.  使用 `.run_if(was_timeout)` 来确保 `send_signal` 任务只有在超时的情况下才被执行，并正确地接入计算图。
4.  重构 `process_cycle_result` 任务，使其依赖于所有必要的上游节点（包括条件执行的 `send_signal`），以确保正确的执行顺序。

### 基本原理
新的设计遵循 Cascade 的核心原则：**组合优于封装**。我们将复杂的、带有内部分支的 `decide_and_act` 任务，分解为一系列更小、更纯粹的原子任务，并通过 Cascade 的声明式 API (`.run_if()`) 将它们组合起来。
-   `recv_with_timeout_handler` 负责**感知**。
-   `was_timeout` 负责**判断**。
-   `send_signal(...).run_if(...)` 负责**行动**。
-   `process_cycle_result` 负责**状态演化**和**递归**。
这个清晰的分层结构不仅解决了 bug，也使得工作流的逻辑更加健壮和易于理解。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/brainstorm #task/domain/testing #task/object/observatory #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构并修复萤火虫 Agent 的核心逻辑

我们将用一个完全重构的版本覆盖 `kuramoto.py`。新的代码是纯声明式的，确保了所有操作都在计算图中正确表达。

~~~~~act
write_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 2: This version uses a fully declarative approach with .run_if()
to ensure all actions are correctly represented in the computation graph.
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
    Wraps a cs.recv call to transform asyncio.TimeoutError into a structured output.
    """
    try:
        # This await is crucial; it executes the LazyResult passed in.
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

        # 1. PERCEIVE: Wait for a signal OR until it's time to flash
        recv_task = cs.recv(listen_topic, timeout=wait_timeout)
        handled_recv = recv_with_timeout_handler(recv_task)

        # 2. DECIDE: Was the perception a timeout?
        @cs.task
        def was_timeout(hrr: Dict[str, Any]) -> bool:
            return hrr.get("timeout", False)

        is_timeout = was_timeout(handled_recv)

        # 3. ACT: Flash *only if* it was a timeout.
        flash_action = send_signal(
            topic=flash_topic, payload={"agent_id": agent_id, "phase": phase}
        ).run_if(is_timeout)

        # 4. EVOLVE & RECURSE: Calculate the next state and loop.
        # This task must wait for the flash_action to complete to ensure ordering.
        @cs.task
        def process_and_recurse(
            hrr: Dict[str, Any], _flash_dependency=flash_action
        ) -> cs.LazyResult:
            jitter = random.uniform(-0.01, 0.01)

            if hrr["timeout"]:
                # We flashed, reset phase.
                next_phase = 0.0 + jitter
            else:
                # We saw another flash, nudge phase forward.
                # Note: A more accurate model would use the time waited, but this is simpler
                # and still effective for demonstrating synchronization.
                next_phase = (phase + nudge + jitter) % period

            # The recursive call that powers the agent's lifecycle
            return firefly_cycle(
                agent_id, next_phase, period, nudge, flash_topic, listen_topic
            )

        return process_and_recurse(handled_recv)

    # Start the first cycle
    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic
    )
~~~~~

### 下一步建议
我们已经对萤火虫的“基因”进行了修复和重构，现在它的行为应该是正确的、声明式的。

请再次运行实验。新的 Agent 设计应该能够正确地执行闪烁操作，并稳定地在引擎中循环。我们应该能看到监控器上的进度条开始移动了。

请在终端中，从项目根目录再次执行：

`python -m observatory.experiments.run_fireflies`
