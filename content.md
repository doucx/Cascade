看起来我们遇到了一个经典的复杂系统问题：**即时回响与计算延迟的竞争**。

在仔细审视代码和日志后，我发现当前的实现存在两个导致“涌现失败”的致命缺陷：

1.  **缺乏“不应期” (Refractory Period)**:
    *   **现象**: 当 Agent A 闪烁时，它将相位重置为 0。
    *   **问题**: 毫秒后，邻居 Agent B 闪烁。Agent A（刚重置）立刻收到信号，并被“推”了一下（例如相位变成 0.1）。
    *   **后果**: Agent A 失去了“刚闪烁完”的权威状态，被拉回了混沌。在生物学和 PCO (Pulse-Coupled Oscillators) 模型中，振荡器在激发后必须有一段“不应期”（Refractory Period），在此期间它对外部信号**充耳不闻**。这是打破对称性、形成同步的关键。

2.  **仿真噪音过大 (Simulation Noise)**:
    *   **现象**: 50 个 Agent 在单线程的 Python `asyncio` 循环中运行。
    *   **问题**: 当一个 Agent 闪烁，系统需要唤醒其他 49 个 Agent。在 Python 中这需要时间（比如 10-20ms）。这段处理延迟对于后续的 Agent 来说，就是**随机相位漂移**。
    *   **后果**: 当 `噪音 (CPU延迟) > 耦合强度 (Nudge)` 时，同步永远无法达成。我们试图用 50 个节点的规模来测试，但这超出了当前单进程模拟的实时精度极限。

---

我将执行一个修复计划：**引入生理学机制（不应期）并降低实验规模以减少噪音**。

# [WIP] fix: 引入不应期机制并优化萤火虫实验参数

## 摘要

### 用户需求
修复萤火虫实验无法同步的问题 (`R` 值停滞在 0.17)。

### 评论
当前的 PCO (Pulse-Coupled Oscillator) 实现过于理想化，忽略了物理和生物系统中必须的“不应期”。同时，50 个 Agent 的规模在单进程模拟中引入了过大的调度延迟噪音，干扰了同步过程。

### 目标
1.  **修改 Agent 逻辑**: 在 `kuramoto.py` 中引入 `refractory_period`（不应期）。在周期开始的前段（例如前 2 秒），Agent 仅单纯流逝时间，不监听网络。
2.  **调整实验参数**: 将 Agent 数量减少到 10 个，以降低 CPU 调度延迟带来的相位噪音。
3.  **验证**: 重新运行实验，观察 `R` 值是否上升。

### 基本原理
*   **不应期**: 防止“回响效应”。刚闪烁过的 Agent 不应立即被其他人的闪烁干扰。
*   **降噪**: 在 `cs.run` 的开销尚未优化到极致前，减少并发数量是提高模拟时间精度的唯一方法。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #concept/emergence #task/domain/testing #task/object/firefly-experiment #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修改 Agent 逻辑，引入不应期

我们将重写 `firefly_agent`。新的生命周期分为两个阶段：
1.  **不应期 (Blind Wait)**: 持续时间 `refractory_period`。调用 `cs.wait`。此期间不订阅 MQTT。
2.  **敏感期 (Listening Phase)**: 持续时间 `period - refractory_period - phase`。调用 `safe_recv`。

~~~~~act
write_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 9: Added Refractory Period to prevent 'echo' effects.
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
    refractory_period: float = 2.0,  # Blind period after flash
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
        refractory_period: float,
    ):
        # --- Logic Branching ---
        
        # 1. Refractory Check: If we are in the "blind" zone, just wait.
        if phase < refractory_period:
            # We are blind. Wait until we exit refractory period.
            blind_wait_duration = refractory_period - phase
            
            # Use cs.wait for pure time passage (no listening)
            wait_action = cs.wait(blind_wait_duration)
            
            @cs.task
            def after_refractory(_):
                # We have advanced time by 'blind_wait_duration'.
                # Our phase is now exactly 'refractory_period'.
                return firefly_cycle(
                    agent_id, refractory_period, period, nudge, flash_topic, listen_topic, connector, refractory_period
                )
            
            return after_refractory(wait_action)

        # 2. Sensitive Check: We are past refractory. Listen for neighbors.
        else:
            time_to_flash = period - phase
            # Ensure we don't have negative timeout due to floating point drift
            wait_timeout = max(0.01, time_to_flash)

            perception = safe_recv(listen_topic, timeout=wait_timeout, connector=connector)

            @cs.task
            def process_perception(p: Dict[str, Any]) -> cs.LazyResult:
                is_timeout = p.get("timeout", False)
                elapsed_time = p.get("elapsed", 0.0)
                
                # Update actual phase based on real time passed
                current_actual_phase = phase + elapsed_time

                # Determine Action
                if is_timeout:
                    # We reached the end of the period. FLASH!
                    flash_payload = {"agent_id": agent_id, "phase": current_actual_phase}
                    
                    # We send the signal *then* recurse with phase 0
                    flash = send_signal(
                        topic=flash_topic, 
                        payload=flash_payload,
                        should_send=True,
                        connector=connector
                    )
                    
                    @cs.task
                    def loop_reset(_, _flash):
                        jitter = random.uniform(0.0, 0.1)
                        return firefly_cycle(
                            agent_id, 0.0 + jitter, period, nudge, flash_topic, listen_topic, connector, refractory_period
                        )
                    
                    return loop_reset(p, flash)
                
                else:
                    # We heard a neighbor! NUDGE!
                    # Advance phase, but cap at period (so we don't flash immediately, 
                    # we just get closer).
                    # NOTE: In some models, if nudge pushes > period, we flash immediately.
                    # Here we keep it simple: just advance.
                    next_phase = current_actual_phase + nudge
                    
                    # If the nudge pushes us past the period, we wrap around or clamp.
                    # Standard PCO: Jump to 1 (fire). But here let's just jump forward.
                    # If next_phase > period, the next cycle loop will see time_to_flash < 0 and fire immediately.
                    
                    return firefly_cycle(
                        agent_id, next_phase, period, nudge, flash_topic, listen_topic, connector, refractory_period
                    )

            return process_perception(perception)

    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic, connector, refractory_period
    )
~~~~~

#### Acts 2: 调整实验脚本参数

我们将实验规模从 50 降至 10，并将 Nudge 从 0.5 增加到 1.0 (10% coupling)，以对抗系统噪音。同时更新对 `firefly_agent` 的调用以包含新参数。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
async def run_experiment(
    num_agents: int = 50,
    period: float = 10.0,
    nudge: float = 0.5,
    duration_seconds: float = 60.0,
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    print(f"🔥 Starting firefly experiment with {num_agents} agents for {duration_seconds}s...")

    # 1. Initialize the Shared Bus
~~~~~
~~~~~python
async def run_experiment(
    num_agents: int = 10,  # Reduced from 50 to minimize simulation noise
    period: float = 2.0,   # Faster cycle for quicker feedback
    nudge: float = 0.2,    # 10% coupling strength
    duration_seconds: float = 30.0,
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    print(f"🔥 Starting firefly experiment with {num_agents} agents for {duration_seconds}s...")

    # 1. Initialize the Shared Bus
~~~~~

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
            connector=connector,
        )
        
        agent_tasks.append(engine.run(agent_workflow))
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
            refractory_period=period * 0.2, # 20% of cycle is blind
        )
        
        agent_tasks.append(engine.run(agent_workflow))
~~~~~

### 下一步建议
如果这次实验 `R` 值能突破 0.5，我们就证明了“不应期”和“噪音控制”是关键。届时我们可以尝试增加 Agent 数量，或者尝试使用 `RedisStateBackend` 进行跨进程（更真实的）测试。
