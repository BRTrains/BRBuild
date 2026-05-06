import logging
import os
from pathlib import Path
logger = logging.getLogger(__name__)

class CandidateFinder:
    ''' Finds vehicle candidates (folders containing a .yaml or .pnml file) in a specified base directory.'''
    def __init__(self, base_directory: str):
        self.base_directory = Path(base_directory).expanduser().resolve()

        self.pnml_extension = ".pnml"
        self.yaml_extension = ".yaml"

        self.excluded_files = {"BRBuild", "GRF", "sound", "roadrailtype"}

    def find_candidates(self):
        candidates = []
        base_dir = self.base_directory
        if not base_dir.is_dir():
            return candidates
        
        logger.debug(f"Scanning for candidates in: {base_dir}")

        for dirpath, _, filenames in os.walk(base_dir):
            folder = Path(dirpath)
            folder_name = folder.name
            if not folder_name:
                continue

            matches = []
            lower_name = folder_name.lower()
            for filename in filenames:
                filename_lower = filename.lower()
                if filename_lower == f"{lower_name}{self.yaml_extension}" or filename_lower == f"{lower_name}{self.pnml_extension}":
                    if not any(excluded in filename_lower for excluded in self.excluded_files):
                        matches.append(f"{dirpath}/{filename}")

            if matches:
                classification = folder.parent.name.lower()
                candidates.append({
                    "name": folder_name,
                    "classification": classification,
                    "path": str(folder),
                    "files": sorted(matches),
                })

        return candidates


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} path/to/base/folder")
        sys.exit(1)

    base_directory = sys.argv[1]
    finder = CandidateFinder(base_directory)
    candidates = finder.find_candidates()
    print(json.dumps(candidates, indent=2))
