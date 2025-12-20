import numpy as np
from typing import List, Tuple

class RenderBuffer:
    """
    Represents what is actually displayed on screen (Chars + Colors).
    Capable of computing diffs against another buffer.
    """
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # Stores the character to be printed
        self.chars = np.full((height, width), ' ', dtype='<U1')
        # Stores the ANSI color code for that character
        # Using fixed length string for optimization, typical ANSI code is ~5-7 chars
        self.colors = np.full((height, width), '', dtype='<U10')

    def update_from_matrix(self, brightness_matrix: np.ndarray):
        """
        Rasterizes the float brightness matrix into chars and colors.
        """
        # 1. Clear
        self.chars[:] = ' '
        self.colors[:] = ''

        # 2. Vectorized conversion logic
        # Brightness > 0.8: Bright White '#'
        # Brightness > 0.5: Cyan '*'
        # Brightness > 0.2: Dim Blue '.'
        # Else: Space
        
        # We use boolean masks for speed
        mask_high = brightness_matrix > 0.8
        mask_mid = (brightness_matrix > 0.4) & (~mask_high)
        mask_low = (brightness_matrix > 0.01) & (~mask_high) & (~mask_mid)

        # Apply Chars
        self.chars[mask_high] = '#'
        self.chars[mask_mid] = 'o'
        self.chars[mask_low] = '.'

        # Apply Colors (Pre-computed ANSI codes)
        # White
        self.colors[mask_high] = '\033[97m' 
        # Cyan
        self.colors[mask_mid] = '\033[36m'
        # Dim Gray/Blue
        self.colors[mask_low] = '\033[90m'

    @staticmethod
    def compute_diff(prev: 'RenderBuffer', curr: 'RenderBuffer') -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns (rows, cols) indices where prev and curr differ.
        """
        # Compare chars and colors simultaneously
        # We can just check chars equality for visual change if logic guarantees color syncs with char
        # But to be safe, check both.
        # Constructing a combined view might be expensive.
        # Let's check chars first, then colors.
        
        diff_mask = (prev.chars != curr.chars) | (prev.colors != curr.colors)
        return np.where(diff_mask)