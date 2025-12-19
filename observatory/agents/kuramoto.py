"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 8: Fixed the "Time Stop" physics bug.
Now correctly accounts for elapsed time during the listening phase.
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
    ):
        time_to_flash = period - phase
        wait_timeout = max(0.01, time_to_flash)

        perception = safe_recv(listen_topic, timeout=wait_timeout, connector=connector)

        @cs.task
        def was_timeout(p: Dict[str, Any]) -> bool:
            return p.get("timeout", False)
            
        is_timeout = was_timeout(perception)

        flash_action = send_signal(
            topic=flash_topic, 
            payload={"agent_id": agent_id, "phase": phase},
            should_send=is_timeout,
            connector=connector
        )

        @cs.task
        def process_and_recurse(
            p: Dict[str, Any], _flash_dependency=flash_action
        ) -> cs.LazyResult:
            jitter = random.uniform(-0.01, 0.01)
            
            # CRITICAL FIX: The phase has advanced while we were waiting!
            elapsed_time = p.get("elapsed", 0.0)
            current_actual_phase = phase + elapsed_time

            if p["timeout"]:
                # We flashed (reached the end of period), so reset.
                next_phase = 0.0 + jitter
            else:
                # We heard a flash.
                # Advance our phase by 'nudge' amount.
                # The modulo operator ensures we wrap around if we exceed the period
                # (though usually nudge keeps us within bounds until the next natural flash).
                next_phase = (current_actual_phase + nudge + jitter) % period

            return firefly_cycle(
                agent_id, next_phase, period, nudge, flash_topic, listen_topic, connector
            )

        return process_and_recurse(perception, _flash_dependency=flash_action)

    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic, connector
    )