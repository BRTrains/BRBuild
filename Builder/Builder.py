import time, logging
logger = logging.getLogger(__name__)

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
            logger.info(f"Skipping project '{project.name}' because build is disabled.")
            return

        startTime = time.time()
        logger.info(f"BRBuild is attempting to build project '{project.name}' in {project.path}.")

        if not project.path.is_dir():
            logger.error(f"Project folder '{project.path}' does not exist.")
            return

        logger.debug(f"Project folder '{project.path}' found. Starting build process.")
        if project.target_folders:
            logger.debug(f"Using target folders: {project.target_folders}")
        else:
            logger.debug("No target folders specified; scanning project root.")        

        candidates = []
        scan_paths = [project.path]
        if project.target_folders:
            scan_paths = [project.path / target for target in project.target_folders]

        try:
            for scan_path in scan_paths:
                if not scan_path.exists():
                    logger.warning(f"Target folder '{scan_path}' does not exist; skipping.")
                    continue
                if not scan_path.is_dir():
                    logger.warning(f"Target path '{scan_path}' is not a directory; skipping.")
                    continue

                logger.debug(f"Finding candidates in folder: {scan_path}")

                finder = CandidateFinder(scan_path)
                found = finder.find_candidates()
                candidates.extend(found)

            logger.info(f"Found {len(candidates)} candidates.")
        except Exception as e:
            logger.exception(f"Error during candidate finding: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        logger.info(f"Candidate finding complete in {elapsed} seconds. Starting YAML parsing.")

        try:
            for candidate in candidates:
                logger.info(f"Processing candidate: {candidate['name']}")                
                # Store the returned .pnml files for collation?
                for file in candidate['files']:
                    logger.debug(f"\tParsing YAML file: {file}")
                    vehicle = VehicleLoader.load(file)  # Example of loading the first file for the candidate
                    logger.debug(f"\tLoaded vehicle: {vehicle.name} with identifier {vehicle.identifier}, {len(vehicle.profiles)} profiles, and {len(vehicle.liveries)} liveries.")

                    iterator = VariantIterator(vehicle)
                    for variant in iterator:
                        logger.debug(f"\tGenerated variant: {variant.vehicle.name}, using livery {variant.livery.name} and profile {variant.profile.identifier}")
                        self.variantList.append(variant)
        except Exception as e:
            logger.exception(f"Error during YAML parsing: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        logger.info(f"YAML parsing complete in {elapsed} seconds. Starting NML collation.")
        
        try:
            # Collate NML
            # Replace with actual build logic
            pass
        except Exception as e:
            logger.exception(f"Error during NML collation: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        logger.info(f"NML collation complete in {elapsed} seconds. Starting newGRF compilation.")
        
        try:
            # Compile newGRF
            # Replace with actual build logic
            pass
        except Exception as e:
            logger.exception(f"Error during newGRF compilation: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        logger.info(f"newGRF compilation complete in {elapsed} seconds. Starting newGRF copying.")
        
        try: 
            # Copy newGRF to OpenTTD newGRF folder  
            # Replace with actual build logic
            pass
        except Exception as e:
            logger.exception(f"Error during newGRF copying: {e}")
            return

        elapsed = round(time.time() - startTime, 2)
        logger.info(f"BRBuild build complete after {elapsed} seconds.")