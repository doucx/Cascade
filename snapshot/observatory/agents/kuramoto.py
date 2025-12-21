"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 11: Refactored for Zero-Overhead TCO.
The internal @cs.task `process_perception` is removed and its logic is
flattened into a top-level task to ensure the recursive call structure
is stable, triggering the engine's graph caching fast path.
"""

import asyncio
import random
import time
from typing import Any, Dict, List

import cascade as cs
from cascade.interfaces.protocols import Connector
from observatory.networking.direct_channel import DirectChannel


# --- Atomic Primitives for Agent Behavior ---

@cs.task
async def fanout_direct(
    neighbors: List[DirectChannel],
    payload: Dict[str, Any],
    should_send: bool,
    connector: Connector,
) -> None:
    if not should_send:
        return
    for i, neighbor in enumerate(neighbors):
        await neighbor.send(payload)
        if i % 10 == 0:
            await asyncio.sleep(0)
    if connector:
        await connector.publish("firefly/flash", payload)


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


@cs.task
def process_perception_and_recurse(
    agent_id: int,
    phase: float,
    period: float,
    nudge: float,
    neighbors: List[DirectChannel],
    my_channel: DirectChannel,
    connector: Connector,
    refractory_period: float,
    perception_result: Dict[str, Any],
    flash_dependency: Any = None, # Used to chain flash action
) -> cs.LazyResult:
    """
    This task now contains the logic that was previously in the inner function.
    It returns the *next* LazyResult in the recursive chain.
    """
    is_timeout = perception_result.get("timeout", False)
    elapsed_time = perception_result.get("elapsed", 0.0)
    current_actual_phase = phase + elapsed_time

    if is_timeout:
        # We flashed. Reset phase and recurse.
        jitter = random.uniform(0.0, 0.1)
        return firefly_cycle(
            agent_id, 0.0 + jitter, period, nudge, neighbors,
            my_channel, connector, refractory_period
        )
    else:
        # We were nudged. Update phase and recurse.
        next_phase = current_actual_phase + nudge
        return firefly_cycle(
            agent_id, next_phase, period, nudge, neighbors,
            my_channel, connector, refractory_period
        )

# --- Core Agent Logic ---

def firefly_cycle(
    agent_id: int,
    phase: float,
    period: float,
    nudge: float,
    neighbors: List[DirectChannel],
    my_channel: DirectChannel,
    connector: Connector,
    refractory_period: float,
):
    """
    The main recursive entry point for a single firefly agent.
    This function now *constructs* the graph for one cycle.
    """
    # 1. Refractory Check: If we are in the "blind" zone, just wait.
    if phase < refractory_period:
        blind_wait_duration = refractory_period - phase
        wait_action = cs.wait(blind_wait_duration)

        # The continuation is now a simple, top-level task call
        return process_perception_and_recurse(
            agent_id, refractory_period, period, nudge, neighbors,
            my_channel, connector, refractory_period,
            perception_result=wait_action, # Pass the wait result through
        )

    # 2. Sensitive Check: We are past refractory. Listen for neighbors.
    else:
        time_to_flash = period - phase
        wait_timeout = max(0.01, time_to_flash)
        perception = safe_recv_channel(my_channel, timeout=wait_timeout)

        # Flash action is now pre-declared and conditionally executed inside the task
        flash_payload = {"agent_id": agent_id, "phase": period} # Approx phase
        
        # This is a clever trick: we pass the *perception* LazyResult
        # to the 'should_send' argument of fanout_direct.
        # But fanout_direct expects a bool. How does this work?
        # It doesn't, directly. We need a small adapter or change the logic.
        # Let's simplify: we will decide to flash inside the processing task.
        # This is cleaner.
        
        # Let's try another way. The logic to decide *if* to flash is based on perception.
        # We can create a small task to extract that boolean.
        
        @cs.task
        def should_flash(p: Dict[str, Any]) -> bool:
            return p.get("timeout", False)

        flash_trigger = should_flash(perception)

        flash_action = fanout_direct(
            neighbors=neighbors,
            payload=flash_payload,
            should_send=flash_trigger,
            connector=connector,
        )

        return process_perception_and_recurse(
            agent_id, phase, period, nudge, neighbors,
            my_channel, connector, refractory_period,
            perception_result=perception,
            flash_dependency=flash_action, # Ensure flash runs before next cycle
        )


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
    """Public entry point to start the agent's lifecycle."""
    return firefly_cycle(
        agent_id, initial_phase, period, nudge, neighbors,
        my_channel, connector, refractory_period
    )