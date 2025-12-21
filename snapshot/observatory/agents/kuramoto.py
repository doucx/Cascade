"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 11: Switched to shared state vector for telemetry.
"""

import asyncio
import random
import time
from typing import Any, Dict, List

import numpy as np
import cascade as cs
from cascade.interfaces.protocols import Connector
from observatory.networking.direct_channel import DirectChannel


# --- Atomic Primitives for Agent Behavior ---


@cs.task
async def fanout_direct(
    neighbors: List[DirectChannel],
    payload: Dict[str, Any],
    should_send: bool,
) -> None:
    """
    Fan-out using DirectChannel. The slow path telemetry is now removed.
    """
    if not should_send:
        return

    for i, neighbor in enumerate(neighbors):
        await neighbor.send(payload)
        if i % 10 == 0:
            await asyncio.sleep(0)


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
    state_vector: np.ndarray,
    refractory_period: float = 2.0,
):
    """
    The main entry point for a single firefly agent.
    Now uses a shared state vector for telemetry.
    """

    # Initial write
    state_vector[agent_id] = initial_phase / period

    def firefly_cycle(
        agent_id: int,
        phase: float,
        period: float,
        nudge: float,
        neighbors: List[DirectChannel],
        my_channel: DirectChannel,
        state_vector: np.ndarray,
        refractory_period: float,
    ):
        # --- Logic Branching ---

        # 1. Refractory Check
        if phase < refractory_period:
            blind_wait_duration = refractory_period - phase
            wait_action = cs.wait(blind_wait_duration)

            @cs.task
            def after_refractory(_):
                new_phase = refractory_period
                state_vector[agent_id] = new_phase / period
                return firefly_cycle(
                    agent_id, new_phase, period, nudge, neighbors, my_channel, state_vector, refractory_period
                )
            return after_refractory(wait_action)

        # 2. Sensitive Check
        else:
            time_to_flash = period - phase
            wait_timeout = max(0.01, time_to_flash)
            perception = safe_recv_channel(my_channel, timeout=wait_timeout)

            @cs.task
            def process_perception(p: Dict[str, Any]) -> cs.LazyResult:
                elapsed_time = p.get("elapsed", 0.0)
                current_actual_phase = phase + elapsed_time

                if p.get("timeout", False):
                    # FLASH!
                    flash_payload = {"agent_id": agent_id, "phase": current_actual_phase}
                    flash = fanout_direct(neighbors=neighbors, payload=flash_payload, should_send=True)

                    @cs.task
                    def loop_reset(_, _flash):
                        jitter = random.uniform(0.0, 0.1)
                        new_phase = 0.0 + jitter
                        state_vector[agent_id] = 1.0  # Visual flash
                        return firefly_cycle(
                            agent_id, new_phase, period, nudge, neighbors, my_channel, state_vector, refractory_period
                        )
                    return loop_reset(p, flash)
                else:
                    # NUDGE!
                    next_phase = current_actual_phase + nudge
                    state_vector[agent_id] = next_phase / period
                    return firefly_cycle(
                        agent_id, next_phase, period, nudge, neighbors, my_channel, state_vector, refractory_period
                    )
            return process_perception(perception)

    return firefly_cycle(
        agent_id, initial_phase, period, nudge, neighbors, my_channel, state_vector, refractory_period
    )