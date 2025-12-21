"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 14: Restored to Elegant Recursion.
With the Engine's new structural hashing TCO, we can revert to the most
natural declarative form. The agent's logic is expressed as a simple
recursive function, and the Engine handles the performance optimization.
"""

import asyncio
import random
import time
from typing import Any, Dict, List

import cascade as cs
from cascade.interfaces.protocols import Connector
from observatory.networking.direct_channel import DirectChannel

# --- Atomic Primitives ---

@cs.task
async def fanout_direct(
    neighbors: List[DirectChannel],
    payload: Dict[str, Any],
    should_send: bool,
    connector: Connector,
) -> None:
    if not should_send:
        return

    # Non-blocking telemetry
    if connector:
        asyncio.create_task(connector.publish("firefly/flash", payload))
        
    for neighbor in neighbors:
        await neighbor.send(payload)

@cs.task
async def safe_recv_channel(
    channel: DirectChannel,
    timeout: float,
) -> Dict[str, Any]:
    start_time = time.time()
    try:
        signal = await asyncio.wait_for(channel.recv(), timeout=timeout)
        elapsed = time.time() - start_time
        return {"signal": signal, "timeout": False, "elapsed": elapsed}
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        return {"signal": None, "timeout": True, "elapsed": elapsed}

# --- Core Agent Logic ---

def firefly_agent(
    agent_id: int,
    initial_phase: float,
    period: float,
    nudge: float,
    neighbors: List[DirectChannel],
    my_channel: DirectChannel,
    connector: Connector,
    refractory_period: float = 2.0,
):
    """The main recursive entry point for a single firefly agent."""

    # 1. Refractory Path
    if initial_phase < refractory_period:
        wait_duration = refractory_period - initial_phase
        wait_action = cs.wait(wait_duration)

        @cs.task
        def after_refractory(_):
            return firefly_agent(
                agent_id, refractory_period, period, nudge, neighbors,
                my_channel, connector, refractory_period
            )
        return after_refractory(wait_action)

    # 2. Sensitive Path
    else:
        time_to_flash = period - initial_phase
        wait_timeout = max(0.01, time_to_flash)
        perception = safe_recv_channel(my_channel, timeout=wait_timeout)

        @cs.task
        def process_perception(p: Dict[str, Any]):
            is_timeout = p.get("timeout", False)
            elapsed_time = p.get("elapsed", 0.0)

            if is_timeout:
                # Flash
                flash_payload = {"agent_id": agent_id, "phase": period}
                flash = fanout_direct(neighbors, flash_payload, True, connector)

                @cs.task
                def reset_and_recurse(_flash_done):
                    jitter = random.uniform(0.0, 0.1)
                    return firefly_agent(
                        agent_id, jitter, period, nudge, neighbors,
                        my_channel, connector, refractory_period
                    )
                return reset_and_recurse(flash)
            else:
                # Nudge
                next_phase = initial_phase + elapsed_time + nudge
                return firefly_agent(
                    agent_id, next_phase, period, nudge, neighbors,
                    my_channel, connector, refractory_period
                )

        return process_perception(perception)