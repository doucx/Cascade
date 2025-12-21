"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 11: Refactored internal loop to be imperative (async while)
             to eliminate graph-building overhead on each cycle.
"""

import asyncio
import random
import time
from typing import Any, Dict, List

import cascade as cs
from cascade.interfaces.protocols import Connector
from observatory.networking.direct_channel import DirectChannel


# --- Helper Functions (No longer @cs.task) ---


async def fanout_direct(
    neighbors: List[DirectChannel],
    payload: Dict[str, Any],
    connector: Connector,
):
    """
    Fan-out using DirectChannel (Fast Path) + Connector (Slow Path).
    """
    # 1. Fast Path: Zero-copy delivery to neighbors
    for i, neighbor in enumerate(neighbors):
        await neighbor.send(payload)
        # Yield to allow other tasks to run in a large fan-out scenario
        if i > 0 and i % 10 == 0:
            await asyncio.sleep(0)

    # 2. Slow Path: Telemetry for Visualization
    if connector:
        await connector.publish("firefly/flash", payload)


async def safe_recv_channel(
    channel: DirectChannel,
    timeout: float,
) -> Dict[str, Any]:
    """
    Waits for a message on a DirectChannel with a timeout.
    """
    start_time = time.time()
    try:
        signal = await asyncio.wait_for(channel.recv(), timeout=timeout)
        elapsed = time.time() - start_time
        return {"signal": signal, "timeout": False, "elapsed": elapsed}
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        return {"signal": None, "timeout": True, "elapsed": elapsed}


# --- Core Agent (now a long-running @cs.task with an internal loop) ---


@cs.task
async def firefly_agent(
    agent_id: int,
    initial_phase: float,
    period: float,
    nudge: float,
    neighbors: List[DirectChannel],
    my_channel: DirectChannel,
    connector: Connector,
    refractory_period: float = 2.0,
):
    """
    This is the main entry point for a single firefly agent.
    It's a long-running task that contains the agent's entire lifecycle.
    """
    phase = initial_phase

    while True:
        # --- Logic Branching ---

        # 1. Refractory Period: We are "blind" and just wait.
        if phase < refractory_period:
            blind_wait_duration = refractory_period - phase
            await asyncio.sleep(blind_wait_duration)
            phase = refractory_period
            continue  # Re-evaluate state in the next loop iteration

        # 2. Sensitive Period: Listen for neighbors until it's time to flash.
        time_to_flash = period - phase
        wait_timeout = max(0.01, time_to_flash)

        perception = await safe_recv_channel(my_channel, timeout=wait_timeout)

        is_timeout = perception.get("timeout", False)
        elapsed_time = perception.get("elapsed", 0.0)
        phase += elapsed_time

        # --- State Update ---
        if is_timeout:
            # FLASH: We reached the end of our cycle.
            flash_payload = {"agent_id": agent_id, "phase": phase}
            await fanout_direct(neighbors, flash_payload, connector)

            # RESET: Start a new cycle with a bit of jitter.
            phase = random.uniform(0.0, 0.1)

        else:
            # NUDGE: A neighbor flashed, so we adjust our phase.
            phase += nudge