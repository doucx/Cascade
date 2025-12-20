import sys

class AnsiDriver:
    """
    Low-level driver for ANSI terminal control.
    Optimized for buffered output to minimize IO syscalls.
    """
    
    # ANSI Constants
    cursor_hide = "\033[?25l"
    cursor_show = "\033[?25h"
    reset = "\033[0m"
    clear = "\033[2J"
    home = "\033[H"

    def __init__(self):
        self._buffer = []

    def hide_cursor(self):
        self._buffer.append(self.cursor_hide)

    def show_cursor(self):
        self._buffer.append(self.cursor_show)
        
    def clear_screen(self):
        self._buffer.append(self.clear)
        self._buffer.append(self.home)

    def move_to(self, row: int, col: int):
        # ANSI coordinates are 1-based
        self._buffer.append(f"\033[{row+1};{col+1}H")

    def write(self, text: str, color_code: str = ""):
        if color_code:
            self._buffer.append(f"{color_code}{text}{self.reset}")
        else:
            self._buffer.append(text)

    def flush(self):
        """Writes the accumulated buffer to stdout and clears it."""
        if not self._buffer:
            return
        sys.stdout.write("".join(self._buffer))
        sys.stdout.flush()
        self._buffer.clear()
        
    def raw_write(self, data: str):
        self._buffer.append(data)

    def close(self):
        self.show_cursor()
        self.flush()