import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Color:
    r: int
    g: int
    b: int

    def to_ansi_bg(self) -> str:
        """Returns ANSI escape code for background color."""
        # Using 24-bit TrueColor: \033[48;2;R;G;Bm
        return f"\033[38;2;{self.r};{self.g};{self.b}m"

class Palettes:
    """Predefined color palettes for simulations."""

    @staticmethod
    def _interpolate(val: float, c1: Color, c2: Color) -> str:
        r = int(c1.r + (c2.r - c1.r) * val)
        g = int(c1.g + (c2.g - c1.g) * val)
        b = int(c1.b + (c2.b - c1.b) * val)
        return f"\033[38;2;{r};{g};{b}m"

    @staticmethod
    def firefly(brightness: np.ndarray) -> np.ndarray:
        """
        Maps 0.0-1.0 brightness to a Firefly gradient.
        0.0 (Refractory/Quiet) -> Dark Blue/Black
        0.5 (Charging) -> Deep Orange
        1.0 (Flash) -> Bright Yellow/White
        """
        # We handle this utilizing numpy vectorization for speed would be ideal,
        # but for simplicity in ANSI generation, we might use a lookup or mask.
        # Here we define 3 discrete levels for performance, or use a mapped array.
        
        # Initialize with Dark (Background)
        # \033[38;2;20;20;30m (Very Dark Blue)
        colors = np.full(brightness.shape, '\033[38;2;30;30;40m', dtype='<U24')
        
        # Low energy (Charging): Reddish
        mask_low = (brightness > 0.1) & (brightness <= 0.6)
        colors[mask_low] = '\033[38;2;100;40;40m'

        # High energy (Pre-flash): Orange
        mask_high = (brightness > 0.6) & (brightness <= 0.9)
        colors[mask_high] = '\033[38;2;200;120;0m'
        
        # Flash: Bright Yellow/White
        mask_flash = brightness > 0.9
        colors[mask_flash] = '\033[38;2;255;255;200m'
        
        return colors

    @staticmethod
    def bottleneck(states: np.ndarray) -> np.ndarray:
        """
        Maps states to bottleneck visualizer colors.
        0.0: Idle (Dim)
        0.5: Waiting (Cyan)
        1.0: Running (White/Green)
        """
        colors = np.full(states.shape, '\033[38;2;40;40;40m', dtype='<U24') # Dim Gray
        
        # Waiting (Cyan)
        mask_wait = (states > 0.4) & (states < 0.8)
        colors[mask_wait] = '\033[38;2;0;200;200m'
        
        # Running (Bright White/Green tint)
        mask_run = states >= 0.8
        colors[mask_run] = '\033[38;2;200;255;200m'
        
        return colors

    @staticmethod
    def conway_diff(states: np.ndarray) -> np.ndarray:
        """
        Maps diff states to colors for Conway's Game of Life validation.
        0: Match-Dead (Dark Gray)
        1: Match-Alive (Bright White)
        2: False Positive / Ghost (Red)
        3: False Negative / Missing (Cyan)
        """
        colors = np.full(states.shape, '\033[38;2;40;40;40m', dtype='<U24') # 0: Dark Gray

        colors[states == 1] = '\033[38;2;240;240;240m' # 1: White
        colors[states == 2] = '\033[38;2;255;50;50m'   # 2: Red
        colors[states == 3] = '\033[38;2;50;200;255m'  # 3: Cyan

        return colors