import os
from typing import Union

class File:
    """
    A declarative wrapper for a file system path.
    
    It provides convenience methods for I/O operations and can be used
    to explicitly declare file dependencies in task signatures.
    """
    def __init__(self, path: Union[str, "File"]):
        self.path = str(path)

    def read_text(self, encoding="utf-8") -> str:
        """Reads the file content as a string."""
        with open(self.path, "r", encoding=encoding) as f:
            return f.read()

    def read_bytes(self) -> bytes:
        """Reads the file content as bytes."""
        with open(self.path, "rb") as f:
            return f.read()

    def write_text(self, data: str, encoding="utf-8") -> None:
        """
        Writes a string to the file. 
        Automatically creates parent directories if they don't exist.
        """
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "w", encoding=encoding) as f:
            f.write(data)

    def write_bytes(self, data: bytes) -> None:
        """
        Writes bytes to the file.
        Automatically creates parent directories if they don't exist.
        """
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "wb") as f:
            f.write(data)

    def exists(self) -> bool:
        """Checks if the file exists."""
        return os.path.exists(self.path)

    def __str__(self) -> str:
        return self.path

    def __repr__(self) -> str:
        return f"File('{self.path}')"