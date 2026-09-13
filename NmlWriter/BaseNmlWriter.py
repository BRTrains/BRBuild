class BaseNmlWriter:
    """Base class for NML block writers providing standardized tab-indented output."""

    def writeline(self, f, line: str = "", indent: int = 0):
        indent_str = "\t" * indent
        f.write(f"{indent_str}{line}\n")
