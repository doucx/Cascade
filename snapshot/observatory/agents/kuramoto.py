"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 10: Refactored to use DirectChannel for O(1) communication.
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
    connector: Connector,  # For visualization/telemetry side-channel
) -> None:
    """
    Fan-out using DirectChannel (Fast Path) + Connector (Slow Path).
    """
    if not should_send:
        return

    # 1. Fast Path: Zero-copy delivery to neighbors
    # We yield to the event loop occasionally to prevent starvation if fan-out is huge
    for i, neighbor in enumerate(neighbors):
        await neighbor.send(payload)
        if i % 10 == 0:
            await asyncio.sleep(0)

    # 2. Slow Path: Telemetry for Visualization
    if connector:
        # We publish to a known topic for the visualizer
        await connector.publish("firefly/flash", payload)


@cs.task
async def safe_recv_channel(
    channel: DirectChannel,
    timeout: float,
) -> Dict[str, Any]:
    """
    Waits for a message on a DirectChannel with a timeout.
    """
    start_time = time.time()
    try:
        # DirectChannel.recv() returns the payload directly
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
    """
    The main entry point for a single firefly agent.
    Now uses DirectChannel topology.
    """

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
                    agent_id,
                    refractory_period,
                    period,
                    nudge,
                    neighbors,
                    my_channel,
                    connector,
                    refractory_period,
                )

            return after_refractory(wait_action)

        # 2. Sensitive Check: We are past refractory. Listen for neighbors.
        else:
            time_to_flash = period - phase
            # Ensure we don't have negative timeout due to floating point drift
            wait_timeout = max(0.01, time_to_flash)

            # Listen to MY channel
            perception = safe_recv_channel(my_channel, timeout=wait_timeout)

            @cs.task
            def process_perception(p: Dict[str, Any]) -> cs.LazyResult:
                is_timeout = p.get("timeout", False)
                elapsed_time = p.get("elapsed", 0.0)

                # Update actual phase based on real time passed
                current_actual_phase = phase + elapsed_time

                # Determine Action
                if is_timeout:
                    # We reached the end of the period. FLASH!
                    flash_payload = {
                        "agent_id": agent_id,
                        "phase": current_actual_phase,
                    }

                    flash = fanout_direct(
                        neighbors=neighbors,
                        payload=flash_payload,
                        should_send=True,
                        connector=connector,
                    )

                    @cs.task
                    def loop_reset(_, _flash):
                        jitter = random.uniform(0.0, 0.1)
                        return firefly_cycle(
                            agent_id,
                            0.0 + jitter,
                            period,
                            nudge,
                            neighbors,
                            my_channel,
                            connector,
                            refractory_period,
                        )

                    return loop_reset(p, flash)

                else:
                    # We heard a neighbor! NUDGE!
                    next_phase = current_actual_phase + nudge
                    return firefly_cycle(
                        agent_id,
                        next_phase,
                        period,
                        nudge,
                        neighbors,
                        my_channel,
                        connector,
                        refractory_period,
                    )

            return process_perception(perception)

    return firefly_cycle(
        agent_id,
        initial_phase,
        period,
        nudge,
        neighbors,
        my_channel,
        connector,
        refractory_period,
    )