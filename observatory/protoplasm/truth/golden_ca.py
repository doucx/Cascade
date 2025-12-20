import numpy as np
from typing import Tuple

class GoldenLife:
    """
    A high-performance, synchronous implementation of Conway's Game of Life
    using NumPy. Serves as the 'Source of Truth' for validation.
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.grid = np.zeros((height, width), dtype=np.int8)

    def seed(self, initial_state: np.ndarray):
        """Sets the initial state of the grid."""
        if initial_state.shape != (self.height, self.width):
            raise ValueError(f"Shape mismatch: expected {(self.height, self.width)}, got {initial_state.shape}")
        self.grid = initial_state.astype(np.int8)

    def step(self) -> np.ndarray:
        """
        Advances the simulation by one generation.
        Returns the new state.
        """
        # Count neighbors using simple array slicing (toroidal/wrap-around boundary)
        # N, S, E, W, NE, NW, SE, SW
        N  = np.roll(self.grid, -1, axis=0)
        S  = np.roll(self.grid,  1, axis=0)
        E  = np.roll(self.grid, -1, axis=1)
        W  = np.roll(self.grid,  1, axis=1)
        NE = np.roll(N, -1, axis=1)
        NW = np.roll(N,  1, axis=1)
        SE = np.roll(S, -1, axis=1)
        SW = np.roll(S,  1, axis=1)

        neighbors = N + S + E + W + NE + NW + SE + SW

        # Apply rules:
        # 1. Any live cell with 2 or 3 live neighbours survives.
        # 2. Any dead cell with 3 live neighbours becomes a live cell.
        # 3. All other live cells die in the next generation.
        
        # Use boolean masks for speed
        alive = self.grid == 1
        keep_alive = (neighbors == 2) | (neighbors == 3)
        resurrect = (neighbors == 3)
        
        next_grid = np.zeros_like(self.grid)
        next_grid[alive & keep_alive] = 1
        next_grid[~alive & resurrect] = 1
        
        self.grid = next_grid
        return self.grid.copy()

    def get_state(self) -> np.ndarray:
        return self.grid.copy()