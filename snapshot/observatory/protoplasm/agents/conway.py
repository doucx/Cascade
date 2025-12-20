import asyncio
from typing import List, Dict, Tuple, Any, Set
import cascade as cs
from cascade.interfaces.protocols import Connector

# --- Atomic Tasks ---

@cs.task
async def broadcast_state(
    topic_base: str,
    agent_id: int,
    generation: int,
    state: int,
    connector: Connector,
) -> None:
    """Publishes current state to a topic sharded by agent ID."""
    payload = {
        "agent_id": agent_id,
        "gen": generation,
        "state": state
    }
    # Topic structure: cell/{agent_id}/state
    await connector.publish(f"{topic_base}/{agent_id}/state", payload)

@cs.task
async def report_to_validator(
    topic: str,
    agent_id: int,
    x: int, y: int,
    generation: int,
    state: int,
    connector: Connector
) -> None:
    """Sends a report to the central validator."""
    payload = {
        "id": agent_id,
        "coords": [x, y],
        "gen": generation,
        "state": state
    }
    await connector.publish(topic, payload)

# --- Agent Logic ---

def conway_agent(
    agent_id: int,
    x: int, 
    y: int,
    initial_state: int,
    neighbor_ids: List[int],
    topic_base: str,
    validator_topic: str,
    connector: Connector,
    max_generations: int = 100
):
    """
    A distributed Game of Life cell.
    It synchronizes with neighbors barrier-style.
    """
    
    # We need a stateful mailbox to handle out-of-order messages from neighbors.
    # Since Cascade tasks are stateless, we pass this mailbox state through the recursion.
    # Mailbox structure: { generation: { neighbor_id: state } }
    initial_mailbox = {}

    def lifecycle(
        gen: int,
        current_state: int,
        mailbox: Dict[int, Dict[int, int]]
    ):
        if gen >= max_generations:
            return current_state

        # 1. Broadcast current state to neighbors (and validator)
        # Note: We broadcast state for 'gen'. Neighbors need this to calculate 'gen+1'.
        broadcast = broadcast_state(topic_base, agent_id, gen, current_state, connector)
        report = report_to_validator(validator_topic, agent_id, x, y, gen, current_state, connector)

        # 2. Wait for all neighbors' state for *this* generation 'gen'
        @cs.task
        async def collect_neighbors(
            _b, _r, # Depend on broadcast/report to ensure they happened
            current_gen: int,
            current_mb: Dict[int, Dict[int, int]],
            my_neighbor_ids: List[int],
            conn: Connector
        ) -> Tuple[Dict[int, int], Dict[int, Dict[int, int]]]:
            
            # Helper to check if we have everything for current_gen
            def is_ready(mb):
                if current_gen not in mb: return False
                return len(mb[current_gen]) >= len(my_neighbor_ids)

            # Fast path: maybe we already have everything in the mailbox?
            if is_ready(current_mb):
                return current_mb[current_gen], current_mb

            # Slow path: Listen for messages until ready
            # We subscribe to a wildcard that covers all neighbors? 
            # Or subscribe to specific topics? 
            # Optimization: Subscribe to "cell/+/state" is easiest but noisy.
            # Ideally: "cell/+/state" but filtered by neighbor list logic?
            # For simplicity in prototype: Subscribe wildcard.
            
            future = asyncio.Future()
            
            async def callback(topic: str, payload: Any):
                # payload: {agent_id, gen, state}
                sender = payload['agent_id']
                p_gen = payload['gen']
                p_state = payload['state']
                
                if sender in my_neighbor_ids:
                    if p_gen not in current_mb:
                        current_mb[p_gen] = {}
                    
                    current_mb[p_gen][sender] = p_state
                    
                    if is_ready(current_mb) and not future.done():
                        future.set_result(None)

            sub = await conn.subscribe(f"{topic_base}/+/state", callback)
            
            try:
                # Wait with a timeout to prevent deadlocks
                await asyncio.wait_for(future, timeout=5.0)
            except asyncio.TimeoutError:
                # In simulation, this is fatal. In prod, maybe fallback?
                # For validation, we crash.
                raise RuntimeError(f"Agent {agent_id} timed out waiting for gen {current_gen} from neighbors {my_neighbor_ids}. Mailbox: {current_mb.get(current_gen)}")
            finally:
                await sub.unsubscribe()
                
            # Cleanup: We can remove old generations from mailbox to save memory
            # Keep current_gen + 1 (for future)
            # Remove current_gen (we are about to consume it) and older
            consumed_data = current_mb[current_gen]
            new_mb = {g: m for g, m in current_mb.items() if g > current_gen}
            
            return consumed_data, new_mb

        collected_data = collect_neighbors(
            broadcast, report, gen, mailbox, neighbor_ids, connector
        )

        # 3. Chain the computation and recursion into a subsequent task
        # This task will only execute after 'collect_neighbors' is done,
        # and it will receive the actual tuple result.
        @cs.task
        def process_and_compute(collected_tuple: Tuple[Dict[int, int], Dict[int, Dict[int, int]]]):
            # Unpacking happens here, at EXECUTION time, which is correct.
            neighbors_data, next_mailbox = collected_tuple

            # --- Compute next state based on neighbors ---
            @cs.task
            def compute_next(neighbor_states: Dict[int, int], my_state: int) -> int:
                alive_neighbors = sum(neighbor_states.values())
                
                if my_state == 1:
                    if alive_neighbors in (2, 3):
                        return 1
                    else:
                        return 0
                else:
                    if alive_neighbors == 3:
                        return 1
                    else:
                        return 0
            
            next_state = compute_next(neighbors_data, current_state)
            
            # --- Recurse ---
            @cs.task
            def step_recursion(ns):
                return lifecycle(gen + 1, ns, next_mailbox)
                
            return step_recursion(next_state)

        return process_and_compute(collected_data)

    return lifecycle(0, initial_state, initial_mailbox)