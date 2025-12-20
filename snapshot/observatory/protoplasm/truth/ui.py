import numpy as np
from typing import Dict

def create_display_grid(actual: np.ndarray, theoretical: np.ndarray) -> np.ndarray:
    """
    Compares actual and theoretical grids and encodes them into a float matrix
    for the UniGridRenderer's 'truth' palette.

    State Encoding:
    - 0.0: Match Dead (default)
    - 1.0: Match Alive
    - 2.0: False Positive (Red)
    - 3.0: False Negative (Cyan)
    """
    display_grid = np.zeros(actual.shape, dtype=np.float32)
    
    # Correctly handle all 4 cases without overlap
    match_alive = (actual == 1) & (theoretical == 1)
    false_pos = (actual == 1) & (theoretical == 0)
    false_neg = (actual == 0) & (theoretical == 1)
    
    display_grid[match_alive] = 1.0
    display_grid[false_pos] = 2.0
    display_grid[false_neg] = 3.0
    
    return display_grid

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