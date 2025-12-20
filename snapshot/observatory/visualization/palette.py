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
        Maps 0.0-1.0 brightness to a Firefly gradient using Rich-compatible styles.
        0.0 (Refractory/Quiet) -> Dark Blue/Black
        0.5 (Charging) -> Deep Orange
        1.0 (Flash) -> Bright Yellow/White
        """
        # Initialize with a dark background color in Rich's rgb format
        colors = np.full(brightness.shape, "rgb(30,30,40)", dtype="<U18")

        # Low energy (Charging): Reddish
        mask_low = (brightness > 0.1) & (brightness <= 0.6)
        colors[mask_low] = "rgb(100,40,40)"

        # High energy (Pre-flash): Orange
        mask_high = (brightness > 0.6) & (brightness <= 0.9)
        colors[mask_high] = "rgb(200,120,0)"

        # Flash: Bright Yellow/White
        mask_flash = brightness > 0.9
        colors[mask_flash] = "rgb(255,255,200)"

        return colors

    @staticmethod
    def bottleneck(states: np.ndarray) -> np.ndarray:
        """
        Maps states to bottleneck visualizer colors using Rich-compatible styles.
        0.0: Idle (Dim Gray)
        0.5: Waiting (Cyan)
        1.0: Running (Bright Green/White)
        """
        # Initialize with Dim Gray
        colors = np.full(states.shape, "rgb(40,40,40)", dtype="<U18")

        # Waiting (Cyan)
        mask_wait = (states > 0.4) & (states < 0.8)
        colors[mask_wait] = "rgb(0,200,200)"

        # Running (Bright Green/White tint)
        mask_run = states >= 0.8
        colors[mask_run] = "rgb(200,255,200)"

        return colors