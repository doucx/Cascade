import numpy as np
from typing import Dict

# Mapping from state values to Rich color names.
TRUTH_PALETTE: Dict[float, str] = {
    0.0: "grey30",         # Match Dead
    1.0: "bright_white",   # Match Alive
    2.0: "red",            # False Positive
    3.0: "cyan",           # False Negative
}

BOTTLENECK_PALETTE: Dict[float, str] = {
    0.0: "grey50",      # Idle
    0.5: "bright_cyan", # Waiting
    1.0: "bright_green",# Running
}

class Palettes:
    """Predefined color palettes for simulations, compatible with Rich/Textual."""

    @staticmethod
    def _map_palette(states: np.ndarray, palette: Dict[float, str], default_color="black") -> np.ndarray:
        """Generic function to map states to colors using a palette dictionary."""
        # Initialize with a default color
        colors = np.full(states.shape, default_color, dtype=object)
        
        # Apply colors based on exact or approximate matches
        for val, color_name in palette.items():
            # Use a small tolerance for float comparisons
            mask = np.isclose(states, val)
            colors[mask] = color_name
        
        return colors
    
    @staticmethod
    def firefly(brightness: np.ndarray) -> np.ndarray:
        """Maps brightness to a Firefly gradient using Rich colors."""
        colors = np.full(brightness.shape, "rgb(30,30,40)", dtype=object)
        
        mask_low = (brightness > 0.1) & (brightness <= 0.6)
        colors[mask_low] = "rgb(100,40,40)" # Reddish

        mask_high = (brightness > 0.6) & (brightness <= 0.9)
        colors[mask_high] = "rgb(200,120,0)" # Orange
        
        mask_flash = brightness > 0.9
        colors[mask_flash] = "rgb(255,255,200)" # Bright Yellow/White
        
        return colors

    @staticmethod
    def bottleneck(states: np.ndarray) -> np.ndarray:
        """Maps bottleneck states to Rich colors."""
        return Palettes._map_palette(states, BOTTLENECK_PALETTE, default_color="grey30")

    @staticmethod
    def truth(states: np.ndarray) -> np.ndarray:
        """Maps truth/diff states to Rich colors."""
        return Palettes._map_palette(states, TRUTH_PALETTE)