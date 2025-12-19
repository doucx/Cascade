"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 7: Deep debug logging enabled.
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
    # DEBUG: Inspect the connector object deeply
    conn_status = "VALID" if connector else "NONE"
    conn_id = id(connector) if connector else "N/A"
    
    print(f"[Agent] send_signal EXEC. should_send={should_send}, connector={conn_status}({conn_id})")
    
    if should_send and connector:
        print(f"[Agent] ⚡ ATTEMPTING PUBLISH to {topic}...")
        await connector.publish(topic, payload)
        print(f"[Agent] ⚡ PUBLISH CALL DONE.")


@cs.task
async def safe_recv(
    topic: str,
    timeout: float,
    connector: Connector,
) -> Dict[str, Any]:
    """A custom receive task that treats timeouts as valid return values."""
    if not connector:
        return {"signal": None, "timeout": True}

    print(f"[Agent] safe_recv START wait={timeout:.4f}s")
    
    future = asyncio.Future()
    async def callback(topic: str, payload: Any):
        if not future.done():
            future.set_result(payload)

    subscription = await connector.subscribe(topic, callback)
    try:
        signal = await asyncio.wait_for(future, timeout=timeout)
        print(f"[Agent] safe_recv GOT SIGNAL")
        return {"signal": signal, "timeout": False}
    except asyncio.TimeoutError:
        print(f"[Agent] safe_recv TIMEOUT")
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
            # DEBUG
            val = p.get("timeout", False)
            print(f"[Agent] was_timeout check: input={p} -> {val}")
            return val
            
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
            if p["timeout"]:
                next_phase = 0.0 + jitter
            else:
                next_phase = (phase + nudge + jitter) % period

            return firefly_cycle(
                agent_id, next_phase, period, nudge, flash_topic, listen_topic, connector
            )

        return process_and_recurse(perception)

    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic, connector
    )