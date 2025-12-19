"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 2: This version uses a fully declarative approach with .run_if()
to ensure all actions are correctly represented in the computation graph.
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
async def recv_with_timeout_handler(recv_lazy_result: cs.LazyResult) -> Dict[str, Any]:
    """
    Wraps a cs.recv call to transform asyncio.TimeoutError into a structured output.
    """
    try:
        # This await is crucial; it executes the LazyResult passed in.
        signal = await recv_lazy_result
        return {"signal": signal, "timeout": False}
    except asyncio.TimeoutError:
        return {"signal": None, "timeout": True}


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

        # 1. PERCEIVE: Wait for a signal OR until it's time to flash
        recv_task = cs.recv(listen_topic, timeout=wait_timeout)
        handled_recv = recv_with_timeout_handler(recv_task)

        # 2. DECIDE: Was the perception a timeout?
        @cs.task
        def was_timeout(hrr: Dict[str, Any]) -> bool:
            return hrr.get("timeout", False)

        is_timeout = was_timeout(handled_recv)

        # 3. ACT: Flash *only if* it was a timeout.
        flash_action = send_signal(
            topic=flash_topic, payload={"agent_id": agent_id, "phase": phase}
        ).run_if(is_timeout)

        # 4. EVOLVE & RECURSE: Calculate the next state and loop.
        # This task must wait for the flash_action to complete to ensure ordering.
        @cs.task
        def process_and_recurse(
            hrr: Dict[str, Any], _flash_dependency=flash_action
        ) -> cs.LazyResult:
            jitter = random.uniform(-0.01, 0.01)

            if hrr["timeout"]:
                # We flashed, reset phase.
                next_phase = 0.0 + jitter
            else:
                # We saw another flash, nudge phase forward.
                # Note: A more accurate model would use the time waited, but this is simpler
                # and still effective for demonstrating synchronization.
                next_phase = (phase + nudge + jitter) % period

            # The recursive call that powers the agent's lifecycle
            return firefly_cycle(
                agent_id, next_phase, period, nudge, flash_topic, listen_topic
            )

        return process_and_recurse(handled_recv)

    # Start the first cycle
    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic
    )