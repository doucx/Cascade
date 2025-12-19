"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 4: Internalized the conditional logic into send_signal.
This prevents the 'skip propagation' issue where skipping the flash action
caused the recursive step to be skipped as well, killing the agent.
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
    should_send: bool,
    connector: Connector = cs.inject("_internal_connector"),
) -> None:
    """
    A task to publish a message to the shared bus.
    Now accepts 'should_send' to handle conditional logic internally,
    ensuring the task always executes and doesn't break downstream dependencies.
    """
    if should_send and connector:
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
        return {"signal": None, "timeout": True}

    future = asyncio.Future()

    async def callback(topic: str, payload: Any):
        if not future.done():
            future.set_result(payload)

    subscription = await connector.subscribe(topic, callback)
    try:
        signal = await asyncio.wait_for(future, timeout=timeout)
        return {"signal": signal, "timeout": False}
    except asyncio.TimeoutError:
        return {"signal": None, "timeout": True}
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
        wait_timeout = max(0.01, time_to_flash)

        # 1. PERCEIVE
        perception = safe_recv(listen_topic, timeout=wait_timeout)

        # 2. DECIDE
        @cs.task
        def was_timeout(p: Dict[str, Any]) -> bool:
            return p.get("timeout", False)

        is_timeout = was_timeout(perception)

        # 3. ACT
        # We pass 'is_timeout' as a data dependency. 
        # The task will always run, but only emit side effects if True.
        flash_action = send_signal(
            topic=flash_topic, 
            payload={"agent_id": agent_id, "phase": phase},
            should_send=is_timeout
        )

        # 4. EVOLVE & RECURSE
        # We explicitly depend on flash_action to ensure ordering (Act before Recurse)
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

            return firefly_cycle(
                agent_id, next_phase, period, nudge, flash_topic, listen_topic
            )

        return process_and_recurse(perception)

    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic
    )