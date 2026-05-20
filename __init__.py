"""BRBuild package root.

This file intentionally keeps imports minimal. Use package submodules
for functionality. Set a package-level __all__ to make `from BRBuild import *`
more predictable.
"""

# Package version (update as part of releases)
__version__ = "0.0.0"

__all__ = [
	"Builder",
	"Grf",
	"NmlWriter",
	"Vehicle",
	"Badge",
	"PropertyCalculation",
]
