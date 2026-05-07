import time, logging
logger = logging.getLogger(__name__)

from NmlWriter import NmlGrfWriter
from NmlWriter.NmlVariantWriter import NmlVariantWriter
from NmlWriter.NmlCollator import NmlCollator
from NmlWriter.NmlCompiler import NmlCompiler
from Vehicle.VariantIterator import VariantIterator
from YamlHandler.VehicleLoader import VehicleLoader
from YamlHandler.GrfLoader import GrfLoader
from Grf.Grf import Grf
from .CandidateFinder import CandidateFinder
from Project.Project import Project

class Builder:

    def __init__(self):        
        self.nmlCollator = NmlCollator()
        self.nmlCompiler = NmlCompiler()

        self.variantList = []
        self.badgeList = []
        self.nml_files = []

        self.successfulVariants = []
        self.failedVariants = []
        return

    def build(self, project_data):
        if isinstance(project_data, Project):
            logger.debug(f"Received project data is already a Project instance: {project_data}")
            project = project_data
        else:
            logger.debug(f"Received project data is not a Project instance, attempting to create one: {project_data}")
            project = Project(project_data)

        if not project.build:
            logger.info(f"Skipping project '{project.name}' because build is disabled.")
            return

        startTime = time.time()
        logger.info(f"BRBuild is attempting to build project '{project.name}' in {project.path}.")

        if not project.path.is_dir():
            logger.error(f"Project folder '{project.path}' does not exist.")
            return
        
        try:
            grfLoader = GrfLoader(project.path / project.grfFolder / "GRF.yaml")
            grf = grfLoader.load()

            nmlWriter = NmlGrfWriter(grf)
            nmlWriter.write_grf_gnml(project.path / project.grfFolder / "GRF.gnml")
        except Exception as e:
            logger.exception(f"Error loading build configuration for project '{project.name}': {e}")
            return

        logger.debug(f"Project folder '{project.path}' found. Starting build process.")     

        candidates = []
        if project.targetFolders:
            logger.debug(f"Scanning specified target folders for candidates: {project.targetFolders}")
            scan_paths = [project.path / target for target in project.targetFolders]
        else:
            logger.debug("No target folders specified; scanning project root.")
            scan_paths = [project.path]

        try:
            candidates = self.find_candidates(scan_paths, candidates)
        except Exception as e:
            logger.exception(f"Error during candidate finding: {e}")
            return
        
        if len(candidates) == 0:
            raise Exception(f"No candidates found for project '{project.name}'. Halting build process.")

        elapsed = round(time.time() - startTime, 2)
        logger.info(f"Candidate finding complete in {elapsed} seconds. Starting YAML parsing.")

        try:
            for candidate in candidates:
                candidate_nml_files = self.process_candidate(candidate)
                if candidate_nml_files and len(candidate_nml_files) > 0:
                    # Store the returned .pnml files for collation
                    self.nml_files.extend(candidate_nml_files)
                else: 
                    logger.warning(f"No NML files generated for candidate '{candidate['name']}'")
        except Exception as e:
            logger.exception(f"Error during YAML parsing: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        logger.info(f"YAML parsing complete in {elapsed} seconds. Starting NML collation.")
        
        if len(self.successfulVariants) == 0:
            raise Exception(f"No successful variants were generated for project '{project.name}'. Halting build process.")
            return

        try:
            self.nmlCollator.collate(self.nml_files, project)
            pass
        except Exception as e:
            logger.exception(f"Error during NML collation: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        logger.info(f"NML collation complete in {elapsed} seconds. Starting newGRF compilation.")
        
        try:
            self.nmlCompiler.compile(self.nml_files, project)
            pass
        except Exception as e:
            logger.exception(f"Error during newGRF compilation: {e}")
            return
        
        elapsed = round(time.time() - startTime, 2)
        logger.info(f"newGRF compilation complete in {elapsed} seconds. Starting newGRF copying.")
        
        try: 
            self.nmlCompiler.copy_newgrf(project)
            pass
        except Exception as e:
            logger.exception(f"Error during newGRF copying: {e}")
            return

        logger.info(f"BRBuild build process for project '{project.name}' completed successfully.")
        logger.info(f"Successful variants: {len(self.successfulVariants)}. Failed variants: {len(self.failedVariants)}.")   
        elapsed = round(time.time() - startTime, 2)
        logger.info(f"BRBuild build complete after {elapsed} seconds.")

    def find_candidates(self, scan_paths, candidates):
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
        return candidates

    def process_candidate(self, candidate):
        nml_files = []

        logger.info(f"Processing candidate: {candidate['name']}")                
        # Store the returned .pnml files for collation?
        for file in candidate['files']:
            logger.debug(f"\tParsing YAML file: {file}")
            vehicle = VehicleLoader.load(file)
            logger.debug(f"\tLoaded vehicle: {vehicle.name} with identifier {vehicle.identifier}, {len(vehicle.profiles)} profiles, and {len(vehicle.liveries)} liveries.")

            iterator = VariantIterator(vehicle)
            for variant in iterator:
                logger.debug(f"\tGenerated variant: {variant.vehicle.name}, using livery {variant.livery.name} and profile {variant.profile.identifier}")
                try:
                    variant.process()
                except Exception as e:
                    logger.exception(f"Error processing variant {variant}: {e}")
                    self.failedVariants.append(variant.__repr__())
                    return

                try:
                    variantWriter = NmlVariantWriter(variant)
                    nml_file = variantWriter.write()
                    nml_files.append(nml_file)

                except Exception as e:
                    logger.exception(f"Unable to write NML for variant {variant}: {e}")
                    self.failedVariants.append(variant.__repr__())
                    return

                self.successfulVariants.append(variant)
        
        return nml_files