import numpy as np
from dataclasses import dataclass

@dataclass
class GridConfig:
    width: int = 100
    height: int = 100
    decay_per_second: float = 4.0 # Brightness fades from 1.0 to 0 in 0.25s

class StateMatrix:
    """
    Manages the 'physics' of the grid:
    - Logical state (is the agent active?)
    - Physical state (brightness/afterglow)
    """

    def __init__(self, config: GridConfig):
        self.cfg = config
        # brightness: Float 0.0 - 1.0 (1.0 = Flash, 0.0 = Dark)
        self.brightness = np.zeros((self.cfg.height, self.cfg.width), dtype=np.float32)
        # active: Boolean (True = Agent exists/alive)
        self.active = np.zeros((self.cfg.height, self.cfg.width), dtype=bool)

    def update(self, x: int, y: int, state: float):
        """
        Updates the state of a single cell.
        state: 1.0 usually indicates a flash trigger.
        """
        if 0 <= x < self.cfg.width and 0 <= y < self.cfg.height:
            self.brightness[y, x] = state
            self.active[y, x] = True

    def decay(self, dt: float):
        """
        Applies time-based decay to the entire matrix.
        Optimized vectorized operation.
        
        Args:
            dt: The time delta in seconds since the last decay.
        """
        decay_amount = self.cfg.decay_per_second * dt
        self.brightness -= decay_amount
        np.clip(self.brightness, 0.0, 1.0, out=self.brightness)

    def get_snapshot(self):
        """Returns a copy of the current brightness matrix."""
        return self.brightness.copy()

    def set_matrix(self, new_matrix: np.ndarray):
        """Directly sets the brightness matrix to a new state."""
        if new_matrix.shape == self.brightness.shape:
            # np.copyto is an efficient way to copy array contents
            np.copyto(self.brightness, new_matrix)