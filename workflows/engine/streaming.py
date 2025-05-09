"""Unified stdout/err streaming & capture."""

import sys
from typing import Optional, TextIO, Callable
from contextlib import contextmanager

class StreamHandler:
    """Handler for streaming output to various destinations."""
    
    def __init__(
        self,
        stream: bool = True,
        file: Optional[TextIO] = None,
        callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize the stream handler.
        
        Args:
            stream: Whether to stream to stdout
            file: Optional file to write to
            callback: Optional callback for each chunk
        """
        self.stream = stream
        self.file = file
        self.callback = callback
        self._buffer = []
        
    def write(self, text: str) -> None:
        """Write text to all configured outputs.
        
        Args:
            text: The text to write
        """
        if self.stream:
            sys.stdout.write(text)
            sys.stdout.flush()
            
        if self.file:
            self.file.write(text)
            self.file.flush()
            
        if self.callback:
            self.callback(text)
            
        self._buffer.append(text)
        
    def getvalue(self) -> str:
        """Get all written text.
        
        Returns:
            The concatenated text
        """
        return "".join(self._buffer)
        
    @contextmanager
    def capture(self):
        """Context manager to capture output.
        
        Yields:
            The handler instance
        """
        try:
            yield self
        finally:
            if self.file:
                self.file.close() 