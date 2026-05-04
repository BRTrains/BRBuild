import sys
import subprocess
from pathlib import Path

# Current project directory (BRMetro)
PROJECT_DIR = Path(__file__).resolve().parent
PROJECT_NAME = PROJECT_DIR.name

# BRBuild location (sibling directory under ~/Dev)
BRBUILD_DIR = PROJECT_DIR.parent / "BRBuild"

# Forward CLI args (e.g. --log)
forward_args = sys.argv[1:]

subprocess.run(
    [sys.executable, str(BRBUILD_DIR / "Run.py"), PROJECT_NAME, *forward_args],
    check=True
)