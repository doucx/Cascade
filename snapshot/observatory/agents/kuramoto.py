"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 3: Replaced cs.recv with a custom safe_recv task.
This ensures timeouts are treated as data, not exceptions, preventing
the engine from aborting the workflow when a firefly needs to flash.
"""
import asyncio
import random
from typing import Any, Dict

import cascade as cs
from cascade.interfaces.protocols import Connector


# --- Atomic Primitives for Agent Behavior ---

@cs.task
async def send_signal(
    topic: str,
    payload: Dict[str, Any],
    connector: Connector = cs.inject("_internal_connector"),
) -> None:
    """A task to publish a message to the shared bus."""
    if connector:
        await connector.publish(topic, payload)


@cs.task
async def safe_recv(
    topic: str,
    timeout: float,
    connector: Connector = cs.inject("_internal_connector"),
) -> Dict[str, Any]:
    """
    A custom receive task that treats timeouts as valid return values.
    Returns: {"signal": payload, "timeout": False} OR {"signal": None, "timeout": True}
    """
    if not connector:
         # Should not happen in a properly configured engine
        return {"signal": None, "timeout": True}

    future = asyncio.Future()

    async def callback(topic: str, payload: Any):
        if not future.done():
            future.set_result(payload)

    subscription = await connector.subscribe(topic, callback)
    try:
        # Wait for the signal
        signal = await asyncio.wait_for(future, timeout=timeout)
        return {"signal": signal, "timeout": False}
    except asyncio.TimeoutError:
        # Crucial: Return data, don't raise exception
        return {"signal": None, "timeout": True}
    finally:
        # Always clean up the subscription to prevent memory leaks
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
):
    """
    This is the main entry point for a single firefly agent.
    It kicks off the recursive cycle.
    """

    def firefly_cycle(
        agent_id: int,
        phase: float,
        period: float,
        nudge: float,
        flash_topic: str,
        listen_topic: str,
    ):
        """A single, declarative life cycle of a firefly."""
        time_to_flash = period - phase
        # Ensure timeout is positive and reasonable
        wait_timeout = max(0.01, time_to_flash)

        # 1. PERCEIVE: Use our custom safe_recv
        perception = safe_recv(listen_topic, timeout=wait_timeout)

        # 2. DECIDE: Was the perception a timeout?
        @cs.task
        def was_timeout(p: Dict[str, Any]) -> bool:
            return p.get("timeout", False)

        is_timeout = was_timeout(perception)

        # 3. ACT: Flash *only if* it was a timeout.
        flash_action = send_signal(
            topic=flash_topic, payload={"agent_id": agent_id, "phase": phase}
        ).run_if(is_timeout)

        # 4. EVOLVE & RECURSE: Calculate the next state and loop.
        @cs.task
        def process_and_recurse(
            p: Dict[str, Any], _flash_dependency=flash_action
        ) -> cs.LazyResult:
            jitter = random.uniform(-0.01, 0.01)

            if p["timeout"]:
                # We flashed, reset phase.
                next_phase = 0.0 + jitter
            else:
                # We saw another flash, nudge phase forward.
                next_phase = (phase + nudge + jitter) % period

            # The recursive call that powers the agent's lifecycle
            return firefly_cycle(
                agent_id, next_phase, period, nudge, flash_topic, listen_topic
            )

        return process_and_recurse(perception)

    # Start the first cycle
    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic
    )