import time
from pathlib import Path
from Builder import CandidateFinder

class Builder:
    name = ""
    baseFolder = ""
    variantList = []
    badgeList = []

    def __init__(self):
        return

    def build(self, name): 

        self.name = name
        self.baseFolder = Path(f"../{name}")

        startTime = time.time()
        print(f"BRBuild is attempting to build project in {self.baseFolder}.")

        if not self.baseFolder.is_dir():
            print(f"Error: Project folder '{self.baseFolder}' does not exist.")
            return

        print(f"Project folder '{self.baseFolder}' found. Starting build process.")
        print("Finding candidates...")

        try:
            finder = CandidateFinder(self.baseFolder)
            candidates = finder.find_candidates()
            print(f"Found {len(candidates)} candidates.")
        except Exception as e:
            print(f"Error during candidate finding: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        print(f"Candidate finding complete in {elapsed} seconds. Starting YAML parsing.")

        try:
            # Parse YAML
            time.sleep(1)  # Replace with actual build logic
        except Exception as e:
            print(f"Error during YAML parsing: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        print(f"YAML parsing complete in {elapsed} seconds. Starting NML collation.")
        
        try:
            # Collate NML
            time.sleep(1)  # Replace with actual build logic
        except Exception as e:
            print(f"Error during NML collation: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        print(f"NML collation complete in {elapsed} seconds. Starting newGRF compilation.")
        
        try:
            # Compile newGRF
            time.sleep(1)  # Replace with actual build logic
        except Exception as e:
            print(f"Error during newGRF compilation: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        print(f"newGRF compilation complete in {elapsed} seconds. Starting newGRF copying.")
        
        try: 
            # Copy newGRF to OpenTTD newGRF folder  
            time.sleep(1)  # Replace with actual build logic
        except Exception as e:
            print(f"Error during newGRF copying: {e}")
            return

        elapsed = round(time.time() - startTime, 2)
        print(f"BRBuild build complete after {elapsed} seconds.")