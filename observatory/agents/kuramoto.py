"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, utilizing the Cascade VM and TailCall optimization.

REVISION 15: Migration to VM TailCall.
This version runs as a single, long-lived async task on the Cascade VM.
It uses `TailCall` to perform zero-overhead recursion, bypassing the
graph construction and solving phases for each step.
"""

import asyncio
import random
import time
from typing import List

import cascade as cs
from cascade.spec.protocols import Connector
from cascade.spec.blueprint import TailCall
from observatory.networking.direct_channel import DirectChannel


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
    The main VM-compatible entry point for a single firefly agent.

    Instead of building a graph of LazyResults, this task executes imperative
    async logic and returns a `TailCall` object to trigger the next iteration.
    """

    # 1. Refractory Path
    if initial_phase < refractory_period:
        wait_duration = refractory_period - initial_phase
        # In VM mode, we use direct asyncio sleep instead of cs.wait
        if wait_duration > 0:
            await asyncio.sleep(wait_duration)

        # Recurse to 'sensitive' phase
        return TailCall(
            kwargs={
                "initial_phase": refractory_period,
                # Pass through other invariant arguments
                "agent_id": agent_id,
                "period": period,
                "nudge": nudge,
                "neighbors": neighbors,
                "my_channel": my_channel,
                "connector": connector,
                "refractory_period": refractory_period,
            }
        )

    # 2. Sensitive Path
    else:
        time_to_flash = period - initial_phase
        # Ensure we don't wait for a negative time or 0
        wait_timeout = max(0.001, time_to_flash)

        start_time = time.time()
        try:
            # Wait for neighbor signal or timeout (which means we flash)
            _signal = await asyncio.wait_for(my_channel.recv(), timeout=wait_timeout)

            # Received Signal -> Nudge
            elapsed = time.time() - start_time
            next_phase = initial_phase + elapsed + nudge

            return TailCall(
                kwargs={
                    "initial_phase": next_phase,
                    "agent_id": agent_id,
                    "period": period,
                    "nudge": nudge,
                    "neighbors": neighbors,
                    "my_channel": my_channel,
                    "connector": connector,
                    "refractory_period": refractory_period,
                }
            )

        except asyncio.TimeoutError:
            # Timeout -> Flash
            flash_payload = {"agent_id": agent_id, "phase": period}

            # Telemetry (Fire and Forget)
            if connector:
                asyncio.create_task(connector.publish("firefly/flash", flash_payload))

            # Broadcast to neighbors
            for neighbor in neighbors:
                await neighbor.send(flash_payload)

            # Reset Phase with slight jitter
            jitter = random.uniform(0.0, 0.1)

            return TailCall(
                kwargs={
                    "initial_phase": jitter,
                    "agent_id": agent_id,
                    "period": period,
                    "nudge": nudge,
                    "neighbors": neighbors,
                    "my_channel": my_channel,
                    "connector": connector,
                    "refractory_period": refractory_period,
                }
            )
