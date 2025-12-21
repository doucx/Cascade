"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 15: Final Architecture - The Imperative Core Pattern.
This version represents the idiomatic way to implement a high-performance,
long-running agent in Cascade. The entire agent lifecycle is a single
@cs.task containing a native `asyncio` `while True` loop. This leverages
Cascade for orchestration (starting the agent) and native asyncio for the
zero-overhead, high-frequency internal loop.
"""

import asyncio
import random
import time
from typing import Any, Dict, List

import cascade as cs
from cascade.interfaces.protocols import Connector
from observatory.networking.direct_channel import DirectChannel


@cs.task(name="firefly_lifecycle")
async def firefly_lifecycle(
    agent_id: int,
    initial_phase: float,
    period: float,
    nudge: float,
    neighbors: List[DirectChannel],
    my_channel: DirectChannel,
    connector: Connector,
    refractory_period: float,
):
    """A single, long-running task representing the entire lifecycle of a firefly."""
    phase = initial_phase

    while True:
        # 1. Refractory Path
        if phase < refractory_period:
            wait_duration = refractory_period - phase
            await asyncio.sleep(wait_duration)
            phase = refractory_period
            # Loop continues to the sensitive path check

        # 2. Sensitive Path
        time_to_flash = period - phase
        wait_timeout = max(0.01, time_to_flash)

        try:
            start_time = time.time()
            # Native asyncio listening on the channel
            await asyncio.wait_for(my_channel.recv(), timeout=wait_timeout)
            elapsed = time.time() - start_time

            # Nudged
            phase += elapsed + nudge

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            phase += elapsed # Phase should be at or very near 'period'
            
            # Flash
            flash_payload = {"agent_id": agent_id, "phase": phase}
            
            # Non-blocking telemetry
            if connector:
                asyncio.create_task(connector.publish("firefly/flash", flash_payload))
            
            # Fan-out to neighbors
            for neighbor in neighbors:
                await neighbor.send(flash_payload)
            
            # Reset
            phase = 0.0 + random.uniform(0.0, 0.1)


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
    # This now simply returns a call to our single, long-running task.
    return firefly_lifecycle(
        agent_id, initial_phase, period, nudge, neighbors,
        my_channel, connector, refractory_period
    )