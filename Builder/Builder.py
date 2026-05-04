import time, logging

from Vehicle.VariantIterator import VariantIterator
from YAMLHandler.VehicleLoader import VehicleLoader
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

        logging.debug(f"Project folder '{project.path}' found. Starting build process.")
        if project.target_folders:
            logging.debug(f"Using target folders: {project.target_folders}")
        else:
            logging.debug("No target folders specified; scanning project root.")        

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

                logging.debug(f"Finding candidates in folder: {scan_path}")

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
                logging.info(f"Processing candidate: {candidate['name']}")                
                # Store the returned .pnml files for collation?
                for file in candidate['files']:
                    logging.debug(f"\tParsing YAML file: {file}")
                    vehicle = VehicleLoader.load(file)  # Example of loading the first file for the candidate
                    logging.debug(f"\tLoaded vehicle: {vehicle.name} with identifier {vehicle.identifier}, {len(vehicle.profiles)} profiles, and {len(vehicle.liveries)} liveries.")

                    iterator = VariantIterator(vehicle)
                    for variant in iterator:
                        logging.debug(f"\tGenerated variant: {variant.vehicle.name}, using livery {variant.livery.name} and profile {variant.profile.identifier}")
                        self.variantList.append(variant)
        except Exception as e:
            logging.exception(f"Error during YAML parsing: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        logging.info(f"YAML parsing complete in {elapsed} seconds. Starting NML collation.")
        
        try:
            # Collate NML
            # Replace with actual build logic
            pass
        except Exception as e:
            logging.exception(f"Error during NML collation: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        logging.info(f"NML collation complete in {elapsed} seconds. Starting newGRF compilation.")
        
        try:
            # Compile newGRF
            # Replace with actual build logic
            pass
        except Exception as e:
            logging.exception(f"Error during newGRF compilation: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        logging.info(f"newGRF compilation complete in {elapsed} seconds. Starting newGRF copying.")
        
        try: 
            # Copy newGRF to OpenTTD newGRF folder  
            # Replace with actual build logic
            pass
        except Exception as e:
            logging.exception(f"Error during newGRF copying: {e}")
            return

        elapsed = round(time.time() - startTime, 2)
        logging.info(f"BRBuild build complete after {elapsed} seconds.")