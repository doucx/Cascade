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
        Maps 0.0-1.0 brightness to a Firefly gradient using vectorized interpolation.
        """
        # Define color stops [R, G, B]
        stop1 = np.array([30, 30, 40])      # Dark Blue (at brightness 0.0)
        stop2 = np.array([200, 120, 0])     # Orange (at brightness 0.5)
        stop3 = np.array([255, 255, 200])   # Bright Yellow (at brightness 1.0)

        # Prepare output arrays
        r = np.zeros_like(brightness, dtype=np.uint8)
        g = np.zeros_like(brightness, dtype=np.uint8)
        b = np.zeros_like(brightness, dtype=np.uint8)

        # --- Vectorized Interpolation ---
        # Mask for the lower half of the gradient (0.0 to 0.5)
        mask1 = brightness <= 0.5
        # Normalize brightness in this range to 0-1 for interpolation
        t1 = brightness[mask1] * 2
        r[mask1] = (stop1[0] + (stop2[0] - stop1[0]) * t1).astype(np.uint8)
        g[mask1] = (stop1[1] + (stop2[1] - stop1[1]) * t1).astype(np.uint8)
        b[mask1] = (stop1[2] + (stop2[2] - stop1[2]) * t1).astype(np.uint8)

        # Mask for the upper half of the gradient (0.5 to 1.0)
        mask2 = brightness > 0.5
        # Normalize brightness in this range to 0-1 for interpolation
        t2 = (brightness[mask2] - 0.5) * 2
        r[mask2] = (stop2[0] + (stop3[0] - stop2[0]) * t2).astype(np.uint8)
        g[mask2] = (stop2[1] + (stop3[1] - stop2[1]) * t2).astype(np.uint8)
        b[mask2] = (stop2[2] + (stop3[2] - stop2[2]) * t2).astype(np.uint8)

        # Create rich-compatible "rgb(r,g,b)" strings. This is the slowest part.
        # We can optimize if needed, but it's more readable for now.
        return np.array([f"rgb({r_},{g_},{b_})" for r_, g_, b_ in zip(r.flat, g.flat, b.flat)]).reshape(r.shape)

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

        # Running (Bright White/Green tint)
        mask_run = states >= 0.8
        colors[mask_run] = "rgb(200,255,200)"
        
        return colors

    @staticmethod
    def truth_diff(diff_matrix: np.ndarray) -> np.ndarray:
        """
        Maps a diff matrix to validation colors (3-Network Model).
        
        0: Dead (Correct)          -> Dim Gray
        1: Alive (Correct)         -> Bright White
        
        Logic Errors (vs Step Prediction):
        2: FP (Logic Ghost)        -> Bright Red
        3: FN (Logic Missing)      -> Cyan
        
        Drift Errors (vs Absolute Truth):
        4: FP (Drift Ghost)        -> Gold
        5: FN (Drift Missing)      -> Violet
        """
        # Default: 0 (Dead/Correct)
        colors = np.full(diff_matrix.shape, "rgb(40,40,40)", dtype="<U18")
        
        colors[diff_matrix == 1] = "rgb(220,220,220)" # Alive (Correct)
        colors[diff_matrix == 2] = "rgb(255,50,50)"   # Logic FP (Red)
        colors[diff_matrix == 3] = "rgb(0,255,255)"   # Logic FN (Cyan)
        colors[diff_matrix == 4] = "rgb(255,215,0)"   # Drift FP (Gold)
        colors[diff_matrix == 5] = "rgb(238,130,238)" # Drift FN (Violet)
        
        return colors