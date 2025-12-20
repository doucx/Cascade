import asyncio
from typing import List, Dict, Tuple, Any, Optional
import cascade as cs
from cascade.interfaces.protocols import Connector

# --- Atomic Tasks (Updated to support explicit dependency chains) ---

@cs.task
async def broadcast_state(
    topic_base: str,
    agent_id: int,
    generation: int,
    state: int,
    connector: Connector,
    rendezvous: Any = None # Dummy argument to force ordering
) -> None:
    """Publishes current state. Waits for rendezvous if provided."""
    payload = {"agent_id": agent_id, "gen": generation, "state": state}
    # Use retain=True to handle subscription gaps (neighbors starting late)
    await connector.publish(f"{topic_base}/{agent_id}/state", payload, retain=True)

@cs.task
async def report_to_validator(
    topic: str,
    agent_id: int,
    x: int, y: int,
    generation: int,
    state: int,
    connector: Connector,
    rendezvous: Any = None # Dummy argument to force ordering
) -> None:
    """Sends a report to the central validator."""
    payload = {"id": agent_id, "coords": [x, y], "gen": generation, "state": state}
    await connector.publish(topic, payload)

@cs.task
async def collect_neighbors(
    current_gen: int,
    current_mb: Dict[int, Dict[int, int]],
    my_neighbor_ids: List[int],
    conn: Connector,
    rendezvous: Any = None # Dummy argument to force ordering
) -> Tuple[Dict[int, int], Dict[int, Dict[int, int]]]:
    """
    Waits for all neighbors' state for the specified generation.
    Returns (neighbors_data, next_mailbox).
    """
    def is_ready(mb):
        return current_gen in mb and len(mb[current_gen]) >= len(my_neighbor_ids)

    # 1. Check if we already have it in the mailbox (from past pushes)
    if is_ready(current_mb):
        data = current_mb[current_gen]
        new_mb = {g: m for g, m in current_mb.items() if g > current_gen}
        return data, new_mb

    # 2. Subscribe and wait for incoming pushes
    future = asyncio.Future()
    
    async def callback(topic: str, payload: Any):
        sender = payload.get('agent_id')
        p_gen = payload.get('gen')
        if sender is None or p_gen is None: return

        if sender in my_neighbor_ids:
            if p_gen not in current_mb:
                current_mb[p_gen] = {}
            current_mb[p_gen][sender] = payload['state']
            
            if is_ready(current_mb) and not future.done():
                future.set_result(None)

    sub = await conn.subscribe(f"cell/+/state", callback)
    try:
        await asyncio.wait_for(future, timeout=10.0) # Generous timeout for high-concurrency stress
    except asyncio.TimeoutError:
        raise RuntimeError(f"Agent timed out waiting for gen {current_gen}. Mailbox state: {current_mb.get(current_gen)}")
    finally:
        await sub.unsubscribe()

    data = current_mb[current_gen]
    new_mb = {g: m for g, m in current_mb.items() if g > current_gen}
    return data, new_mb

# --- Core Agent Logic ---

def conway_agent(
    agent_id: int,
    x: int, y: int,
    initial_state: int,
    neighbor_ids: List[int],
    topic_base: str,
    validator_topic: str,
    connector: Connector,
    max_generations: int = 100
):
    def lifecycle(gen: int, current_state: int, mailbox: Dict[int, Dict[int, int]]):
        if gen >= max_generations:
            return current_state

        # 1. Synchronization Barrier: 
        # Prevents agents from publishing before neighbors are ready to listen.
        rendezvous = cs.wait(0.05)

        # 2. Trigger Side-Effects (Broadcast & Report)
        # These are guarded by the barrier.
        b_act = broadcast_state(topic_base, agent_id, gen, current_state, connector, rendezvous=rendezvous)
        r_act = report_to_validator(validator_topic, agent_id, x, y, gen, current_state, connector, rendezvous=rendezvous)

        # 3. Wait for Data
        # This task also respects the barrier.
        collected_data = collect_neighbors(gen, mailbox, neighbor_ids, connector, rendezvous=rendezvous)

        # 4. Process and Recurse (Runtime Handling)
        # This wrapper task ensures unpacking and logic happen ONLY when data is ready.
        @cs.task(name=f"agent_{agent_id}_step_{gen}")
        def process_and_compute(data_tuple, _b_done, _r_done):
            neighbors_data, next_mailbox = data_tuple
            
            # --- Local Rule Application ---
            alive_neighbors = sum(neighbors_data.values())
            if current_state == 1:
                next_state = 1 if alive_neighbors in (2, 3) else 0
            else:
                next_state = 1 if alive_neighbors == 3 else 0

            # --- Tail Recursion ---
            return lifecycle(gen + 1, next_state, next_mailbox)

        return process_and_compute(collected_data, b_act, r_act)

    return lifecycle(0, initial_state, {})