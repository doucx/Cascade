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
                    agent_id,
                    refractory_period,
                    period,
                    nudge,
                    flash_topic,
                    listen_topic,
                    connector,
                    refractory_period,
                )

            return after_refractory(wait_action)

        # 2. Sensitive Check: We are past refractory. Listen for neighbors.
        else:
            time_to_flash = period - phase
            # Ensure we don't have negative timeout due to floating point drift
            wait_timeout = max(0.01, time_to_flash)

            perception = safe_recv(
                listen_topic, timeout=wait_timeout, connector=connector
            )

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

                    # We send the signal *then* recurse with phase 0
                    flash = send_signal(
                        topic=flash_topic,
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
                            flash_topic,
                            listen_topic,
                            connector,
                            refractory_period,
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
                        agent_id,
                        next_phase,
                        period,
                        nudge,
                        flash_topic,
                        listen_topic,
                        connector,
                        refractory_period,
                    )

            return process_perception(perception)

    return firefly_cycle(
        agent_id,
        initial_phase,
        period,
        nudge,
        flash_topic,
        listen_topic,
        connector,
        refractory_period,
    )
