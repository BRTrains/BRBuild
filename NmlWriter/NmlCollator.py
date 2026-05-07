import logging
logger = logging.getLogger(__name__)

class NmlCollator:
    def __init__(self):
        pass

    def collate(self, files, project_name):
        self.output_file = f"Build/{project_name}.nml"

        with open(self.output_file, 'w') as f:
            for file in files:
                logger.debug(f"Collating file: {file}")
                with open(file, 'r') as infile:
                    content = infile.read()
                    f.write(f"\n\n// File: {file}\n")
                    f.write(content)
        logger.info(f"Collated NML written to {self.output_file}")