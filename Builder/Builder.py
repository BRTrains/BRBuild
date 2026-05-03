import time, logging
from pathlib import Path
from .CandidateFinder import CandidateFinder
from Project.Project import Project

class Builder:
    variantList = []
    badgeList = []

    def __init__(self):
        return

    def build(self, project_data):
        if isinstance(project_data, Project):
            project = project_data
        else:
            project = Project(project_data)

        if not project.build:
            logging.info(f"Skipping project '{project.name}' because build is disabled.")
            return

        startTime = time.time()
        logging.info(f"BRBuild is attempting to build project '{project.name}' in {project.path}.")

        if not project.path.is_dir():
            logging.error(f"Project folder '{project.path}' does not exist.")
            return

        logging.info(f"Project folder '{project.path}' found. Starting build process.")
        if project.target_folders:
            logging.info(f"Using target folders: {project.target_folders}")
        else:
            logging.info("No target folders specified; scanning project root.")        

        candidates = []
        scan_paths = [project.path]
        if project.target_folders:
            scan_paths = [project.path / target for target in project.target_folders]

        try:
            for scan_path in scan_paths:
                if not scan_path.exists():
                    logging.warning(f"Target folder '{scan_path}' does not exist; skipping.")
                    continue
                if not scan_path.is_dir():
                    logging.warning(f"Target path '{scan_path}' is not a directory; skipping.")
                    continue

                logging.info(f"Finding candidates in folder: {scan_path}")

                finder = CandidateFinder(scan_path)
                found = finder.find_candidates()
                candidates.extend(found)

            logging.info(f"Found {len(candidates)} candidates.")
        except Exception as e:
            logging.exception(f"Error during candidate finding: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        logging.info(f"Candidate finding complete in {elapsed} seconds. Starting YAML parsing.")

        try:
            for candidate in candidates:
                logging.info(f"Processing candidate: {candidate['name']} (classification: {candidate['classification']}, files: {candidate['files']})")
                # Replace with actual YAML parsing logic
                # Store the returned .pnml files for collation?
        except Exception as e:
            logging.exception(f"Error during YAML parsing: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        logging.info(f"YAML parsing complete in {elapsed} seconds. Starting NML collation.")
        
        try:
            # Collate NML
            time.sleep(1)  # Replace with actual build logic
        except Exception as e:
            logging.exception(f"Error during NML collation: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        logging.info(f"NML collation complete in {elapsed} seconds. Starting newGRF compilation.")
        
        try:
            # Compile newGRF
            time.sleep(1)  # Replace with actual build logic
        except Exception as e:
            logging.exception(f"Error during newGRF compilation: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        logging.info(f"newGRF compilation complete in {elapsed} seconds. Starting newGRF copying.")
        
        try: 
            # Copy newGRF to OpenTTD newGRF folder  
            time.sleep(1)  # Replace with actual build logic
        except Exception as e:
            logging.exception(f"Error during newGRF copying: {e}")
            return

        elapsed = round(time.time() - startTime, 2)
        logging.info(f"BRBuild build complete after {elapsed} seconds.")