"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.
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
    Wraps a cs.recv call to transform asyncio.TimeoutError into a structured output,
    making it a predictable control flow mechanism instead of an exception.
    """
    try:
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

    @cs.task
    def process_cycle_result(
        agent_id: int,
        cycle_result: Dict[str, Any],
        period: float,
        nudge: float,
        flash_topic: str,
        listen_topic: str,
    ):
        """
        Takes the result of one cycle, calculates the new state,
        and recursively calls the next cycle.
        """
        current_phase = cycle_result["phase"]
        # Add a small random jitter to avoid perfect, static synchronization
        jitter = random.uniform(-0.01, 0.01)

        # Main logic:
        # If the cycle timed out, it means we flashed. Reset phase.
        if cycle_result["timeout"]:
            next_phase = 0.0 + jitter
        else:
            # We received a signal. Nudge the phase forward.
            # We also account for the time we spent waiting.
            time_waited = cycle_result["time_waited"]
            next_phase = (current_phase + time_waited + nudge + jitter) % period
        
        # This is the recursive call
        return firefly_cycle(
            agent_id, next_phase, period, nudge, flash_topic, listen_topic
        )

    def firefly_cycle(
        agent_id: int,
        phase: float,
        period: float,
        nudge: float,
        flash_topic: str,
        listen_topic: str,
    ):
        """A single life cycle of a firefly."""
        time_to_flash = period - phase
        
        # We must ensure timeout is positive
        wait_timeout = max(0.01, time_to_flash)

        # Wait for a signal OR until it's time to flash
        recv_task = cs.recv(listen_topic, timeout=wait_timeout)
        handled_recv = recv_with_timeout_handler(recv_task)
        
        # Decide what to do based on whether we timed out or received a signal
        @cs.task
        def decide_and_act(handled_recv_result: Dict[str, Any]) -> Dict[str, Any]:
            if handled_recv_result["timeout"]:
                # Our turn to flash!
                send_signal(
                    topic=flash_topic,
                    payload={"agent_id": agent_id, "phase": phase},
                )
                return {"phase": phase, "timeout": True, "time_waited": wait_timeout}
            else:
                # We saw another flash
                return {"phase": phase, "timeout": False, "time_waited": wait_timeout}

        decision = decide_and_act(handled_recv)
        
        # This is TCO: the result of this subflow is another subflow
        return process_cycle_result(
            agent_id, decision, period, nudge, flash_topic, listen_topic
        )

    # Start the first cycle
    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic
    )