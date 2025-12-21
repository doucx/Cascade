"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 12: True Zero-Overhead TCO Refactor.
This revision fundamentally restructures the agent to be compatible with
the engine's `_is_simple_task` fast path for TCO. The recursive call
now only contains literal values, and all dependent computations are
chained as siblings, not passed as nested LazyResult arguments.
"""

import asyncio
import random
import time
from typing import Any, Dict, List

import cascade as cs
from cascade.interfaces.protocols import Connector
from observatory.networking.direct_channel import DirectChannel


# --- Atomic Primitives ---
# These remain unchanged as they are already optimal.

@cs.task
async def fanout_direct(
    neighbors: List[DirectChannel],
    payload: Dict[str, Any],
    should_send: bool,
    connector: Connector,
) -> None:
    if not should_send:
        return
    if connector:
        # Fork telemetry to not block critical path
        asyncio.create_task(connector.publish("firefly/flash", payload))
        
    for i, neighbor in enumerate(neighbors):
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

# --- TCO-Optimized Core Loop ---

@cs.task(name="firefly_tco_loop")
def _firefly_tco_loop(
    agent_id: int,
    phase: float,
    period: float,
    nudge: float,
    # Note: Complex objects are passed by reference and are stable
    neighbors: List[DirectChannel],
    my_channel: DirectChannel,
    connector: Connector,
    refractory_period: float,
) -> cs.LazyResult:
    """
    This is the core recursive task. It ONLY contains literals.
    Its job is to construct the graph for the *next* step.
    This structure ensures `_is_simple_task` passes.
    """
    
    # 1. Refractory Path
    if phase < refractory_period:
        wait_duration = refractory_period - phase
        wait_action = cs.wait(wait_duration)
        
        # The continuation task simply updates the phase and re-calls this loop.
        @cs.task
        def after_refractory(_wait_result):
            # Return the next TCO-compatible call
            return _firefly_tco_loop(
                agent_id, refractory_period, period, nudge, neighbors,
                my_channel, connector, refractory_period
            )
        return after_refractory(wait_action)

    # 2. Sensitive Path
    else:
        time_to_flash = period - phase
        wait_timeout = max(0.01, time_to_flash)
        perception = safe_recv_channel(my_channel, timeout=wait_timeout)

        # A task to decide the next phase based on perception
        @cs.task
        def decide_next_phase(p_result: Dict[str, Any]):
            is_timeout = p_result.get("timeout", False)
            elapsed_time = p_result.get("elapsed", 0.0)
            
            if is_timeout:
                # Flashed: reset phase with jitter
                return 0.0 + random.uniform(0.0, 0.1)
            else:
                # Nudged: update phase
                return phase + elapsed_time + nudge
        
        next_phase_lazy = decide_next_phase(perception)
        
        # A task to decide if we should flash
        @cs.task
        def should_flash(p_result: Dict[str, Any]) -> bool:
            return p_result.get("timeout", False)

        flash_trigger = should_flash(perception)
        flash_payload = {"agent_id": agent_id, "phase": period}
        flash_action = fanout_direct(
            neighbors, flash_payload, flash_trigger, connector
        )

        # The final aggregator task that chains dependencies and returns the next loop call
        @cs.task
        def continue_loop(next_phase_val: float, _flash_done: Any):
            return _firefly_tco_loop(
                agent_id, next_phase_val, period, nudge, neighbors,
                my_channel, connector, refractory_period
            )
            
        return continue_loop(next_phase_lazy, flash_action)


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
    # The very first call is TCO-compatible
    return _firefly_tco_loop(
        agent_id, initial_phase, period, nudge, neighbors,
        my_channel, connector, refractory_period
    )