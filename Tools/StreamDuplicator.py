import re
import sys


ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


class StreamDuplicator:
    ''' Split the console output to both the console and a log file '''
    def __init__(self, stream_a, stream_b, enable_a: bool = True, enable_b: bool = True):
        self.stream_a = stream_a  # usually stdout
        self.stream_b = stream_b  # file
        self.enable_a = enable_a
        self.enable_b = enable_b

    def write(self, data):
        if self.enable_a and self.stream_a is not None:
            self.stream_a.write(data)

        if self.enable_b and self.stream_b is not None:
            # strip only for file output
            self.stream_b.write(strip_ansi(data))

    def flush(self):
        if self.enable_a and self.stream_a is not None:
            self.stream_a.flush()
        if self.enable_b and self.stream_b is not None:
            self.stream_b.flush()

    def fileno(self):
        return self.stream_a.fileno()

    def isatty(self):
        return self.stream_a.isatty()