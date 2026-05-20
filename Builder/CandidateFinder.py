import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class CandidateFinder:
    """Finds vehicle candidates (folders containing a matching .yaml file) in a specified base directory."""

    def __init__(self, base_directory: str):
        self.base_directory = Path(base_directory).expanduser().resolve()

        self.pnml_extension = ".pnml"
        self.yaml_extension = ".yaml"

        self.excluded_files = {"brbuild", "grf", "sound", "roadrailtype"}

    def find_candidates(self):
        candidates = []

        if not self.base_directory.is_dir():
            return candidates

        logger.debug(f"Scanning for candidates in: {self.base_directory}")

        for dirpath, _, filenames in os.walk(self.base_directory):
            folder = Path(dirpath)
            folder_name = folder.name

            if not folder_name:
                continue

            lower_name = folder_name.lower()

            yaml_matches = []
            pnml_files = []

            for filename in filenames:
                filename_lower = filename.lower()
                filepath = str(folder / filename)

                # Collect all PNML files in the folder
                if filename_lower.endswith(self.pnml_extension):
                    pnml_files.append(filepath)

                # Candidate identification is YAML only
                if filename_lower == f"{lower_name}{self.yaml_extension}":
                    if not any(excluded in filename_lower for excluded in self.excluded_files):
                        yaml_matches.append(filepath)

            # Skip folders without matching YAML file
            if not yaml_matches:
                continue

            classification = folder.parent.name.lower()

            candidates.append({
                "name": folder_name,
                "classification": classification,
                "path": str(folder),
                "files": sorted(yaml_matches),
                "pnml_files": sorted(pnml_files),
            })

        return candidates


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} path/to/base/folder")
        sys.exit(1)

    base_directory = sys.argv[1]

    finder = CandidateFinder(base_directory)
    candidates = finder.find_candidates()

    print(json.dumps(candidates, indent=2))