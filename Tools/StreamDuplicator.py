import sys


class StreamDuplicator:
    def __init__(self, stream_a, stream_b, enable_a: bool = True, enable_b: bool = True):
        self.stream_a = stream_a
        self.stream_b = stream_b
        self.enable_a = enable_a
        self.enable_b = enable_b

    def write(self, data):
        if self.enable_a and self.stream_a is not None:
            self.stream_a.write(data)
        if self.enable_b and self.stream_b is not None:
            self.stream_b.write(data)

    def flush(self):
        if self.enable_a and self.stream_a is not None:
            self.stream_a.flush()
        if self.enable_b and self.stream_b is not None:
            self.stream_b.flush()

    # critical for compatibility with sys.stdout consumers
    def fileno(self):
        if self.stream_a is not None:
            return self.stream_a.fileno()
        raise OSError("No underlying stream with fileno")

    def isatty(self):
        if self.stream_a is not None:
            return self.stream_a.isatty()
        return False