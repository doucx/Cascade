import numpy as np
from dataclasses import dataclass

@dataclass
class GridConfig:
    width: int = 100
    height: int = 100
    decay_rate: float = 0.1

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

    def decay(self):
        """
        Applies decay to the entire matrix.
        Optimized vectorized operation.
        """
        # Subtract decay_rate, clip at 0.0
        self.brightness -= self.cfg.decay_rate
        np.clip(self.brightness, 0.0, 1.0, out=self.brightness)

    def get_snapshot(self):
        """Returns a copy of the current brightness matrix."""
        return self.brightness.copy()