import time


class Builder:
    name = ""
    baseFolder = ""
    variantList = []
    badgeList = []

    def __init__(self):
        return

    def build(self, name, baseFolder): 
        self.name = name
        self.baseFolder = baseFolder

        startTime = time.time()
        print(f"BRBuild is building project in {self.name}.")

        try:
            # Parse YAML
            time.sleep(1)  # Replace with actual build logic
        except Exception as e:
            print(f"Error during YAML parsing: {e}")
            return
        
        print("YAML parsing complete. Starting NML collation.")
        
        try:
            # Collate NML
            time.sleep(1)  # Replace with actual build logic
        except Exception as e:
            print(f"Error during NML collation: {e}")
            return
        
        print("NML collation complete. Starting newGRF compilation.")
        
        try:
            # Compile newGRF
            time.sleep(1)  # Replace with actual build logic
        except Exception as e:
            print(f"Error during newGRF compilation: {e}")
            return
        
        print("newGRF compilation complete. Starting newGRF copying.")
        
        try: 
            # Copy newGRF to OpenTTD newGRF folder  
            time.sleep(1)  # Replace with actual build logic
        except Exception as e:
            print(f"Error during newGRF copying: {e}")
            return

        endTime = time.time()
        elapsed = round(endTime - startTime, 2)
        print(f"BRBuild build complete after {elapsed} seconds.")