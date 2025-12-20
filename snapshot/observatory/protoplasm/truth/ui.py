import numpy as np
from typing import Dict

def create_display_grid(actual: np.ndarray, theoretical: np.ndarray) -> np.ndarray:
    """
    Compares actual and theoretical grids and encodes them into a float matrix
    for the UniGridRenderer's 'truth' palette using a robust arithmetic method.

    State Encoding:
    - 0.0: Match Dead (default)
    - 1.0: Match Alive
    - 2.0: False Positive (Red)
    - 3.0: False Negative (Cyan)
    """
    # 1. Arithmetic State Encoding:
    # We treat the (theoretical, actual) pair as a 2-bit number to get a unique index.
    # - (0, 0) -> 0 + 2*0 = 0  (Match Dead)
    # - (1, 0) -> 1 + 2*0 = 1  (False Negative)
    # - (0, 1) -> 0 + 2*1 = 2  (False Positive)
    # - (1, 1) -> 1 + 2*1 = 3  (Match Alive)
    state_indices = theoretical.astype(np.int8) + actual.astype(np.int8) * 2

    # 2. Lookup Table (LUT):
    # Maps the integer state index to the desired float value for rendering.
    # Index 0 -> Match Dead   -> 0.0
    # Index 1 -> False Negative -> 3.0
    # Index 2 -> False Positive -> 2.0
    # Index 3 -> Match Alive   -> 1.0
    lookup_table = np.array([0.0, 3.0, 2.0, 1.0], dtype=np.float32)

    # 3. Vectorized Lookup:
    # Use the indices to pull values from the LUT to form the final grid.
    return lookup_table[state_indices]

def format_status_line(
    gen: int, 
    current_buffer_size: int, 
    total_agents: int, 
    errors: Dict[str, int]
) -> str:
    """Formats the detailed status line for the validator UI."""
    # Progress Bar
    progress = current_buffer_size / total_agents if total_agents > 0 else 0
    bar_len = 10
    filled = int(bar_len * progress)
    bar = "█" * filled + "░" * (bar_len - filled)
    
    # Error Status
    total_err = errors.get('abs', 0) + errors.get('rel', 0)
    status_icon = "✅" if total_err == 0 else "❌"
    
    return (
        f"Gen {gen}: [{bar}] {current_buffer_size}/{total_agents} | "
        f"{status_icon} Err: {total_err} "
        f"(Abs:{errors.get('abs', 0)} Rel:{errors.get('rel', 0)})"
    )